"""인증 의존성 — 모든 모듈이 쓰는 current_user.

여기가 app/modules/auth 가 아니라 shared 에 있는 이유: 모든 모듈이 현재 사용자를
필요로 하는데, 그때마다 auth 모듈을 직접 import 하면 모든 모듈이 auth 에 묶인다.
의존성은 횡단 관심사이므로 shared 가 맞다. 방향은 shared -> auth 한 쪽이다.

**두 가지 자격을 같은 지점에서 받는다** — 사람의 access JWT 와 기계의 PAT.
장비 연계 스크립트가 PAT 로 같은 엔드포인트를 부르므로, 권한 판정이 한 곳이어야
"사람은 되는데 스크립트는 안 되는" 어긋남이 안 생긴다.
"""

from __future__ import annotations

import logging

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.auth import security, services
from app.shared.errors import AppError, Forbidden
from app.shared.request_context import set_actor_token

logger = logging.getLogger(__name__)

_UNAUTHENTICATED = "로그인이 필요합니다."


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization")
    if not header or not header.lower().startswith("bearer "):
        return None
    return header[7:].strip() or None


#: 경로 앞머리 -> 그 아래 **쓰기**에 필요한 범위. 긴 것부터 본다.
#:
#: 이 표에 없는 경로는 기계 자격으로 못 쓴다 — **모르는 것은 막는다**. 새
#: 엔드포인트가 생길 때마다 자동으로 열리면 그것을 알아채는 사람이 아무도 없다.
#: 계정·서버 설정이 여기 없는 것은 실수가 아니라 결정이다.
_WRITE_SCOPES: tuple[tuple[str, str], ...] = (
    ("/api/equipment-series", "catalog:write"),
    ("/api/equipment-models", "catalog:write"),
    ("/api/spec-definitions", "catalog:write"),
    ("/api/spec-groups", "catalog:write"),
    ("/api/condition-keys", "catalog:write"),
    ("/api/vocabularies", "catalog:write"),
    ("/api/methods", "catalog:write"),
    ("/api/equipment", "equipment:write"),
    ("/api/capabilities", "equipment:write"),
)

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

#: POST 지만 **아무것도 안 바꾸는** 것들. 본문에 물음을 싣기 때문에 POST 일 뿐이다.
#:
#: 이걸 빼먹으면 읽기 전용 토큰이 **검색을 못 한다** — 그리고 검색은 이 시스템이
#: 존재하는 이유다. 실측으로 드러났다: 범위를 준 토큰이 `/api/resolve` 와
#: `/api/search/capabilities` 에서 403 을 받았다.
_READ_ONLY_POSTS = ("/api/resolve", "/api/search/")


def _needed_scope(path: str) -> str | None:
    """이 경로의 쓰기에 필요한 범위. 없으면 None (= 아무 범위로도 못 쓴다).

    **긴 앞머리부터 본다.** `/api/equipment-series` 가 `/api/equipment` 보다 먼저
    걸려야 한다 — 아니면 계열 수정이 장비 범위로 통과한다.
    """
    for prefix, scope in sorted(_WRITE_SCOPES, key=lambda one: -len(one[0])):
        if path.startswith(prefix):
            return scope
    return None


def _enforce_token_scope(request: Request, token_scopes: list[str], path: str) -> None:
    """기계 자격의 쓰기를 범위로 막는다.

    **사람 세션에는 안 건다** — 그 사람의 권한이 이미 한계다. 범위는 기계 자격에만
    있는 개념이고, 둘을 같은 축으로 섞으면 화면에서 되던 일이 이유 없이 막힌다.
    """
    reading = request.method in _SAFE_METHODS or any(
        path.startswith(prefix) for prefix in _READ_ONLY_POSTS
    )
    if reading:
        if "read" in token_scopes:
            return
        raise Forbidden(
            "TSC-AUTH-0104",
            "이 토큰에는 읽기 범위(read)가 없습니다.",
        )

    needed = _needed_scope(path)
    if needed is None:
        raise Forbidden(
            "TSC-AUTH-0105",
            "개인 토큰으로는 이 경로를 고칠 수 없습니다. 화면에서 하세요.",
            details={"path": path},
        )
    if needed not in token_scopes:
        raise Forbidden(
            "TSC-AUTH-0106",
            f"이 토큰에는 {needed} 범위가 없습니다.",
            details={"needed": needed, "granted": token_scopes},
        )


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _bearer(request)
    if token is None:
        raise AppError("TSC-AUTH-0100", _UNAUTHENTICATED, status=401)

    if token.startswith(security.ACCEPTED_PAT_PREFIXES):
        found = services.resolve_pat(db, token)
        if found is None:
            logger.warning("PAT 인증 실패 (prefix=%s)", token[: len(security.PAT_PREFIX) + 6])
            raise AppError("TSC-AUTH-0101", "토큰이 유효하지 않습니다.", status=401)
        user, pat = found
        _enforce_token_scope(request, list(pat.scopes or []), request.url.path)
        # **감사에 토큰 이름을 남긴다.** 소유자만 남기면 사람이 넣은 것과 기계가
        # 넣은 것이 구별되지 않는다.
        set_actor_token(pat.name)
        # 접근 로그 미들웨어가 "누가" 를 알 수 있게 scope 에 남긴다. 미들웨어는
        # 인증보다 바깥에 있어서 스스로는 사용자를 알 수 없다.
        request.scope["tsc_user_id"] = user.id
        return user

    payload = security.decode_access_token(token)
    if payload is None:
        # 사유(만료·서명 불일치)는 응답에 싣지 않는다 — 공격자에게 힌트가 된다.
        raise AppError("TSC-AUTH-0102", "세션이 만료되었습니다.", status=401)

    signed_in = db.get(User, payload["sub"])
    if signed_in is None:
        raise Forbidden("TSC-AUTH-0002", "삭제된 계정입니다. 관리자에게 문의하세요.")
    services.ensure_can_sign_in(signed_in)
    request.scope["tsc_user_id"] = signed_in.id
    return signed_in


def require_system_admin(user: User = Depends(current_user)) -> User:
    if not user.is_system_admin:
        raise Forbidden("TSC-AUTH-0103", "권한이 없습니다.")
    return user

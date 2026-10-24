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
import re

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.auth import security, services
from app.shared import confirm
from app.shared.errors import AppError, Forbidden
from app.shared.request_context import set_actor_token

logger = logging.getLogger(__name__)

_UNAUTHENTICATED = "로그인 필요."


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
    ("/api/test-item-properties", "catalog:write"),
    # 시험 항목의 검색 축(`set_test_item_axes`). 표에 없어서 MCP 도구가 늘 403 이었다 —
    # 경로 몇 개만 눌러 보던 시험이 못 잡았다(아래 시험이 이제 쓰기 도구 전부를 본다).
    ("/api/test-items", "catalog:write"),
    ("/api/equipment", "equipment:write"),
    ("/api/equipment-test-items", "equipment:write"),
    # 부서가 등록하는 시험 절차 — 장비와 같은 「부서 것」 이라 같은 범위다.
    ("/api/reliability-tests", "equipment:write"),
    ("/api/attribute-definitions", "catalog:write"),
    # **사내 규격서는 부서 것이다** — 장비·신뢰성 시험과 같은 범위를 쓴다. 전에는 표에
    # 없어서 기계 자격으로 못 썼는데, 그러면 AI 가 시험은 올리면서 **그 근거 문서는 못
    # 붙인다** — 값이 틀렸을 때 되짚을 자리가 없어진다(2026-09-30). 대신 누가 넣었는지가
    # 줄에 남는다(`submitted_via`).
    ("/api/spec-documents", "equipment:write"),
    # 첨부는 **붙는 대상의 것**이다 — 지금은 신뢰성 시험뿐이라 그 범위를 쓴다.
    # 대상이 늘면(장비 사진·교정 성적서) 경로를 가르는 것이 아니라 이 한 줄을 다시 본다.
    ("/api/attachments", "equipment:write"),
    # **검토함 — 시스템 관리자의 토큰이면 MCP 로도 정한다**(2026-10-04, 사용자 결정). 전에는 이
    # 표에 없어서 기계 자격으로 아예 막았다(「고른 것이 곧 정본이니 사람이 화면에서」). 고른
    # 것이 카탈로그를 바꾸므로 카탈로그 범위를 쓴다. 확정 자격(시스템 관리자)은 그대로 서버가
    # 보고, 누가 MCP 로 정했는지가 줄(`decided_by_label`)과 감사에 남는다.
    ("/api/review", "catalog:write"),
)

#: **사람 확인을 받으면** 기계 자격으로도 쓰는 경로 — 관리 일(ADR 0013, 2026-10-22 사용자
#: 결정).
#:
#: 위 표는 「토큰이 혼자 해도 되는 일」 이고 이 표는 「사람이 AI 화면의 확인 창에서 내용을
#: 보고 수락해야 되는 일」 이다(`shared/confirm.py`). 범위는 `admin:write` 하나 — 사람이
#: 따로 골라 준 토큰만 연다. 자격(시스템 관리자 · 부서 관리자)은 종전대로 각 엔드포인트가
#: 본다.
_CONFIRMED_WRITES: tuple[tuple[str, str], ...] = (
    ("/api/accounts", "admin:write"),
    ("/api/workspaces", "admin:write"),
    ("/api/notices", "admin:write"),
    ("/api/hub", "admin:write"),
    ("/api/voc", "admin:write"),
)

#: **비밀값을 다루는 경로는 어떤 확인으로도 기계 자격에 안 연다**(2026-10-22 사용자 결정).
#: 토큰 발급 · 폐기, 임시 비밀번호(계정 만들기 · 비밀번호 초기화), 로그인 · 가입 — 열면 평문
#: 비밀이 AI 대화 기록에 남는다. 허브 토큰 입력은 같은 이유로 허브 서비스가 막는다.
_SECRET_WRITES = re.compile(
    r"^/api/(auth/.*|accounts|accounts/signup|accounts/[^/]+/reset-password)$"
)

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

#: POST 지만 **아무것도 안 바꾸는** 것들. 본문에 물음을 싣기 때문에 POST 일 뿐이다.
#:
#: 이걸 빼먹으면 읽기 전용 토큰이 **검색을 못 한다** — 그리고 검색은 이 시스템이
#: 존재하는 이유다. 실측으로 드러났다: 범위를 준 토큰이 `/api/resolve` 와
#: `/api/search/test-items` 에서 403 을 받았다.
_READ_ONLY_POSTS = (
    "/api/resolve",
    "/api/search/",
    # 저장 **안 한** 조건으로 장비를 본다 — 조건을 본문에 실을 뿐 아무것도 안 바꾼다. 적으면서
    # 「이 조건이면 장비 0대」 를 먼저 보는 자리라 읽기 토큰으로도 돼야 한다(2026-10-25).
    "/api/reliability-tests/capability-preview",
)


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
            "이 토큰에 읽기 범위(read) 없음.",
        )

    needed = _needed_scope(path)
    if needed is None:
        _enforce_confirmed_write(request, token_scopes, path)
        return
    if needed not in token_scopes:
        raise Forbidden(
            "TSC-AUTH-0106",
            f"이 토큰에 {needed} 범위 없음.",
            details={"needed": needed, "granted": token_scopes},
        )


def _confirmed_scope(path: str) -> str | None:
    for prefix, scope in _CONFIRMED_WRITES:
        if path == prefix or path.startswith(prefix + "/"):
            return scope
    return None


def _enforce_confirmed_write(request: Request, token_scopes: list[str], path: str) -> None:
    """범위 표 밖의 쓰기 — **사람 확인을 받은 관리 일만** 지난다.

    순서가 뜻이다: 비밀값 경로는 무엇으로도 안 열고(①), 관리 경로는 `admin:write` 를 고른
    토큰이어야 하고(②), 그 위에 사람이 확인 창에서 수락해야 한다(③). ②를 ③보다 먼저 보는
    것은, 범위 없는 토큰으로 확인 창부터 띄우면 사람이 수락하고 나서야 403 을 받기 때문이다.
    """
    scope = _confirmed_scope(path)
    if scope is None or _SECRET_WRITES.match(path):
        raise Forbidden(
            "TSC-AUTH-0105",
            "개인 토큰으로는 이 경로 수정 불가. 화면에서 수정 필요."
            + (" 비밀값(토큰 · 비밀번호)을 다루는 경로." if scope is not None else ""),
            details={"path": path},
        )
    if scope not in token_scopes:
        raise Forbidden(
            "TSC-AUTH-0106",
            f"이 토큰에 {scope} 범위 없음(관리 작업 — 계정 · 부서 · 공지 · 허브 · VOC).",
            details={"needed": scope, "granted": token_scopes},
        )
    confirm.require(
        "TSC-AUTH-0107",
        "관리 작업은 사용자 확인 필요.",
        summary=f"관리 작업 {request.method} {path}",
        # 토큰 이름은 이 판정 **뒤에** 남는다 — 여기서는 기계 통로임을 직접 말한다.
        machine=True,
    )


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _bearer(request)
    if token is None:
        raise AppError("TSC-AUTH-0100", _UNAUTHENTICATED, status=401)

    if token.startswith(security.ACCEPTED_PAT_PREFIXES):
        found = services.resolve_pat(db, token)
        if found is None:
            logger.warning("PAT 인증 실패 (prefix=%s)", token[: len(security.PAT_PREFIX) + 6])
            raise AppError("TSC-AUTH-0101", "유효하지 않은 토큰.", status=401)
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
        raise AppError("TSC-AUTH-0102", "세션 만료.", status=401)

    signed_in = db.get(User, payload["sub"])
    if signed_in is None:
        raise Forbidden("TSC-AUTH-0002", "삭제된 계정. 관리자 문의 필요.")
    services.ensure_can_sign_in(signed_in)
    request.scope["tsc_user_id"] = signed_in.id
    return signed_in


def require_system_admin(user: User = Depends(current_user)) -> User:
    if not user.is_system_admin:
        raise Forbidden("TSC-AUTH-0103", "권한 없음.")
    return user

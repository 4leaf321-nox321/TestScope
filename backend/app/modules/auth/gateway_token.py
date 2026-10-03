"""HWAX 포털 MCP 게이트웨이의 **사람별 위임** — 그 사람의 TestScope 토큰을 자동으로 내준다.

HWAX 앱들의 **표준 위임 창구**와 같은 모양이다. 계약의 정본은 포털 요청서
(HWAXPortal `docs/sso-delegation/ra-request.md`)이고, Report Archive 가 2026-10-03 에 같은
계약으로 먼저 붙었다(`backend/app/modules/sso/gateway_token.py` v0.171.1). 소비자는
게이트웨이 하나다(`per_user_sso.testscope`, `X-Heax-Client: gateway`).

    POST /api/auth/sso            그 사람의 TestScope 토큰 발급
    POST /api/auth/sso/verify     비밀만 확인 — 204 / 401. 아무것도 안 만든다(설정 점검용)
    POST /api/auth/sso/revoke     그 사람·그 client 의 위임 토큰 폐기 — 200 {"revoked": n}

    공통 헤더  X-Heax-Gateway-Secret: <HEAX_SSO_SECRET>
              X-Heax-User-Email:     <포털이 확인한 이메일>          (verify 는 없어도 된다)
              X-Heax-User-Name:      <표시 이름, 퍼센트 인코딩>      (선택 — 지금은 안 쓴다)
              X-Heax-Client:         <client — 토큰 이름에 쓴다. client 마다 하나씩만 둔다>
    발급 응답  {"success": true, "data": {"access_token": "tsc_pat_…", "token_type": "bearer",
              "expires_in": 172800, "needs_workspace": bool}} — 요청서의 봉투 그대로.
              게이트웨이는 어디 있든 access_token 을 깊이 탐색으로 찾고, expires_in 은 토큰과
              같은 객체에서 읽는다(`_mint_user_pat`). 캐시는 최대 12시간, expires_in 보다
              2분 먼저 버리고, 401 을 받으면 한 번 다시 받는다.

## 왜 SSO 가 아닌가

사용자가 HWAX 에 로그인했다고 TestScope 가 그 사람을 들여보내는 것이 SSO 다. 이 창구는
그렇지 않다 — **TestScope 에 이미 있는 계정**에 한해, 게이트웨이가 공유 비밀로 「이 사람」
을 말하면 그 사람 이름의 개인 토큰(`tsc_pat_`)을 내준다. 계정이 없으면 만들지 않는다
(아래). 브라우저로 TestScope 에 들어오는 길은 종전대로 TestScope 로그인뿐이다.

지금까지는 사람이 TestScope 에서 토큰을 발급해 HWAX 「개인 토큰 → 외부 연결」 에 붙여
넣었다(HWAX 쪽 `connections.py`). 이 창구가 그 수작업을 대신한다. ⚠ HWAX 쪽은 비밀이
생기는 순간 **위임 전용**이 된다 — 이 창구가 안 돌면 TestScope 도구 전부가 거부되고 등록
토큰으로 돌아가지 않는다. 그래서 순서는 반드시 **TestScope 먼저**다(배포.md).

## 지키는 것

- **비밀은 상수 시간으로 비교한다.** 비밀이 비면 세 창구 모두 없다(404) — 게이트웨이는
  404 를 「TestScope 쪽이 아직 안 켬」 으로 읽는다. 그래서 사람 하나의 거절(없는 계정 ·
  승인 대기 · 정지)은 404 가 아니라 **403** 이어야 한다. 404 로 내면 창구 전체가 꺼진
  줄 안다 — RA 가 겪고 고친 자리다.
- `HEAX_SSO_ALLOWED_IPS` 가 있으면 그 IP 에서 온 것만. 리버스 프록시 뒤에 두면 클라이언트
  IP 가 프록시 것이 되므로 그 주소를 적는다(TestScope 는 `X-Forwarded-For` 를 믿지 않는다).
- **이메일 형식이 아니면 401.** 형식 검사 없이 통과시키면 쓰레기 문자열로 계정을 찾거나
  (JIT 가 있는 앱에서는) 만든다. `admin` 같은 짧은 아이디는 화면 로그인용이지 위임 대상이
  아니다 — 포털은 이메일로 사람을 가리킨다.
- **계정을 만들지 않는다.** TestScope 는 가입 → 관리자 승인 → 부서 배정의 절차가 있다
  (`accounts.signup` 은 `pending` 으로 만들고, 승인이 부서를 정한다). 위임 창구가 승인
  없이 `active` 계정을 만들면 그 절차가 뚫리고, `pending` 으로 만들면 어차피 토큰을 못
  준다. 그래서 RA 와 달리 JIT 가 없다 — 없는 사람은 403 과 「TestScope 에서 가입 승인부터」
  로 답한다. 그 사람이 로그인할 수 없는 상태(승인 대기 · 정지 · 삭제)도 403 이다.
- **토큰은 읽기 전용이다.** 범위를 `read` 로 고정한다. 포털에서 들어오는 쓰기는 우리가
  프롬프트를 못 보는 통로다 — 사용자가 「HWAX 에는 읽기만」 을 정했고, 그것을 여기서
  강제한다(붙여넣기 방식에서는 강제할 수 없던 것). 쓰기가 필요하면 TestScope 에서 발급한
  토큰을 종전처럼 쓴다.
- **같은 client 의 직전 토큰은 폐기하고 새로 낸다.** 게이트웨이가 12시간마다 다시 받아
  가므로 남겨 두면 목록이 쌓인다. 지우지 않고 `revoked_at` 을 찍는다 — TestScope 의 폐기는
  원래 그렇고, 「언제 누가 받아 갔나」 가 목록에 남는다. 게이트웨이도 「새 발급이 직전 것을
  회수한다」 를 전제로 사용자 단위로 발급을 직렬화한다.
- 토큰 수명은 **2일** — 게이트웨이가 12시간 캐시한다. 새어 나가도 이틀이다.
- 발급은 감사(`PAT_ISSUED_FOR_GATEWAY`)와 접근 로그(그 사람 명의)에 남는다.
"""

from __future__ import annotations

import hmac
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import unquote

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modules.accounts.models import User
from app.modules.auth import security
from app.modules.auth.models import PersonalAccessToken
from app.shared import audit
from app.shared.errors import AppError, Forbidden, NotFound

logger = logging.getLogger(__name__)

#: 게이트웨이가 12시간 캐시하므로 길 필요가 없다. 짧을수록 새어 나간 토큰의 수명이 짧다.
TOKEN_DAYS = 2
#: 토큰 이름 — 사용자의 「내 정보 → 토큰」 목록에 이대로 보인다. client 별로 하나씩만 둔다.
TOKEN_NAME = "HWAX 포탈 게이트웨이"
#: **읽기 전용으로 고정한다.** 포털에서 들어오는 쓰기는 우리가 프롬프트를 못 보는 통로다.
SCOPES = ("read",)

HEADER_SECRET = "x-heax-gateway-secret"
HEADER_EMAIL = "x-heax-user-email"
HEADER_NAME = "x-heax-user-name"
HEADER_CLIENT = "x-heax-client"

#: 이메일 「형식」 판정 — @ 하나, 도메인에 점. 실수·오배선을 거르는 용도라 더 엄밀할 필요는
#: 없다. `.local` 같은 사내 도메인도 통과한다(화면 로그인과 같은 자세 — `LoginRequest` 주석).
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def enabled() -> bool:
    return bool(get_settings().heax_sso_secret.strip())


def token_name(client: str) -> str:
    client = (client or "").strip()[:40]
    return f"{TOKEN_NAME} ({client})" if client else TOKEN_NAME


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def gate(request: Request) -> None:
    """세 창구 공통 — 꺼짐 404 · 허용 밖 IP 403 · 비밀 불일치 401. 통과면 돌아온다."""
    settings = get_settings()
    if not enabled():
        # 꺼져 있으면 있는지조차 흘리지 않는다 — 게이트웨이는 이 404 를 「아직 안 켬」 으로
        # 읽는다.
        raise NotFound("TSC-AUTH-0200", "not found")
    allowed = {ip.strip() for ip in settings.heax_sso_allowed_ips.split(",") if ip.strip()}
    if allowed and _client_ip(request) not in allowed:
        logger.warning("auth/sso: 허용되지 않은 IP %s", _client_ip(request))
        raise Forbidden("TSC-AUTH-0201", "허용되지 않은 위치입니다.")
    given = (request.headers.get(HEADER_SECRET) or "").strip().encode("utf-8")
    expected = settings.heax_sso_secret.strip().encode("utf-8")
    if not hmac.compare_digest(given, expected):
        logger.warning("auth/sso: 비밀 불일치 (%s)", _client_ip(request))
        raise AppError("TSC-AUTH-0202", "게이트웨이 비밀이 맞지 않습니다.", status=401)


def _email(request: Request) -> str:
    """헤더의 이메일 — 없으면 400, 형식이 아니면 401. 소문자로 돌려준다."""
    email = (request.headers.get(HEADER_EMAIL) or "").strip().lower()
    if not email:
        raise AppError("TSC-AUTH-0203", "X-Heax-User-Email 이 필요합니다.", status=400)
    if not _EMAIL_RE.match(email):
        logger.warning("auth/sso: 이메일 형식 아님 (%s)", _client_ip(request))
        raise AppError(
            "TSC-AUTH-0204", "X-Heax-User-Email 이 이메일 형식이 아닙니다.", status=401
        )
    return email


def _name(request: Request) -> str:
    raw = request.headers.get(HEADER_NAME) or ""
    try:
        return unquote(raw).strip()[:100]
    except Exception:  # 이름이 깨져 와도 발급은 한다
        return ""


def _user(db: Session, email: str) -> User:
    """그 이메일의 사람. **없으면 만들지 않는다**(모듈 설명). 못 쓰는 계정도 403."""
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise Forbidden(
            "TSC-AUTH-0205",
            "TestScope 에 그 이메일의 계정이 없습니다 — TestScope 에서 가입하고 승인을 "
            "받은 뒤 다시 시도하십시오. 포털에서 계정을 만들어 주지 않습니다.",
        )
    if user.deleted_at is not None or user.status != "active":
        why = "승인 대기 중" if user.status == "pending" else "쓸 수 없는 상태"
        raise Forbidden(
            "TSC-AUTH-0206",
            f"TestScope 계정이 {why}입니다 — TestScope 관리자에게 문의하십시오.",
        )
    return user


def _revoke_same_name(db: Session, user: User, name: str) -> int:
    """같은 client 의 살아 있는 직전 토큰을 폐기한다. 지우지 않는다 — 목록에 남는다."""
    rows = db.scalars(
        select(PersonalAccessToken).where(
            PersonalAccessToken.user_id == user.id,
            PersonalAccessToken.name == name,
            PersonalAccessToken.revoked_at.is_(None),
        )
    ).all()
    now = datetime.now(UTC)
    for row in rows:
        row.revoked_at = now
    return len(rows)


def issue(db: Session, request: Request) -> dict[str, Any]:
    """그 사람의 읽기 전용 토큰을 내준다. **`gate` 를 먼저 지나야 한다.**"""
    email = _email(request)
    user = _user(db, email)
    client = (request.headers.get(HEADER_CLIENT) or "").strip()
    name = token_name(client)

    replaced = _revoke_same_name(db, user, name)
    raw, prefix, token_hash = security.new_pat()
    pat = PersonalAccessToken(
        user_id=user.id,
        name=name,
        prefix=prefix,
        token_hash=token_hash,
        scopes=list(SCOPES),
        expires_at=datetime.now(UTC) + timedelta(days=TOKEN_DAYS),
    )
    db.add(pat)
    db.flush()
    audit.record(
        db,
        action=audit.PAT_ISSUED_FOR_GATEWAY,
        actor=user,
        target_table="personal_access_tokens",
        target_id=pat.id,
        target_label=name,
        changes={
            "client": client or None,
            "scopes": list(SCOPES),
            "expires_in": TOKEN_DAYS * 86400,
            "client_ip": _client_ip(request) or None,
            "replaced": replaced,
            "portal_name": _name(request) or None,
        },
    )
    db.commit()
    # 접근 로그가 「누가」 를 알 수 있게 — 이 요청은 인증 의존성을 안 지나서 스스로 적는다.
    request.scope["tsc_user_id"] = user.id
    logger.info("auth/sso: %s 에게 발급(%s), 직전 %d개 폐기", user.email, name, replaced)
    return {
        "access_token": raw,
        "token_type": "bearer",
        "expires_in": TOKEN_DAYS * 86400,
        # 아직 대표 부서가 없는 사람 — 승인은 됐는데 부서를 안 정한 경우. 참고용이다.
        "needs_workspace": user.home_workspace_id is None,
    }


def revoke(db: Session, request: Request) -> int:
    """그 사람·그 client 의 위임 토큰을 폐기한다. 사람이 없거나 토큰이 없어도 0 — 폐기할
    것이 없을 뿐이다. **`gate` 를 먼저 지나야 한다.**"""
    email = _email(request)
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        return 0
    name = token_name(request.headers.get(HEADER_CLIENT) or "")
    revoked = _revoke_same_name(db, user, name)
    db.commit()
    logger.info("auth/sso/revoke: %s — %d개", email, revoked)
    return revoked


__all__ = [
    "SCOPES",
    "TOKEN_DAYS",
    "TOKEN_NAME",
    "enabled",
    "gate",
    "issue",
    "revoke",
    "token_name",
]

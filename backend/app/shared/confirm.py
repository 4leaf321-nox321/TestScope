"""**사람 확인 증표** — AI 화면에서 사람이 수락한 요청만 사람 몫의 결정을 지난다(ADR 0013).

기계 자격(PAT)은 그동안 사람 몫의 결정(신뢰성 시험 확정 · 계정 승인 · 부서 · 공지 …)을 아예
못 했다. 2026-10-22 사용자 결정으로 연다 — **대신 AI 가 스스로 정하지 못하게**, 사람이 AI
클라이언트의 확인 창(MCP elicitation)에서 내용을 보고 수락한 요청만 받는다.

**증표는 MCP 서버만 만든다.** 확인 창에서 사람이 수락한 뒤에 그 요청(메서드 · 경로 · 쿼리 ·
토큰 · 본문)에 서명해 `X-Human-Confirm` 으로 싣는다. 서명 열쇠는 `JWT_SECRET` 에서 뽑는다 —
같은 `backend\\.env` 를 읽는 MCP 서버만 안다. AI 는 열쇠가 없으니 증표를 못 만들고, 받은
증표는 **그 요청 하나**에만 맞는다(본문을 바꾸거나 다른 토큰으로 보내면 안 맞는다, 2분 뒤
만료, 한 번만).

**증표는 권한이 아니다.** 토큰의 범위와 그 사람의 자격은 그대로 서버가 본다 — 증표가 하는
일은 「기계 통로라서 막던 것」 을 사람이 보고 수락했다는 이유로 푸는 것 하나다. 그래서
만능 토큰이 아니다: 증표만으로는 아무 요청도 인증되지 않는다.

서명 방식은 `mcp_server/confirm.py` 와 **같아야 한다** — 두 벌이라 시험이 둘을 맞대 본다
(`tests/unit/test_confirm.py`).
"""

from __future__ import annotations

import hashlib
import hmac
import threading
import time
from typing import Any

from fastapi import Request

from app.config import get_settings
from app.shared.errors import AppError, Forbidden
from app.shared.request_context import get_actor_token, is_confirmed, mark_confirmed

HEADER = "X-Human-Confirm"
VERSION = "v1"

#: 증표의 수명. 사람이 수락한 **뒤에** 서명하므로 길 필요가 없다 — 확인 창을 읽는 시간은
#: 여기 안 들어간다.
TTL_SECONDS = 120

#: 쓴 증표(nonce → 만료 시각). 같은 증표를 두 번 못 쓰게. 백엔드는 프로세스 하나로 돈다.
_seen: dict[str, float] = {}
_lock = threading.Lock()

#: 막힌 자리가 덧붙이는 한 줄 — **무엇을 하면 되는지.** 「사람만」 으로 끝내면 AI 는 거기서
#: 멈추고 사람은 그것을 권한 문제로 읽는다.
HOW = (
    "AI 화면의 확인 창에서 사용자가 수락하면 실행됨(MCP 도구가 묻고 다시 보냄)."
    " 확인 창을 띄울 수 없는 클라이언트면 TestScope 화면에서."
)


def derive_key(secret: str) -> bytes:
    """`JWT_SECRET` 에서 증표 열쇠를 뽑는다. 세션 서명과 같은 열쇠를 그대로 쓰지 않는다."""
    return hmac.new(secret.encode(), b"testscope-human-confirm-v1", hashlib.sha256).digest()


def signature(
    key: bytes,
    *,
    ts: str,
    nonce: str,
    method: str,
    path: str,
    query: str,
    token: str,
    body: bytes,
) -> str:
    """요청 하나에 대한 서명. 토큰과 본문은 해시로만 싣는다(증표에 비밀이 안 남게)."""
    message = "\n".join(
        (
            VERSION,
            ts,
            nonce,
            method.upper(),
            path,
            query,
            hashlib.sha256(token.encode()).hexdigest(),
            hashlib.sha256(body).hexdigest(),
        )
    )
    return hmac.new(key, message.encode(), hashlib.sha256).hexdigest()


def _refuse(why: str) -> Forbidden:
    return Forbidden(
        "TSC-AUTH-0108",
        f"사용자 확인 증표가 맞지 않음({why}). 실행 안 함. MCP 서버와 백엔드가 같은"
        " backend\\.env(JWT_SECRET)를 쓰는지 확인 필요.",
    )


def _first_use(nonce: str, until: float, now: float) -> bool:
    with _lock:
        for old in [one for one, expiry in _seen.items() if expiry < now]:
            del _seen[old]
        if nonce in _seen:
            return False
        _seen[nonce] = until
        return True


async def read_proof(request: Request) -> None:
    """앱 전역 의존성 — 증표가 실려 오면 검증하고, 맞으면 이 요청을 「확인됨」 으로 표시한다.

    **증표가 없으면 아무 일도 안 한다.** 화면 · 보통의 MCP 쓰기는 그대로 지난다. 실려 왔는데
    안 맞으면 조용히 무시하지 않고 거절한다 — 무시하면 사람이 수락한 것이 「확인 필요」 로
    되돌아와 같은 확인 창이 끝없이 뜬다.

    본문을 읽어야 해서 비동기다. FastAPI 가 본문을 이미 읽었으면 그 값을 그대로 받는다.
    """
    sent = request.headers.get(HEADER)
    if not sent:
        return
    parts = sent.split(".")
    if len(parts) != 4 or parts[0] != VERSION:
        raise _refuse("모양")
    _, ts, nonce, claimed = parts
    try:
        when = int(ts)
    except ValueError:
        raise _refuse("시각") from None
    now = time.time()
    if abs(now - when) > TTL_SECONDS:
        raise _refuse("만료")
    header = request.headers.get("authorization") or ""
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    if not token:
        raise _refuse("토큰 없음")
    body = await request.body()
    expected = signature(
        derive_key(get_settings().jwt_secret),
        ts=ts,
        nonce=nonce,
        method=request.method,
        path=request.scope["path"],
        query=request.scope.get("query_string", b"").decode("latin-1"),
        token=token,
        body=body,
    )
    if not hmac.compare_digest(expected, claimed):
        raise _refuse("서명")
    if not _first_use(nonce, when + TTL_SECONDS, now):
        raise _refuse("이미 쓴 증표")
    mark_confirmed()


def require(
    code: str,
    message: str,
    *,
    summary: str,
    status: int = 403,
    details: dict[str, Any] | None = None,
    machine: bool | None = None,
) -> None:
    """기계 통로면 **사람 확인을 요구한다.** 사람 세션과 확인된 요청은 그냥 지난다.

    `machine` 은 인증 의존성 안에서 부를 때만 준다 — 거기서는 토큰 이름이 아직 안 남았다
    (`get_actor_token()` 이 None). 안 주면 그것으로 판정해, 범위 판정에서 부른 이 함수가
    아무것도 안 막는 일이 생긴다.

    `summary` 는 확인 창에 그대로 실린다 — 사람이 그것만 읽고 수락할지 정한다. 그러므로
    **무엇이 어떻게 바뀌는지**를 쓴다(이름 · 건수 · 되돌릴 수 있는지). 「확정합니다」 만으로는
    무엇을 확정하는지 모른 채 누르게 된다.
    """
    by_machine = get_actor_token() is not None if machine is None else machine
    if not by_machine or is_confirmed():
        return
    raise AppError(
        code,
        f"{message} {HOW}",
        status=status,
        details={**(details or {}), "needs_confirmation": True, "confirm": summary},
    )

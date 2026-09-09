"""요청 ID — 사용자 신고와 로그를 잇는 유일한 끈.

원격 디버깅이 없는 사내 설치에서 "그 화면에서 안 돼요" 를 재현하려면, 사용자가
본 오류 응답과 서버 로그가 같은 id 로 묶여 있어야 한다.

**순수 ASGI 미들웨어로 구현한다.** Starlette 의 BaseHTTPMiddleware 는 downstream
을 별도 태스크로 실행해서, dispatch 에서 설정한 ContextVar 가 엔드포인트와 예외
핸들러에 전파되지 않는다 — 그러면 로그와 오류 본문의 request_id 가 둘 다 '-' 로
찍힌다. 순수 ASGI 는 같은 컨텍스트에서 downstream 을 호출하므로 전파된다.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_request_id: ContextVar[str] = ContextVar("request_id", default="-")

#: 어느 통로로 들어왔나 · 어느 토큰이 썼나. **감사가 이것을 남긴다.**
#:
#: `actor_id` 는 토큰 소유자, 즉 사람이다 — 그것만으로는 사람이 넣은 것과 AI 가
#: 넣은 것이 구별되지 않는다. ContextVar 로 두는 이유는 request_id 와 같다:
#: 감사를 남기는 자리(services)가 Request 를 들고 있지 않다.
#:
#: **값이 아니라 dict 를 담는다.** 토큰 이름은 인증 의존성(`shared/auth.py`)이
#: 채우는데, FastAPI 는 동기 의존성을 **스레드풀에서** 돌린다 — 거기서 ContextVar
#: 를 `set` 하면 그 변경은 복사본에만 남고 엔드포인트로 안 돌아온다. 미들웨어가
#: 만든 dict 를 **같이 가리키게** 두면 그 안을 고치는 것은 전파된다.
#:
#: (BaseHTTPMiddleware 로 request_id 가 사라지던 것과 같은 부류의 함정이다.)
#: 기본값을 None 으로 둔다 — 가변 기본값은 요청 사이에 공유된다(ruff B039).
#: 미들웨어 밖에서 부르는 자리(시험·스크립트)는 빈 값을 본다.
_actor: ContextVar[dict[str, str | None] | None] = ContextVar("actor", default=None)

HEADER = "X-Request-ID"
_HEADER_BYTES = HEADER.lower().encode()

#: 호출자가 스스로 밝히는 통로. **보안 경계가 아니라 감사 표식이다** —
#: 누구나 적을 수 있고, 그래도 「이 변경은 MCP 로 들어왔다」 를 남기는 값은 있다.
_CLIENT_BYTES = b"x-client"


def get_request_id() -> str:
    return _request_id.get()


def get_actor_client() -> str | None:
    return (_actor.get() or {}).get("client")


def get_actor_token() -> str | None:
    return (_actor.get() or {}).get("token")


def set_actor_token(name: str | None) -> None:
    """인증이 끝난 뒤 부른다 — 어느 토큰이 이 요청을 냈나.

    **`set` 이 아니라 dict 를 고친다.** 이 함수는 스레드풀에서 불릴 수 있고,
    거기서 ContextVar 를 갈아 끼우면 엔드포인트는 옛 값을 본다.
    """
    holder = _actor.get()
    if holder is not None:
        holder["token"] = name


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 역방향 프록시나 클라이언트가 id 를 들고 오면 그대로 이어 쓴다.
        incoming = dict(scope.get("headers") or {}).get(_HEADER_BYTES)
        rid = incoming.decode() if incoming else uuid.uuid4().hex[:12]
        token = _request_id.set(rid)

        client = dict(scope.get("headers") or {}).get(_CLIENT_BYTES)
        actor = _actor.set({"client": client.decode()[:40] if client else None, "token": None})

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                message["headers"].append((_HEADER_BYTES, rid.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            _request_id.reset(token)
            _actor.reset(actor)

"""접근 로그 미들웨어.

**모든 API 요청을 남기지 않는다.** 알림 배지 폴링까지 적으면 표가 의미 없는 행으로
차서 정작 찾을 것을 못 찾는다. 상태를 바꾸는 요청과 로그인만 남긴다 — 사용자
지원에 필요한 것은 "무엇을 했는가" 이지 "무엇을 봤는가" 가 아니다.

기록은 요청 처리와 별개 세션에서 한다. 로그를 남기다 실패해도 사용자의 요청은
성공해야 한다.

## 보존 기간이 지나면 지운다

전에는 아무도 안 지워서 끝없이 자랐다. 하루 한 번, **응답을 보낸 뒤** 스레드에서 보존
기간(`ACCESS_LOG_RETENTION_DAYS`, 기본 365일)보다 오래된 줄을 지운다. 0 이면 지우지 않는다.

**주기 작업(`app/jobs/schedule.py`)에 안 얹은 이유**: 그것은 워커가 돌리는데, 워커는 따로
띄우는 프로세스라 **안 떠 있는 설치가 있다**(배포.md — 「워커가 없어도 앱은 돈다」). 줄을
쓰는 것은 서버이므로 지우는 것도 서버가 하면, 워커 유무와 상관없이 표가 끝없이 자라지 않는다.
감사 기록(`audit_entries`)은 지우지 않는다: 그쪽은 「누가 무엇을 바꿨나」 의 유일한 답이다.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import get_settings
from app.database import SessionLocal
from app.modules.audit.models import AccessLog
from app.shared.request_context import get_request_id

logger = logging.getLogger(__name__)

#: 지우기 간격. 보존 기간이 날 단위라 하루 한 번이면 된다. 워커가 여럿이면 저마다 하루 한
#: 번 돌지만 같은 줄을 지우는 일이라 겹쳐도 해가 없다.
PRUNE_EVERY_SECONDS = 24 * 3600.0
_next_prune = 0.0
"""다음에 지울 때(`time.monotonic`). 0 이면 기동 뒤 첫 기록에서 한 번 돈다."""


def prune(db: Session, *, days: int) -> int:
    """`days` 일보다 오래된 접근 로그를 지운다. 지운 줄 수를 돌려준다. 0 이하면 안 지운다."""
    if days <= 0:
        return 0
    cutoff = datetime.now(UTC) - timedelta(days=days)
    result = db.execute(delete(AccessLog).where(AccessLog.created_at < cutoff))
    db.commit()
    return int(getattr(result, "rowcount", 0) or 0)


def _prune_quietly(factory: Callable[[], Session]) -> None:
    """지우다 실패해도 요청과는 상관없다 — 남기고 넘어간다. 다음 날 다시 돈다."""
    days = get_settings().access_log_retention_days
    db = factory()
    try:
        gone = prune(db, days=days)
        if gone:
            logger.info("접근 로그 %d줄을 지웠습니다 (보존 %d일)", gone, days)
    except Exception:
        logger.exception("접근 로그 정리 실패")
    finally:
        db.close()


#: 남길 메서드. GET 은 기본적으로 안 남긴다(조회는 양이 많고 가치가 낮다).
_RECORDED_METHODS = {"POST", "PATCH", "PUT", "DELETE"}

#: 남기지 않을 경로. 폴링과 헬스체크가 대부분이다.
_SKIP = ("/api/health", "/api/notifications/unread-count")


def _action(path: str) -> str:
    if path.endswith("/auth/login"):
        return "LOGIN"
    if path.endswith("/auth/logout"):
        return "LOGOUT"
    return "API"


class AccessLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path", ""))
        method = str(scope.get("method", ""))
        status_holder = {"status": 0}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = int(message["status"])
            await send(message)

        await self.app(scope, receive, send_wrapper)

        if not path.startswith("/api/") or path in _SKIP:
            return
        if method not in _RECORDED_METHODS:
            return

        # 세션 공장을 app.state 에서 가져온다. SessionLocal 을 직접 부르면 설정과
        # 무관하게 늘 같은 DB 를 보게 되어, 테스트가 자기 DB 를 쓰지 못한다.
        factory = getattr(scope["app"].state, "session_factory", SessionLocal)
        try:
            headers = dict(scope.get("headers") or {})
            client = scope.get("client")
            db = factory()
            try:
                db.add(
                    AccessLog(
                        user_id=scope.get("tsc_user_id"),
                        action=_action(path),
                        path=path[:300],
                        method=method,
                        status_code=status_holder["status"],
                        request_id=get_request_id(),
                        client_ip=client[0] if client else None,
                        user_agent=(headers.get(b"user-agent") or b"").decode()[:300] or None,
                    )
                )
                db.commit()
            finally:
                db.close()
        except Exception:
            # 로그를 남기다 실패해도 사용자의 요청은 이미 끝났다. 삼키되 남긴다.
            logger.exception("접근 로그 기록 실패 (%s %s)", method, path)

        global _next_prune
        now = time.monotonic()
        if now >= _next_prune:
            _next_prune = now + PRUNE_EVERY_SECONDS
            # **스레드에서.** 처음 도는 날은 수십만 줄일 수 있고, 그동안 이벤트 루프를 잡으면
            # 다른 요청이 전부 멈춘다. 응답은 이미 나갔다.
            await run_in_threadpool(_prune_quietly, factory)

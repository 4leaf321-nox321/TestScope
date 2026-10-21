"""허브 수신 작업 — **워커가 돈다.** 야간 1회 · 수동 실행 · 주간 전량 대조.

수신은 길다(타입 수십 · 행 수만). 요청 안에서 돌리면 화면이 그동안 멈추고, 끊기면 반쯤 받은
채로 남는다 — 그래서 작업 큐에 넣고 워커가 받는다. 화면은 현황을 다시 읽는다.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jobs import handlers, kinds, queue
from app.jobs.models import Job
from app.modules.hub import sync
from app.modules.hub.models import HubConnection
from app.shared.errors import Conflict

logger = logging.getLogger(__name__)

#: 야간 시각은 한국 시각으로 적는다 — 운영자가 그렇게 말한다.
KST = ZoneInfo("Asia/Seoul")


@handlers.handler(kinds.HUB_SYNC)
def run_sync(db: Session, payload: dict[str, Any]) -> None:
    try:
        sync.run(
            db,
            trigger=str(payload.get("trigger") or "manual"),
            full=bool(payload.get("full")),
            by=payload.get("by"),
        )
    except Conflict:
        # 이미 돌고 있다 — 이 작업은 할 일이 없다. 실패로 쌓으면 진짜 실패가 묻힌다.
        logger.info("허브 수신이 이미 실행 중이라 건너뜁니다.")


def slot_of(nightly_at: str, now: datetime) -> datetime:
    """`now` 직전(또는 같은) 야간 시각 — UTC 로."""
    try:
        hour, minute = (int(part) for part in nightly_at.split(":", 1))
    except ValueError:
        hour, minute = 1, 0
    local = now.astimezone(KST)
    slot = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if local < slot:
        slot -= timedelta(days=1)
    return slot.astimezone(UTC)


def enqueue_nightly(db: Session, now: datetime | None = None) -> bool:
    """야간 시각이 지났는데 그 뒤로 넣은 야간 작업이 없으면 넣는다. 넣었으면 True.

    **큐가 곧 상태다**(`schedule.py` 와 같은 판단) — 워커가 재시작해도 하루 한 번만 넣는다.
    7일 넘게 전량을 안 받았으면 이번 것이 전량 대조다(요청서 §5.7 8항).
    """
    now = now or datetime.now(UTC)
    conn = db.scalar(select(HubConnection).limit(1))
    if conn is None or not conn.enabled or not conn.base_url or not conn.token_sealed:
        return False
    slot = slot_of(conn.nightly_at, now)
    already = db.scalar(
        select(Job.id).where(
            Job.kind == kinds.HUB_SYNC,
            Job.created_at >= slot,
            Job.payload["trigger"].astext.in_(("schedule", "reconcile")),
        )
    )
    if already is not None:
        return False
    full = sync.due_full(db)
    queue.enqueue(
        db,
        kind=kinds.HUB_SYNC,
        payload={
            "trigger": "reconcile" if full else "schedule",
            "full": full,
            "by": "야간 자동",
        },
        max_attempts=1,
    )
    return True

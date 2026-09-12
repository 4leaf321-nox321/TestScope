"""알림 라우터 — 내게 온 것만."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.notifications import rules, services
from app.modules.notifications.models import Notification
from app.modules.notifications.schemas import NotificationOut, UnreadCountOut
from app.shared.auth import current_user
from app.shared.errors import NotFound

router = APIRouter(prefix="/notifications", tags=["notifications"])

#: 사람마다 마지막으로 교정을 훑은 시각. **프로세스 안에서만** 든다 — 재시작하면 한 번
#: 더 훑을 뿐이고, dedupe_key 가 같은 알림을 막는다.
_swept_at: dict[uuid.UUID, datetime] = {}
SWEEP_EVERY_SECONDS = 600


def _sweep(db: Session, user: User) -> None:
    """교정 만료 알림은 날이 되면 생기는 것이라 스케줄러 대신 **읽는 요청이 훑는다.**

    배지가 1분마다 부르므로 10분에 한 번만. 더 자주 해도 dedupe 가 막지만 조회는 돈다.
    """
    now = datetime.now(UTC)
    last = _swept_at.get(user.id)
    if last is not None and (now - last).total_seconds() < SWEEP_EVERY_SECONDS:
        return
    _swept_at[user.id] = now
    if rules.sweep_calibration(db, user):
        db.commit()


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = Query(default=False),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[NotificationOut]:
    _sweep(db, user)
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    rows = db.scalars(stmt.order_by(Notification.created_at.desc()).limit(100))
    return [NotificationOut.model_validate(row) for row in rows]


@router.get("/unread-count", response_model=UnreadCountOut)
def unread_count(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> UnreadCountOut:
    """상단 배지가 주기적으로 부른다. **접근 로그에서 뺀 경로다** — 안 빼면 표가
    이 한 줄로 가득 찬다."""
    _sweep(db, user)
    return UnreadCountOut(unread=services.unread_count(db, user.id))


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> NotificationOut:
    row = db.get(Notification, notification_id)
    if row is None or row.user_id != user.id:
        raise NotFound("TSC-NOTIFICATIONS-0001", "알림을 찾을 수 없습니다.")
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        db.commit()
        db.refresh(row)
    return NotificationOut.model_validate(row)


@router.post("/read-all", response_model=UnreadCountOut)
def mark_all_read(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> UnreadCountOut:
    now = datetime.now(UTC)
    for row in db.scalars(
        select(Notification).where(
            Notification.user_id == user.id, Notification.read_at.is_(None)
        )
    ):
        row.read_at = now
    db.commit()
    return UnreadCountOut(unread=0)

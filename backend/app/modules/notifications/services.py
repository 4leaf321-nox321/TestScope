"""알림을 만드는 **한 곳.**

도메인 코드가 Notification 을 직접 add 하지 않는다. 라우트마다 손으로 만들면
어떤 알림은 링크를 빼먹고, 그러면 사람은 그것을 보고 나서 무엇을 해야 할지
스스로 찾아야 한다.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.notifications.models import Notification

#: 알림의 종류. 화면이 아이콘을 고르는 근거이자, **나중에 사람이 끄고 켤 단위**다.
#: 언제 누구에게 가는지는 `rules.py` 가 정한다.
ACCOUNT_PENDING = "account.pending"
ACCOUNT_APPROVED = "account.approved"
CALIBRATION_DUE = "calibration.due"
EQUIPMENT_STATUS_CHANGED = "equipment.status_changed"


def notify(
    db: Session,
    *,
    user_id: uuid.UUID,
    kind: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
    dedupe_key: str | None = None,
) -> Notification | None:
    """알림 하나. **부르는 쪽이 커밋한다** — 그 변경과 같은 트랜잭션에 있어야
    "알림은 갔는데 변경은 롤백된" 상태가 안 생긴다.

    `dedupe_key` 가 있으면 같은 사람에게 같은 키로는 한 번만 — 이미 있으면 None.
    """
    if dedupe_key is not None:
        held = db.scalar(
            select(Notification.id).where(
                Notification.user_id == user_id, Notification.dedupe_key == dedupe_key
            )
        )
        if held is not None:
            return None
    row = Notification(
        user_id=user_id, kind=kind, title=title, body=body, link=link, dedupe_key=dedupe_key
    )
    db.add(row)
    # 같은 배치 안에서 같은 키를 두 번 만나도 위 조회가 보게 — 세션은 autoflush 를 안 한다.
    db.flush()
    return row


def unread_count(db: Session, user_id: uuid.UUID) -> int:
    rows = db.scalars(
        select(Notification.id).where(
            Notification.user_id == user_id, Notification.read_at.is_(None)
        )
    )
    return len(list(rows))

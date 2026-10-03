"""공지 라우터 — 읽기는 누구나, 쓰기는 시스템 관리자.

**초안 → 게시가 두 걸음이다.** 반쯤 쓴 공지를 저장해 둘 자리가 없으면 사람은 완성될 때까지
창을 열어 두거나(그러다 닫히면 날아간다) 메모장에 쓴다. 그리고 게시는 **따로 누른다** —
고치다가 저장 단추 하나로 전사에 나가면, 그 단추를 누를 때마다 망설이게 된다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.notices.models import Notice, NoticeRead
from app.modules.notices.schemas import NoticeOut, NoticeUpdateRequest, NoticeWriteRequest
from app.shared.auth import current_user, require_system_admin
from app.shared.errors import Conflict, NotFound

router = APIRouter(prefix="/notices", tags=["notices"])


def _out(db: Session, notice: Notice, user: User) -> NoticeOut:
    author = db.get(User, notice.author_id) if notice.author_id else None
    read = db.scalar(
        select(NoticeRead).where(
            NoticeRead.notice_id == notice.id, NoticeRead.user_id == user.id
        )
    )
    return NoticeOut(
        id=notice.id,
        title=notice.title,
        body=notice.body,
        level=notice.level,
        is_popup=notice.is_popup,
        published_at=notice.published_at,
        expires_at=notice.expires_at,
        author_name=author.display_name if author else None,
        read=read is not None,
        created_at=notice.created_at,
    )


@router.get("", response_model=list[NoticeOut])
def list_notices(
    include_drafts: bool = Query(default=False),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[NoticeOut]:
    stmt = select(Notice)
    if not include_drafts or not user.is_system_admin:
        # 초안은 쓴 사람만 본다. 반쯤 쓴 글이 전사에 보이면 그 자체가 사고다.
        stmt = stmt.where(Notice.published_at.is_not(None))
    rows = db.scalars(stmt.order_by(Notice.created_at.desc()).limit(100))
    return [_out(db, row, user) for row in rows]


@router.get("/popup", response_model=list[NoticeOut])
def popup_notices(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[NoticeOut]:
    """읽지 않은 팝업 공지. **스스로 뜬다** — 공지 화면에 들어가야만 보이면
    배포 없이 안내를 전한다는 목적이 성립하지 않는다."""
    now = datetime.now(UTC)
    read_ids = select(NoticeRead.notice_id).where(NoticeRead.user_id == user.id)
    rows = db.scalars(
        select(Notice)
        .where(
            Notice.is_popup.is_(True),
            Notice.published_at.is_not(None),
            Notice.id.not_in(read_ids),
            (Notice.expires_at.is_(None)) | (Notice.expires_at > now),
        )
        .order_by(Notice.created_at.desc())
    )
    return [_out(db, row, user) for row in rows]


@router.post("", response_model=NoticeOut, status_code=201)
def create_notice(
    payload: NoticeWriteRequest,
    admin: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> NoticeOut:
    notice = Notice(
        title=payload.title,
        body=payload.body,
        level=payload.level,
        is_popup=payload.is_popup,
        published_at=datetime.now(UTC) if payload.publish else None,
        expires_at=payload.expires_at,
        author_id=admin.id,
    )
    db.add(notice)
    db.commit()
    db.refresh(notice)
    return _out(db, notice, admin)


def _get(db: Session, notice_id: uuid.UUID) -> Notice:
    notice = db.get(Notice, notice_id)
    if notice is None:
        raise NotFound("TSC-NOTICES-0001", "공지를 찾을 수 없음.")
    return notice


@router.patch("/{notice_id}", response_model=NoticeOut)
def update_notice(
    notice_id: uuid.UUID,
    payload: NoticeUpdateRequest,
    admin: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> NoticeOut:
    """공지를 고친다 — 초안이든 게시된 것이든. **게시 여부는 안 바꾼다**(`/publish` 가 한다).

    게시된 팝업을 고쳐도 **이미 읽은 사람에게 다시 뜨지 않는다.** 크게 바뀌었으면 새 공지로
    내는 편이 맞다 — 읽음을 지우면 오타 하나 고칠 때마다 전사에 팝업이 다시 뜬다.
    """
    notice = _get(db, notice_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field in ("title", "body", "level", "is_popup") and value is None:
            continue  # 비울 수 없는 칸 — None 은 「안 바꿈」 이다.
        setattr(notice, field, value)
    db.commit()
    db.refresh(notice)
    return _out(db, notice, admin)


@router.post("/{notice_id}/publish", response_model=NoticeOut)
def publish_notice(
    notice_id: uuid.UUID,
    admin: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> NoticeOut:
    """초안을 **게시한다** — 그 순간부터 모두에게 보이고, 팝업이면 스스로 뜬다.

    이미 게시된 것은 409 다. 다시 누른다고 게시 시각을 지금으로 옮기면 「언제 알렸나」 가
    바뀐다 — 그 시각은 「공지했는데 왜 몰랐어」 에 답하는 근거다.
    """
    notice = _get(db, notice_id)
    if notice.published_at is not None:
        raise Conflict("TSC-NOTICES-0002", "이미 게시된 공지.")
    notice.published_at = datetime.now(UTC)
    db.commit()
    db.refresh(notice)
    return _out(db, notice, admin)


@router.post("/{notice_id}/read", response_model=NoticeOut)
def mark_read(
    notice_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> NoticeOut:
    notice = db.get(Notice, notice_id)
    if notice is None:
        raise NotFound("TSC-NOTICES-0001", "공지를 찾을 수 없음.")
    existing = db.scalar(
        select(NoticeRead).where(
            NoticeRead.notice_id == notice.id, NoticeRead.user_id == user.id
        )
    )
    if existing is None:
        db.add(NoticeRead(notice_id=notice.id, user_id=user.id))
        db.commit()
    return _out(db, notice, user)


@router.delete("/{notice_id}", status_code=204)
def delete_notice(
    notice_id: uuid.UUID,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> None:
    notice = db.get(Notice, notice_id)
    if notice is None:
        raise NotFound("TSC-NOTICES-0001", "공지를 찾을 수 없음.")
    db.delete(notice)
    db.commit()

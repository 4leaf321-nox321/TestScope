"""공지 라우터 — 읽기는 누구나, 쓰기는 시스템 관리자."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.notices.models import Notice, NoticeRead
from app.modules.notices.schemas import NoticeOut, NoticeWriteRequest
from app.shared.auth import current_user, require_system_admin
from app.shared.errors import NotFound

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


@router.post("/{notice_id}/read", response_model=NoticeOut)
def mark_read(
    notice_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> NoticeOut:
    notice = db.get(Notice, notice_id)
    if notice is None:
        raise NotFound("TAS-NOTICES-0001", "공지를 찾을 수 없습니다.")
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
        raise NotFound("TAS-NOTICES-0001", "공지를 찾을 수 없습니다.")
    db.delete(notice)
    db.commit()

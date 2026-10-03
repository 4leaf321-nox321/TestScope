"""VOC 라우터 — **게시판이고 절차다.**

접수는 로그인한 누구나. **목록도 누구나 본다** — 게시판이라 그렇다. 낸 사람과 관리자만
보게 두면 같은 문제를 여럿이 따로 내고, 무엇이 고쳐졌는지 낸 사람만 안다.

상태를 옮기는 것은 관리자와 낸 사람이 **각자 갈 수 있는 곳만**(`ADMIN_MOVES`·
`AUTHOR_MOVES`), 말을 보태는 것은 누구나.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.voc.models import (
    ADMIN_MOVES,
    AUTHOR_MOVES,
    NOTE_REQUIRED,
    VOC_STATUS_LABELS,
    VOC_STATUSES,
    VocEvent,
    VocItem,
)
from app.modules.voc.schemas import (
    VocCreateRequest,
    VocDetailOut,
    VocEventOut,
    VocItemOut,
    VocMoveRequest,
)
from app.shared.auth import current_user
from app.shared.errors import AppError, NotFound
from app.shared.pagination import MAX_LIMIT, Page, clamp_limit

router = APIRouter(prefix="/voc", tags=["voc"])

#: 「아직 끝나지 않은 것」 — 목록의 기본. 종료·반려는 쌓이기만 하므로 기본에서 뺀다.
OPEN_STATUSES = ("open", "accepted", "in_progress", "resolved")


def _names(db: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    """사람 이름을 **한 번에.** 줄마다 찾으면 목록 한 쪽이 질의 수십 번이 된다."""
    if not ids:
        return {}
    rows = db.execute(select(User.id, User.display_name).where(User.id.in_(ids))).all()
    return {one_id: name for one_id, name in rows}


def _moves(item: VocItem, user: User) -> list[str]:
    """**이 사람이** 지금 옮길 수 있는 곳. 관리자와 낸 사람의 길이 다르다."""
    out: list[str] = []
    if user.is_system_admin:
        out += list(ADMIN_MOVES.get(item.status, ()))
    if item.created_by_id == user.id:
        out += [one for one in AUTHOR_MOVES.get(item.status, ()) if one not in out]
    return out


def _out(item: VocItem, names: dict[uuid.UUID, str], comments: int) -> VocItemOut:
    return VocItemOut(
        id=item.id,
        seq=item.seq,
        title=item.title,
        status=item.status,
        status_label=VOC_STATUS_LABELS.get(item.status, item.status),
        created_by_name=names.get(item.created_by_id) if item.created_by_id else None,
        created_at=item.created_at,
        status_at=item.status_at,
        comment_count=comments,
    )


@router.get("", response_model=Page[VocItemOut])
def list_items(
    status: str | None = Query(default=None),
    mine: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Page[VocItemOut]:
    """VOC 목록. **기본은 아직 끝나지 않은 것**(종료·반려 제외).

    `status=all` 이면 전부, `status=<코드>` 면 그것만. `mine=true` 면 내가 낸 것만 —
    「내가 낸 그거 어떻게 됐지」 가 가장 흔한 물음이다.
    """
    stmt = select(VocItem)
    if status == "all":
        pass
    elif status:
        if status not in VOC_STATUSES:
            raise AppError(
                "TSC-VOC-0001",
                f"모르는 상태입니다: {status}",
                status=400,
                details={"statuses": list(VOC_STATUSES)},
            )
        stmt = stmt.where(VocItem.status == status)
    else:
        stmt = stmt.where(VocItem.status.in_(OPEN_STATUSES))
    if mine:
        stmt = stmt.where(VocItem.created_by_id == user.id)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    kept = clamp_limit(limit)
    rows = list(db.scalars(stmt.order_by(VocItem.seq.desc()).limit(kept).offset(offset)))
    # **말의 수도 한 번에 센다.** 줄마다 세면 쉰 줄짜리 목록이 질의 쉰 번이다.
    counted: dict[uuid.UUID, int] = {
        item_id: n
        for item_id, n in db.execute(
            select(VocEvent.item_id, func.count())
            .where(
                VocEvent.item_id.in_([one.id for one in rows]),
                VocEvent.from_status.is_not(None),
            )
            .group_by(VocEvent.item_id)
        ).all()
    }
    names = _names(db, {one.created_by_id for one in rows if one.created_by_id})
    return Page(
        items=[_out(one, names, counted.get(one.id, 0)) for one in rows],
        total=total,
        limit=kept,
        offset=offset,
    )


@router.post("", response_model=VocDetailOut, status_code=201)
def create_item(
    payload: VocCreateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> VocDetailOut:
    """한 건을 낸다.

    **등록도 이벤트로 남는다** — 흐름의 첫 줄이 비면 언제 낸 것인지가 카드 머리에만 있고,
    그러면 읽는 눈이 두 군데를 오간다.
    """
    item = VocItem(
        title=payload.title.strip(),
        body=payload.body.strip(),
        page_path=payload.page_path,
        status="open",
        created_by_id=user.id,
        status_by_id=user.id,
    )
    db.add(item)
    db.flush()
    db.add(VocEvent(item_id=item.id, by_id=user.id, from_status=None, to_status="open"))
    db.commit()
    db.refresh(item)
    return _detail(db, item, user)


@router.get("/{item_id}", response_model=VocDetailOut)
def get_item(
    item_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> VocDetailOut:
    return _detail(db, _get(db, item_id), user)


@router.post("/{item_id}/move", response_model=VocDetailOut)
def move_item(
    item_id: uuid.UUID,
    payload: VocMoveRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> VocDetailOut:
    """상태를 옮기거나 말을 보탠다.

    **지금 상태를 그대로 보내면 댓글이다** — 누구나 할 수 있다. 다른 상태로 보내는 것은
    관리자와 낸 사람이 각자 갈 수 있는 곳만.

    `resolved`·`rejected`·`open`(다시 열기)으로 옮길 때는 **말이 있어야 한다.** 「해결」 만
    찍힌 건은 무엇이 바뀌었는지 아무도 모르고, 이유 없는 「반려」 는 낸 사람이 같은 것을
    다시 낼 수밖에 없다.
    """
    item = _get(db, item_id)
    to = payload.to_status
    if to not in VOC_STATUSES:
        raise AppError(
            "TSC-VOC-0001",
            f"모르는 상태입니다: {to}",
            status=400,
            details={"statuses": list(VOC_STATUSES)},
        )
    note = (payload.note or "").strip() or None

    if to == item.status:
        # 댓글 — 상태는 그대로다. 빈 댓글은 안 받는다(아무 말도 안 하는 줄이 쌓인다).
        if note is None:
            raise AppError("TSC-VOC-0002", "할 말을 적어 주십시오.", status=400)
    else:
        allowed = _moves(item, user)
        if to not in allowed:
            raise AppError(
                "TSC-VOC-0003",
                f"「{VOC_STATUS_LABELS[item.status]}」 에서 "
                f"「{VOC_STATUS_LABELS[to]}」 로는 옮길 수 없습니다.",
                status=403,
                details={"can_move": allowed},
            )
        if to in NOTE_REQUIRED and note is None:
            raise AppError(
                "TSC-VOC-0004",
                f"「{VOC_STATUS_LABELS[to]}」 로 옮길 때는 무엇을 했는지"
                "(또는 왜 안 하는지) 적어야 합니다.",
                status=400,
            )

    db.add(
        VocEvent(
            item_id=item.id,
            by_id=user.id,
            from_status=item.status,
            to_status=to,
            note=note,
        )
    )
    if to != item.status:
        item.status = to
        item.status_at = datetime.now(UTC)
        item.status_by_id = user.id
    db.commit()
    db.refresh(item)
    return _detail(db, item, user)


def _get(db: Session, item_id: uuid.UUID) -> VocItem:
    item = db.get(VocItem, item_id)
    if item is None:
        raise NotFound("TSC-VOC-0005", "그 VOC 를 찾을 수 없습니다.")
    return item


def _detail(db: Session, item: VocItem, user: User) -> VocDetailOut:
    events = list(
        db.scalars(select(VocEvent).where(VocEvent.item_id == item.id).order_by(VocEvent.at))
    )
    names = _names(
        db,
        {one.by_id for one in events if one.by_id}
        | ({item.created_by_id} if item.created_by_id else set()),
    )
    comments = sum(1 for one in events if one.from_status is not None)
    base = _out(item, names, comments)
    can = _moves(item, user)
    return VocDetailOut(
        **base.model_dump(),
        body=item.body,
        page_path=item.page_path,
        events=[
            VocEventOut(
                id=one.id,
                at=one.at,
                by_name=names.get(one.by_id) if one.by_id else None,
                from_status=one.from_status,
                to_status=one.to_status,
                note=one.note,
            )
            for one in events
        ],
        can_move=can,
        note_required=[one for one in can if one in NOTE_REQUIRED],
    )

"""VOC 의 판정 — 라우터 밖에서도 쓰는 것만.

첨부(`attachments`)가 「이 VOC 에 자료를 붙여도 되나」 를 물으러 온다. 그 판정을 라우터에
두면 다른 모듈이 라우터를 부르게 된다(구조 규칙 위반) — 그래서 여기 둔다.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.voc.models import VocItem
from app.shared.errors import Forbidden, NotFound


def get_item(db: Session, item_id: uuid.UUID) -> VocItem:
    item = db.get(VocItem, item_id)
    if item is None:
        raise NotFound("TSC-VOC-0005", "해당 VOC를 찾을 수 없음.")
    return item


def can_attach(item: VocItem, user: User) -> bool:
    """**낸 사람과 시스템 관리자**가 자료(화면 갈무리·로그)를 붙이고 지운다.

    말은 누구나 보태지만(게시판이다) 자료는 그 건의 것이다 — 남이 붙인 그림을 지울 수
    있으면 낸 사람의 근거가 사라진다. 보는 것은 누구나다(목록이 그렇듯이).
    """
    return user.is_system_admin or item.created_by_id == user.id


def require_attachable(db: Session, user: User, item_id: uuid.UUID) -> VocItem:
    item = get_item(db, item_id)
    if not can_attach(item, user):
        raise Forbidden(
            "TSC-VOC-0006",
            "VOC 자료 첨부·삭제는 작성자와 시스템 관리자만 가능. 추가할 내용은 댓글로 등록.",
        )
    return item

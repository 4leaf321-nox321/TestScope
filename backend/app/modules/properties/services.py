"""물성 ↔ 시험 항목 연결의 조회·편집.

연결은 **전사 지식**이다 — 「인장으로 항복강도를 얻는다」 는 부서마다 다르지 않다.
그래서 고치는 것은 시스템 관리자다(시험 항목 축이 closed 인 것과 같은 이유).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.properties.models import TestItemProperty
from app.modules.properties.schemas import PropertyOut, TestItemPropertyOut
from app.modules.vocabulary.models import Vocabulary, VocabularyAlias, VocabularyTerm
from app.shared.errors import Conflict, Forbidden, NotFound

#: 물성 축의 slug. 반입·화면·검색이 이 이름으로 건다.
PROPERTY_AXIS = "property"
TEST_ITEM_AXIS = "test_item"


def _axis_id(db: Session, slug: str) -> uuid.UUID:
    axis = db.scalar(select(Vocabulary).where(Vocabulary.slug == slug))
    if axis is None:
        raise NotFound("TSC-PROPERTIES-0001", f"기준정보 축이 없습니다: {slug}")
    return axis.id


def _term_of(db: Session, term_id: uuid.UUID, slug: str, *, what: str) -> VocabularyTerm:
    """그 축의 값인지까지 본다. **다른 축의 id 가 들어오면 조용히 이상한 연결이 생긴다** —
    제조사 id 를 시험 항목 자리에 넣어도 FK 는 통과하기 때문이다."""
    term = db.get(VocabularyTerm, term_id)
    if term is None or term.vocabulary_id != _axis_id(db, slug):
        raise NotFound("TSC-PROPERTIES-0002", f"{what}을 찾을 수 없습니다.")
    return term


def _link_out(
    row: TestItemProperty, terms: dict[uuid.UUID, VocabularyTerm]
) -> TestItemPropertyOut:
    item = terms.get(row.test_item_term_id)
    prop = terms.get(row.property_term_id)
    return TestItemPropertyOut(
        id=row.id,
        test_item_term_id=row.test_item_term_id,
        test_item=item.value if item else "",
        property_term_id=row.property_term_id,
        property=prop.value if prop else "",
        property_code=prop.code if prop else None,
        status=row.status,
        source=row.source,
        note=row.note,
        confirmed_at=row.confirmed_at,
        created_at=row.created_at,
    )


def _terms_by_id(db: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, VocabularyTerm]:
    if not ids:
        return {}
    return {
        row.id: row
        for row in db.scalars(select(VocabularyTerm).where(VocabularyTerm.id.in_(ids)))
    }


def list_links(
    db: Session,
    *,
    test_item_term_id: uuid.UUID | None,
    property_term_id: uuid.UUID | None,
    status: str | None,
) -> list[TestItemPropertyOut]:
    stmt = select(TestItemProperty)
    if test_item_term_id is not None:
        stmt = stmt.where(TestItemProperty.test_item_term_id == test_item_term_id)
    if property_term_id is not None:
        stmt = stmt.where(TestItemProperty.property_term_id == property_term_id)
    if status is not None:
        stmt = stmt.where(TestItemProperty.status == status)
    rows = list(db.scalars(stmt.order_by(TestItemProperty.created_at)))
    terms = _terms_by_id(
        db, {one.test_item_term_id for one in rows} | {one.property_term_id for one in rows}
    )
    out = [_link_out(one, terms) for one in rows]
    out.sort(key=lambda one: (one.test_item, one.property))
    return out


def list_properties(
    db: Session, *, query: str | None, domain: str | None, include_unlinked: bool
) -> list[PropertyOut]:
    """물성 전부와 각각을 내는 시험 항목. **한 번에 센다** — 271 물성마다 연결을
    따로 조회하면 목록 한 장이 300 번 왕복한다."""
    axis_id = _axis_id(db, PROPERTY_AXIS)
    stmt = select(VocabularyTerm).where(
        VocabularyTerm.vocabulary_id == axis_id, VocabularyTerm.status == "active"
    )
    props = list(db.scalars(stmt))
    if domain:
        props = [one for one in props if (one.code or "").split(".")[0] == domain]

    links = list(
        db.scalars(
            select(TestItemProperty).where(
                TestItemProperty.property_term_id.in_([one.id for one in props])
            )
        )
    )
    by_property: dict[uuid.UUID, list[TestItemProperty]] = {}
    for one in links:
        by_property.setdefault(one.property_term_id, []).append(one)
    terms = _terms_by_id(db, {one.test_item_term_id for one in links}) | {
        one.id: one for one in props
    }
    aliases: dict[uuid.UUID, list[str]] = {}
    for term_id, value in db.execute(
        select(VocabularyAlias.term_id, VocabularyAlias.value).where(
            VocabularyAlias.term_id.in_([one.id for one in props]),
            VocabularyAlias.is_active.is_(True),
        )
    ):
        aliases.setdefault(term_id, []).append(value)

    needle = (query or "").strip().lower()
    out: list[PropertyOut] = []
    for prop in props:
        names = [prop.value, prop.code or "", *aliases.get(prop.id, [])]
        if needle and not any(needle in one.lower() for one in names):
            continue
        mine = by_property.get(prop.id, [])
        if not include_unlinked and not mine:
            continue
        attrs: dict[str, Any] = prop.attributes or {}
        out.append(
            PropertyOut(
                id=prop.id,
                value=prop.value,
                code=prop.code,
                domain=(prop.code or "").split(".")[0] or None,
                symbol=attrs.get("symbol"),
                si_unit=attrs.get("si_unit"),
                aliases=sorted(aliases.get(prop.id, [])),
                links=sorted(
                    (_link_out(one, terms) for one in mine), key=lambda one: one.test_item
                ),
            )
        )
    out.sort(key=lambda one: (one.domain or "", one.value))
    return out


def test_item_ids_for_property(db: Session, property_term_id: uuid.UUID) -> list[uuid.UUID]:
    """검색이 쓴다 — 물성으로 물으면 그것을 내는 시험 항목 전부로 펼친다.
    제안 상태도 포함한다: 아직 확인 안 된 연결을 빼면 검색이 「없다」 고 답하고, 그 답은
    「아직 안 봤다」 와 다르다(ADR 0003)."""
    return list(
        db.scalars(
            select(TestItemProperty.test_item_term_id).where(
                TestItemProperty.property_term_id == property_term_id
            )
        )
    )


def _require_admin(user: User) -> None:
    if not user.is_system_admin:
        raise Forbidden(
            "TSC-PROPERTIES-0003",
            "물성과 시험 항목의 연결은 전사 지식이라 시스템 관리자만 고칩니다.",
        )


def create_link(db: Session, user: User, payload: dict[str, Any]) -> TestItemProperty:
    _require_admin(user)
    item = _term_of(db, payload["test_item_term_id"], TEST_ITEM_AXIS, what="시험 항목")
    prop = _term_of(db, payload["property_term_id"], PROPERTY_AXIS, what="물성")
    clash = db.scalar(
        select(TestItemProperty).where(
            TestItemProperty.test_item_term_id == item.id,
            TestItemProperty.property_term_id == prop.id,
        )
    )
    if clash is not None:
        raise Conflict(
            "TSC-PROPERTIES-0004", f"이미 이어져 있습니다: {item.value} → {prop.value}"
        )
    # 사람이 손으로 더한 것은 그 자체가 확인이다 — 제안으로 두면 자기가 만든 것을
    # 자기가 다시 확인하는 헛걸음이 생긴다.
    now = datetime.now(UTC)
    row = TestItemProperty(
        test_item_term_id=item.id,
        property_term_id=prop.id,
        status="confirmed",
        source="manual",
        note=payload.get("note"),
        created_by_id=user.id,
        confirmed_by_id=user.id,
        confirmed_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_link(db: Session, link_id: uuid.UUID) -> TestItemProperty:
    row = db.get(TestItemProperty, link_id)
    if row is None:
        raise NotFound("TSC-PROPERTIES-0005", "연결을 찾을 수 없습니다.")
    return row


def update_link(
    db: Session, user: User, link_id: uuid.UUID, changes: dict[str, Any]
) -> TestItemProperty:
    _require_admin(user)
    row = get_link(db, link_id)
    if "note" in changes:
        row.note = changes["note"]
    if "status" in changes and changes["status"] is not None:
        status = changes["status"]
        if status == "confirmed" and row.status != "confirmed":
            row.confirmed_by_id = user.id
            row.confirmed_at = datetime.now(UTC)
        if status == "suggested":
            row.confirmed_by_id = None
            row.confirmed_at = None
        row.status = status
    db.commit()
    db.refresh(row)
    return row


def delete_link(db: Session, user: User, link_id: uuid.UUID) -> None:
    _require_admin(user)
    row = get_link(db, link_id)
    db.delete(row)
    db.commit()


def link_out(db: Session, row: TestItemProperty) -> TestItemPropertyOut:
    return _link_out(row, _terms_by_id(db, {row.test_item_term_id, row.property_term_id}))

"""시험 · 장비에 **허브 기준정보를 잇는 칸** — 「값 고르기」(kind=term) 칸 중 허브 축을
가리키는 것.

운영에서는 이 연결을 MCP 로 한다(2026-10-21 사용자 결정). 두 가지가 그것을 쉽게 한다:

- **허브 칸만 보내면 그 칸만 바뀐다.** 보통 속성 쓰기는 「통째로 갈아 끼우기」 라, 기계가 허브
  칸
  하나를 붙이려면 그 시험의 다른 값을 전부 다시 보내야 했다 — 하나 빠뜨리면 그 값이 지워진다.
  기계 자격이 허브 칸만 보내면 다른 값은 건드리지 않는다.
- **확정된 신뢰성 시험에도 된다.** 확정은 그 시점 내용의 보증이라 기계 자격의 수정을 막는데(ADR
  0009), 허브 기준정보를 잇는 것은 시험 내용이 아니라 **분류 표시**다 — 사용자 결정으로 이 칸만
  예외다. 무엇을 바꿨는지는 감사(`reliability_test.hub_linked`)에 남는다.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.attributes.models import AttributeDefinition, AttributeValue
from app.modules.attributes.schemas import AttributeValueIn
from app.modules.vocabulary.models import Vocabulary, VocabularyTerm
from app.shared.errors import AppError

_COLUMN = {
    "reliability_test": AttributeValue.reliability_test_id,
    "equipment": AttributeValue.equipment_id,
}


def hub_definitions(db: Session, target: str) -> dict[uuid.UUID, AttributeDefinition]:
    """이 대상의 허브 칸 — 허브 축을 가리키는 「값 고르기」 칸."""
    return {
        row.id: row
        for row in db.scalars(
            select(AttributeDefinition)
            .join(Vocabulary, Vocabulary.id == AttributeDefinition.vocabulary_id)
            .where(
                AttributeDefinition.target == target,
                AttributeDefinition.kind == "term",
                Vocabulary.hub_type_slug.is_not(None),
            )
        )
    }


def is_hub_patch(db: Session, target: str, items: list[AttributeValueIn]) -> bool:
    """보낸 값이 **전부 허브 칸**인가. 하나라도 아니면 보통의 통째 쓰기다."""
    if not items or target not in _COLUMN:
        return False
    hub = hub_definitions(db, target)
    return all(item.definition_id is not None and item.definition_id in hub for item in items)


def patch(
    db: Session,
    *,
    target: str,
    object_id: uuid.UUID,
    items: list[AttributeValueIn],
    revision_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """허브 칸만 바꾼다 — 다른 값은 그대로. 값(`term_id`)을 비우면 그 칸을 뗀다.

    돌려주는 것은 감사에 남길 {칸 이름: {before, after}}.
    """
    column = _COLUMN[target]
    hub = hub_definitions(db, target)
    changes: dict[str, Any] = {}
    for item in items:
        assert item.definition_id is not None
        definition = hub[item.definition_id]
        after: VocabularyTerm | None = None
        if item.term_id is not None:
            after = db.get(VocabularyTerm, item.term_id)
            if after is None or after.vocabulary_id != definition.vocabulary_id:
                raise AppError(
                    "TSC-HUB-0006",
                    f"{definition.label}: 이 칸의 축(허브 기준정보)의 값이 아님.",
                    status=422,
                )
        olds = list(
            db.scalars(
                select(AttributeValue).where(
                    column == object_id,
                    AttributeValue.definition_id == definition.id,
                    AttributeValue.set_label.is_not_distinct_from(item.set_label or None),
                    AttributeValue.step_order.is_not_distinct_from(item.step_order),
                    AttributeValue.document_revision_id.is_not_distinct_from(revision_id),
                )
            )
        )
        before_ids = {old.term_id for old in olds if old.is_current}
        if before_ids == ({after.id} if after else set()):
            continue
        before = [
            term.value
            for term_id in before_ids
            if term_id and (term := db.get(VocabularyTerm, term_id)) is not None
        ]
        for old in olds:
            db.delete(old)
        db.flush()
        if after is not None:
            value = AttributeValue(
                definition_id=definition.id,
                term_id=after.id,
                document_revision_id=revision_id,
                set_label=item.set_label or None,
                step_order=item.step_order,
                note=item.note,
                is_current=True,
            )
            setattr(value, column.key, object_id)
            db.add(value)
        changes[definition.label] = {
            "before": ", ".join(before) or None,
            "after": after.value if after else None,
        }
    db.flush()
    return changes

"""항목 정의·값 — 정의는 시스템 관리자가, 초안은 값을 적는 사람이 만든다.

값을 붙이는 쪽(신뢰성 시험 · 보유 장비)의 권한 판정은 **그쪽 서비스**가 한다. 여기는 그 뒤에
불려서 값의 형만 본다.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.attributes.models import (
    ATTRIBUTE_KINDS,
    ATTRIBUTE_STATUSES,
    ATTRIBUTE_TARGETS,
    AttributeDefinition,
    AttributeValue,
)
from app.modules.attributes.schemas import (
    AttributeDefinitionOut,
    AttributeValueIn,
    AttributeValueOut,
)
from app.modules.methods.models import TestMethod
from app.modules.vocabulary.models import ConditionKey, Vocabulary, VocabularyTerm
from app.shared.attribute_text import display_attribute
from app.shared.errors import AppError, Conflict, NotFound
from app.shared.text import clean

#: 어느 대상의 값이 어느 열에 붙나. 새 대상은 여기 한 줄.
_TARGET_COLUMN = {
    "reliability_test": AttributeValue.reliability_test_id,
    "equipment": AttributeValue.equipment_id,
    "series": AttributeValue.series_id,
    "method": AttributeValue.method_id,
}

#: 종류마다 수치 칸을 쓰는 것. 단위는 이들만 뜻이 있다.
_NUMERIC_KINDS = {"number", "range", "condition"}


# ---------------------------------------------------------------- 정의


def _value_counts(db: Session, definition_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not definition_ids:
        return {}
    rows = db.execute(
        select(AttributeValue.definition_id, func.count())
        .where(AttributeValue.definition_id.in_(definition_ids))
        .group_by(AttributeValue.definition_id)
    ).all()
    return {definition_id: int(count) for definition_id, count in rows}


def _definition_outs(
    db: Session, rows: list[AttributeDefinition]
) -> list[AttributeDefinitionOut]:
    if not rows:
        return []
    counts = _value_counts(db, [r.id for r in rows])
    condition_ids = {r.condition_key_id for r in rows if r.condition_key_id}
    conditions = (
        {
            c.id: c.label
            for c in db.scalars(select(ConditionKey).where(ConditionKey.id.in_(condition_ids)))
        }
        if condition_ids
        else {}
    )
    vocabulary_ids = {r.vocabulary_id for r in rows if r.vocabulary_id}
    vocabularies = (
        {
            v.id: v.slug
            for v in db.scalars(select(Vocabulary).where(Vocabulary.id.in_(vocabulary_ids)))
        }
        if vocabulary_ids
        else {}
    )
    return [
        AttributeDefinitionOut(
            id=r.id,
            target=r.target,
            key=r.key,
            label=r.label,
            kind=r.kind,
            unit=r.unit,
            choices=list(r.choices or []),
            condition_key_id=r.condition_key_id,
            condition_key_label=conditions.get(r.condition_key_id)
            if r.condition_key_id
            else None,
            vocabulary_id=r.vocabulary_id,
            vocabulary_slug=vocabularies.get(r.vocabulary_id) if r.vocabulary_id else None,
            status=r.status,
            is_required=r.is_required,
            help=r.help,
            sort_order=r.sort_order,
            is_active=r.is_active,
            merged_into_id=r.merged_into_id,
            value_count=counts.get(r.id, 0),
            created_at=r.created_at,
        )
        for r in rows
    ]


def definition_out(db: Session, row: AttributeDefinition) -> AttributeDefinitionOut:
    return _definition_outs(db, [row])[0]


def list_definitions(
    db: Session, *, target: str, include_inactive: bool = False
) -> list[AttributeDefinitionOut]:
    """정식이 먼저, 그 다음 초안. 같은 층 안에서는 sort_order → 이름."""
    _check_target(target)
    stmt = select(AttributeDefinition).where(AttributeDefinition.target == target)
    if not include_inactive:
        stmt = stmt.where(AttributeDefinition.is_active.is_(True))
    rows = list(
        db.scalars(
            stmt.order_by(
                AttributeDefinition.status.desc(),  # standard > draft
                AttributeDefinition.sort_order,
                AttributeDefinition.label,
            )
        )
    )
    return _definition_outs(db, rows)


def get_definition(db: Session, definition_id: uuid.UUID) -> AttributeDefinition:
    row = db.get(AttributeDefinition, definition_id)
    if row is None:
        raise NotFound("TSC-ATTR-0001", "속성 정의를 찾을 수 없습니다.")
    return row


def _check_target(target: str) -> None:
    if target not in ATTRIBUTE_TARGETS:
        raise AppError("TSC-ATTR-0002", f"모르는 대상입니다: {target}")


def _check_kind(kind: str) -> None:
    if kind not in ATTRIBUTE_KINDS:
        raise AppError("TSC-ATTR-0003", f"모르는 종류입니다: {kind}")


def _find_by_label(
    db: Session, target: str, label: str, *, except_id: uuid.UUID | None = None
) -> AttributeDefinition | None:
    """살아 있는 같은 이름 — 대소문자·앞뒤 공백 무시. 「온도」 와 「온도 」 가 둘이 되지
    않게."""
    stmt = select(AttributeDefinition).where(
        AttributeDefinition.target == target,
        AttributeDefinition.is_active.is_(True),
        func.lower(AttributeDefinition.label) == label.lower(),
    )
    if except_id is not None:
        stmt = stmt.where(AttributeDefinition.id != except_id)
    return db.scalar(stmt)


def _check_axes(db: Session, kind: str, payload: dict[str, Any]) -> None:
    """종류가 요구하는 축이 있나. condition 은 조건 축, term 은 기준정보 축."""
    if kind == "condition":
        key_id = payload.get("condition_key_id")
        if key_id is None or db.get(ConditionKey, key_id) is None:
            raise AppError("TSC-ATTR-0004", "조건 종류는 검색 조건 축을 골라야 합니다.")
    if kind == "term":
        vocabulary_id = payload.get("vocabulary_id")
        if vocabulary_id is None or db.get(Vocabulary, vocabulary_id) is None:
            raise AppError("TSC-ATTR-0004", "기준정보 종류는 어느 축인지 골라야 합니다.")
    if kind == "choice" and not [c for c in payload.get("choices") or [] if clean(c)]:
        raise AppError("TSC-ATTR-0004", "선택 종류는 선택지를 하나 이상 적어야 합니다.")


def _auto_key() -> str:
    return f"draft-{uuid.uuid4().hex[:8]}"


#: key 에 쓸 수 있는 글자. **주소에 그대로 실리는 이름**이라(`?attr=invest_year>=2020`)
#: 한글·공백·연산자 글자가 들어가면 그 속성은 영영 못 거른다 — 적어 두고 못 찾는 칸이 된다.
_KEY_SHAPE = re.compile(r"^[A-Za-z0-9_.-]{1,60}$")


def _check_key_shape(key: str) -> None:
    if _KEY_SHAPE.match(key) is None:
        raise AppError(
            "TSC-ATTR-0009",
            f"key 「{key}」 는 못 씁니다 — 영문·숫자·_ . - 만 됩니다(거르기 주소에 실립니다).",
        )


def _check_key_free(db: Session, key: str, *, except_id: uuid.UUID | None) -> None:
    stmt = select(AttributeDefinition).where(AttributeDefinition.key == key)
    if except_id is not None:
        stmt = stmt.where(AttributeDefinition.id != except_id)
    if db.scalar(stmt) is not None:
        raise Conflict("TSC-ATTR-0005", f"같은 key 의 속성이 있습니다: {key}")


def create_definition(db: Session, user: User, payload: dict[str, Any]) -> AttributeDefinition:
    """시스템 관리자의 등록. 조사 중인 후보를 **미리 초안으로** 넣어 두는 데도 쓴다 — 그러면
    부서가 처음 적을 때부터 목록에 뜬다."""
    target = str(payload["target"])
    _check_target(target)
    kind = str(payload.get("kind") or "text")
    _check_kind(kind)
    status = str(payload.get("status") or "standard")
    if status not in ATTRIBUTE_STATUSES:
        raise AppError("TSC-ATTR-0003", f"모르는 상태입니다: {status}")
    label = clean(str(payload["label"]))
    if not label:
        raise AppError("TSC-ATTR-0006", "이름을 적어 주세요.")
    if _find_by_label(db, target, label) is not None:
        raise Conflict("TSC-ATTR-0007", f"같은 이름의 속성이 있습니다: {label}")
    _check_axes(db, kind, payload)
    key = clean(str(payload.get("key") or "")) or _auto_key()
    _check_key_shape(key)
    _check_key_free(db, key, except_id=None)
    row = AttributeDefinition(
        target=target,
        key=key,
        label=label,
        kind=kind,
        unit=clean(str(payload.get("unit") or "")),
        choices=[clean(c) for c in payload.get("choices") or [] if clean(c)],
        condition_key_id=payload.get("condition_key_id") if kind == "condition" else None,
        vocabulary_id=payload.get("vocabulary_id") if kind == "term" else None,
        status=status,
        is_required=bool(payload.get("is_required", False)),
        help=payload.get("help"),
        sort_order=int(payload.get("sort_order") or 0),
        created_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_definition(
    db: Session, definition_id: uuid.UUID, changes: dict[str, Any]
) -> AttributeDefinition:
    """`changes` 는 `exclude_unset`. 정식으로 올리기는 `status="standard"` 하나로 한다.

    종류는 **값이 없을 때만** 바뀐다 — 문장으로 적힌 값 열 개를 수치 항목으로 바꾸면 그 열 개는
    읽을 수 없는 값이 된다. 그때는 새 항목을 만들고 합치는 쪽이 정직하다.
    """
    row = get_definition(db, definition_id)
    if "label" in changes:
        label = clean(str(changes["label"]))
        if not label:
            raise AppError("TSC-ATTR-0006", "이름을 적어 주세요.")
        if _find_by_label(db, row.target, label, except_id=row.id) is not None:
            raise Conflict("TSC-ATTR-0007", f"같은 이름의 속성이 있습니다: {label}")
        row.label = label
    if changes.get("key"):
        key = clean(str(changes["key"]))
        _check_key_shape(key)
        _check_key_free(db, key, except_id=row.id)
        row.key = key
    if "kind" in changes and changes["kind"] != row.kind:
        kind = str(changes["kind"])
        _check_kind(kind)
        if _value_counts(db, [row.id]).get(row.id, 0) > 0:
            raise Conflict(
                "TSC-ATTR-0008",
                "값이 적힌 속성의 종류는 바꿀 수 없습니다. 새 속성을 만들고 합치세요.",
            )
        row.kind = kind
    if "unit" in changes:
        row.unit = clean(str(changes["unit"] or ""))
    if "choices" in changes and changes["choices"] is not None:
        row.choices = [clean(c) for c in changes["choices"] if clean(c)]
    if "condition_key_id" in changes:
        row.condition_key_id = changes["condition_key_id"]
    if "vocabulary_id" in changes:
        row.vocabulary_id = changes["vocabulary_id"]
    if changes.get("status"):
        status = str(changes["status"])
        if status not in ATTRIBUTE_STATUSES:
            raise AppError("TSC-ATTR-0003", f"모르는 상태입니다: {status}")
        row.status = status
    if "is_required" in changes and changes["is_required"] is not None:
        row.is_required = bool(changes["is_required"])
    if "help" in changes:
        row.help = changes["help"]
    if "sort_order" in changes and changes["sort_order"] is not None:
        row.sort_order = int(changes["sort_order"])
    if "is_active" in changes and changes["is_active"] is not None:
        row.is_active = bool(changes["is_active"])
    # 정식으로 올리는 순간 축이 필요한 종류는 축이 있어야 한다.
    if row.status == "standard":
        _check_axes(
            db,
            row.kind,
            {
                "condition_key_id": row.condition_key_id,
                "vocabulary_id": row.vocabulary_id,
                "choices": row.choices,
            },
        )
    db.commit()
    db.refresh(row)
    return row


def delete_definition(db: Session, definition_id: uuid.UUID) -> None:
    """**값이 하나도 없을 때만** 지운다 — 오타로 생긴 초안을 치우는 길.

    값이 있으면 409 — 지우면 그 값들이 무엇이었는지 알 수 없어진다. 그때는 끄거나 합친다.
    다른 항목이 「여기로 합쳐졌다」 고 가리키는 것도 못 지운다(「어디 갔어」 의 답이 사라진다).
    """
    row = get_definition(db, definition_id)
    if _value_counts(db, [row.id]).get(row.id, 0) > 0:
        raise Conflict(
            "TSC-ATTR-0013", "값이 적힌 속성은 지울 수 없습니다. 끄거나 다른 속성에 합치세요."
        )
    pointing = db.scalar(
        select(AttributeDefinition.id).where(AttributeDefinition.merged_into_id == row.id)
    )
    if pointing is not None:
        raise Conflict(
            "TSC-ATTR-0013", "다른 속성이 이 속성으로 합쳐져 있어 지울 수 없습니다."
        )
    db.delete(row)
    db.commit()


def merge_into(db: Session, source_id: uuid.UUID, target_id: uuid.UUID) -> AttributeDefinition:
    """이름만 다른 항목 둘을 하나로 — 값이 남는 쪽으로 옮겨 가고 원래 항목은 꺼진다.

    종류가 같아야 한다. 문장 초안을 수치 항목에 합치면 값이 안 읽히기 때문이다. 같은 대상에
    두 값이 다 있으면 남는 쪽 값을 두고 옮기는 쪽을 버린다 — 정식(또는 남기려는 쪽)이 더
    낫다고 본다. 단위는 값에 있으므로 환산하지 않고 옮긴다.
    """
    source = get_definition(db, source_id)
    target = get_definition(db, target_id)
    if source.id == target.id:
        raise AppError("TSC-ATTR-0009", "같은 속성입니다.")
    if source.target != target.target:
        raise AppError("TSC-ATTR-0009", "붙는 대상이 다른 속성은 합칠 수 없습니다.")
    if source.kind != target.kind:
        raise Conflict(
            "TSC-ATTR-0009",
            f"종류가 다른 속성은 합칠 수 없습니다: {source.kind} → {target.kind}",
        )
    if not target.is_active:
        raise AppError("TSC-ATTR-0009", "꺼진 속성으로는 합칠 수 없습니다.")
    column = _TARGET_COLUMN[source.target]
    held = {
        object_id
        for object_id in db.scalars(
            select(column).where(AttributeValue.definition_id == target.id)
        )
    }
    for value in db.scalars(
        select(AttributeValue).where(AttributeValue.definition_id == source.id)
    ):
        object_id = getattr(value, column.key)
        if object_id in held:
            db.delete(value)
        else:
            value.definition_id = target.id
            held.add(object_id)
    source.is_active = False
    source.merged_into_id = target.id
    db.commit()
    db.refresh(target)
    return target


# ---------------------------------------------------------------- 값


def _ensure_draft(
    db: Session, user: User | None, target: str, label: str, kind: str
) -> AttributeDefinition:
    """같은 이름이 살아 있으면 그것, 없으면 초안을 만든다. 종류는 처음 적은 사람이 정한다."""
    existing = _find_by_label(db, target, label)
    if existing is not None:
        return existing
    _check_kind(kind)
    if kind in ("condition", "term", "choice"):
        # 축·선택지가 필요한 종류는 초안으로 못 만든다 — 관리자가 정의부터 만든다.
        raise AppError("TSC-ATTR-0010", f"{kind} 종류의 속성은 관리자가 먼저 정의합니다.")
    row = AttributeDefinition(
        target=target,
        key=_auto_key(),
        label=label,
        kind=kind,
        status="draft",
        created_by=user.id if user else None,
    )
    db.add(row)
    db.flush()
    return row


def _check_value_shape(
    db: Session, definition: AttributeDefinition, item: AttributeValueIn
) -> None:
    """종류가 요구하는 칸이 채워졌나. 비어 있는 값은 보내지 말고 빼는 것이 규칙이다."""
    kind = definition.kind
    label = definition.label
    if kind == "number" and item.num_value is None:
        raise AppError("TSC-ATTR-0011", f"「{label}」 은 수치가 필요합니다.")
    if kind in ("range", "condition") and item.num_min is None and item.num_max is None:
        raise AppError("TSC-ATTR-0011", f"「{label}」 은 최소나 최대 중 하나는 필요합니다.")
    if (
        kind in ("range", "condition")
        and item.num_min is not None
        and item.num_max is not None
        and item.num_min > item.num_max
    ):
        raise AppError("TSC-ATTR-0011", f"「{label}」 의 최소가 최대보다 큽니다.")
    if kind == "text" and not clean(item.text_value or ""):
        raise AppError("TSC-ATTR-0011", f"「{label}」 은 글이 필요합니다.")
    if kind == "choice":
        picked = clean(item.text_value or "")
        if picked not in (definition.choices or []):
            raise AppError(
                "TSC-ATTR-0011",
                f"「{label}」 은 선택지 중 하나여야 합니다.",
                details={"choices": list(definition.choices or [])},
            )
    if kind == "boolean" and item.bool_value is None:
        raise AppError("TSC-ATTR-0011", f"「{label}」 은 있음/없음이 필요합니다.")
    if kind == "date" and item.date_value is None:
        raise AppError("TSC-ATTR-0011", f"「{label}」 은 날짜가 필요합니다.")
    if kind == "term":
        term = db.get(VocabularyTerm, item.term_id) if item.term_id else None
        if term is None or term.vocabulary_id != definition.vocabulary_id:
            raise AppError(
                "TSC-ATTR-0011", f"「{label}」 은 그 축의 기준정보 값이어야 합니다."
            )
    if kind == "method":
        method = db.get(TestMethod, item.method_id) if item.method_id else None
        if method is None or method.deleted_at is not None:
            raise AppError("TSC-ATTR-0011", f"「{label}」 은 있는 규격이어야 합니다.")


def set_values(
    db: Session,
    user: User | None,
    *,
    target: str,
    object_id: uuid.UUID,
    items: list[AttributeValueIn],
) -> None:
    """대상 하나의 값을 **통째로** 바꾼다. 커밋은 부르는 쪽이 한다.

    같은 항목이 두 번 오면 뒤의 것이 남는다. 새 이름은 초안을 만든다.
    """
    _check_target(target)
    column = _TARGET_COLUMN[target]
    for old in db.scalars(select(AttributeValue).where(column == object_id)):
        db.delete(old)
    db.flush()
    seen: dict[uuid.UUID, AttributeValue] = {}
    for item in items:
        if item.definition_id is not None:
            definition = get_definition(db, item.definition_id)
            if definition.target != target:
                raise AppError(
                    "TSC-ATTR-0012", f"「{definition.label}」 은 이 대상의 속성이 아닙니다."
                )
            if not definition.is_active:
                raise AppError("TSC-ATTR-0012", f"「{definition.label}」 은 꺼진 속성입니다.")
        else:
            label = clean(item.new_label or "")
            if not label:
                raise AppError("TSC-ATTR-0006", "속성 이름을 적어 주세요.")
            definition = _ensure_draft(db, user, target, label, item.new_kind)
        _check_value_shape(db, definition, item)
        numeric = definition.kind in _NUMERIC_KINDS
        value = AttributeValue(
            definition_id=definition.id,
            num_value=item.num_value if definition.kind == "number" else None,
            num_min=item.num_min if definition.kind in ("range", "condition") else None,
            num_max=item.num_max if definition.kind in ("range", "condition") else None,
            unit=clean(item.unit or "") if numeric else "",
            text_value=clean(item.text_value or "")
            if definition.kind in ("text", "choice")
            else None,
            bool_value=item.bool_value if definition.kind == "boolean" else None,
            date_value=item.date_value if definition.kind == "date" else None,
            term_id=item.term_id if definition.kind == "term" else None,
            ref_method_id=item.method_id if definition.kind == "method" else None,
            note=clean(item.note or "") or None,
        )
        setattr(value, column.key, object_id)
        seen[definition.id] = value
    for value in seen.values():
        db.add(value)
    db.flush()


def display_of(
    value: AttributeValue,
    definition: AttributeDefinition,
    *,
    term_value: str | None,
    method_code: str | None,
) -> str:
    """사람이 읽는 한 줄. 화면과 MCP 와 색인 카드가 같은 글자를 쓰게 서버가 만든다."""
    return display_attribute(
        definition.kind,
        num_value=value.num_value,
        num_min=value.num_min,
        num_max=value.num_max,
        unit=value.unit,
        text_value=value.text_value,
        bool_value=value.bool_value,
        date_value=value.date_value,
        term_value=term_value,
        method_code=method_code,
    )


def values_of(
    db: Session, *, target: str, object_ids: list[uuid.UUID], include_draft: bool = True
) -> dict[uuid.UUID, list[AttributeValueOut]]:
    """여러 대상의 값을 질의 몇 번으로. 정식이 먼저, 초안이 뒤."""
    _check_target(target)
    out: dict[uuid.UUID, list[AttributeValueOut]] = {one: [] for one in object_ids}
    if not object_ids:
        return out
    column = _TARGET_COLUMN[target]
    stmt = (
        select(AttributeValue, AttributeDefinition)
        .join(AttributeDefinition, AttributeDefinition.id == AttributeValue.definition_id)
        .where(column.in_(object_ids))
        .order_by(
            AttributeDefinition.status.desc(),
            AttributeDefinition.sort_order,
            AttributeDefinition.label,
        )
    )
    if not include_draft:
        stmt = stmt.where(AttributeDefinition.status == "standard")
    pairs = db.execute(stmt).all()
    term_ids = {v.term_id for v, _ in pairs if v.term_id}
    terms = (
        {
            t.id: t.value
            for t in db.scalars(select(VocabularyTerm).where(VocabularyTerm.id.in_(term_ids)))
        }
        if term_ids
        else {}
    )
    method_ids = {v.ref_method_id for v, _ in pairs if v.ref_method_id}
    methods = (
        {
            m.id: m.code
            for m in db.scalars(select(TestMethod).where(TestMethod.id.in_(method_ids)))
        }
        if method_ids
        else {}
    )
    for value, definition in pairs:
        term_value = terms.get(value.term_id) if value.term_id else None
        method_code = methods.get(value.ref_method_id) if value.ref_method_id else None
        out[getattr(value, column.key)].append(
            AttributeValueOut(
                definition_id=definition.id,
                label=definition.label,
                kind=definition.kind,
                status=definition.status,
                unit=value.unit,
                num_value=value.num_value,
                num_min=value.num_min,
                num_max=value.num_max,
                text_value=value.text_value,
                bool_value=value.bool_value,
                date_value=value.date_value,
                term_id=value.term_id,
                term_value=term_value,
                method_id=value.ref_method_id,
                method_code=method_code,
                note=value.note,
                display=display_of(
                    value, definition, term_value=term_value, method_code=method_code
                ),
            )
        )
    return out

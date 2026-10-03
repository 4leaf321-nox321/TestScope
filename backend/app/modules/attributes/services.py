"""항목 정의·값 — 정의는 시스템 관리자가, 초안은 값을 적는 사람이 만든다.

값을 붙이는 쪽(신뢰성 시험 · 보유 장비)의 권한 판정은 **그쪽 서비스**가 한다. 여기는 그 뒤에
불려서 값의 형만 본다.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import func, or_, select
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
from app.modules.documents.models import SpecDocument, SpecDocumentRevision
from app.modules.methods.models import TestMethod
from app.modules.vocabulary.models import ConditionKey, Vocabulary, VocabularyTerm
from app.shared.attribute_text import display_attribute
from app.shared.errors import AppError, Conflict, NotFound
from app.shared.text import clean
from app.shared.units import same_unit

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
        raise NotFound("TSC-ATTR-0001", "속성 정의를 찾을 수 없음.")
    return row


def _check_target(target: str) -> None:
    if target not in ATTRIBUTE_TARGETS:
        raise AppError("TSC-ATTR-0002", f"알 수 없는 대상: {target}")


def _check_kind(kind: str) -> None:
    if kind not in ATTRIBUTE_KINDS:
        raise AppError("TSC-ATTR-0003", f"알 수 없는 종류: {kind}")


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
    """종류가 요구하는 축이 있나. condition 은 조건 축, term 은 온톨로지 축."""
    if kind == "condition":
        key_id = payload.get("condition_key_id")
        if key_id is None or db.get(ConditionKey, key_id) is None:
            raise AppError("TSC-ATTR-0004", "조건 종류는 검색 조건 축 선택 필요.")
    if kind == "term":
        vocabulary_id = payload.get("vocabulary_id")
        if vocabulary_id is None or db.get(Vocabulary, vocabulary_id) is None:
            raise AppError("TSC-ATTR-0004", "온톨로지 종류는 축 선택 필요.")
    if kind == "choice" and not [c for c in payload.get("choices") or [] if clean(c)]:
        raise AppError("TSC-ATTR-0004", "선택 종류는 선택지를 하나 이상 입력해야 함.")


def _auto_key() -> str:
    return f"draft-{uuid.uuid4().hex[:8]}"


#: key 에 쓸 수 있는 글자. **주소에 그대로 실리는 이름**이라(`?attr=invest_year>=2020`)
#: 한글·공백·연산자 글자가 들어가면 그 속성은 영영 못 거른다 — 적어 두고 못 찾는 칸이 된다.
_KEY_SHAPE = re.compile(r"^[A-Za-z0-9_.-]{1,60}$")


def _check_key_shape(key: str) -> None:
    if _KEY_SHAPE.match(key) is None:
        raise AppError(
            "TSC-ATTR-0009",
            f"사용할 수 없는 key: {key}. 영문·숫자·_ . -만 사용 가능(필터 주소에 포함됨).",
        )


def _check_key_free(db: Session, key: str, *, except_id: uuid.UUID | None) -> None:
    stmt = select(AttributeDefinition).where(AttributeDefinition.key == key)
    if except_id is not None:
        stmt = stmt.where(AttributeDefinition.id != except_id)
    if db.scalar(stmt) is not None:
        raise Conflict("TSC-ATTR-0005", f"같은 key의 속성이 있음: {key}")


def create_definition(db: Session, user: User, payload: dict[str, Any]) -> AttributeDefinition:
    """시스템 관리자의 등록. 조사 중인 후보를 **미리 초안으로** 넣어 두는 데도 쓴다 — 그러면
    부서가 처음 적을 때부터 목록에 뜬다."""
    target = str(payload["target"])
    _check_target(target)
    kind = str(payload.get("kind") or "text")
    _check_kind(kind)
    status = str(payload.get("status") or "standard")
    if status not in ATTRIBUTE_STATUSES:
        raise AppError("TSC-ATTR-0003", f"알 수 없는 상태: {status}")
    label = clean(str(payload["label"]))
    if not label:
        raise AppError("TSC-ATTR-0006", "이름 입력 필요.")
    if _find_by_label(db, target, label) is not None:
        raise Conflict("TSC-ATTR-0007", f"같은 이름의 속성이 있음: {label}")
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


def keep_unit(db: Session, definition: AttributeDefinition, unit: str) -> int:
    """정의의 단위가 `unit` 으로 바뀌기 전에, **단위 없이 적힌 값에 지금 단위를 적어 둔다.**
    적어 둔 값 수를 돌려준다.

    값의 단위 칸이 비어 있으면 정의의 단위로 읽힌다. 그래서 정의를 cm 에서 m 로 고치거나
    m 인 속성에 합치는 순간 152 가 152 m 가 된다 — 숫자는 그대로인데 뜻이 바뀌고, 그것을
    알리는 곳이 없다. 고치기 전의 단위를 그 값들에 적으면 숫자도 뜻도 그대로다. 조건 축
    (`vocabulary/unit_change.py`)처럼 묻지 않는 이유가 이것이다 — 값마다 단위 칸이 있어 지킬
    수 있다.
    """
    if not definition.unit or same_unit(definition.unit, unit):
        return 0
    stamped = 0
    for value in db.scalars(
        select(AttributeValue).where(
            AttributeValue.definition_id == definition.id,
            AttributeValue.unit == "",
            or_(
                AttributeValue.num_value.is_not(None),
                AttributeValue.num_min.is_not(None),
                AttributeValue.num_max.is_not(None),
            ),
        )
    ):
        value.unit = definition.unit
        stamped += 1
    return stamped


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
            raise AppError("TSC-ATTR-0006", "이름 입력 필요.")
        if _find_by_label(db, row.target, label, except_id=row.id) is not None:
            raise Conflict("TSC-ATTR-0007", f"같은 이름의 속성이 있음: {label}")
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
                "값이 입력된 속성의 종류는 변경 불가. 새 속성을 만든 뒤 병합 필요.",
            )
        row.kind = kind
    if "unit" in changes:
        unit = clean(str(changes["unit"] or ""))
        keep_unit(db, row, unit)
        row.unit = unit
    if "choices" in changes and changes["choices"] is not None:
        row.choices = [clean(c) for c in changes["choices"] if clean(c)]
    if "condition_key_id" in changes:
        row.condition_key_id = changes["condition_key_id"]
    if "vocabulary_id" in changes:
        row.vocabulary_id = changes["vocabulary_id"]
    if changes.get("status"):
        status = str(changes["status"])
        if status not in ATTRIBUTE_STATUSES:
            raise AppError("TSC-ATTR-0003", f"알 수 없는 상태: {status}")
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
            "TSC-ATTR-0013",
            "값이 입력된 속성은 삭제 불가. 끄거나 다른 속성에 병합 필요.",
        )
    pointing = db.scalar(
        select(AttributeDefinition.id).where(AttributeDefinition.merged_into_id == row.id)
    )
    if pointing is not None:
        raise Conflict("TSC-ATTR-0013", "다른 속성이 이 속성으로 병합되어 있어 삭제 불가.")
    db.delete(row)
    db.commit()


def merge_into(db: Session, source_id: uuid.UUID, target_id: uuid.UUID) -> AttributeDefinition:
    """이름만 다른 항목 둘을 하나로 — 값이 남는 쪽으로 옮겨 가고 원래 항목은 꺼진다.

    종류가 같아야 한다. 문장 초안을 수치 항목에 합치면 값이 안 읽히기 때문이다. 같은 대상에
    두 값이 다 있으면 남는 쪽 값을 두고 옮기는 쪽을 버린다 — 정식(또는 남기려는 쪽)이 더
    낫다고 본다. 단위는 값에 있으므로 환산하지 않고 옮긴다 — **단위 칸이 빈 값은 옮기기 전에
    옮기는 쪽의 단위를 적어 둔다**(`keep_unit`). 안 그러면 cm 속성의 152 가 m 속성으로 가서
    152 m 가 된다.
    """
    source = get_definition(db, source_id)
    target = get_definition(db, target_id)
    if source.id == target.id:
        raise AppError("TSC-ATTR-0009", "같은 속성끼리는 병합 불가.")
    if source.target != target.target:
        raise AppError("TSC-ATTR-0009", "대상이 다른 속성은 병합 불가.")
    if source.kind != target.kind:
        raise Conflict(
            "TSC-ATTR-0009",
            f"종류가 다른 속성은 병합 불가: {source.kind} → {target.kind}",
        )
    if not target.is_active:
        raise AppError("TSC-ATTR-0009", "꺼진 속성으로는 병합 불가.")
    keep_unit(db, source, target.unit)
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
    if kind in ("condition", "term", "choice", "pairs", "matrix"):
        # 축·선택지·짝처럼 **모양이 있는** 종류는 초안으로 못 만든다 — 관리자가 정의부터.
        raise AppError("TSC-ATTR-0010", f"{kind} 종류의 속성은 관리자가 먼저 정의해야 함.")
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
        raise AppError("TSC-ATTR-0011", f"{label}: 수치 필요.")
    # **숫자 대신 말로 적을 수도 있다** — 「상온」 · 「규격에 따름」 · 「1축씩 3방향」.
    # 그런 줄은 사람이 읽고 장비 판정에는 안 실린다(capability 가 값 없는 조건을 「제한
    # 없음」 으로 넘긴다). 비고까지 비면 아무 말도 안 하는 줄이라 거절한다.
    if (
        kind in ("range", "condition")
        and item.num_min is None
        and item.num_max is None
        # 조건은 **점 하나**로도 적는다 — 이산 점(-40 · -20 · 25 · 85 °C)이 그렇다.
        and not (kind == "condition" and item.num_value is not None)
        and not clean(item.note or "")
    ):
        raise AppError(
            "TSC-ATTR-0011",
            f"{label}: 최소·최대(또는 점 하나) 입력 필요. 숫자로 적을 수 없으면 비고에 입력.",
        )
    if (
        kind in ("range", "condition")
        and item.num_min is not None
        and item.num_max is not None
        and item.num_min > item.num_max
    ):
        raise AppError("TSC-ATTR-0011", f"{label}: 최소가 최대보다 큼.")
    if kind == "text" and not clean(item.text_value or ""):
        raise AppError("TSC-ATTR-0011", f"{label}: 글 입력 필요.")
    if kind == "choice":
        picked = clean(item.text_value or "")
        if picked not in (definition.choices or []):
            raise AppError(
                "TSC-ATTR-0011",
                f"{label}: 선택지 중 하나여야 함.",
                details={"choices": list(definition.choices or [])},
            )
    if kind == "boolean" and item.bool_value is None:
        raise AppError("TSC-ATTR-0011", f"{label}: 있음/없음 선택 필요.")
    if kind == "date" and item.date_value is None:
        raise AppError("TSC-ATTR-0011", f"{label}: 날짜 필요.")
    if kind == "term":
        # **맞는 값이 축에 없을 때 그 사실을 남길 자리가 있어야 한다.** 조건은 숫자를 비우고
        # 비고만 실어도 통과하는데 온톨로지 값은 400 이었다 — 그래서 옮겨 적는 쪽은 「축에
        # 없다」 를 말할 방법이 없어 **그냥 비웠고**, 빈 칸은 「없다」 로 읽혔다. 비우는
        # 것과 아무 말 없이 비우는 것은 다르다. 축이 닫혀 있을수록(시험 항목·물성) 이
        # 자리가 필요하다 — 값을 더할 수 있는 사람은 관리자뿐이다.
        if item.term_id is None and clean(item.note or ""):
            pass
        else:
            term = db.get(VocabularyTerm, item.term_id) if item.term_id else None
            if term is None or term.vocabulary_id != definition.vocabulary_id:
                raise AppError(
                    "TSC-ATTR-0011",
                    f"{label}: 해당 축의 온톨로지 값이어야 함."
                    " 맞는 값이 없으면 비우고 비고(note)에 원문 입력.",
                )
    if kind == "method":
        method = db.get(TestMethod, item.method_id) if item.method_id else None
        if method is None or method.deleted_at is not None:
            raise AppError("TSC-ATTR-0011", f"{label}: 등록된 규격이어야 함.")
    if kind == "document":
        document = db.get(SpecDocument, item.document_id) if item.document_id else None
        if document is None or document.deleted_at is not None:
            raise AppError("TSC-ATTR-0011", f"{label}: 등록된 사내 규격서여야 함.")
    if kind in ("pairs", "matrix"):
        _check_pairs_shape(kind, label, item.json_value)


def _pair_rows(label: str, rows: Any) -> None:
    """짝 목록 한 벌 — 이름과 숫자가 둘 다 있어야 한다.

    **이름 없는 숫자는 못 읽는다.** 「4」 만 남으면 그것이 A등급인지 1단계인지 알 수 없고,
    그 값은 적어 둔 사람 말고는 아무도 못 쓴다.
    """
    if not isinstance(rows, list) or not rows:
        raise AppError("TSC-ATTR-0011", f"{label}: 줄이 하나 이상 필요.")
    for one in rows:
        if not isinstance(one, dict):
            raise AppError("TSC-ATTR-0011", f"{label}: 줄 형식이 올바르지 않음.")
        name = clean(str(one.get("label") or ""))
        value = one.get("value")
        if not name:
            raise AppError("TSC-ATTR-0011", f"{label}: 이름이 빈 줄 있음.")
        if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
            raise AppError("TSC-ATTR-0011", f"{label}: {name} 값은 숫자여야 함.")


def _check_pairs_shape(kind: str, label: str, rows: Any) -> None:
    if kind == "pairs":
        _pair_rows(label, rows)
        return
    if not isinstance(rows, list) or not rows:
        raise AppError("TSC-ATTR-0011", f"{label}: 줄이 하나 이상 필요.")
    for one in rows:
        if not isinstance(one, dict):
            raise AppError("TSC-ATTR-0011", f"{label}: 줄 형식이 올바르지 않음.")
        name = clean(str(one.get("label") or ""))
        if not name:
            raise AppError("TSC-ATTR-0011", f"{label}: 이름이 빈 사양 있음.")
        _pair_rows(f"{label} / {name}", one.get("entries"))


def set_values(
    db: Session,
    user: User | None,
    *,
    target: str,
    object_id: uuid.UUID,
    items: list[AttributeValueIn],
    revision_id: uuid.UUID | None = None,
) -> None:
    """대상 하나의 값을 **통째로** 바꾼다. 커밋은 부르는 쪽이 한다.

    **같은 자리에 두 줄이 오면 거절한다**(422). 예전에는 뒤의 것이 남았는데, 보낸 쪽은
    둘 다 보냈다고 알고 있으니 그 손실이 아무 데도 안 드러났다 — 수백 건을 적재하면서
    조건이 하나씩 사라지는데 누구도 그 사실을 모르는 것이 실제 위험이다. 자리는 (칸,
    묶음, 차례)이고, 같은 칸을 여러 벌 적으려면 **묶음을 달면 된다.**

    **신뢰성 시험은 판마다 한 벌씩 쌓인다**(`revision_id`). 시험은 한 줄이고 판은 값에
    붙으므로, 이 부름은 **그 판의 값만** 갈아 끼운다 — 개정 18을 올려도 14의 값은 남아
    이력이 된다. 판을 안 주면 판 없는 값만 바뀐다(다른 대상은 판이 없어 예전 그대로다).

    새 이름은 초안을 만든다.
    """
    _check_target(target)
    column = _TARGET_COLUMN[target]
    # **그 판의 것만 지운다.** 통째로 지우면 개정 18을 올리는 순간 14의 값이 사라지고,
    # 이력이 있다고 알고 있던 사람은 그것을 영영 못 찾는다.
    stale = select(AttributeValue).where(
        column == object_id,
        AttributeValue.document_revision_id.is_not_distinct_from(revision_id),
    )
    for old in db.scalars(stale):
        db.delete(old)
    db.flush()
    # **열쇠가 (정의, 묶음, 차례) 다.** 정의만으로 누르면 동작·저장이 서로를 덮어써서
    # 마지막 한 줄만 남는다 — 보낸 사람은 둘 다 보냈다고 알고 있다.
    seen: dict[tuple[uuid.UUID, str, int], AttributeValue] = {}
    clashes: list[str] = []
    for item in items:
        if item.definition_id is not None:
            definition = get_definition(db, item.definition_id)
            if definition.target != target:
                raise AppError("TSC-ATTR-0012", f"{definition.label}: 이 대상의 속성이 아님.")
            if not definition.is_active:
                raise AppError("TSC-ATTR-0012", f"{definition.label}: 꺼진 속성.")
        else:
            label = clean(item.new_label or "")
            if not label:
                raise AppError("TSC-ATTR-0006", "속성 이름 입력 필요.")
            definition = _ensure_draft(db, user, target, label, item.new_kind)
        _check_value_shape(db, definition, item)
        numeric = definition.kind in _NUMERIC_KINDS
        value = AttributeValue(
            definition_id=definition.id,
            # **조건은 점으로도 적는다.** 이산 점(-40 · -20 · 25 · 85 °C)은 구간이 아니라
            # 값 하나다. 판정은 이미 이 칸을 읽을 줄 알았는데(`ConditionQuery(at=…)`)
            # 여기서 버리고 있어서, 그 길이 닿지 않았다.
            num_value=item.num_value if definition.kind in ("number", "condition") else None,
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
            ref_document_id=(item.document_id if definition.kind == "document" else None),
            json_value=(item.json_value if definition.kind in ("pairs", "matrix") else None),
            note=clean(item.note or "") or None,
            set_label=clean(item.set_label or "") or None,
            step_order=item.step_order,
            step_label=clean(item.step_label or "") or None,
            # **원문은 안 다듬는다.** 줄바꿈과 띄어쓰기가 문서의 모양이고, 그것을 고르면
            # 「그대로」 가 아니게 된다 — 앞뒤 공백만 턴다.
            source_text=(item.source_text or "").strip() or None,
            original_value=clean(item.original_value or "") or None,
            original_unit=clean(item.original_unit or "") or None,
        )
        setattr(value, column.key, object_id)
        where = (
            definition.id,
            value.set_label or "",
            value.step_order if value.step_order is not None else -1,
        )
        if where in seen:
            # **덮어쓰지 않고 말한다.** 어느 칸이 몇 번 왔는지까지 적어 준다 — 「값이
            # 겹칩니다」 만으로는 스무 줄 중 어느 것을 고칠지 알 수 없다.
            clashes.append(_where_text(definition.label, value))
        seen[where] = value
    if clashes:
        raise AppError(
            "TSC-ATTR-0013",
            "같은 자리에 값 중복: "
            + " · ".join(sorted(set(clashes)))
            + ". 같은 칸을 여러 벌 입력하려면 묶음(set_label)이나 차례(step_order)로"
            " 구분 필요. 구분하지 않으면 한 줄만 남고 나머지는 삭제됨.",
            status=422,
            details={"duplicates": sorted(set(clashes))},
        )
    for value in seen.values():
        value.document_revision_id = revision_id
        # **끄고 들어간다.** 새 판의 값을 켠 채로 넣으면, 옛 판의 값이 아직 켜져 있어서
        # 「자리마다 하나」 인덱스를 어긴다 — 표식은 아래에서 한 번에 다시 세운다.
        value.is_current = target != "reliability_test"
        db.add(value)
    db.flush()
    if target == "reliability_test":
        _mark_current(db, object_id)


def _mark_current(db: Session, test_id: uuid.UUID) -> None:
    """자리마다 **지금 값**을 하나 고른다 — 판 순서가 가장 뒤인 것.

    **읽는 쪽이 이 판정을 다시 하지 않게** 칸에 적어 둔다(모델의 `is_current` 참고).
    유일 인덱스가 자리마다 하나임을 보증하므로, 여기서 틀리면 커밋이 막힌다 — 조용히
    두 개가 서는 일은 없다.

    판 없는 값은 **가장 아래**다. 판을 적은 값이 하나라도 있으면 그것이 이긴다 — 나중에
    판을 붙인 것이 더 정확한 정보다.
    """
    rows = list(
        db.scalars(select(AttributeValue).where(AttributeValue.reliability_test_id == test_id))
    )
    if not rows:
        return
    orders = {
        one.id: one.sort_order
        for one in db.scalars(
            select(SpecDocumentRevision).where(
                SpecDocumentRevision.id.in_(
                    {r.document_revision_id for r in rows if r.document_revision_id}
                )
            )
        )
    }
    slots: dict[tuple[uuid.UUID, str, int], list[AttributeValue]] = {}
    for one in rows:
        where = (
            one.definition_id,
            one.set_label or "",
            one.step_order if one.step_order is not None else -1,
        )
        slots.setdefault(where, []).append(one)
    # **두 번에 나눠 쓴다.** 켜고 끄는 것을 한 문장에 섞으면 그 사이에 자리마다 둘이
    # 켜진 순간이 생기고, 유일 인덱스는 그 순간을 본다(미룰 수 없는 인덱스다).
    winners: list[AttributeValue] = []
    for mine in slots.values():
        # 판이 없으면 -1 — 판을 적은 것이 언제나 이긴다.
        winners.append(
            max(
                mine,
                key=lambda one: (
                    orders.get(one.document_revision_id, -1)
                    if one.document_revision_id
                    else -1
                ),
            )
        )
    for one in rows:
        one.is_current = False
    db.flush()
    for one in winners:
        one.is_current = True
    db.flush()


def _where_text(label: str, value: AttributeValue) -> str:
    """「시험 온도」 · 「시험 온도(동작)」 · 「시험 온도(온도 사이클 2번째)」."""
    if not value.set_label and value.step_order is None:
        return label
    inside = value.set_label or ""
    if value.step_order is not None:
        inside = f"{inside} {value.step_order}번째".strip()
    return f"{label}({inside})"


def display_of(
    value: AttributeValue,
    definition: AttributeDefinition,
    *,
    term_value: str | None,
    method_code: str | None,
    document_code: str | None = None,
) -> str:
    """사람이 읽는 한 줄. 화면과 MCP 와 색인 카드가 같은 글자를 쓰게 서버가 만든다.

    **값에 단위가 없으면 칸의 단위를 쓴다.** 「85 이상」 은 85 N 인지 85 kN 인지 알 수
    없고, 그 둘은 자릿수가 셋 다르다 — 화면은 단위를 함께 보내지만 MCP 가 빠뜨릴 수 있다.
    짝 종류(`pairs`·`matrix`)는 아예 줄마다 단위를 안 적는다: 「등급별 수량」 은 통째로
    「개」 다.
    """
    unit = value.unit or definition.unit
    return display_attribute(
        definition.kind,
        num_value=value.num_value,
        num_min=value.num_min,
        num_max=value.num_max,
        unit=unit,
        text_value=value.text_value,
        bool_value=value.bool_value,
        date_value=value.date_value,
        term_value=term_value,
        method_code=method_code,
        document_code=document_code,
        json_value=value.json_value,
    )


def values_of(
    db: Session,
    *,
    target: str,
    object_ids: list[uuid.UUID],
    include_draft: bool = True,
    include_past: bool = False,
) -> dict[uuid.UUID, list[AttributeValueOut]]:
    """여러 대상의 값을 질의 몇 번으로. 정식이 먼저, 초안이 뒤.

    **지금 값만 준다**(`is_current`). 신뢰성 시험은 판마다 값이 쌓이므로(0046), 안 거르면
    카드에 개정 14의 85 °C 와 18의 95 °C 가 나란히 서서 어느 것이 지금 조건인지 안 보인다.
    과거 판까지 보려면 `include_past=True` — 이력 화면이 그렇게 부른다.
    """
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
            # **묶음이 먼저 뭉친다.** 정의 순서로만 늘어놓으면 동작의 온도와 저장의 온도가
            # 나란히 서고, 읽는 사람은 그 둘이 한 벌인 줄 안다. 이름 없는 묶음이 맨 앞이다.
            AttributeValue.set_label.nulls_first(),
            AttributeValue.step_order.nulls_first(),
            AttributeDefinition.sort_order,
            AttributeDefinition.label,
        )
    )
    if not include_draft:
        stmt = stmt.where(AttributeDefinition.status == "standard")
    if not include_past:
        stmt = stmt.where(AttributeValue.is_current.is_(True))
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
    document_ids = {v.ref_document_id for v, _ in pairs if v.ref_document_id}
    documents = (
        {
            d.id: d.code
            for d in db.scalars(select(SpecDocument).where(SpecDocument.id.in_(document_ids)))
        }
        if document_ids
        else {}
    )
    # 판 이름도 한 번에 — id 만 오면 사람이 못 읽는다.
    revisions = {
        one.id: one.label
        for one in db.scalars(
            select(SpecDocumentRevision).where(
                SpecDocumentRevision.id.in_(
                    {v.document_revision_id for v, _ in pairs if v.document_revision_id}
                )
            )
        )
    }
    for value, definition in pairs:
        term_value = terms.get(value.term_id) if value.term_id else None
        method_code = methods.get(value.ref_method_id) if value.ref_method_id else None
        document_code = documents.get(value.ref_document_id) if value.ref_document_id else None
        out[getattr(value, column.key)].append(
            AttributeValueOut(
                definition_id=definition.id,
                label=definition.label,
                kind=definition.kind,
                status=definition.status,
                set_label=value.set_label,
                step_order=value.step_order,
                step_label=value.step_label,
                document_revision_id=value.document_revision_id,
                document_revision_label=revisions.get(value.document_revision_id)
                if value.document_revision_id
                else None,
                is_current=value.is_current,
                source_text=value.source_text,
                original_value=value.original_value,
                original_unit=value.original_unit,
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
                json_value=value.json_value,
                method_code=method_code,
                document_id=value.ref_document_id,
                document_code=document_code,
                note=value.note,
                display=display_of(
                    value,
                    definition,
                    term_value=term_value,
                    method_code=method_code,
                    document_code=document_code,
                ),
            )
        )
    return out

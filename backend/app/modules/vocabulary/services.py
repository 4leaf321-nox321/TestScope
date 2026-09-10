"""기준정보 로직 — 값을 만들고, 고치고, 합친다.

## 만들 때 별칭까지 뒤진다

중복은 사후에 합치는 것보다 **애초에 안 생기게 하는 것**이 싸다. UTM 을 등록하려는
사람에게 "만능재료시험기가 이미 있습니다" 라고 말해 주는 자리가 여기다.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.equipment.models import (
    Equipment,
    EquipmentCalibration,
    EquipmentModel,
    EquipmentSeries,
    ModelSpecValue,
    SpecSource,
)
from app.modules.methods.models import MethodRequirement, TestMethod
from app.modules.test_items.models import (
    EquipmentTestCondition,
    EquipmentTestItem,
    SeriesTestItem,
)
from app.modules.vocabulary.models import (
    VOCABULARY_DOMAIN_LABELS,
    ConditionKey,
    Vocabulary,
    VocabularyAlias,
    VocabularyTerm,
)
from app.modules.vocabulary.schemas import (
    ConditionKeyOut,
    SpecDefinitionOut,
    SpecGroupOut,
    TermOut,
    VocabularyOut,
)
from app.modules.vocabulary.specs import (
    SpecDefinition,
    SpecDefinitionCategory,
    SpecGroup,
)
from app.shared import audit
from app.shared.errors import AppError, Conflict, NotFound
from app.shared.text import clean, compare_key


def get_vocabulary(db: Session, slug: str) -> Vocabulary:
    found = db.scalar(select(Vocabulary).where(Vocabulary.slug == slug))
    if found is None:
        raise NotFound("TSC-VOCAB-0001", f"기준정보 축을 찾을 수 없습니다: {slug}")
    return found


def _term_count(db: Session, vocabulary_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(VocabularyTerm)
            .where(VocabularyTerm.vocabulary_id == vocabulary_id)
        )
        or 0
    )


def list_vocabularies(db: Session) -> list[VocabularyOut]:
    """축 목록. **어디의 축인지를 함께 준다.**

    화면이 그것으로 묶는다 — 한 목록에 일곱이 나란히 서면 「이게 어디 쓰이는 값이지」 를
    알 수 없고, 그때 규격 제정기관 축에 회사 이름이 들어간다.
    """
    rows = db.scalars(select(Vocabulary).order_by(Vocabulary.sort_order, Vocabulary.label))
    return [
        VocabularyOut(
            id=row.id,
            slug=row.slug,
            label=row.label,
            domain=row.domain,
            # 이름까지 서버가 준다 — 화면마다 사전을 두면 한 곳만 안 고쳐진다.
            domain_label=VOCABULARY_DOMAIN_LABELS.get(row.domain, row.domain),
            description=row.description,
            entry_policy=row.entry_policy,
            parent_slug=row.parent_slug,
            sort_order=row.sort_order,
            term_count=_term_count(db, row.id),
        )
        for row in rows
    ]


def _aliases_of(db: Session, term_id: uuid.UUID) -> list[str]:
    return list(
        db.scalars(
            select(VocabularyAlias.value)
            .where(VocabularyAlias.term_id == term_id, VocabularyAlias.is_active.is_(True))
            .order_by(VocabularyAlias.value)
        )
    )


#: 축마다 **무엇이 그 값을 가리키나.** (모델, 칸) 목록이다.
#:
#: 이 표가 없으면 쓰임 수를 셀 수 없고, 쓰임 수가 없으면 기준정보 화면은 지워도 되는
#: 값과 안 되는 값을 구별하지 못한다 — 「이 제조사 지워도 되나」 에 답하는 자리가 여기다.
#:
#: 여기 없는 축은 0 이 아니라 **모른다**가 맞지만, 축을 만들면서 이 표에 한 줄 더하는
#: 것을 잊는 편이 훨씬 흔하다. `tests/api/test_vocabulary_usage.py` 가 그것을 잡는다.
_REFERENCES: dict[str, list[tuple[Any, Any]]] = {
    "test_item": [
        (EquipmentTestItem, EquipmentTestItem.test_item_term_id),
        (SeriesTestItem, SeriesTestItem.test_item_term_id),
        (TestMethod, TestMethod.test_item_term_id),
    ],
    "equipment_category": [
        (EquipmentSeries, EquipmentSeries.category_term_id),
        (Equipment, Equipment.category_term_id),
        (SpecDefinitionCategory, SpecDefinitionCategory.category_term_id),
    ],
    "manufacturer": [
        (EquipmentSeries, EquipmentSeries.maker_term_id),
        (SpecSource, SpecSource.maker_term_id),
    ],
    "form_factor": [
        (EquipmentSeries, EquipmentSeries.form_factor_term_id),
        (EquipmentModel, EquipmentModel.form_factor_term_id),
    ],
    "drive": [(EquipmentSeries, EquipmentSeries.drive_term_id)],
    "site": [(Equipment, Equipment.site_term_id)],
    "calibration_provider": [(EquipmentCalibration, EquipmentCalibration.provider_term_id)],
    "standard_body": [(TestMethod, TestMethod.body_term_id)],
}


def _usage_of(db: Session, vocabulary: Vocabulary) -> dict[uuid.UUID, int]:
    """그 축의 값마다 몇 군데서 쓰이나. **셀 때 센다.**

    전에는 `vocabulary_terms.usage_count` 칸에 적어 두게 되어 있었는데, **아무도 안
    갱신했다** — 장비 700대와 계열 200개를 들이고도 모든 값이 0 이었다. 0 인 화면은
    거짓말을 하고, 그 거짓말로는 값을 지울지 말지 정할 수 없다.

    칸당 GROUP BY 한 번이다(축 하나에 두세 번). 가리키는 칸에 인덱스가 있어서 값이
    백 개든 천 개든 같은 비용이다 — 틀린 수를 싸게 얻느니 맞는 수를 이 값에 치른다.
    """
    out: dict[uuid.UUID, int] = {}
    for model, column in _REFERENCES.get(vocabulary.slug, []):
        stmt = select(column, func.count()).where(column.is_not(None)).group_by(column)
        deleted = getattr(model, "deleted_at", None)
        if deleted is not None:
            # 지운 장비가 값을 붙잡고 있으면 「쓰는 데가 있다」 가 거짓이 된다.
            stmt = stmt.where(deleted.is_(None))
        for term_id, count in db.execute(stmt).all():
            out[term_id] = out.get(term_id, 0) + count
    return out


def term_out(
    db: Session,
    term: VocabularyTerm,
    *,
    vocabulary: Vocabulary | None = None,
    usage: dict[uuid.UUID, int] | None = None,
) -> TermOut:
    """값 한 줄.

    쓰임 수는 **목록이 한 번에 세어 넘긴다**(`list_terms`). 안 넘기면 여기서 그 축을
    한 번 센다 — 한 줄을 그리려고 축 전체를 세는 셈이지만, 한 줄짜리 호출은 드물다.
    """
    vocab = vocabulary or db.get(Vocabulary, term.vocabulary_id)
    parent = db.get(VocabularyTerm, term.parent_term_id) if term.parent_term_id else None
    if usage is None:
        usage = _usage_of(db, vocab) if vocab else {}
    return TermOut(
        id=term.id,
        vocabulary_slug=vocab.slug if vocab else "",
        value=term.value,
        code=term.code,
        parent_term_id=term.parent_term_id,
        parent_value=parent.value if parent else None,
        status=term.status,
        usage_count=usage.get(term.id, 0),
        aliases=_aliases_of(db, term.id),
        attributes=term.attributes,
        created_at=term.created_at,
    )


def list_terms(
    db: Session, *, slug: str, query: str | None, include_deprecated: bool
) -> list[TermOut]:
    vocabulary = get_vocabulary(db, slug)
    stmt = select(VocabularyTerm).where(VocabularyTerm.vocabulary_id == vocabulary.id)
    if not include_deprecated:
        # **기본은 숨긴다.** 폐기한 값이 피커에 뜨면 사람이 그걸 또 고른다.
        stmt = stmt.where(VocabularyTerm.status == "active")
    if query:
        stmt = stmt.where(VocabularyTerm.normalized.contains(compare_key(query)))
    rows = db.scalars(stmt.order_by(VocabularyTerm.value))
    # **한 번에 센다.** 줄마다 세면 값 108개짜리 축에서 조회가 수백 번 돈다.
    usage = _usage_of(db, vocabulary)
    return [term_out(db, row, vocabulary=vocabulary, usage=usage) for row in rows]


def _find_by_key(db: Session, vocabulary_id: uuid.UUID, key: str) -> VocabularyTerm | None:
    """값과 **별칭 양쪽**을 뒤진다.

    별칭을 안 보면 UTM 을 다시 등록할 수 있게 되고, 그 순간 별칭을 등록해 둔 뜻이
    사라진다 — 예방이 목적인 표가 아무것도 예방하지 못한다.
    """
    found = db.scalar(
        select(VocabularyTerm).where(
            VocabularyTerm.vocabulary_id == vocabulary_id, VocabularyTerm.normalized == key
        )
    )
    if found is not None:
        return found
    alias = db.scalar(
        select(VocabularyAlias).where(
            VocabularyAlias.vocabulary_id == vocabulary_id, VocabularyAlias.normalized == key
        )
    )
    return db.get(VocabularyTerm, alias.term_id) if alias else None


def create_term(
    db: Session,
    *,
    slug: str,
    value: str,
    code: str | None,
    parent_term_id: uuid.UUID | None,
    attributes: dict[str, Any],
    actor: User,
    is_admin: bool,
) -> VocabularyTerm:
    vocabulary = get_vocabulary(db, slug)

    # closed 축은 관리자만 채운다. **검색의 축이 되는 것**이라 오타 하나가 값이
    # 되면 그 장비는 영영 검색에 안 걸린다.
    if vocabulary.entry_policy == "closed" and not is_admin:
        raise AppError(
            "TSC-VOCAB-0002",
            f"{vocabulary.label}은 관리자만 값을 추가할 수 있습니다.",
            status=403,
        )

    text = clean(value)
    key = compare_key(text)
    existing = _find_by_key(db, vocabulary.id, key)
    if existing is not None:
        raise Conflict(
            "TSC-VOCAB-0003",
            f"이미 있는 값입니다: {existing.value}",
            details={"term_id": str(existing.id), "value": existing.value},
        )

    term = VocabularyTerm(
        vocabulary_id=vocabulary.id,
        value=text,
        normalized=key,
        code=clean(code) if code else None,
        parent_term_id=parent_term_id,
        attributes=attributes,
        created_by_id=actor.id,
    )
    db.add(term)
    db.commit()
    db.refresh(term)
    return term


def get_term(db: Session, term_id: uuid.UUID) -> VocabularyTerm:
    term = db.get(VocabularyTerm, term_id)
    if term is None:
        raise NotFound("TSC-VOCAB-0004", "값을 찾을 수 없습니다.")
    return term


def update_term(
    db: Session,
    *,
    term_id: uuid.UUID,
    value: str | None,
    code: str | None,
    parent_term_id: uuid.UUID | None,
    status: str | None,
    attributes: dict[str, Any] | None,
    actor: User,
) -> VocabularyTerm:
    term = get_term(db, term_id)

    if value is not None:
        text = clean(value)
        key = compare_key(text)
        if key != term.normalized:
            clash = _find_by_key(db, term.vocabulary_id, key)
            if clash is not None and clash.id != term.id:
                raise Conflict("TSC-VOCAB-0003", f"이미 있는 값입니다: {clash.value}")
            # **이름 변경은 감사에 남긴다.** 이 값을 가리키는 장비 수십 대의 표시가
            # 한꺼번에 바뀌는 일이고, 나중에 "왜 이름이 달라졌지" 를 물을 자리가
            # 여기밖에 없다.
            audit.record(
                db,
                action=audit.VOCABULARY_RENAMED,
                actor=actor,
                target_table="vocabulary_terms",
                target_id=term.id,
                target_label=term.value,
                changes={"value": {"before": term.value, "after": text}},
            )
        term.value = text
        term.normalized = key

    if code is not None:
        term.code = clean(code) or None
    if parent_term_id is not None:
        term.parent_term_id = parent_term_id
    if status is not None:
        term.status = status
    if attributes is not None:
        term.attributes = attributes

    db.commit()
    db.refresh(term)
    return term


def add_alias(db: Session, *, term_id: uuid.UUID, value: str) -> VocabularyTerm:
    term = get_term(db, term_id)
    text = clean(value)
    key = compare_key(text)

    existing = _find_by_key(db, term.vocabulary_id, key)
    if existing is not None:
        raise Conflict(
            "TSC-VOCAB-0005",
            f"그 표기는 이미 {existing.value}을(를) 가리킵니다.",
        )

    db.add(
        VocabularyAlias(
            vocabulary_id=term.vocabulary_id, term_id=term.id, value=text, normalized=key
        )
    )
    db.commit()
    db.refresh(term)
    return term


def merge_terms(
    db: Session, *, source_id: uuid.UUID, target_id: uuid.UUID, actor: User
) -> VocabularyTerm:
    """원본을 대상으로 합치고, 원본 이름을 **대상의 별칭으로 남긴다.**

    지워 버리면 같은 오타가 또 들어온다 — 그때는 아무도 그것이 예전에 합쳐졌던
    값이라는 것을 모른다.
    """
    source = get_term(db, source_id)
    target = get_term(db, target_id)
    if source.id == target.id:
        raise AppError("TSC-VOCAB-0006", "같은 값끼리는 합칠 수 없습니다.", status=400)
    if source.vocabulary_id != target.vocabulary_id:
        raise AppError("TSC-VOCAB-0007", "다른 축의 값끼리는 합칠 수 없습니다.", status=400)

    # 원본을 가리키던 하위 값을 대상으로 옮긴다. 안 옮기면 부모 잃은 값이 남는다.
    for child in db.scalars(
        select(VocabularyTerm).where(VocabularyTerm.parent_term_id == source.id)
    ):
        child.parent_term_id = target.id

    # 원본의 별칭도 함께 넘긴다 — 별칭의 별칭이 되면 조회가 두 단계가 된다.
    for alias in db.scalars(
        select(VocabularyAlias).where(VocabularyAlias.term_id == source.id)
    ):
        alias.term_id = target.id

    db.add(
        VocabularyAlias(
            vocabulary_id=target.vocabulary_id,
            term_id=target.id,
            value=source.value,
            normalized=source.normalized,
        )
    )
    audit.record(
        db,
        action=audit.VOCABULARY_MERGED,
        actor=actor,
        target_table="vocabulary_terms",
        target_id=target.id,
        target_label=target.value,
        changes={"merged_from": {"before": source.value, "after": target.value}},
    )
    db.delete(source)
    db.commit()
    db.refresh(target)
    return target


# --- 조건 정의 ---------------------------------------------------------------


def _condition_usage(db: Session, condition_key_id: uuid.UUID) -> int:
    limits = (
        db.scalar(
            select(func.count())
            .select_from(EquipmentTestCondition)
            .where(EquipmentTestCondition.condition_key_id == condition_key_id)
        )
        or 0
    )
    requirements = (
        db.scalar(
            select(func.count())
            .select_from(MethodRequirement)
            .where(MethodRequirement.condition_key_id == condition_key_id)
        )
        or 0
    )
    return limits + requirements


def condition_out(db: Session, row: ConditionKey) -> ConditionKeyOut:
    return ConditionKeyOut(
        id=row.id,
        key=row.key,
        label=row.label,
        kind=row.kind,
        dimension=row.dimension,
        si_unit=row.si_unit,
        display_unit=row.display_unit,
        choices=row.choices,
        help=row.help,
        sort_order=row.sort_order,
        is_active=row.is_active,
        usage_count=_condition_usage(db, row.id),
    )


def list_conditions(db: Session, *, include_inactive: bool) -> list[ConditionKeyOut]:
    stmt = select(ConditionKey)
    if not include_inactive:
        stmt = stmt.where(ConditionKey.is_active.is_(True))
    rows = db.scalars(stmt.order_by(ConditionKey.sort_order, ConditionKey.label))
    return [condition_out(db, row) for row in rows]


def get_condition(db: Session, condition_id: uuid.UUID) -> ConditionKey:
    found = db.get(ConditionKey, condition_id)
    if found is None:
        raise NotFound("TSC-VOCAB-0008", "조건 정의를 찾을 수 없습니다.")
    return found


def create_condition(db: Session, *, payload: dict[str, Any]) -> ConditionKey:
    if db.scalar(select(ConditionKey).where(ConditionKey.key == payload["key"])) is not None:
        raise Conflict("TSC-VOCAB-0009", f"이미 있는 조건 키입니다: {payload['key']}")
    row = ConditionKey(**payload)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_condition(
    db: Session, *, condition_id: uuid.UUID, changes: dict[str, Any], actor: User
) -> ConditionKey:
    """조건 정의를 고친다.

    **단위를 바꾸는 것은 되돌릴 수 없는 부류다.** kN 을 N 으로 고치는 순간, 이미
    저장된 숫자 전부가 다른 값이 된다 — 그때 무엇이 바뀌었는지 물을 자리가 감사
    기록밖에 없다. key 는 아예 못 바꾼다: 코드와 검색이 그 이름을 걸고 있다.
    """
    row = get_condition(db, condition_id)
    before = {
        "si_unit": row.si_unit,
        "display_unit": row.display_unit,
        "dimension": row.dimension,
        "is_active": row.is_active,
    }

    for field, value in changes.items():
        if value is not None:
            setattr(row, field, value)

    after = {
        "si_unit": row.si_unit,
        "display_unit": row.display_unit,
        "dimension": row.dimension,
        "is_active": row.is_active,
    }
    diff = audit.diff(before, after)
    if diff:
        audit.record(
            db,
            action=audit.CONDITION_KEY_CHANGED,
            actor=actor,
            target_table="condition_keys",
            target_id=row.id,
            target_label=row.label,
            changes=diff,
        )
    db.commit()
    db.refresh(row)
    return row


# --- 사양 정의 ---------------------------------------------------------------
#
# 조건 정의(ConditionKey)와 나란한 자리다. 조건은 검색이 묻는 일곱 축이고, 사양은
# 사양서에 적힌 수백 칸이다. 한 표로 합치면 검색 폼에 외형 치수가 뜬다(ADR 0005).


def _definition_count(db: Session, group_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(SpecDefinition)
            .where(SpecDefinition.group_id == group_id)
        )
        or 0
    )


def group_out(db: Session, row: SpecGroup) -> SpecGroupOut:
    return SpecGroupOut(
        id=row.id,
        slug=row.slug,
        label=row.label,
        description=row.description,
        sort_order=row.sort_order,
        definition_count=_definition_count(db, row.id),
    )


def list_spec_groups(db: Session) -> list[SpecGroupOut]:
    rows = db.scalars(select(SpecGroup).order_by(SpecGroup.sort_order, SpecGroup.label))
    return [group_out(db, row) for row in rows]


def get_spec_group(db: Session, group_id: uuid.UUID) -> SpecGroup:
    found = db.get(SpecGroup, group_id)
    if found is None:
        raise NotFound("TSC-SPEC-0001", "사양 그룹을 찾을 수 없습니다.")
    return found


def create_spec_group(db: Session, *, payload: dict[str, Any]) -> SpecGroup:
    if db.scalar(select(SpecGroup).where(SpecGroup.slug == payload["slug"])) is not None:
        raise Conflict("TSC-SPEC-0002", f"이미 있는 그룹 키입니다: {payload['slug']}")
    row = SpecGroup(**payload)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_spec_group(
    db: Session, *, group_id: uuid.UUID, changes: dict[str, Any]
) -> SpecGroup:
    row = get_spec_group(db, group_id)
    for field, value in changes.items():
        if value is not None:
            setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row


def delete_spec_group(db: Session, group_id: uuid.UUID) -> None:
    """**든 사양이 있으면 거절한다.** 그룹은 사양이 매달리는 자리라 지우면 그
    사양들이 어디에 속했는지가 사라진다 — DB 도 RESTRICT 로 막지만, 그때 나오는
    말은 사람이 읽을 수 없다."""
    row = get_spec_group(db, group_id)
    using = _definition_count(db, row.id)
    if using:
        raise Conflict(
            "TSC-SPEC-0003",
            f"이 그룹에 사양이 {using}개 있습니다. 먼저 다른 그룹으로 옮기세요.",
        )
    db.delete(row)
    db.commit()


def _definition_categories(db: Session, definition_id: uuid.UUID) -> list[VocabularyTerm]:
    return list(
        db.scalars(
            select(VocabularyTerm)
            .join(
                SpecDefinitionCategory,
                SpecDefinitionCategory.category_term_id == VocabularyTerm.id,
            )
            .where(SpecDefinitionCategory.definition_id == definition_id)
            .order_by(VocabularyTerm.value)
        )
    )


def _definition_usage(db: Session, definition_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(ModelSpecValue)
            .where(ModelSpecValue.definition_id == definition_id)
        )
        or 0
    )


def definition_out(db: Session, row: SpecDefinition) -> SpecDefinitionOut:
    group = db.get(SpecGroup, row.group_id)
    key = db.get(ConditionKey, row.condition_key_id) if row.condition_key_id else None
    terms = _definition_categories(db, row.id)
    return SpecDefinitionOut(
        id=row.id,
        key=row.key,
        label=row.label,
        group_id=row.group_id,
        group_slug=group.slug if group else "",
        group_label=group.label if group else "",
        kind=row.kind,
        dimension=row.dimension,
        si_unit=row.si_unit,
        display_unit=row.display_unit,
        choices=row.choices,
        condition_key_id=row.condition_key_id,
        condition_label=key.label if key else None,
        reflect_as=row.reflect_as,
        help=row.help,
        sort_order=row.sort_order,
        is_active=row.is_active,
        category_term_ids=[term.id for term in terms],
        categories=[term.value for term in terms],
        usage_count=_definition_usage(db, row.id),
    )


def list_spec_definitions(
    db: Session,
    *,
    include_inactive: bool,
    group_id: uuid.UUID | None = None,
    category_term_id: uuid.UUID | None = None,
) -> list[SpecDefinitionOut]:
    """사양 정의 목록.

    **분류로 거르면 공통도 함께 준다.** 공통 사양은 붙은 분류 행이 없어서, 조인으로
    거르면 통째로 사라진다 — 그러면 전원·무게가 어느 장비 화면에도 안 뜬다.
    """
    stmt = select(SpecDefinition)
    if not include_inactive:
        stmt = stmt.where(SpecDefinition.is_active.is_(True))
    if group_id is not None:
        stmt = stmt.where(SpecDefinition.group_id == group_id)
    if category_term_id is not None:
        matching = select(SpecDefinitionCategory.definition_id).where(
            SpecDefinitionCategory.category_term_id == category_term_id
        )
        common = select(SpecDefinitionCategory.definition_id)
        stmt = stmt.where(SpecDefinition.id.in_(matching) | SpecDefinition.id.not_in(common))
    rows = db.scalars(stmt.order_by(SpecDefinition.sort_order, SpecDefinition.label))
    return [definition_out(db, row) for row in rows]


def get_spec_definition(db: Session, definition_id: uuid.UUID) -> SpecDefinition:
    found = db.get(SpecDefinition, definition_id)
    if found is None:
        raise NotFound("TSC-SPEC-0004", "사양 정의를 찾을 수 없습니다.")
    return found


def _set_definition_categories(
    db: Session, definition: SpecDefinition, term_ids: list[uuid.UUID]
) -> None:
    """붙는 분류를 **통째로 바꾼다.** 빈 목록이면 공통이 된다.

    고를 수 있는 것은 장비 분류 축의 값뿐이다 — 제조사나 시험 항목을 넣으면 그
    사양은 어느 화면에도 안 뜨고, 안 뜨는 이유를 화면이 말해 주지 않는다.
    """
    axis = get_vocabulary(db, "equipment_category")
    for term_id in term_ids:
        term = db.get(VocabularyTerm, term_id)
        if term is None or term.vocabulary_id != axis.id:
            raise AppError(
                "TSC-SPEC-0005", "장비 분류 축의 값만 고를 수 있습니다.", status=400
            )

    for old in db.scalars(
        select(SpecDefinitionCategory).where(
            SpecDefinitionCategory.definition_id == definition.id
        )
    ):
        db.delete(old)
    db.flush()
    for term_id in dict.fromkeys(term_ids):
        db.add(SpecDefinitionCategory(definition_id=definition.id, category_term_id=term_id))


def create_spec_definition(db: Session, *, payload: dict[str, Any]) -> SpecDefinition:
    if (
        db.scalar(select(SpecDefinition).where(SpecDefinition.key == payload["key"]))
        is not None
    ):
        raise Conflict("TSC-SPEC-0006", f"이미 있는 사양 키입니다: {payload['key']}")
    get_spec_group(db, payload["group_id"])

    term_ids: list[uuid.UUID] = payload.pop("category_term_ids", [])
    row = SpecDefinition(**payload)
    db.add(row)
    db.flush()
    _set_definition_categories(db, row, term_ids)
    db.commit()
    db.refresh(row)
    return row


def update_spec_definition(
    db: Session, *, definition_id: uuid.UUID, changes: dict[str, Any], actor: User
) -> SpecDefinition:
    """사양 정의를 고친다.

    **key 와 kind 는 못 바꾼다.** key 는 코드와 반입 스크립트가 걸고 있고, kind 는
    값이 어느 칸에 담겼는지를 정한다 — number 를 text 로 바꾸면 이미 저장된 숫자가
    읽히지 않는 칸에 남는다. 바꾸려면 새로 만들고 옛것을 끈다.

    단위를 바꾸는 것은 조건 정의와 같은 부류다. 이미 저장된 숫자 전부의 뜻이 바뀌니
    감사 기록에 남긴다.
    """
    row = get_spec_definition(db, definition_id)
    before = {
        "si_unit": row.si_unit,
        "display_unit": row.display_unit,
        "condition_key_id": str(row.condition_key_id) if row.condition_key_id else None,
        "reflect_as": row.reflect_as,
        "is_active": row.is_active,
    }

    if changes.get("group_id") is not None:
        get_spec_group(db, changes["group_id"])
    if "category_term_ids" in changes and changes["category_term_ids"] is not None:
        _set_definition_categories(db, row, changes["category_term_ids"])

    for field, value in changes.items():
        if field == "category_term_ids":
            continue
        # condition_key_id 는 None 으로 지울 일이 있는 칸이지만, 부분 수정에서
        # None 은 "안 바꿈" 이다. 끊으려면 사양을 끄거나 새로 정의한다 —
        # 조용히 끊기면 그 사양이 왜 검색에서 사라졌는지 아무도 못 찾는다.
        if value is not None:
            setattr(row, field, value)

    after = {
        "si_unit": row.si_unit,
        "display_unit": row.display_unit,
        "condition_key_id": str(row.condition_key_id) if row.condition_key_id else None,
        "reflect_as": row.reflect_as,
        "is_active": row.is_active,
    }
    diff = audit.diff(before, after)
    if diff:
        audit.record(
            db,
            action=audit.SPEC_DEFINITION_CHANGED,
            actor=actor,
            target_table="spec_definitions",
            target_id=row.id,
            target_label=row.label,
            changes=diff,
        )
    db.commit()
    db.refresh(row)
    return row


def delete_spec_definition(db: Session, definition_id: uuid.UUID) -> None:
    """**적힌 값이 있으면 거절한다.** 지우는 대신 끈다(`is_active`) — 지우면 그
    숫자가 무엇이었는지 알 수 없게 된다."""
    row = get_spec_definition(db, definition_id)
    using = _definition_usage(db, row.id)
    if using:
        raise Conflict(
            "TSC-SPEC-0007",
            f"이 사양으로 적힌 값이 {using}개 있습니다. 지우는 대신 끄세요.",
        )
    db.delete(row)
    db.commit()

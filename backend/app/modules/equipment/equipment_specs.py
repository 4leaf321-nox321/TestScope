"""개체 사양 — **카탈로그 값 위에 실측을 덮는다.**

기종 사양(`specs.py`)은 「제조사가 그렇게 적었다」 이고, 여기 값은 「우리가 이 대를
재 보니 그렇더라」 다. 둘은 믿는 정도가 다르므로 **둘 다 남는다.**

## 복사가 아니라 겹쳐 보기

등록할 때 기종 사양을 개체로 복사해 두지 않는다. 개체는 **다른 값만** 갖고 나머지는
기종 사양이 그대로 보인다. 전부 복사하면 두 가지를 잃는다 — 카탈로그가 개정돼도 안
따라오고, 무엇보다 어느 값이 실측인지 구별이 사라진다.

시험 항목을 복사로 둔 것(ADR 0004)과 다른 판단이다. 시험 항목은 「그때 그렇게 판단했다」 는
스냅샷이라 굳는 것이 맞고, 사양 수치는 두 출처가 함께 보여야 사람이 고를 수 있다.

## 검색축에 이어진 사양은 시험 조건을 갱신한다

기종 사양이 등록 시점에 그랬듯이, 실측도 이 장비의 시험 조건으로 들어간다. 다만
**손으로 고쳐 둔 조건은 안 덮는다** — 사람이 재서 적은 값을 사양표가 덮으면 그
손실은 검색 결과가 어긋난 날에야 드러난다.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.equipment import specs
from app.modules.equipment.models import (
    Equipment,
    EquipmentModel,
    EquipmentSpecValue,
    ModelSpecValue,
    SpecSource,
)
from app.modules.equipment.schemas import (
    EquipmentSpecGroupOut,
    EquipmentSpecItemOut,
    EquipmentSpecSheetOut,
    EquipmentSpecValueOut,
)
from app.modules.test_items.models import EquipmentTestCondition, EquipmentTestItem
from app.modules.vocabulary.models import ConditionKey
from app.modules.vocabulary.specs import SpecDefinition, SpecGroup
from app.shared.errors import AppError, NotFound

#: 값이 담기는 칸들. 기종 사양과 같은 규칙이다 — 종류에 안 맞는 칸은 비운다.
_VALUE_FIELDS = ("num_value", "num_min", "num_max", "text_value", "bool_value")

#: 사양에서 따라 들어온 조건에 남기는 꼬리표.
#:
#: **이것이 붙은 조건만 다시 덮는다.** 사람이 직접 적은 조건과 구별할 방법이 이것뿐이고,
#: 구별하지 못하면 실측을 저장할 때마다 손으로 고쳐 둔 값이 조용히 사라진다.
_FROM_SPEC = "사양"
_FROM_MEASURED = "실측"


def _measured_out(db: Session, row: EquipmentSpecValue) -> EquipmentSpecValueOut:
    source = db.get(SpecSource, row.source_id) if row.source_id else None
    return EquipmentSpecValueOut(
        id=row.id,
        num_value=row.num_value,
        num_min=row.num_min,
        num_max=row.num_max,
        text_value=row.text_value,
        bool_value=row.bool_value,
        measured_on=row.measured_on,
        note=row.note,
        source_id=row.source_id,
        source_path=source.path if source else None,
        source_page=row.source_page,
        updated_at=row.updated_at,
    )


def sheet(db: Session, equipment: Equipment) -> EquipmentSpecSheetOut:
    """이 장비의 사양표 — 기종 값과 실측을 **한 줄에 함께** 담는다.

    두 출처를 따로 주면 화면이 그것을 맞추게 되고, 맞추는 코드는 화면마다 조금씩
    달라진다. 어느 화면에서는 실측이 이기고 어느 화면에서는 사양서가 이기는 상태가
    그렇게 생긴다.
    """
    model = db.get(EquipmentModel, equipment.model_id) if equipment.model_id else None

    catalog: dict[uuid.UUID, ModelSpecValue] = {}
    if model is not None:
        for stated_row in db.scalars(
            select(ModelSpecValue).where(ModelSpecValue.model_id == model.id)
        ):
            catalog[stated_row.definition_id] = stated_row

    measured: dict[uuid.UUID, EquipmentSpecValue] = {}
    for measured_row in db.scalars(
        select(EquipmentSpecValue).where(EquipmentSpecValue.equipment_id == equipment.id)
    ):
        measured[measured_row.definition_id] = measured_row

    wanted = set(catalog) | set(measured)
    if not wanted:
        return EquipmentSpecSheetOut(
            equipment_id=equipment.id,
            model_id=equipment.model_id,
            model_name=model.name if model else None,
            groups=[],
            override_count=0,
        )

    rows = db.execute(
        select(SpecDefinition, SpecGroup)
        .join(SpecGroup, SpecGroup.id == SpecDefinition.group_id)
        .where(SpecDefinition.id.in_(wanted))
        .order_by(
            SpecGroup.sort_order,
            SpecGroup.label,
            SpecDefinition.sort_order,
            SpecDefinition.label,
        )
    ).all()

    category = specs.category_of(db, model) if model else equipment.category_term_id
    groups: list[EquipmentSpecGroupOut] = []
    for definition, group in rows:
        if not groups or groups[-1].group_id != group.id:
            groups.append(
                EquipmentSpecGroupOut(
                    group_id=group.id,
                    slug=group.slug,
                    label=group.label,
                    description=group.description,
                    items=[],
                )
            )
        stated = catalog.get(definition.id)
        groups[-1].items.append(
            EquipmentSpecItemOut(
                definition_id=definition.id,
                key=definition.key,
                label=definition.label,
                kind=definition.kind,
                si_unit=definition.si_unit,
                display_unit=definition.display_unit,
                choices=definition.choices,
                sort_order=definition.sort_order,
                condition_key_id=definition.condition_key_id,
                catalog=(
                    specs.value_out(db, stated, definition, category_term_id=category)
                    if stated is not None
                    else None
                ),
                measured=(
                    _measured_out(db, measured[definition.id])
                    if definition.id in measured
                    else None
                ),
            )
        )
    return EquipmentSpecSheetOut(
        equipment_id=equipment.id,
        model_id=equipment.model_id,
        model_name=model.name if model else None,
        groups=groups,
        override_count=len(measured),
    )


def _as_condition(
    definition: SpecDefinition, row: EquipmentSpecValue
) -> tuple[float | None, float | None] | None:
    """이 값이 검색 조건의 어느 끝인가. 기종 사양과 **같은 규칙**이다.

    구간은 양끝을 그대로 쓰고, 수치 하나는 `reflect_as` 가 정한다 — 최대하중은
    천장이고 분해능은 바닥이다. 고른 값·문장·참거짓은 범위 비교가 성립하지 않아
    조건으로 안 옮긴다.
    """
    if definition.kind == "range":
        low, high = row.num_min, row.num_max
    elif definition.kind == "number":
        low = row.num_value if definition.reflect_as == "min" else None
        high = row.num_value if definition.reflect_as == "max" else None
    else:
        return None
    if low is None and high is None:
        return None
    return low, high


def _reflect(
    db: Session, equipment: Equipment, definition: SpecDefinition, row: EquipmentSpecValue
) -> bool:
    """실측을 이 장비의 시험 조건으로 옮긴다. 하나라도 바꿨으면 참.

    **손으로 고쳐 둔 조건은 안 덮는다.** 사양에서 따라온 조건에는 꼬리표가 붙어
    있어서(`_FROM_SPEC`·`_FROM_MEASURED`), 그것이 없는 조건은 사람이 적은 것으로 본다.
    구별을 포기하면 실측을 저장할 때마다 실측이 실측을 덮는 꼴이 된다.
    """
    if definition.condition_key_id is None:
        return False
    bounds = _as_condition(definition, row)
    if bounds is None:
        return False
    low, high = bounds

    changed = False
    for test_item in db.scalars(
        select(EquipmentTestItem).where(EquipmentTestItem.equipment_id == equipment.id)
    ):
        limit = db.scalar(
            select(EquipmentTestCondition).where(
                EquipmentTestCondition.equipment_test_item_id == test_item.id,
                EquipmentTestCondition.condition_key_id == definition.condition_key_id,
            )
        )
        if limit is None:
            db.add(
                EquipmentTestCondition(
                    equipment_test_item_id=test_item.id,
                    condition_key_id=definition.condition_key_id,
                    min_value=low,
                    max_value=high,
                    note=f"{_FROM_MEASURED} {definition.label}에서 따옴",
                )
            )
            changed = True
            continue
        if limit.note is None or not limit.note.startswith((_FROM_SPEC, _FROM_MEASURED)):
            # 사람이 적은 조건이다. **그대로 둔다** — 실측 한 칸이 손으로 확인한
            # 범위를 덮으면, 그 손실은 검색이 틀린 답을 낸 날에야 드러난다.
            continue
        limit.min_value = low
        limit.max_value = high
        limit.note = f"{_FROM_MEASURED} {definition.label}에서 따옴"
        changed = True
    return changed


def upsert(
    db: Session, equipment: Equipment, payload: dict[str, Any], actor: User
) -> tuple[EquipmentSpecValueOut, str | None, bool]:
    """실측 한 칸을 넣거나 덮어쓴다. (값, 이어진 검색축 이름, 시험 항목에 반영됐나).

    검증은 기종 사양과 **같은 함수**를 쓴다 — 두 벌로 두면 한쪽만 고쳐지고, 그때부터
    같은 값이 한 화면에서는 저장되고 다른 화면에서는 거절된다.
    """
    definition = specs.get_definition(db, payload["definition_id"])
    if not definition.is_active:
        raise AppError(
            "TSC-SPEC-0012",
            f"{definition.label}은(는) 더 쓰지 않는 사양입니다.",
            status=400,
        )
    specs.check_value(definition, payload)

    if (
        payload.get("source_id") is not None
        and db.get(SpecSource, payload["source_id"]) is None
    ):
        raise NotFound("TSC-SPEC-0013", "출처 문서를 찾을 수 없습니다.")

    row = db.scalar(
        select(EquipmentSpecValue).where(
            EquipmentSpecValue.equipment_id == equipment.id,
            EquipmentSpecValue.definition_id == definition.id,
        )
    )
    if row is None:
        row = EquipmentSpecValue(
            equipment_id=equipment.id,
            definition_id=definition.id,
            created_by_id=actor.id,
        )
        db.add(row)

    # **종류에 안 맞는 칸은 비운다.** 남겨 두면 number 로 고친 사양에 옛 구간이 붙어
    # 있고, 화면마다 어느 칸을 읽느냐에 따라 다른 값이 보인다.
    for field in _VALUE_FIELDS:
        setattr(row, field, payload.get(field))
    row.measured_on = payload.get("measured_on")
    row.note = payload.get("note")
    row.source_id = payload.get("source_id")
    row.source_page = payload.get("source_page")
    db.flush()

    reflected = _reflect(db, equipment, definition, row)
    db.commit()
    db.refresh(row)

    axis = (
        db.get(ConditionKey, definition.condition_key_id)
        if definition.condition_key_id
        else None
    )
    return _measured_out(db, row), (axis.label if axis else None), reflected


def delete(db: Session, equipment: Equipment, definition_id: uuid.UUID) -> None:
    """실측을 지운다 — 그 칸은 다시 카탈로그 값으로 보인다.

    **따라 들어간 시험 조건은 안 지운다.** 그 조건은 이미 이 장비의 것이고, 그 사이에
    사람이 고쳐 뒀을 수 있다. 사양표를 정리했다고 시험 항목이 조용히 줄면 검색 결과가
    이유 없이 바뀐다(기종 사양의 규칙과 같다).
    """
    row = db.scalar(
        select(EquipmentSpecValue).where(
            EquipmentSpecValue.equipment_id == equipment.id,
            EquipmentSpecValue.definition_id == definition_id,
        )
    )
    if row is None:
        raise NotFound("TSC-SPEC-0015", "이 장비에 적힌 실측 사양이 아닙니다.")
    db.delete(row)
    db.commit()

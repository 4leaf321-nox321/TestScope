"""모델의 사양 **값** — 넣고, 읽고, 역량으로 반영한다.

정의는 `vocabulary/specs.py` 에 있다. 여기는 그 정의에 실제 숫자를 채우는 자리다.

## 값이 있는 것만 준다

정의는 수백 개고 대부분의 모델은 그중 스물을 채운다. 빈 칸까지 다 내보내면 목록
한 번에 수백 줄이 오가고, 화면은 그 대부분을 회색으로 그린다. **빈 칸 목록은
정의 API 가 준다** — 화면이 둘을 겹쳐 그린다.

## 분류 밖 사양도 지운 적 없다

정의에 붙은 분류가 이 모델의 분류와 안 맞아도 값은 그대로 보여 준다(`applies`
가 false 로 온다). 분류를 나중에 고쳤다고 이미 적은 사양이 화면에서 사라지면,
사람은 그것이 지워졌다고 믿는다(ADR 0005).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.equipment.models import (
    Equipment,
    EquipmentModel,
    EquipmentSeries,
    ModelSpecValue,
    SpecSource,
)
from app.modules.equipment.schemas import (
    ModelSpecGroupOut,
    ModelSpecSheetOut,
    ModelSpecValueOut,
)
from app.modules.vocabulary.models import ConditionKey
from app.modules.vocabulary.specs import (
    SpecDefinition,
    SpecDefinitionCategory,
    SpecGroup,
)
from app.shared.errors import AppError, NotFound

#: 값이 담기는 칸들. 종류마다 채우는 것이 다르고, 나머지는 비워 둔다.
_VALUE_FIELDS = ("num_value", "num_min", "num_max", "text_value", "bool_value")


def category_of(db: Session, model: EquipmentModel) -> uuid.UUID | None:
    """이 기종의 장비 분류. **계열이 갖는다** — 기종마다 적으면 열 번 다 같을 이유가
    없고, 그때 사양표에 뜨는 칸이 기종마다 달라진다."""
    series = db.get(EquipmentSeries, model.series_id)
    return series.category_term_id if series else None


def get_definition(db: Session, definition_id: uuid.UUID) -> SpecDefinition:
    found = db.get(SpecDefinition, definition_id)
    if found is None:
        raise NotFound("TAS-SPEC-0004", "사양 정의를 찾을 수 없습니다.")
    return found


def _applies_to(
    db: Session, definition_id: uuid.UUID, category_term_id: uuid.UUID | None
) -> bool:
    """이 정의가 그 분류의 장비에 붙나. **붙은 분류가 없으면 공통이라 언제나 참.**"""
    rows = list(
        db.scalars(
            select(SpecDefinitionCategory.category_term_id).where(
                SpecDefinitionCategory.definition_id == definition_id
            )
        )
    )
    if not rows:
        return True
    return category_term_id in rows


def value_out(
    db: Session,
    row: ModelSpecValue,
    definition: SpecDefinition,
    *,
    category_term_id: uuid.UUID | None,
) -> ModelSpecValueOut:
    source = db.get(SpecSource, row.source_id) if row.source_id else None
    return ModelSpecValueOut(
        id=row.id,
        definition_id=definition.id,
        key=definition.key,
        label=definition.label,
        kind=definition.kind,
        si_unit=definition.si_unit,
        display_unit=definition.display_unit,
        choices=definition.choices,
        sort_order=definition.sort_order,
        is_active=definition.is_active,
        condition_key_id=definition.condition_key_id,
        applies=_applies_to(db, definition.id, category_term_id),
        num_value=row.num_value,
        num_min=row.num_min,
        num_max=row.num_max,
        text_value=row.text_value,
        bool_value=row.bool_value,
        note=row.note,
        source_id=row.source_id,
        source_path=source.path if source else None,
        source_page=row.source_page,
        updated_at=row.updated_at,
    )


def sheet(db: Session, model: EquipmentModel) -> ModelSpecSheetOut:
    """이 기종에 적힌 사양을 그룹 순서대로 준다."""
    category = category_of(db, model)
    rows = db.execute(
        select(ModelSpecValue, SpecDefinition, SpecGroup)
        .join(SpecDefinition, SpecDefinition.id == ModelSpecValue.definition_id)
        .join(SpecGroup, SpecGroup.id == SpecDefinition.group_id)
        .where(ModelSpecValue.model_id == model.id)
        .order_by(
            SpecGroup.sort_order,
            SpecGroup.label,
            SpecDefinition.sort_order,
            SpecDefinition.label,
        )
    ).all()

    groups: list[ModelSpecGroupOut] = []
    for value, definition, group in rows:
        if not groups or groups[-1].group_id != group.id:
            groups.append(
                ModelSpecGroupOut(
                    group_id=group.id,
                    slug=group.slug,
                    label=group.label,
                    description=group.description,
                    items=[],
                )
            )
        groups[-1].items.append(value_out(db, value, definition, category_term_id=category))
    return ModelSpecSheetOut(model_id=model.id, groups=groups)


def _check(definition: SpecDefinition, payload: dict[str, Any]) -> None:
    """종류에 맞는 칸이 채워졌나 본다.

    **틀린 칸에 담긴 값은 조용히 사라진다.** 구간 사양에 num_value 만 보내면 저장은
    되지만 화면은 아무것도 못 그리고, 그때 사람은 "저장이 안 됐다" 고 말한다.
    """
    kind = definition.kind
    if kind == "number" and payload.get("num_value") is None:
        raise AppError("TAS-SPEC-0008", f"{definition.label}: 값이 필요합니다.", status=400)
    if kind == "range":
        low, high = payload.get("num_min"), payload.get("num_max")
        if low is None and high is None:
            raise AppError(
                "TAS-SPEC-0009",
                f"{definition.label}: 최소나 최대 중 하나는 있어야 합니다.",
                status=400,
            )
        if low is not None and high is not None and low > high:
            raise AppError(
                "TAS-SPEC-0010", f"{definition.label}: 최소가 최대보다 큽니다.", status=400
            )
    if kind in ("choice", "text") and not payload.get("text_value"):
        raise AppError("TAS-SPEC-0008", f"{definition.label}: 값이 필요합니다.", status=400)
    if (
        kind == "choice"
        and definition.choices
        and payload["text_value"] not in definition.choices
    ):
        raise AppError(
            "TAS-SPEC-0011",
            f"{definition.label}: 고를 수 있는 값이 아닙니다 "
            f"({', '.join(definition.choices)}).",
            status=400,
        )
    if kind == "boolean" and payload.get("bool_value") is None:
        raise AppError("TAS-SPEC-0008", f"{definition.label}: 값이 필요합니다.", status=400)


def conditions_from_specs(
    db: Session, model_id: uuid.UUID
) -> dict[uuid.UUID, tuple[float | None, float | None, str]]:
    """이 기종의 사양에서 **검색 조건을 뽑는다.** {조건 id: (최소, 최대, 사양 이름)}.

    ## 왜 저장할 때가 아니라 여기서 계산하나

    역량은 계열에 붙고 사양은 기종에 붙는다(ADR 0006). 사양을 저장하는 순간 계열
    역량에 써 넣으면, 0.5 kN 짜리 기종의 값이 그 계열 전체의 조건이 된다 — 같은
    계열의 300 kN 짜리가 검색에서 0.5 kN 으로 답한다.

    그래서 **보유 장비를 만들 때** 그 장비가 가리키는 기종의 사양으로 계산한다.
    그때 비로소 「어느 기종의 것인가」 가 하나로 정해진다.

    ## 종류에 따라 어느 끝인지가 갈린다

    구간은 양끝을 그대로 쓴다. 수치 하나는 `reflect_as` 가 정한다 — 최대하중은
    천장이고 최소 게이지 폭은 바닥이다. **하나로 정해 두면 절반이 거꾸로 반영되고,
    거꾸로 반영된 값은 검색이 조용히 틀린 답을 내는 방식으로만 드러난다.**

    고른 값·문장·참거짓은 뺀다. 범위 비교가 성립하지 않아서, 검색이 그것을
    숫자처럼 다루면 아무것도 안 맞거나 전부 맞는다.
    """
    out: dict[uuid.UUID, tuple[float | None, float | None, str]] = {}
    rows = db.execute(
        select(ModelSpecValue, SpecDefinition)
        .join(SpecDefinition, SpecDefinition.id == ModelSpecValue.definition_id)
        .where(
            ModelSpecValue.model_id == model_id,
            SpecDefinition.condition_key_id.is_not(None),
        )
    ).all()
    for value, definition in rows:
        if definition.kind == "range":
            low, high = value.num_min, value.num_max
        elif definition.kind == "number":
            low = value.num_value if definition.reflect_as == "min" else None
            high = value.num_value if definition.reflect_as == "max" else None
        else:
            continue
        if low is None and high is None:
            continue
        assert definition.condition_key_id is not None  # 위 where 절이 보장한다
        out[definition.condition_key_id] = (low, high, definition.label)
    return out


def upsert(
    db: Session, model: EquipmentModel, payload: dict[str, Any]
) -> tuple[ModelSpecValueOut, str | None, int]:
    """사양 값 하나를 넣거나 덮어쓴다. (값, 이어진 검색축 이름, 이미 등록된 대수).

    ## 왜 둘을 더 돌려주나

    화면이 "저장했습니다" 만 말하면 두 가지를 사람이 알 수 없다.

    **이 숫자가 검색에 쓰이나** — 검색축에 이어진 사양만 역량 조건이 된다. 이어져
    있으면 그 축 이름을 말해 준다.

    **이미 등록된 장비는 어떻게 되나** — 안 바뀐다(ADR 0004 의 복사 규칙). 대수를
    말해 주지 않으면 사람은 바뀌었다고 믿고, 그 믿음은 검색 결과가 어긋난 날에야
    깨진다.
    """
    definition = get_definition(db, payload["definition_id"])
    if not definition.is_active:
        raise AppError(
            "TAS-SPEC-0012",
            f"{definition.label}은(는) 더 쓰지 않는 사양입니다.",
            status=400,
        )
    _check(definition, payload)

    if (
        payload.get("source_id") is not None
        and db.get(SpecSource, payload["source_id"]) is None
    ):
        raise NotFound("TAS-SPEC-0013", "출처 문서를 찾을 수 없습니다.")

    row = db.scalar(
        select(ModelSpecValue).where(
            ModelSpecValue.model_id == model.id,
            ModelSpecValue.definition_id == definition.id,
        )
    )
    if row is None:
        row = ModelSpecValue(model_id=model.id, definition_id=definition.id)
        db.add(row)

    # **종류에 안 맞는 칸은 비운다.** 남겨 두면 number 로 고친 사양에 옛 구간이
    # 그대로 붙어 있고, 화면마다 어느 칸을 읽느냐에 따라 다른 값이 보인다.
    for field in _VALUE_FIELDS:
        setattr(row, field, payload.get(field))
    row.note = payload.get("note")
    row.source_id = payload.get("source_id")
    row.source_page = payload.get("source_page")
    db.commit()
    db.refresh(row)

    axis = (
        db.get(ConditionKey, definition.condition_key_id)
        if definition.condition_key_id
        else None
    )
    units = (
        db.scalar(
            select(func.count())
            .select_from(Equipment)
            .where(Equipment.model_id == model.id, Equipment.deleted_at.is_(None))
        )
        or 0
    )
    return (
        value_out(db, row, definition, category_term_id=category_of(db, model)),
        axis.label if axis else None,
        units,
    )


def delete(db: Session, model: EquipmentModel, definition_id: uuid.UUID) -> None:
    """사양 값을 지운다.

    **따라 들어간 역량 조건은 안 지운다.** 그 조건은 이미 이 모델의 것이고, 그
    사이에 사람이 고쳐 뒀을 수 있다 — 사양표를 정리했다고 역량이 조용히 줄면
    검색 결과가 이유 없이 바뀐다.
    """
    row = db.scalar(
        select(ModelSpecValue).where(
            ModelSpecValue.model_id == model.id,
            ModelSpecValue.definition_id == definition_id,
        )
    )
    if row is None:
        raise NotFound("TAS-SPEC-0014", "이 모델에 적힌 사양이 아닙니다.")
    db.delete(row)
    db.commit()

"""이 기종만의 사양 — **정의 없이 기종에 붙는 값, 그리고 그것을 정의로 올리는 길.**

카탈로그 원본의 사양 키 950종 중 803종이 한 기종에만 나온다. 정의로 다 세우면 「사양
추가」 목록이 못 쓰게 되고(ADR 0005 를 쓰게 한 그 실패), 버리면 그 기종을 아는 데 필요한
것이 원문 JSON 안에만 남는다. 여기는 그 사이 자리다.

## 정의로 올리기는 사람이 누른다

기계가 이름을 지어내면 그것이 진실이 된다 — `stroke_mm_pk_pk` 를 「스트로크 밀리미터
피크피크」 로 세우면 아무도 못 고친다. 그래서 「정의로 세우기」 는 이름·단위·종류를 사람이
적어 누르는 것이고, 누르는 순간 같은 원본 키를 가진 다른 기종의 줄도 함께 옮겨 간다 —
한 기종만 옮기면 같은 값이 두 자리에 산다.

수치로 못 읽는 줄(「약 300」)은 **그대로 둔다.** 지어서 300 으로 옮기면 「약」 이 사라진다.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.equipment.models import EquipmentModel, ModelFreeSpec, ModelSpecValue
from app.modules.equipment.schemas import FreeSpecOut, FreeSpecPromoteResult
from app.modules.equipment.specs import category_of
from app.modules.vocabulary.specs import SpecDefinition, SpecDefinitionCategory, SpecGroup
from app.shared.errors import AppError, Conflict, NotFound
from app.shared.text import clean

_NUMBER = re.compile(r"^[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?$")
#: 「0 ~ 600」 · 「0-600」 · 「0 to 600」. 엔 대시(U+2013)도 받는다 — 카탈로그가 그렇게 적는다.
_RANGE = re.compile(
    r"^([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)?\s*(?:~|\u2013|-|to|\u2026)\s*"
    r"([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)?$"
)


def _same_key_counts(db: Session, rows: list[ModelFreeSpec]) -> dict[str, int]:
    """원본 키마다 그 키를 가진 **다른** 기종 수. 0 이 아니면 정의로 세울 때다."""
    keys = {row.source_key for row in rows if row.source_key}
    if not keys:
        return {}
    return {
        key: int(count) - 1
        for key, count in db.execute(
            select(ModelFreeSpec.source_key, func.count(func.distinct(ModelFreeSpec.model_id)))
            .where(ModelFreeSpec.source_key.in_(keys))
            .group_by(ModelFreeSpec.source_key)
        ).all()
    }


def list_out(db: Session, model_id: uuid.UUID) -> list[FreeSpecOut]:
    rows = list(
        db.scalars(
            select(ModelFreeSpec)
            .where(ModelFreeSpec.model_id == model_id)
            .order_by(ModelFreeSpec.label)
        )
    )
    counts = _same_key_counts(db, rows)
    return [
        FreeSpecOut(
            id=row.id,
            label=row.label,
            value_text=row.value_text,
            unit=row.unit,
            note=row.note,
            source_key=row.source_key,
            origin=row.origin,
            source_id=row.source_id,
            source_page=row.source_page,
            same_key_models=counts.get(row.source_key or "", 0),
        )
        for row in rows
    ]


def _get(db: Session, model: EquipmentModel, free_id: uuid.UUID) -> ModelFreeSpec:
    row = db.get(ModelFreeSpec, free_id)
    if row is None or row.model_id != model.id:
        raise NotFound("TSC-SPEC-0020", "이 기종의 사양을 찾을 수 없습니다.")
    return row


def add(db: Session, model: EquipmentModel, payload: dict[str, Any]) -> ModelFreeSpec:
    row = ModelFreeSpec(
        model_id=model.id,
        label=clean(payload["label"]),
        value_text=clean(payload["value_text"]),
        unit=clean(payload["unit"]) or None if payload.get("unit") else None,
        note=payload.get("note") or None,
        origin="manual",
        source_id=payload.get("source_id"),
        source_page=payload.get("source_page"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update(
    db: Session, model: EquipmentModel, free_id: uuid.UUID, payload: dict[str, Any]
) -> ModelFreeSpec:
    row = _get(db, model, free_id)
    row.label = clean(payload["label"])
    row.value_text = clean(payload["value_text"])
    row.unit = clean(payload["unit"]) or None if payload.get("unit") else None
    row.note = payload.get("note") or None
    row.source_id = payload.get("source_id")
    row.source_page = payload.get("source_page")
    db.commit()
    db.refresh(row)
    return row


def delete(db: Session, model: EquipmentModel, free_id: uuid.UUID) -> None:
    db.delete(_get(db, model, free_id))
    db.commit()


def _fields_for(kind: str, text: str) -> dict[str, Any] | None:
    """글자 값을 정의 종류의 칸으로. **못 읽으면 None** — 지어서 옮기지 않는다."""
    text = clean(text)
    if kind == "text":
        return {"text_value": text}
    if kind == "boolean":
        low = text.lower()
        if low in ("예", "있음", "true", "yes", "y", "o"):
            return {"bool_value": True}
        if low in ("아니오", "없음", "false", "no", "n", "x"):
            return {"bool_value": False}
        return None
    if kind == "number":
        return {"num_value": float(text)} if _NUMBER.match(text) else None
    if kind == "range":
        if _NUMBER.match(text):
            # 값 하나뿐이면 상한으로 본다 — 「1500」 은 「1500 까지」 다.
            return {"num_max": float(text)}
        match = _RANGE.match(text)
        if match is None or (match.group(1) is None and match.group(2) is None):
            return None
        return {
            "num_min": float(match.group(1)) if match.group(1) else None,
            "num_max": float(match.group(2)) if match.group(2) else None,
        }
    return None


def promote(
    db: Session, model: EquipmentModel, free_id: uuid.UUID, payload: dict[str, Any]
) -> FreeSpecPromoteResult:
    """이 기종만의 사양을 **정의로 세우고** 값을 옮긴다.

    정의는 이 기종의 분류에 붙는다 — 안 붙이면 공통이 되어 모든 장비의 「사양 추가」 에
    뜬다. 같은 원본 키를 가진 다른 기종의 줄은 함께 옮긴다(`apply_same_key`).
    """
    row = _get(db, model, free_id)
    key = payload["key"]
    if db.scalar(select(SpecDefinition).where(SpecDefinition.key == key)) is not None:
        raise Conflict("TSC-SPEC-0021", f"사양 정의 키 「{key}」 가 이미 있습니다.")
    group = db.get(SpecGroup, payload["group_id"])
    if group is None:
        raise NotFound("TSC-SPEC-0022", "사양 그룹을 찾을 수 없습니다.")
    kind = payload["kind"]
    unit = clean(payload.get("unit") or "")

    definition = SpecDefinition(
        key=key,
        label=clean(payload["label"]),
        group_id=group.id,
        kind=kind,
        dimension="",
        si_unit=unit,
        display_unit=unit,
        sort_order=900,
        help=(
            f"「기종 고유 사양」 에서 승격 — 원본 키 `{row.source_key}`."
            if row.source_key
            else "「기종 고유 사양」 에서 승격."
        ),
    )
    db.add(definition)
    db.flush()
    category = category_of(db, model)
    if category is not None:
        db.add(SpecDefinitionCategory(definition_id=definition.id, category_term_id=category))

    targets = [row]
    if payload.get("apply_same_key", True) and row.source_key:
        targets = [
            *db.scalars(
                select(ModelFreeSpec).where(
                    ModelFreeSpec.source_key == row.source_key, ModelFreeSpec.id != row.id
                )
            ),
            row,
        ]

    moved = left = 0
    for one in targets:
        fields = _fields_for(kind, one.value_text)
        if fields is None:
            left += 1
            continue
        db.add(
            ModelSpecValue(
                model_id=one.model_id,
                definition_id=definition.id,
                note=one.note,
                source_id=one.source_id,
                source_page=one.source_page,
                **fields,
            )
        )
        db.delete(one)
        moved += 1
    if moved == 0:
        # 이 줄조차 못 옮기면 정의만 덩그러니 남는다 — 사람이 값을 고쳐 다시 누르게 한다.
        db.rollback()
        raise AppError(
            "TSC-SPEC-0023",
            f"「{row.value_text}」 를 {kind} 로 읽을 수 없습니다. 값을 숫자로 고치거나 종류를"
            " 「글자」 로 하십시오.",
            status=400,
        )
    db.commit()
    return FreeSpecPromoteResult(definition_id=definition.id, moved=moved, left=left)

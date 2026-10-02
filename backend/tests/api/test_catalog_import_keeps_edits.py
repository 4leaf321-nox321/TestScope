"""카탈로그 반입은 **손으로 고쳐 둔 사양을 안 덮는다.**

## 왜 이 시험이 있나

규칙은 처음부터 코드에 있었다 — `_import_specs` 가 그 기종의 기존 값 정의를 **DB 에서**
읽어 `taken` 에 담고, `_add_value` 가 `definition.id in taken` 이면 바로 돌아간다. 주석도
「손으로 고쳐 둔 것이 사양서보다 정확하다」 라고 적어 두었다.

**그런데 그것을 지키는 시험이 없었다.** `taken` 을 DB 에서 안 읽게 바꾸는 리팩터 한 번이면
보호가 조용히 사라지고, 그 다음 운영 반입에서 손으로 고친 값이 전부 사양서 값으로 돌아간다 —
그리고 고친 사람은 사라진 줄도 모른다. 주석은 보증이 아니다.

빈말이 아니다: 두 기종(인스트론 9450RHK · 9420 High Energy)의 단위환산을 사람이 운영
서버에서 직접 했다(2026-10-03). 이 시험은 그 작업을 지키려고 있다.

같은 규칙을 API 쪽에서 지키는 것은 `test_spec_overwrite.py` 다 — 두 경로가 같은 약속을
한다는 것이 이 두 파일의 요지다.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.equipment.models import EquipmentModel, EquipmentSeries, ModelSpecValue
from app.modules.vocabulary.specs import SpecDefinition

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from catalog_import.values import _import_specs  # type: ignore[import-not-found]

#: 원본 카탈로그가 쓰는 키. 정의 이름과 **다르다** — 반입이 그 둘을 잇는 것이 일이다.
SOURCE_KEY = "weight_kg_for_test"


def _model(db: Session) -> EquipmentModel:
    # `normalized` 는 비교키라 NOT NULL 이다 — 반입이 id 가 아니라 이것으로 찾는다.
    name = f"계열-{uuid.uuid4().hex[:6]}"
    series = EquipmentSeries(name=name, normalized=name.lower())
    db.add(series)
    db.flush()
    kind = f"기종-{uuid.uuid4().hex[:6]}"
    model = EquipmentModel(series_id=series.id, name=kind, normalized=kind.lower())
    db.add(model)
    db.flush()
    return model


def _weight(db: Session) -> SpecDefinition:
    """설치가 심어 두는 수치 사양. 분류를 안 붙여서 어느 기종에서도 쓴다."""
    found = db.scalar(select(SpecDefinition).where(SpecDefinition.key == "weight"))
    assert found is not None, "설치 씨앗에 weight 가 없다"
    return found


def _held(db: Session, model: EquipmentModel, definition: SpecDefinition) -> ModelSpecValue:
    row = db.scalar(
        select(ModelSpecValue).where(
            ModelSpecValue.model_id == model.id,
            ModelSpecValue.definition_id == definition.id,
        )
    )
    assert row is not None
    return row


def test_손으로_고친_값을_반입이_안_덮는다(db: Session) -> None:
    model = _model(db)
    definition = _weight(db)
    # 사람이 단위환산을 해 둔 값. 비고까지 적었다 — 그 비고가 근거다.
    db.add(
        ModelSpecValue(
            model_id=model.id,
            definition_id=definition.id,
            num_value=30.0,
            note="kg 으로 환산 (운영에서 사람이 고침)",
        )
    )
    db.flush()

    # 사양서는 다른 수를 말한다. 반입을 돌린다.
    #
    # `aliases` 로 **원본 키 → 정의** 짝을 직접 준다. 안 주면 반입이 그 키를 「이 기종만의
    # 사양」 으로 돌려서 `taken` 검사를 아예 안 지나고, 그러면 이 시험이 거짓으로 통과한다.
    made = _import_specs(
        db,
        model,
        {SOURCE_KEY: 300.0},
        {definition.key: definition},
        None,
        {},
        {SOURCE_KEY: (definition.key, 1.0)},
    )
    db.flush()

    # **안 덮었다.** 새로 만든 것도 없다.
    assert made == 0, "반입이 있는 자리에 값을 새로 넣었다"
    row = _held(db, model, definition)
    assert row.num_value == 30.0, "사람이 고친 값이 사양서 값으로 돌아갔다"
    assert row.note == "kg 으로 환산 (운영에서 사람이 고침)", "근거가 사라졌다"


def test_빈_자리는_반입이_채운다(db: Session) -> None:
    """안 덮는다는 것이 **아무것도 안 넣는다**는 뜻이면 반입이 쓸모가 없다."""
    model = _model(db)
    definition = _weight(db)
    made = _import_specs(
        db,
        model,
        {SOURCE_KEY: 300.0},
        {definition.key: definition},
        None,
        {},
        {SOURCE_KEY: (definition.key, 1.0)},
    )
    db.flush()
    assert made == 1
    assert _held(db, model, definition).num_value == 300.0

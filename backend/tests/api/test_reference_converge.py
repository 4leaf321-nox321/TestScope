"""온톨로지 따라잡기 — 있는 정의의 빈 축 연결을 채우고, 문장 하중을 구간으로 바꾼다.

경도계 67 기종이 하중 사양을 갖고도 검색에 「모름」 으로 답했다. 정의가 문장(text)이라
축에 못 이어서다. 정의 표만 고치면 **이미 만들어진 정의는 안 따라온다** — 그래서
`ensure_reference_data` 가 비어 있는 것만 채우고, 두 번 돌려도 같아야 한다.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.equipment.models import ModelSpecValue
from app.modules.vocabulary.models import ConditionKey
from app.modules.vocabulary.reference import (
    SPEC_DEFINITION_LINKS,
    _text_to_range,
    converge_spec_definitions,
    ensure_reference_data,
)
from app.modules.vocabulary.specs import SpecDefinition
from tests.api.conftest import Signed
from tests.api.test_model_specs import _definitions, _model


def _definition(db: Session, key: str) -> SpecDefinition:
    row = db.scalar(select(SpecDefinition).where(SpecDefinition.key == key))
    assert row is not None, key
    return row


def _key_id(db: Session, key: str) -> Any:
    return db.scalar(select(ConditionKey.id).where(ConditionKey.key == key))


def test_문장_하중은_양끝을_구간에_담고_목록은_비고에_남긴다() -> None:
    assert _text_to_range("500 · 750 · 1000 · 1500") == (
        500.0,
        1500.0,
        "고를 수 있는 값 500 · 750 · 1000 · 1500",
    )
    # 이미 양끝인 것은 비고가 없다 — 「min 0.5 · max 250」 를 또 적으면 두 번 보인다.
    assert _text_to_range("min 0.5 · max 250") == (0.5, 250.0, None)
    assert _text_to_range("옵션에 따라 다름") is None


def test_설치가_새_축_다섯을_심고_사양_정의를_잇는다(
    client: TestClient, admin: Signed
) -> None:
    keys = {
        row["key"] for row in client.get("/api/condition-keys", headers=admin.headers).json()
    }
    assert {"voltage", "current", "torque", "acceleration", "impact_energy"} <= keys

    definitions = _definitions(client, admin)
    # 표에 적힌 정의는 이어져 있다(카탈로그 손 정의·승격분은 반입이 만드니 여기 없다).
    for key in ("test_load_series", "torque_capacity", "impact_energy"):
        assert definitions[key]["condition_key_id"] is not None, key
    # 문장이던 경도계 하중이 구간이다.
    assert definitions["test_load_series"]["kind"] == "range"


def test_있던_문장_값은_구간으로_바뀌고_두_번_돌려도_같다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    # 「옛날 DB」 를 흉내 낸다: 정의를 문장으로 되돌리고 문장 값 둘을 넣는다.
    definition = _definition(db, "test_load_series")
    definition.kind = "text"
    model = _model(client, admin)
    listed = ModelSpecValue(
        model_id=model["id"], definition_id=definition.id, text_value="15 · 30 · 45 · 60"
    )
    paired = ModelSpecValue(
        model_id=_model(client, admin)["id"],
        definition_id=definition.id,
        text_value="min 3 · max 3000",
    )
    db.add_all([listed, paired])
    db.commit()

    counts = ensure_reference_data(db)
    assert counts.converted_values == 2
    db.refresh(definition)
    db.refresh(listed)
    db.refresh(paired)
    assert definition.kind == "range"
    assert (listed.num_min, listed.num_max) == (15, 60)
    assert listed.text_value is None
    assert listed.note == "고를 수 있는 값 15 · 30 · 45 · 60"
    assert (paired.num_min, paired.num_max) == (3, 3000)
    assert paired.note is None

    # 멱등 — 이미 구간이니 아무것도 안 바꾼다.
    again = ensure_reference_data(db)
    assert (again.converted_values, again.linked_definitions) == (0, 0)

    # 이제 그 값이 검색 조건이 된다: kgf -> kN 으로 환산해서.
    shown = client.get(f"/api/equipment-models/{model['id']}/specs", headers=admin.headers)
    assert shown.status_code == 200, shown.text
    rows = [one for group in shown.json()["groups"] for one in group["items"]]
    row = next(one for one in rows if one["key"] == "test_load_series")
    assert row["condition_key_id"] is not None
    assert row["axis_unit_mismatch"] is False

    db.delete(listed)
    db.delete(paired)
    db.commit()


def test_사람이_다른_축으로_바꿔_둔_정의는_안_건드린다(db: Session) -> None:
    definition = _definition(db, "torque_capacity")
    assert SPEC_DEFINITION_LINKS["torque_capacity"] == "torque"
    original = definition.condition_key_id
    try:
        # 사람이 화면에서 「하중」 으로 바꿔 뒀다 — 표와 다르지만 그 사람의 판단이다.
        definition.condition_key_id = _key_id(db, "force")
        db.commit()
        linked, _ = converge_spec_definitions(db)
        db.commit()
        db.refresh(definition)
        assert linked == 0
        assert definition.condition_key_id == _key_id(db, "force")

        # 비워 두면 표가 채운다.
        definition.condition_key_id = None
        db.commit()
        linked, _ = converge_spec_definitions(db)
        db.commit()
        db.refresh(definition)
        assert linked == 1
        assert definition.condition_key_id == _key_id(db, "torque")
    finally:
        definition.condition_key_id = original
        db.commit()


def test_반입은_낱개_목록을_구간과_비고로_담는다() -> None:
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    sys.path.insert(0, str(scripts))
    from import_catalog import _value_fields  # type: ignore[import-not-found]

    definition = SpecDefinition(key="x", label="x", kind="range", reflect_as="max")
    fields = _value_fields(definition, {"values": [500, 750, 1000, 1500]}, 1.0)
    assert fields == {
        "num_min": 500,
        "num_max": 1500,
        "note": "고를 수 있는 값 500 · 750 · 1000 · 1500",
    }
    # 둘이면 그냥 구간이다 — 비고에 또 적지 않는다.
    assert _value_fields(definition, {"min": 3, "max": 3000}, 1.0) == {
        "num_min": 3,
        "num_max": 3000,
        "note": None,
    }

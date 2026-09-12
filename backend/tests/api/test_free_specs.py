"""이 기종만의 사양 — **정의 없이 값을 들이고, 여럿이 되면 정의로 올린다.**

카탈로그 원본의 사양 키 950종 중 803종이 한 기종에만 나온다. 전부 정의로 세우면 「사양
추가」 목록이 못 쓰게 되고, 버리면 그 기종을 아는 데 필요한 것이 원문에만 남는다.

여기서 지키는 것:

1. 정의 없이 이름·값·단위를 기종에 붙일 수 있고, 상세가 그것을 준다.
2. 「정의로 세우기」 는 사람이 이름·단위·종류를 적어 누른다. 정의는 그 기종의 분류에 붙고,
   같은 원본 키를 가진 다른 기종의 줄도 함께 옮긴다.
3. 수치로 못 읽는 줄(「약 300」)은 **그대로 둔다** — 지어서 옮기지 않는다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import Signed


def _model(client: TestClient, admin: Signed, series_id: str | None = None) -> dict[str, Any]:
    if series_id is None:
        series = client.post(
            "/api/equipment-series",
            json={"name": f"계열-{uuid.uuid4().hex[:6]}"},
            headers=admin.headers,
        )
        assert series.status_code == 201, series.text
        series_id = series.json()["id"]
    made = client.post(
        "/api/equipment-models",
        json={"series_id": series_id, "name": f"기종-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    body: dict[str, Any] = made.json()
    return body


def _free(
    client: TestClient, admin: Signed, model_id: str, **payload: object
) -> dict[str, Any]:
    made = client.post(
        f"/api/equipment-models/{model_id}/free-specs",
        json={"label": "스핀들 종류", "value_text": "LV 4종", **payload},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    body: dict[str, Any] = made.json()
    return body


def _seed_same_key(model_id: str, key: str, value: str) -> str:
    """반입이 하는 일 — 원본 키를 단 줄을 심는다."""
    from app.database import SessionLocal
    from app.modules.equipment.models import ModelFreeSpec

    db = SessionLocal()
    try:
        row = ModelFreeSpec(
            model_id=uuid.UUID(model_id),
            label=key,
            value_text=value,
            unit="mm",
            source_key=key,
            origin="catalog",
        )
        db.add(row)
        db.commit()
        return str(row.id)
    finally:
        db.close()


def test_정의_없이_값을_붙이고_고치고_지운다(client: TestClient, admin: Signed) -> None:
    model = _model(client, admin)
    made = _free(client, admin, model["id"], unit=None, note="옵션 UL 어댑터 시 6종")
    assert made["origin"] == "manual"
    assert made["same_key_models"] == 0

    read = client.get(f"/api/equipment-models/{model['id']}", headers=admin.headers).json()
    assert [one["label"] for one in read["free_specs"]] == ["스핀들 종류"]

    fixed = client.put(
        f"/api/equipment-models/{model['id']}/free-specs/{made['id']}",
        json={"label": "스핀들", "value_text": "LV 4종 · RV 6종"},
        headers=admin.headers,
    )
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["value_text"] == "LV 4종 · RV 6종"

    gone = client.delete(
        f"/api/equipment-models/{model['id']}/free-specs/{made['id']}", headers=admin.headers
    )
    assert gone.status_code == 204
    read = client.get(f"/api/equipment-models/{model['id']}", headers=admin.headers).json()
    assert read["free_specs"] == []


def test_정의로_세우면_같은_키의_다른_기종도_함께_옮긴다(
    client: TestClient, admin: Signed
) -> None:
    """한 기종만 옮기면 같은 값이 두 자리에 산다."""
    key = f"stroke_pk_{uuid.uuid4().hex[:6]}"
    first = _model(client, admin)
    second = _model(client, admin)
    third = _model(client, admin)
    free_id = _seed_same_key(first["id"], key, "0 ~ 152")
    _seed_same_key(second["id"], key, "203")
    # 수치로 못 읽는 것 — 지어서 옮기면 「약」 이 사라진다.
    _seed_same_key(third["id"], key, "약 300")

    read = client.get(f"/api/equipment-models/{first['id']}", headers=admin.headers).json()
    assert read["free_specs"][0]["same_key_models"] == 2

    groups = client.get("/api/spec-groups", headers=admin.headers).json()
    promoted = client.post(
        f"/api/equipment-models/{first['id']}/free-specs/{free_id}/promote",
        json={
            "key": key,
            "label": "가진 변위 (peak-to-peak)",
            "group_id": groups[0]["id"],
            "kind": "range",
            "unit": "mm",
        },
        headers=admin.headers,
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json() == {
        "definition_id": promoted.json()["definition_id"],
        "moved": 2,
        "left": 1,
    }

    # 옮겨 간 값은 정의 사양표에 선다 — 「0 ~ 152」 는 범위, 「203」 은 상한.
    sheet = client.get(f"/api/equipment-models/{first['id']}/specs", headers=admin.headers)
    values = [one for group in sheet.json()["groups"] for one in group["items"]]
    assert values[0]["num_min"] == 0 and values[0]["num_max"] == 152
    sheet = client.get(f"/api/equipment-models/{second['id']}/specs", headers=admin.headers)
    values = [one for group in sheet.json()["groups"] for one in group["items"]]
    assert values[0]["num_min"] is None and values[0]["num_max"] == 203

    # 못 읽은 줄은 그대로 남는다.
    read = client.get(f"/api/equipment-models/{third['id']}", headers=admin.headers).json()
    assert [one["value_text"] for one in read["free_specs"]] == ["약 300"]
    read = client.get(f"/api/equipment-models/{first['id']}", headers=admin.headers).json()
    assert read["free_specs"] == []

    # 같은 키로 또 세울 수 없다.
    other = _seed_same_key(third["id"], key + "x", "1")
    again = client.post(
        f"/api/equipment-models/{third['id']}/free-specs/{other}/promote",
        json={
            "key": key,
            "label": "x",
            "group_id": groups[0]["id"],
            "kind": "number",
            "unit": "",
        },
        headers=admin.headers,
    )
    assert again.status_code == 409


def test_이_줄조차_못_읽으면_정의를_안_남긴다(client: TestClient, admin: Signed) -> None:
    model = _model(client, admin)
    made = _free(client, admin, model["id"], value_text="약 300")
    groups = client.get("/api/spec-groups", headers=admin.headers).json()
    key = f"about_{uuid.uuid4().hex[:6]}"
    refused = client.post(
        f"/api/equipment-models/{model['id']}/free-specs/{made['id']}/promote",
        json={
            "key": key,
            "label": "x",
            "group_id": groups[0]["id"],
            "kind": "number",
            "unit": "",
        },
        headers=admin.headers,
    )
    assert refused.status_code == 400, refused.text
    definitions = client.get("/api/spec-definitions", headers=admin.headers).json()
    assert key not in {one["key"] for one in definitions}

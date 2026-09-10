"""개체 사양 — **카탈로그 위에 실측을 덮는다.**

여기서 지키는 것들:

1. 복사가 아니라 겹쳐 보기다 — 개체가 안 적은 칸은 기종 값이 그대로 보인다.
2. 덮은 칸은 **둘 다** 온다. 어느 것이 잰 값인지 화면이 말할 수 있어야 한다.
3. 검색축에 이어진 실측은 이 장비의 시험 조건을 갱신한다.
4. **손으로 고쳐 둔 조건은 안 덮는다.**
5. 실측을 지우면 그 칸은 다시 카탈로그 값으로 보이고, 시험 조건은 그대로 남는다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import Signed, site_id


def _definitions(client: TestClient, admin: Signed) -> dict[str, dict[str, Any]]:
    response = client.get("/api/spec-definitions", headers=admin.headers)
    assert response.status_code == 200, response.text
    return {row["key"]: row for row in response.json()}


def _catalog_unit(client: TestClient, admin: Signed) -> tuple[str, str, dict[str, Any]]:
    """기종 사양이 적힌 계열에서 장비 한 대를 만든다. (장비 id, 기종 id, 정의들).

    등록하는 순간 계열의 시험 항목이 이 장비로 복사되고, 조건은 기종 사양에서 온다
    (ADR 0006) — 실측이 덮을 대상이 그때 생긴다.
    """
    definitions = _definitions(client, admin)
    series = client.post(
        "/api/equipment-series",
        json={"name": f"계열-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert series.status_code == 201, series.text
    series_id = series.json()["id"]

    item = client.post(
        "/api/vocabularies/test_item/terms",
        json={"value": f"인장-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert item.status_code == 201, item.text
    test_item = client.post(
        f"/api/equipment-series/{series_id}/test_items",
        json={"test_item_term_id": item.json()["id"]},
        headers=admin.headers,
    )
    assert test_item.status_code == 201, test_item.text

    model = client.post(
        "/api/equipment-models",
        json={"series_id": series_id, "name": f"기종-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert model.status_code == 201, model.text
    model_id = model.json()["id"]

    stated = client.put(
        f"/api/equipment-models/{model_id}/specs",
        json={"definition_id": definitions["force_capacity"]["id"], "num_value": 250},
        headers=admin.headers,
    )
    assert stated.status_code == 200, stated.text

    made = client.post(
        "/api/equipment",
        json={
            "asset_no": f"SPC-{uuid.uuid4().hex[:6]}",
            "name": "사양을 덮을 장비",
            "workspace_slug": admin.workspace,
            "site_term_id": site_id(client, admin),
            "location": "3동 201호",
            "model_id": model_id,
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return made.json()["id"], model_id, definitions


def _sheet(client: TestClient, admin: Signed, equipment_id: str) -> dict[str, Any]:
    response = client.get(f"/api/equipment/{equipment_id}/specs", headers=admin.headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _item(sheet: dict[str, Any], key: str) -> dict[str, Any] | None:
    for group in sheet["groups"]:
        for item in group["items"]:
            if item["key"] == key:
                found: dict[str, Any] = item
                return found
    return None


def test_안_덮은_칸은_기종_값이_그대로_보인다(client: TestClient, admin: Signed) -> None:
    equipment_id, _, _ = _catalog_unit(client, admin)
    sheet = _sheet(client, admin, equipment_id)
    assert sheet["override_count"] == 0

    force = _item(sheet, "force_capacity")
    assert force is not None
    assert force["catalog"]["num_value"] == 250
    assert force["measured"] is None


def test_실측을_덮으면_둘_다_온다(client: TestClient, admin: Signed) -> None:
    """하나만 주면 사람은 그 수치가 잰 값인지 사양서 값인지 알 수 없고, 그 둘은
    믿는 정도가 다르다."""
    equipment_id, _, definitions = _catalog_unit(client, admin)
    saved = client.put(
        f"/api/equipment/{equipment_id}/specs",
        json={
            "definition_id": definitions["force_capacity"]["id"],
            "num_value": 300,
            "measured_on": "2026-09-01",
            "note": "수검 성적서 기준",
        },
        headers=admin.headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["condition_label"] == "하중 용량"
    assert saved.json()["reflected"] is True

    sheet = _sheet(client, admin, equipment_id)
    assert sheet["override_count"] == 1
    force = _item(sheet, "force_capacity")
    assert force is not None
    assert force["catalog"]["num_value"] == 250
    assert force["measured"]["num_value"] == 300
    assert force["measured"]["measured_on"] == "2026-09-01"


def test_실측은_이_장비의_시험_항목_조건을_갱신한다(client: TestClient, admin: Signed) -> None:
    equipment_id, _, definitions = _catalog_unit(client, admin)
    client.put(
        f"/api/equipment/{equipment_id}/specs",
        json={"definition_id": definitions["force_capacity"]["id"], "num_value": 300},
        headers=admin.headers,
    )

    test_items = client.get(
        f"/api/equipment-test-items?equipment_id={equipment_id}", headers=admin.headers
    )
    assert test_items.status_code == 200, test_items.text
    limits = [
        limit
        for test_item in test_items.json()
        for limit in test_item["limits"]
        if limit["condition_key"] == "force"
    ]
    assert limits, test_items.text
    # 사양서 250 이 아니라 우리가 잰 300 이다.
    assert limits[0]["max_value"] == 300


def test_손으로_고쳐_둔_조건은_안_덮는다(client: TestClient, admin: Signed) -> None:
    """사람이 재서 적은 값을 사양표가 덮으면, 그 손실은 검색이 틀린 답을 낸 날에야
    드러난다."""
    equipment_id, _, definitions = _catalog_unit(client, admin)
    test_items = client.get(
        f"/api/equipment-test-items?equipment_id={equipment_id}", headers=admin.headers
    ).json()
    equipment_test_item_id = test_items[0]["id"]
    conditions = client.get("/api/condition-keys", headers=admin.headers).json()
    force_key = next(row["id"] for row in conditions if row["key"] == "force")

    handwritten = client.put(
        f"/api/equipment-test-items/{equipment_test_item_id}/limits",
        json={
            "condition_key_id": force_key,
            "max_value": 120,
            "note": "지그가 120 까지만 버틴다 — 실제로 걸어 봄",
        },
        headers=admin.headers,
    )
    assert handwritten.status_code == 200, handwritten.text

    saved = client.put(
        f"/api/equipment/{equipment_id}/specs",
        json={"definition_id": definitions["force_capacity"]["id"], "num_value": 300},
        headers=admin.headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["reflected"] is False

    after = client.get(
        f"/api/equipment-test-items?equipment_id={equipment_id}", headers=admin.headers
    ).json()
    limit = next(limit for limit in after[0]["limits"] if limit["condition_key"] == "force")
    assert limit["max_value"] == 120


def test_실측을_지우면_카탈로그_값으로_돌아가고_시험_항목은_남는다(
    client: TestClient, admin: Signed
) -> None:
    equipment_id, _, definitions = _catalog_unit(client, admin)
    definition_id = definitions["force_capacity"]["id"]
    client.put(
        f"/api/equipment/{equipment_id}/specs",
        json={"definition_id": definition_id, "num_value": 300},
        headers=admin.headers,
    )

    dropped = client.delete(
        f"/api/equipment/{equipment_id}/specs/{definition_id}", headers=admin.headers
    )
    assert dropped.status_code == 204, dropped.text

    sheet = _sheet(client, admin, equipment_id)
    force = _item(sheet, "force_capacity")
    assert force is not None
    assert force["measured"] is None
    assert force["catalog"]["num_value"] == 250

    # **시험 조건은 그대로다.** 사양표를 정리했다고 검색 결과가 이유 없이 바뀌면 안 된다.
    after = client.get(
        f"/api/equipment-test-items?equipment_id={equipment_id}", headers=admin.headers
    ).json()
    limit = next(limit for limit in after[0]["limits"] if limit["condition_key"] == "force")
    assert limit["max_value"] == 300


def test_종류에_안_맞는_칸은_거절한다(client: TestClient, admin: Signed) -> None:
    """기종 사양과 **같은 검증**을 쓴다 — 두 벌로 두면 같은 값이 한 화면에서는
    저장되고 다른 화면에서는 거절된다."""
    equipment_id, _, definitions = _catalog_unit(client, admin)
    refused = client.put(
        f"/api/equipment/{equipment_id}/specs",
        json={"definition_id": definitions["force_capacity"]["id"], "text_value": "삼백"},
        headers=admin.headers,
    )
    assert refused.status_code == 400, refused.text
    assert refused.json()["error"]["code"] == "TSC-SPEC-0008"

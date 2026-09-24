"""시험 항목 카탈로그 — **사슬의 가운데에서 출발하는 눈.**

    물성  ⇄  시험 항목  →  규격  →  계열/기종  →  보유 장비

네 카탈로그 화면이 전부 시험 항목으로 향하는데 시험 항목에서 출발하는 화면이 없었다.

여기서 지키는 것 — 항목마다 사슬 전체의 수를 준다(0 이 공백) · 보유 장비는 내가 볼 수
있는 것만 센다 · 검색축은 통째로 바꾼다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import Signed, category_id, site_id


def _term(client: TestClient, admin: Signed, axis: str, value: str) -> str:
    made = client.post(
        f"/api/vocabularies/{axis}/terms", json={"value": value}, headers=admin.headers
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def _row(client: TestClient, admin: Signed, item_id: str) -> dict[str, Any]:
    rows = client.get("/api/test-items", headers=admin.headers)
    assert rows.status_code == 200, rows.text
    found = next(one for one in rows.json() if one["id"] == item_id)
    assert isinstance(found, dict)
    return found


def test_항목마다_사슬_전체의_수를_준다(client: TestClient, admin: Signed) -> None:
    tag = uuid.uuid4().hex[:6]
    item = _term(client, admin, "test_item", f"인장-{tag}")
    before = _row(client, admin, item)
    assert before["properties_total"] == 0 and before["series_count"] == 0
    assert before["equipment_count"] == 0

    # 물성 하나, 규격 하나(요구 조건 없음), 계열 하나(기종 둘), 보유 장비 한 대.
    prop = client.post(
        "/api/vocabularies/property/terms",
        json={"value": f"항복강도-{tag}", "code": f"mechanical.ys_{tag}"},
        headers=admin.headers,
    ).json()["id"]
    client.post(
        "/api/test-item-properties",
        json={"test_item_term_id": item, "property_term_id": prop},
        headers=admin.headers,
    )
    method = client.post(
        "/api/methods",
        json={"code": f"ISO {tag}", "title": "T", "test_item_term_ids": [item]},
        headers=admin.headers,
    ).json()
    series = client.post(
        "/api/equipment-series", json={"name": f"계열-{tag}"}, headers=admin.headers
    ).json()
    for name in ("A", "B"):
        client.post(
            "/api/equipment-models",
            json={"series_id": series["id"], "name": f"{name}-{tag}"},
            headers=admin.headers,
        )
    client.post(
        f"/api/equipment-series/{series['id']}/test-items",
        json={"test_item_term_id": item, "method_code": method["code"]},
        headers=admin.headers,
    )
    equipment = client.post(
        "/api/equipment",
        json={
            "asset_no": f"UTM-{tag}",
            "name": "만능기",
            "workspace_slug": admin.workspace,
            "site_term_id": site_id(client, admin),
            "location": "3동",
            "category_term_id": category_id(client, admin),
        },
        headers=admin.headers,
    ).json()
    client.post(
        "/api/equipment-test-items",
        json={"equipment_id": equipment["id"], "test_item_term_id": item},
        headers=admin.headers,
    )

    after = _row(client, admin, item)
    assert after["properties_total"] == 1 and after["properties_confirmed"] == 1
    assert after["methods_total"] == 1 and after["methods_with_requirements"] == 0
    assert after["series_count"] == 1 and after["model_count"] == 2
    assert after["equipment_count"] == 1

    detail = client.get(f"/api/test-items/{item}", headers=admin.headers)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert [one["property"] for one in body["properties"]] == [f"항복강도-{tag}"]
    assert body["methods"][0]["code"] == method["code"]
    assert body["series"][0]["model_count"] == 2
    assert body["series"][0]["method_codes"] == [method["code"]]
    assert body["equipment"][0]["asset_no"] == f"UTM-{tag}"


def test_검색축을_통째로_바꾼다(client: TestClient, admin: Signed) -> None:
    """인장은 하중·속도·온도 — 전에는 어디에도 없어 검색이 축 일곱 개를 다 물었다."""
    item = _term(client, admin, "test_item", f"굽힘-{uuid.uuid4().hex[:6]}")
    keys = {
        row["key"]: row["id"]
        for row in client.get("/api/condition-keys", headers=admin.headers).json()
    }
    put = client.put(
        f"/api/test-items/{item}/condition-keys",
        json={"condition_key_ids": [keys["force"], keys["temperature"]]},
        headers=admin.headers,
    )
    assert put.status_code == 204, put.text
    assert set(_row(client, admin, item)["condition_keys"]) == {"하중 용량", "시험 온도"}

    # 통째로 바꾼다 — 온도를 빼면 온도가 사라진다.
    client.put(
        f"/api/test-items/{item}/condition-keys",
        json={"condition_key_ids": [keys["force"]]},
        headers=admin.headers,
    )
    assert _row(client, admin, item)["condition_keys"] == ["하중 용량"]

    # 시험 항목이 아닌 값은 거절한다.
    maker = _term(client, admin, "manufacturer", f"제조사-{uuid.uuid4().hex[:6]}")
    assert client.get(f"/api/test-items/{maker}", headers=admin.headers).status_code == 404

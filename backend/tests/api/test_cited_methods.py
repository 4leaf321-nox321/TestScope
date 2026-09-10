"""인용 규격 — 검색 사슬의 **세 번째 칸.**

    시험 항목 -> 요구 조건 -> **시험법** -> 가능한 장비 -> 보유 위치

카탈로그가 계열마다 인용한 규격이 453건 들어와 있는데, 전에는 시험 항목의 비고에 글자로만
붙어 있었다: `"카탈로그 인용 규격: ASTM D638 · ISO 527"`. 그래서 그 453건은 **아무것도
가리키지 않는 목록**이었다.

여기서 지키는 것:

1. 규격은 **표로** 이어진다 — 시험 항목을 규격마다 쪼개지 않으면서.
2. 시험 항목 응답이 그 규격들을 함께 준다.
3. **요구 조건이 있는지 말해 준다** — 없으면 검색이 조건으로 좁히지 못한다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import Signed


def _method(client: TestClient, admin: Signed, item_id: str) -> dict[str, Any]:
    response = client.post(
        "/api/methods",
        json={
            "code": f"ASTM D{uuid.uuid4().hex[:4]}",
            "title": "Standard Test Method",
            "test_item_term_id": item_id,
        },
        headers=admin.headers,
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def test_시험_항목이_인용_규격을_함께_준다(client: TestClient, admin: Signed) -> None:
    """규격을 못 주면 「ASTM D638 되는 장비」 에 답할 수 없다."""
    item = client.post(
        "/api/vocabularies/test_item/terms",
        json={"value": f"인장-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert item.status_code == 201, item.text
    item_id = item.json()["id"]
    method = _method(client, admin, item_id)

    series = client.post(
        "/api/equipment-series",
        json={"name": f"계열-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert series.status_code == 201, series.text
    series_id = series.json()["id"]
    test_item = client.post(
        f"/api/equipment-series/{series_id}/test_items",
        json={"test_item_term_id": item_id, "method_code": method["code"]},
        headers=admin.headers,
    )
    assert test_item.status_code == 201, test_item.text

    read = client.get(f"/api/equipment-series/{series_id}", headers=admin.headers)
    assert read.status_code == 200, read.text
    rows = read.json()["test_items"]
    assert rows, read.text
    # 화면이 그리는 자리다. 모양만 확인한다 — 반입이 채우는 것은 아래 시험이 본다.
    assert isinstance(rows[0]["methods"], list)


def test_요구_조건이_없는_규격은_그렇다고_말한다(client: TestClient, admin: Signed) -> None:
    """**말 안 하면 아무도 안 채운다.** 그리고 그 사이 검색은 조건으로 좁히지 못한다."""
    from app.database import SessionLocal
    from app.modules.equipment import catalog
    from app.modules.test_items.models import SeriesTestItem, SeriesTestItemMethod

    item = client.post(
        "/api/vocabularies/test_item/terms",
        json={"value": f"충격-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    ).json()
    method = _method(client, admin, item["id"])
    series = client.post(
        "/api/equipment-series",
        json={"name": f"계열-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    ).json()
    made = client.post(
        f"/api/equipment-series/{series['id']}/test_items",
        json={"test_item_term_id": item["id"]},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text

    # 반입이 하는 일을 그대로 한다 — 시험 항목을 쪼개지 않고 규격을 **옆 표로** 단다.
    db = SessionLocal()
    try:
        test_item = db.get(SeriesTestItem, uuid.UUID(made.json()["id"]))
        assert test_item is not None
        db.add(
            SeriesTestItemMethod(
                series_test_item_id=test_item.id, method_id=uuid.UUID(method["id"])
            )
        )
        db.commit()
        rows = catalog._test_items(db, test_item.series_id)
    finally:
        db.close()

    cited = [one for row in rows for one in row.methods]
    assert cited, rows
    assert cited[0].code == method["code"]
    # 요구 조건을 안 적었으니 거짓이어야 한다.
    assert cited[0].has_requirements is False


def test_규격을_쪼개서_시험_항목을_늘리지_않는다(client: TestClient, admin: Signed) -> None:
    """카탈로그는 인장 하나에 규격 셋을 함께 건다. 시험 항목 셋으로 만들면 **검색이 같은
    장비를 여덟 줄로 답한다** — 실제로 그렇게 나왔다."""
    from app.database import SessionLocal
    from app.modules.equipment import catalog
    from app.modules.test_items.models import SeriesTestItem, SeriesTestItemMethod

    item = client.post(
        "/api/vocabularies/test_item/terms",
        json={"value": f"인장-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    ).json()
    methods = [_method(client, admin, item["id"]) for _ in range(3)]
    series = client.post(
        "/api/equipment-series",
        json={"name": f"계열-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    ).json()
    made = client.post(
        f"/api/equipment-series/{series['id']}/test_items",
        json={"test_item_term_id": item["id"]},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text

    db = SessionLocal()
    try:
        test_item = db.get(SeriesTestItem, uuid.UUID(made.json()["id"]))
        assert test_item is not None
        for method in methods:
            db.add(
                SeriesTestItemMethod(
                    series_test_item_id=test_item.id, method_id=uuid.UUID(method["id"])
                )
            )
        db.commit()
        rows = catalog._test_items(db, test_item.series_id)
    finally:
        db.close()

    # 규격은 셋인데 시험 항목은 하나다.
    assert len(rows) == 1, rows
    assert len(rows[0].methods) == 3

"""항목 미정 인용 규격 — **못 하는 시험과 끊긴 연결을 가른다.**

카탈로그 객체의 규격 목록은 계열에 평평하게 붙어 온다. 만능시험기가 ASTM D638 · ISO 178 ·
ASTM E8 을 함께 인용하면 그중 무엇이 굽힘의 것인지 반입은 모른다. 전에는 그 사이 **누가
인용했나가 DB 어디에도 없어서**, 시험법 464 중 287 이 「가능 장비 없음」 으로 서 있었다.

여기서 지키는 것:

1. 미정 인용은 `series_pending_methods` 에 남고, 시험법 목록이 그 수를 말한다.
2. 규격에 시험 항목을 **정하는 순간** 인용한 계열의 그 시험 항목에 붙는다 — 사람이 계열마다
   다시 잇지 않는다.
3. 계열에 그 시험 항목을 **나중에 더해도** 붙는다.
4. `?test_item=none` · `?cited=none` 이 홈의 「남은 일」 과 같은 조건으로 거른다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import Signed


def _term(client: TestClient, admin: Signed, prefix: str) -> str:
    made = client.post(
        "/api/vocabularies/test_item/terms",
        json={"value": f"{prefix}-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def _method(client: TestClient, admin: Signed, item_id: str | None) -> dict[str, Any]:
    made = client.post(
        "/api/methods",
        json={
            "code": f"ISO {uuid.uuid4().hex[:5]}",
            "title": "Standard",
            "test_item_term_id": item_id,
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    body: dict[str, Any] = made.json()
    return body


def _series(client: TestClient, admin: Signed) -> str:
    made = client.post(
        "/api/equipment-series",
        json={"name": f"계열-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def _pend(series_id: str, method_id: str) -> None:
    """반입이 하는 일 — 계열이 인용했는데 항목을 못 정한 규격을 미정 표에 남긴다."""
    from app.database import SessionLocal
    from app.modules.test_items.models import SeriesPendingMethod

    db = SessionLocal()
    try:
        db.add(
            SeriesPendingMethod(series_id=uuid.UUID(series_id), method_id=uuid.UUID(method_id))
        )
        db.commit()
    finally:
        db.close()


def test_시험_항목을_정하면_인용한_계열에_붙는다(client: TestClient, admin: Signed) -> None:
    """**끊긴 연결이 이어지는 순간이다.** 규격 하나에 항목을 정했는데 계열 다섯이 각각
    다시 이어야 한다면 아무도 안 한다."""
    item = _term(client, admin, "굽힘")
    method = _method(client, admin, None)
    series_id = _series(client, admin)
    added = client.post(
        f"/api/equipment-series/{series_id}/test-items",
        json={"test_item_term_id": item},
        headers=admin.headers,
    )
    assert added.status_code == 201, added.text
    _pend(series_id, method["id"])

    before = client.get(f"/api/methods/{method['id']}", headers=admin.headers).json()
    assert before["pending_series_count"] == 1
    assert before["series_count"] == 0
    assert before["cited_series"][0]["pending"] is True

    fixed = client.patch(
        f"/api/methods/{method['id']}",
        json={"test_item_term_id": item},
        headers=admin.headers,
    )
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["pending_series_count"] == 0
    assert fixed.json()["series_count"] == 1

    series = client.get(f"/api/equipment-series/{series_id}", headers=admin.headers).json()
    assert series["pending_methods"] == []
    cited = [one["code"] for row in series["test_items"] for one in row["methods"]]
    assert method["code"] in cited


def test_계열에_시험_항목을_나중에_더해도_붙는다(client: TestClient, admin: Signed) -> None:
    """규격의 항목은 정해졌는데 계열에 그 시험이 없으면 미정으로 남는다 — 그 시험을 더하는
    순간 붙어야 사람이 두 번 잇지 않는다."""
    item = _term(client, admin, "압축")
    method = _method(client, admin, None)
    series_id = _series(client, admin)
    _pend(series_id, method["id"])
    client.patch(
        f"/api/methods/{method['id']}", json={"test_item_term_id": item}, headers=admin.headers
    )
    # 계열에 그 시험이 없어 아직 미정.
    series = client.get(f"/api/equipment-series/{series_id}", headers=admin.headers).json()
    assert [one["code"] for one in series["pending_methods"]] == [method["code"]]

    added = client.post(
        f"/api/equipment-series/{series_id}/test-items",
        json={"test_item_term_id": item},
        headers=admin.headers,
    )
    assert added.status_code == 201, added.text
    series = client.get(f"/api/equipment-series/{series_id}", headers=admin.headers).json()
    assert series["pending_methods"] == []
    assert [one["code"] for one in series["test_items"][0]["methods"]] == [method["code"]]


def test_항목_미정과_안_이어진_것을_따로_거른다(client: TestClient, admin: Signed) -> None:
    """홈의 「남은 일」 이 `?test_item=none` 으로 온다 — 세는 조건과 거르는 조건이 같아야
    한다. `?cited=none` 은 어느 계열에도 안 이어진 것이다."""
    item = _term(client, admin, "경도")
    undecided = _method(client, admin, None)
    decided_unlinked = _method(client, admin, item)
    linked = _method(client, admin, item)
    series_id = _series(client, admin)
    added = client.post(
        f"/api/equipment-series/{series_id}/test-items",
        json={"test_item_term_id": item, "method_code": linked["code"]},
        headers=admin.headers,
    )
    assert added.status_code == 201, added.text

    def listed(filters: str, method: dict[str, Any]) -> bool:
        # 목록은 한 쪽 200 이라 코드로 좁혀 묻는다 — 거르기가 같이 걸려야 한다.
        response = client.get(
            f"/api/methods?{filters}&query={method['code']}", headers=admin.headers
        )
        assert response.status_code == 200, response.text
        return method["id"] in {row["id"] for row in response.json()["items"]}

    assert listed("test_item=none", undecided)
    assert not listed("test_item=none", decided_unlinked)

    assert listed("cited=none", undecided)
    assert listed("cited=none", decided_unlinked)
    assert not listed("cited=none", linked)

    # 값 id 로 거르는 옛 모양도 그대로 된다.
    assert listed(f"test_item={item}", decided_unlinked)
    assert listed(f"test_item={item}", linked)
    assert not listed(f"test_item={item}", undecided)


def test_홈이_항목_미정_시험법을_센다(client: TestClient, admin: Signed) -> None:
    _method(client, admin, None)
    response = client.get("/api/server/maintenance", headers=admin.headers)
    assert response.status_code == 200, response.text
    keys = {row["key"]: row for row in response.json()}
    assert "method_without_test_item" in keys
    assert keys["method_without_test_item"]["link"] == "/methods?test_item=none"
    assert keys["method_without_test_item"]["count"] >= 1

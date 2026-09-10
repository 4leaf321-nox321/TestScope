"""검색 사슬 — 이 저장소가 존재하는 이유를 그대로 시험한다.

시험 항목  ->  요구 조건  ->  시험법  ->  가능한 장비  ->  보유 위치

"80도 환경에서 20 kN 이상의 인장시험 가능한 장비 있어?"
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import Signed, category_id, site_id


def _equipment(client: TestClient, admin: Signed, **extra: object) -> dict[str, Any]:
    payload = {
        "asset_no": f"UTM-{uuid.uuid4().hex[:6]}",
        "name": "만능재료시험기",
        "workspace_slug": admin.workspace,
        # 거점·상세위치·장비유형은 비울 수 없다(0008) — 어디 있고 무슨 종류인지
        # 모르는 장비는 찾아도 소용이 없다.
        "site_term_id": site_id(client, admin),
        "location": "3동 201호",
        "category_term_id": category_id(client, admin),
        **extra,
    }
    response = client.post("/api/equipment", json=payload, headers=admin.headers)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def _test_item(client: TestClient, admin: Signed, equipment_id: str, item_id: str) -> str:
    response = client.post(
        "/api/equipment-test-items",
        json={"equipment_id": equipment_id, "test_item_term_id": item_id},
        headers=admin.headers,
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _limit(
    client: TestClient,
    admin: Signed,
    equipment_test_item_id: str,
    condition_id: str,
    low: float | None,
    high: float | None,
) -> None:
    response = client.put(
        f"/api/equipment-test-items/{equipment_test_item_id}/limits",
        json={"condition_key_id": condition_id, "min_value": low, "max_value": high},
        headers=admin.headers,
    )
    assert response.status_code == 200, response.text


def test_조건을_갖춘_장비를_찾아_위치까지_알려준다(
    client: TestClient,
    admin: Signed,
    term_factory: Callable[[str, str], str],
    condition_ids: dict[str, str],
) -> None:
    item = term_factory("test_item", f"인장-{uuid.uuid4().hex[:6]}")
    equipment = _equipment(client, admin, name="UTM 300kN")
    test_item = _test_item(client, admin, equipment["id"], item)
    _limit(client, admin, test_item, condition_ids["temperature"], -70, 300)
    _limit(client, admin, test_item, condition_ids["force"], 0, 300)

    found = client.post(
        "/api/search/test_items",
        json={
            "test_item_term_id": item,
            "conditions": [
                {"condition_key_id": condition_ids["temperature"], "at": 80},
                {"condition_key_id": condition_ids["force"], "at_least": 20},
            ],
            "include_unavailable": False,
        },
        headers=admin.headers,
    ).json()

    assert found["total"] == 1
    hit = found["hits"][0]
    assert hit["asset_no"] == equipment["asset_no"]
    assert hit["verdict"] == "match"
    # **찾은 다음에 갈 곳이 나온다.** 없으면 검색은 절반만 한 것이다.
    assert hit["location"] == "3동 201호"
    assert hit["workspace_name"]


def test_범위를_벗어나면_결과에서_빠지고_그_수를_말해_준다(
    client: TestClient,
    admin: Signed,
    term_factory: Callable[[str, str], str],
    condition_ids: dict[str, str],
) -> None:
    """안 되는 장비를 목록에 남기는 것은 답이 아니라 소음이다. 다만 **몇 건이
    걸러졌는지**는 말해 준다 — 0 건일 때 그 숫자가 "없어서" 와 "조건이 좁아서" 를
    가른다."""
    item = term_factory("test_item", f"압축-{uuid.uuid4().hex[:6]}")
    equipment = _equipment(client, admin)
    test_item = _test_item(client, admin, equipment["id"], item)
    _limit(client, admin, test_item, condition_ids["force"], 0, 10)

    found = client.post(
        "/api/search/test_items",
        json={
            "test_item_term_id": item,
            "conditions": [{"condition_key_id": condition_ids["force"], "at_least": 20}],
            "include_unavailable": False,
        },
        headers=admin.headers,
    ).json()

    assert found["total"] == 0
    assert found["unmet_count"] == 1


def test_안_적힌_조건은_된다고_답하지_않는다(
    client: TestClient,
    admin: Signed,
    term_factory: Callable[[str, str], str],
    condition_ids: dict[str, str],
) -> None:
    """**모름을 됨과 섞지 않는다.** 섞으면 아무것도 안 적힌 장비가 모든 조건을
    만족하는 것으로 나오고, 사람은 그것을 믿고 가서 헛걸음을 한다."""
    item = term_factory("test_item", f"충격-{uuid.uuid4().hex[:6]}")
    equipment = _equipment(client, admin)
    test_item = _test_item(client, admin, equipment["id"], item)
    _limit(client, admin, test_item, condition_ids["force"], 0, 300)
    # 온도는 일부러 안 적는다.

    found = client.post(
        "/api/search/test_items",
        json={
            "test_item_term_id": item,
            "conditions": [
                {"condition_key_id": condition_ids["temperature"], "at": 80},
                {"condition_key_id": condition_ids["force"], "at_least": 20},
            ],
            "include_unavailable": False,
        },
        headers=admin.headers,
    ).json()

    hit = found["hits"][0]
    assert hit["verdict"] == "partial"
    verdicts = {one["condition_label"]: one["verdict"] for one in hit["conditions"]}
    assert verdicts["시험 온도"] == "unknown"
    assert verdicts["하중 용량"] == "met"


def test_점검_중인_장비는_기본_결과에서_빠진다(
    client: TestClient,
    admin: Signed,
    term_factory: Callable[[str, str], str],
    condition_ids: dict[str, str],
) -> None:
    """오늘 시험을 잡을 수 없는 장비를 가능하다고 답하면, 그 답을 믿고 일정을 짠
    사람이 막힌다. 다만 "원래 할 수 있는 시험인가" 를 묻는 사람도 있으므로
    손잡이는 남긴다."""
    item = term_factory("test_item", f"피로-{uuid.uuid4().hex[:6]}")
    equipment = _equipment(client, admin, status="maintenance")
    test_item = _test_item(client, admin, equipment["id"], item)
    _limit(client, admin, test_item, condition_ids["force"], 0, 300)

    def search(include_unavailable: bool) -> dict[str, Any]:
        response = client.post(
            "/api/search/test_items",
            json={
                "test_item_term_id": item,
                "conditions": [],
                "include_unavailable": include_unavailable,
            },
            headers=admin.headers,
        )
        body: dict[str, Any] = response.json()
        return body

    assert search(False)["total"] == 0
    assert search(True)["total"] == 1


def test_거꾸로_넣은_범위는_거절한다(
    client: TestClient,
    admin: Signed,
    term_factory: Callable[[str, str], str],
    condition_ids: dict[str, str],
) -> None:
    """조용히 통과시키면 그 장비는 검색에서 아무것도 안 맞고, 사람은 "왜 우리
    장비가 안 나오지" 를 묻게 된다 — 원인은 어디에도 안 보인다."""
    item = term_factory("test_item", f"굽힘-{uuid.uuid4().hex[:6]}")
    equipment = _equipment(client, admin)
    test_item = _test_item(client, admin, equipment["id"], item)

    response = client.put(
        f"/api/equipment-test-items/{test_item}/limits",
        json={"condition_key_id": condition_ids["force"], "min_value": 300, "max_value": 20},
        headers=admin.headers,
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "TSC-CAPABILITIES-0005"

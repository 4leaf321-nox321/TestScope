"""표의 **속성 아닌 열**로 거르기 — 이름 · 목적 · 시험 항목 · 보유 장비.

속성에는 `attr` 문법이 있는데 이 넷에는 없었다. 1784건에서 「목적을 안 적은 줄」 을 찾으려면
서른여섯 쪽을 눈으로 훑어야 했고, 그러면 아무도 안 찾는다 — **화면이 열로 보여 주는 것은
열로 거를 수 있어야 한다.**

여기서 지키는 것:

1. 이름·목적·시험 항목은 **든 글자**로 걸린다. 이름 조건이 목적까지 뒤지지 않는다(`q` 와
   다른 점이고, 그래서 따로 있다).
2. `none` 은 **안 적힌 것**이다 — 목적이 빈 줄 · 시험 항목을 안 정한 줄.
3. `equipment=none` 은 **그 사업부에 돌릴 장비가 한 대도 없는 줄.** 「안 정함」 과 다르다.
4. 사업부마다 장비가 다르다 — 저 사업부에 장비가 있다고 이 사업부가 할 수 있는 것이 아니다.
5. 여럿이면 **모두** 만족해야 한다(속성 조건과 같다).
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


def _test(client: TestClient, admin: Signed, **body: Any) -> dict[str, Any]:
    made = client.post(
        "/api/reliability-tests",
        json={"division_code": "mx", **body},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    out: dict[str, Any] = made.json()
    return out


def _equipment_for(client: TestClient, admin: Signed, tag: str, term_id: str) -> None:
    """그 시험 항목이 되는 장비 한 대 — 관리자의 부서에 놓는다(= mx 사업부)."""
    made = client.post(
        "/api/equipment",
        json={
            "asset_no": f"EQ-{tag}",
            "name": "챔버",
            "workspace_slug": admin.workspace,
            "site_term_id": site_id(client, admin),
            "location": "3동",
            "category_term_id": category_id(client, admin),
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    linked = client.post(
        "/api/equipment-test-items",
        json={"equipment_id": made.json()["id"], "test_item_term_id": term_id},
        headers=admin.headers,
    )
    assert linked.status_code in (200, 201), linked.text


def test_이름_목적_시험항목으로_거른다(client: TestClient, admin: Signed) -> None:
    tag = uuid.uuid4().hex[:6]
    shock = _term(client, admin, "test_item", f"열충격-{tag}")
    tensile = _term(client, admin, "test_item", f"인장-{tag}")

    _test(
        client,
        admin,
        name=f"고온고습-{tag}",
        purpose="고온에서 오래 버티나",
        test_item_term_ids=[shock],
    )
    _test(client, admin, name=f"열충격-{tag}", purpose="", test_item_term_ids=[tensile])
    # 목적도 시험 항목도 안 적은 줄 — **채워야 할 자리**가 이것이다.
    _test(client, admin, name=f"낙하-{tag}")

    def names(**params: str) -> set[str]:
        got = client.get(
            "/api/reliability-tests",
            params={"division": "mx", "status": "all", "q": tag, "limit": 200, **params},
            headers=admin.headers,
        )
        assert got.status_code == 200, got.text
        return {one["name"] for one in got.json()["items"]}

    assert names() == {f"고온고습-{tag}", f"열충격-{tag}", f"낙하-{tag}"}
    # 이름으로 — **목적까지 뒤지지 않는다.** 「고온」 은 열충격의 목적에 없고 이름에도 없다.
    assert names(name="고온") == {f"고온고습-{tag}"}
    assert names(purpose="고온") == {f"고온고습-{tag}"}
    # 목적을 안 적은 줄 — 채워야 할 자리를 찾는 물음이다.
    assert names(purpose="none") == {f"열충격-{tag}", f"낙하-{tag}"}
    # 시험 항목 이름으로, 그리고 **하나도 안 정한 줄**로.
    assert names(test_item=f"열충격-{tag}") == {f"고온고습-{tag}"}
    assert names(test_item="none") == {f"낙하-{tag}"}
    # 여럿이면 모두 만족해야 한다 — 「또는」 으로 읽으면 결과 수를 오해한다.
    assert names(purpose="none", test_item="none") == {f"낙하-{tag}"}


def test_돌릴_장비가_없는_줄을_찾는다(client: TestClient, admin: Signed) -> None:
    """목록이 줄마다 노란 「0대」 를 적고 있는데 그것으로 좁힐 길이 없었다."""
    tag = uuid.uuid4().hex[:6]
    able = _term(client, admin, "test_item", f"인장-{tag}")
    none = _term(client, admin, "test_item", f"방사선-{tag}")
    _equipment_for(client, admin, tag, able)

    _test(client, admin, name=f"되는것-{tag}", test_item_term_ids=[able])
    _test(client, admin, name=f"안되는것-{tag}", test_item_term_ids=[none])
    _test(client, admin, name=f"안정함-{tag}")
    # 항목이 둘인데 하나만 돼도 **할 수 있는 시험**이다.
    _test(client, admin, name=f"둘중하나-{tag}", test_item_term_ids=[able, none])

    def names(**params: str) -> set[str]:
        got = client.get(
            "/api/reliability-tests",
            params={"division": "mx", "status": "all", "q": tag, "limit": 200, **params},
            headers=admin.headers,
        )
        assert got.status_code == 200, got.text
        return {one["name"] for one in got.json()["items"]}

    assert names(equipment="none") == {
        f"안되는것-{tag}",
        f"안정함-{tag}",
    }
    # **「안 정함」 과 「장비 없음」 은 다르다** — 앞은 항목을 아직 안 이은 것이고, 뒤는
    # 이었는데 그 항목이 되는 장비가 없는 것이다. 해야 할 일이 다르다.
    assert names(equipment="none", test_item="none") == {f"안정함-{tag}"}

    # 전사 목록에서도 같은 물음이 선다 — 확정된 것만 보이므로 후보는 안 걸린다.
    wide = client.get(
        "/api/reliability-tests",
        params={"status": "all", "q": tag, "equipment": "none", "limit": 200},
        headers=admin.headers,
    )
    assert wide.status_code == 200, wide.text
    assert {one["name"] for one in wide.json()["items"]} == {
        f"안되는것-{tag}",
        f"안정함-{tag}",
    }


def test_사업부마다_장비가_다르다(client: TestClient, admin: Signed) -> None:
    """같은 항목이라도 저 사업부에는 장비가 있고 이 사업부에는 없다 — 항목만 보면
    「어딘가에는 있다」 를 「우리가 할 수 있다」 로 읽는다."""
    tag = uuid.uuid4().hex[:6]
    item = _term(client, admin, "test_item", f"경도-{tag}")
    # 장비는 관리자의 부서(mx 사업부)에만 있다.
    _equipment_for(client, admin, tag, item)

    _test(client, admin, name=f"우리것-{tag}", test_item_term_ids=[item])
    made = client.post(
        "/api/reliability-tests",
        json={"division_code": "vd", "name": f"남의것-{tag}", "test_item_term_ids": [item]},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text

    got = client.get(
        "/api/reliability-tests",
        params={"status": "all", "q": tag, "equipment": "none", "limit": 200},
        headers=admin.headers,
    )
    assert got.status_code == 200, got.text
    # mx 에는 장비가 있으니 안 걸리고, vd 에는 없으니 걸린다.
    assert {one["name"] for one in got.json()["items"]} == {f"남의것-{tag}"}

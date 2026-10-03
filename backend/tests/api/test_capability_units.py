"""신뢰성 조건의 단위 — **축의 단위로 옮겨 판정하고, 그 단위로 말한다.**

낙하 높이 축은 si_unit 이 m, display_unit 이 cm 다. 판정만 si_unit(m)으로 옮기고 장비 조건·
판정 글자·검색 화면은 display_unit(cm)이라, 152 cm 가 1.52 가 되어 「1.52 cm 에서」 로 찍히고
0~100 cm 장비를 통과했다(2026-10-03). 두 단위가 같은 열여섯 축에서는 안 드러나던 일이다.

여기서 지키는 것 셋 — 축 단위로 적은 값은 그대로 · 다른 단위(m)로 적은 값은 축 단위(cm)로
환산 · si_unit 이 빈 축(사이클 수 「회」)도 환산 없이 판정.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import Signed, category_id, site_id


def _condition_definitions(client: TestClient, admin: Signed) -> dict[str, dict[str, Any]]:
    rows = client.get(
        "/api/attribute-definitions",
        params={"target": "reliability_test"},
        headers=admin.headers,
    ).json()
    return {one["key"]: one for one in rows if one["kind"] == "condition"}


def _equipment_with_limit(
    client: TestClient,
    admin: Signed,
    *,
    item: str,
    condition_id: str,
    low: float | None,
    high: float | None,
    name: str,
) -> str:
    """시험 항목 하나와 조건 한 칸을 가진 장비. 조건 값은 **축의 단위 그대로** 적는다 —
    화면(`TestItemPanel`)이 그렇게 보낸다."""
    equipment = client.post(
        "/api/equipment",
        json={
            "asset_no": f"DT-{uuid.uuid4().hex[:6]}",
            "name": name,
            "workspace_slug": admin.workspace,
            "site_term_id": site_id(client, admin),
            "location": "3동 201호",
            "category_term_id": category_id(client, admin),
        },
        headers=admin.headers,
    )
    assert equipment.status_code == 201, equipment.text
    test_item = client.post(
        "/api/equipment-test-items",
        json={"equipment_id": equipment.json()["id"], "test_item_term_id": item},
        headers=admin.headers,
    )
    assert test_item.status_code == 201, test_item.text
    limit = client.put(
        f"/api/equipment-test-items/{test_item.json()['id']}/limits",
        json={"condition_key_id": condition_id, "min_value": low, "max_value": high},
        headers=admin.headers,
    )
    assert limit.status_code == 200, limit.text
    return str(equipment.json()["id"])


def _capability(client: TestClient, admin: Signed, test_id: str) -> dict[str, Any]:
    answer = client.get(f"/api/reliability-tests/{test_id}/equipment", headers=admin.headers)
    assert answer.status_code == 200, answer.text
    body: dict[str, Any] = answer.json()
    return body


def _reliability_test(
    client: TestClient,
    admin: Signed,
    *,
    name: str,
    item: str,
    attributes: list[dict[str, Any]],
) -> str:
    made = client.post(
        "/api/reliability-tests",
        json={
            "division_code": "mx",
            "name": name,
            "test_item_term_ids": [item],
            "attributes": attributes,
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def test_cm_로_적은_낙하_높이는_cm_로_판정하고_cm_로_말한다(
    client: TestClient,
    admin: Signed,
    term_factory: Callable[[str, str], str],
    condition_ids: dict[str, str],
) -> None:
    tag = uuid.uuid4().hex[:6]
    item = term_factory("test_item", f"지그 낙하-{tag}")
    # 축의 단위(cm)로 적힌 장비 조건 둘 — 200 cm 까지 되는 것과 100 cm 까지 되는 것.
    _equipment_with_limit(
        client,
        admin,
        item=item,
        condition_id=condition_ids["drop_height"],
        low=0,
        high=200,
        name=f"낙하 시험기 2 m-{tag}",
    )
    _equipment_with_limit(
        client,
        admin,
        item=item,
        condition_id=condition_ids["drop_height"],
        low=0,
        high=100,
        name=f"낙하 시험기 1 m-{tag}",
    )
    definitions = _condition_definitions(client, admin)
    # 조건 속성 칸의 단위는 축의 표시 단위(cm)다 — 152 는 152 cm 다.
    assert definitions["reliability_cond_drop_height"]["unit"] == "cm"
    test_id = _reliability_test(
        client,
        admin,
        name=f"지그 낙하 152 cm-{tag}",
        item=item,
        attributes=[
            {
                "definition_id": definitions["reliability_cond_drop_height"]["id"],
                "num_value": 152,
            }
        ],
    )

    body = _capability(client, admin, test_id)
    assert body["skipped"] == []
    assert body["conditions_asked"] == 1
    row = body["items"][0]
    # 1.52 로 옮겨 묻던 때는 1 m 짜리도 통과했다 — 152 cm 는 2 m 짜리만 된다.
    assert {one["equipment_name"] for one in row["hits"]} == {f"낙하 시험기 2 m-{tag}"}
    assert row["unmet_count"] == 1
    condition = row["hits"][0]["conditions"][0]
    assert condition["verdict"] == "met"
    assert condition["asked"] == "152 cm 에서"
    assert condition["condition_range"] == "0 cm ~ 200 cm"
    assert condition["display_unit"] == "cm"


def test_m_로_적은_낙하_높이는_cm_로_환산해_판정한다(
    client: TestClient,
    admin: Signed,
    term_factory: Callable[[str, str], str],
    condition_ids: dict[str, str],
) -> None:
    """문서가 1.5 m 로 적으면 그렇게 적는다 — 서버가 150 cm 로 옮긴다(축 정의의 약속)."""
    tag = uuid.uuid4().hex[:6]
    item = term_factory("test_item", f"지그 낙하-{tag}")
    _equipment_with_limit(
        client,
        admin,
        item=item,
        condition_id=condition_ids["drop_height"],
        low=0,
        high=200,
        name=f"낙하 시험기 2 m-{tag}",
    )
    _equipment_with_limit(
        client,
        admin,
        item=item,
        condition_id=condition_ids["drop_height"],
        low=0,
        high=100,
        name=f"낙하 시험기 1 m-{tag}",
    )
    definitions = _condition_definitions(client, admin)
    test_id = _reliability_test(
        client,
        admin,
        name=f"지그 낙하 1.5 m-{tag}",
        item=item,
        attributes=[
            {
                "definition_id": definitions["reliability_cond_drop_height"]["id"],
                "num_value": 1.5,
                "unit": "m",
            }
        ],
    )

    body = _capability(client, admin, test_id)
    assert body["skipped"] == []
    row = body["items"][0]
    assert {one["equipment_name"] for one in row["hits"]} == {f"낙하 시험기 2 m-{tag}"}
    assert row["unmet_count"] == 1
    assert row["hits"][0]["conditions"][0]["asked"] == "150 cm 에서"


def test_si_unit_이_빈_축도_환산_없이_판정한다(
    client: TestClient,
    admin: Signed,
    term_factory: Callable[[str, str], str],
    condition_ids: dict[str, str],
) -> None:
    """사이클 수는 si_unit 이 비고 display_unit 이 「회」 다. si_unit 으로 옮기던 때는
    「회」 를 「」 로 못 바꾼다며 조건을 빼고(`skipped`) 판정했다 — 조건 하나가 빠진 채
    「가능」 이 나온 셈이다."""
    tag = uuid.uuid4().hex[:6]
    item = term_factory("test_item", f"열충격-{tag}")
    _equipment_with_limit(
        client,
        admin,
        item=item,
        condition_id=condition_ids["cycles"],
        low=1,
        high=1000,
        name=f"열충격 챔버-{tag}",
    )
    definitions = _condition_definitions(client, admin)
    test_id = _reliability_test(
        client,
        admin,
        name=f"열충격 24 cyc-{tag}",
        item=item,
        attributes=[
            {"definition_id": definitions["reliability_cond_cycles"]["id"], "num_value": 24}
        ],
    )

    body = _capability(client, admin, test_id)
    assert body["skipped"] == []
    row = body["items"][0]
    assert {one["equipment_name"] for one in row["hits"]} == {f"열충격 챔버-{tag}"}
    assert row["hits"][0]["conditions"][0]["asked"] == "24 회 에서"

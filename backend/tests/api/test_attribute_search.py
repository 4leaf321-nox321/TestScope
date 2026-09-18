"""속성으로 묻기 — **적어 둔 것을 되찾을 수 있나.**

여기서 지키는 것 — 목록이 속성 값으로 걸러진다(수치·문장·있음, 단위가 달라도) · 여러 조건은
모두 만족해야 한다 · 모르는 속성·못 읽는 꼴은 조용히 빈 답을 내지 않고 400 · 신뢰성 시험의
조건 속성이 그대로 장비 판정이 된다(범위는 위·아래 두 물음) · 못 바꾸는 단위는 빼고 말한다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import Signed, category_id, site_id


def _definition(client: TestClient, admin: Signed, **payload: Any) -> dict[str, Any]:
    made = client.post("/api/attribute-definitions", json=payload, headers=admin.headers)
    assert made.status_code == 201, made.text
    body: dict[str, Any] = made.json()
    return body


def _equipment(client: TestClient, admin: Signed, **extra: Any) -> dict[str, Any]:
    made = client.post(
        "/api/equipment",
        json={
            "asset_no": f"EQ-{uuid.uuid4().hex[:6]}",
            "name": "챔버",
            "workspace_slug": admin.workspace,
            "site_term_id": site_id(client, admin),
            "location": "3동 201호",
            "category_term_id": category_id(client, admin),
            **extra,
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    body: dict[str, Any] = made.json()
    return body


def _assets(client: TestClient, admin: Signed, *attrs: str) -> set[str]:
    got = client.get(
        "/api/equipment",
        params=[("attr", one) for one in attrs] + [("limit", "200")],
        headers=admin.headers,
    )
    assert got.status_code == 200, got.text
    return {one["asset_no"] for one in got.json()["items"]}


def test_장비_목록을_속성_값으로_거른다(client: TestClient, admin: Signed) -> None:
    tag = uuid.uuid4().hex[:6]
    year = _definition(
        client,
        admin,
        target="equipment",
        label=f"투자 연도-{tag}",
        key=f"invest_year_{tag}",
        kind="number",
        status="standard",
    )
    use = _definition(
        client,
        admin,
        target="equipment",
        label=f"장비 용도-{tag}",
        key=f"use_{tag}",
        kind="text",
        status="standard",
    )
    url = _definition(
        client,
        admin,
        target="equipment",
        label=f"예약 URL-{tag}",
        key=f"book_{tag}",
        kind="text",
        status="standard",
    )

    old = _equipment(
        client,
        admin,
        attributes=[
            {"definition_id": year["id"], "num_value": 2016},
            {"definition_id": use["id"], "text_value": "고온 신뢰성 평가"},
        ],
    )
    new = _equipment(
        client,
        admin,
        attributes=[
            {"definition_id": year["id"], "num_value": 2022},
            {"definition_id": use["id"], "text_value": "고온 수명"},
            {"definition_id": url["id"], "text_value": "http://booking/1"},
        ],
    )
    blank = _equipment(client, admin)

    assert _assets(client, admin, f"invest_year_{tag}>=2020") == {new["asset_no"]}
    assert _assets(client, admin, f"invest_year_{tag}<2020") == {old["asset_no"]}
    # 값이 안 적힌 장비는 어느 쪽에도 안 든다 — 「모른다」 는 「아니다」 가 아니다.
    assert blank["asset_no"] not in _assets(client, admin, f"invest_year_{tag}>=1900")
    # 적혀 있기만 하면.
    assert _assets(client, admin, f"book_{tag}*") == {new["asset_no"]}
    # 포함(대소문자·부분 일치)과 AND.
    assert _assets(client, admin, f"use_{tag}~고온") == {old["asset_no"], new["asset_no"]}
    assert _assets(client, admin, f"use_{tag}~고온", f"invest_year_{tag}>=2020") == {
        new["asset_no"]
    }
    assert _assets(client, admin, f"use_{tag}=고온 수명") == {new["asset_no"]}
    assert _assets(client, admin, f"use_{tag}!=고온 수명") == {old["asset_no"]}

    # key 는 주소에 실리는 이름이라 한글·공백은 못 쓴다 — 쓰면 영영 못 거르는 칸이 된다.
    assert (
        client.post(
            "/api/attribute-definitions",
            json={
                "target": "equipment",
                "label": f"못 거르는 칸-{tag}",
                "key": f"투자 연도 {tag}",
                "kind": "text",
            },
            headers=admin.headers,
        ).status_code
        == 400
    )

    # 오타는 빈 답이 아니라 400 — 빈 답이면 사람은 값이 안 적힌 줄 안다.
    assert (
        client.get(
            "/api/equipment", params={"attr": f"없는키_{tag}>=1"}, headers=admin.headers
        ).status_code
        == 400
    )
    assert (
        client.get(
            "/api/equipment", params={"attr": f"invest_year_{tag}"}, headers=admin.headers
        ).status_code
        == 400
    )
    assert (
        client.get(
            "/api/equipment",
            params={"attr": f"invest_year_{tag}>=올해"},
            headers=admin.headers,
        ).status_code
        == 400
    )


def test_단위가_달라도_같은_자로_잰다(client: TestClient, admin: Signed) -> None:
    """kN 으로 적힌 값과 N 으로 적힌 값이 같은 물음에 답해야 한다 — 안 그러면 1000배 틀린다."""
    tag = uuid.uuid4().hex[:6]
    load = _definition(
        client,
        admin,
        target="equipment",
        label=f"하중-{tag}",
        key=f"load_{tag}",
        kind="number",
        unit="kN",
        status="standard",
    )
    big = _equipment(
        client,
        admin,
        attributes=[{"definition_id": load["id"], "num_value": 50000, "unit": "N"}],
    )
    small = _equipment(
        client,
        admin,
        attributes=[{"definition_id": load["id"], "num_value": 5, "unit": "kN"}],
    )
    found = _assets(client, admin, f"load_{tag}>=20")
    assert big["asset_no"] in found and small["asset_no"] not in found


def test_시험의_조건_속성이_그대로_장비_판정이_된다(
    client: TestClient,
    admin: Signed,
    term_factory: Callable[[str, str], str],
    condition_ids: dict[str, str],
) -> None:
    """이 시스템의 물음 — 「이 시험, 어느 장비로 돌리나」. 시험 항목까지만 이으면 답이
    「인장 되는 장비 N대」 라 사람이 다시 장비를 하나씩 열어 봐야 한다."""
    tag = uuid.uuid4().hex[:6]
    item = term_factory("test_item", f"고온인장-{tag}")
    temperature = _definition(
        client,
        admin,
        target="reliability_test",
        label=f"시험 온도-{tag}",
        key=f"temp_{tag}",
        kind="condition",
        unit="degC",
        condition_key_id=condition_ids["temperature"],
        status="standard",
    )
    nonsense = _definition(
        client,
        admin,
        target="reliability_test",
        label=f"측정 주기-{tag}",
        key=f"cycle_{tag}",
        kind="condition",
        unit="쇼어",
        condition_key_id=condition_ids["temperature"],
        status="standard",
    )

    # 챔버 둘 — 하나는 -40 ~ 150 까지, 하나는 상온 위쪽만.
    wide = _equipment(client, admin, name=f"광역 챔버-{tag}")
    narrow = _equipment(client, admin, name=f"고온 챔버-{tag}")
    for equipment, low, high in ((wide, -40, 150), (narrow, 20, 150)):
        linked = client.post(
            "/api/equipment-test-items",
            json={"equipment_id": equipment["id"], "test_item_term_id": item},
            headers=admin.headers,
        )
        assert linked.status_code == 201, linked.text
        limited = client.put(
            f"/api/equipment-test-items/{linked.json()['id']}/limits",
            json={
                "condition_key_id": condition_ids["temperature"],
                "min_value": low,
                "max_value": high,
            },
            headers=admin.headers,
        )
        assert limited.status_code == 200, limited.text

    test = client.post(
        "/api/reliability-tests",
        json={
            "workspace_slug": admin.workspace,
            "name": f"열충격-{tag}",
            "test_item_term_ids": [item],
            "attributes": [
                {
                    "definition_id": temperature["id"],
                    "num_min": -40,
                    "num_max": 125,
                    "unit": "degC",
                },
                {"definition_id": nonsense["id"], "num_min": 3, "num_max": 5, "unit": "쇼어"},
            ],
        },
        headers=admin.headers,
    )
    assert test.status_code == 201, test.text

    answer = client.get(
        f"/api/reliability-tests/{test.json()['id']}/equipment", headers=admin.headers
    )
    assert answer.status_code == 200, answer.text
    body = answer.json()
    # 범위 하나는 물음 둘 — 위로 125 까지, 아래로 -40 까지.
    assert body["conditions_asked"] == 2
    # 못 바꾸는 단위는 조용히 빼지 않고 말한다.
    assert [one["label"] for one in body["skipped"]] == [f"측정 주기-{tag}"]
    row = body["items"][0]
    assert row["value"] == f"고온인장-{tag}"
    names = {one["equipment_name"] for one in row["hits"]}
    assert names == {f"광역 챔버-{tag}"}
    assert row["unmet_count"] == 1
    verdicts = {one["verdict"] for one in row["hits"][0]["conditions"]}
    assert verdicts == {"met"}


def test_시험_목록도_조건_속성으로_거른다(
    client: TestClient, admin: Signed, condition_ids: dict[str, str]
) -> None:
    """-40 이하로 내려가는 시험만. 조건을 적어 두고도 못 찾으면 적을 이유가 없다."""
    tag = uuid.uuid4().hex[:6]
    temperature = _definition(
        client,
        admin,
        target="reliability_test",
        label=f"시험 온도-{tag}",
        key=f"temp_{tag}",
        kind="condition",
        unit="degC",
        condition_key_id=condition_ids["temperature"],
        status="standard",
    )
    for name, low, high in ((f"열충격-{tag}", -40, 125), (f"고온고습-{tag}", 85, 85)):
        made = client.post(
            "/api/reliability-tests",
            json={
                "workspace_slug": admin.workspace,
                "name": name,
                "attributes": [
                    {
                        "definition_id": temperature["id"],
                        "num_min": low,
                        "num_max": high,
                        "unit": "degC",
                    }
                ],
            },
            headers=admin.headers,
        )
        assert made.status_code == 201, made.text

    cold = client.get(
        "/api/reliability-tests", params={"attr": f"temp_{tag}<=-40"}, headers=admin.headers
    )
    assert cold.status_code == 200, cold.text
    assert [one["name"] for one in cold.json()] == [f"열충격-{tag}"]

    hot = client.get(
        "/api/reliability-tests", params={"attr": f"temp_{tag}>=100"}, headers=admin.headers
    )
    assert {one["name"] for one in hot.json()} == {f"열충격-{tag}"}

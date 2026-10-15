"""신뢰성 시험 수행 가능 현황 · 대체된 규격을 가리키는 곳(2026-10-16).

현황판(`/reliability-tests/coverage`)이 지키는 것:

1. 「되는 장비」 와 같은 판정에 교정을 더한다 — 조건이 다 맞고 교정이 유효한 장비만 「돌릴 수
   있음」, 교정 만료는 빼고, 조건 일부를 모르거나 교정 이력이 없으면 「확인 필요」.
2. 시험의 상태는 병목 항목이 정한다 — 불가 · 확인 필요 · 1대뿐 · 교정 임박 · 여유.

대체된 규격(`/methods/superseded-refs`)이 지키는 것:

3. 옛 판을 가리키는 신뢰성 시험 · 장비 시험 항목이 새 판과 함께 서고, 남은 일과 알림이 그것을
   말한다. 새 판으로 고치면 빠진다.
4. 규격을 병합하면 신뢰성 시험이 근거로 적은 참조도 남는 쪽으로 옮겨 간다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import Signed, category_id, site_id


def _definitions(client: TestClient, admin: Signed) -> dict[str, dict[str, Any]]:
    rows = client.get(
        "/api/attribute-definitions",
        params={"target": "reliability_test"},
        headers=admin.headers,
    ).json()
    return {one["key"]: one for one in rows}


def _equipment(
    client: TestClient,
    admin: Signed,
    *,
    item: str,
    limit: tuple[float, float] | None,
    condition_id: str,
    calibration: str = "none",
    method_id: str | None = None,
) -> dict[str, Any]:
    """시험 항목 하나를 가진 장비. `calibration`: none(대상 아님) · valid · soon · expired ·
    missing(대상인데 이력 없음)."""
    tag = uuid.uuid4().hex[:6]
    required = calibration != "none"
    made = client.post(
        "/api/equipment",
        json={
            "asset_no": f"CV-{tag}",
            "name": f"낙하 시험기-{tag}",
            "workspace_slug": admin.workspace,
            "site_term_id": site_id(client, admin),
            "location": "3동 201호",
            "category_term_id": category_id(client, admin),
            "calibration_required": required,
            "calibration_interval_months": 12 if required else None,
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    equipment: dict[str, Any] = made.json()
    test_item = client.post(
        "/api/equipment-test-items",
        json={
            "equipment_id": equipment["id"],
            "test_item_term_id": item,
            "method_id": method_id,
        },
        headers=admin.headers,
    )
    assert test_item.status_code == 201, test_item.text
    equipment["test_item_id"] = test_item.json()["id"]
    if limit is not None:
        put = client.put(
            f"/api/equipment-test-items/{test_item.json()['id']}/limits",
            json={
                "condition_key_id": condition_id,
                "min_value": limit[0],
                "max_value": limit[1],
            },
            headers=admin.headers,
        )
        assert put.status_code == 200, put.text
    today = date.today()
    due = {
        "valid": today + timedelta(days=300),
        "soon": today + timedelta(days=20),
        "expired": today - timedelta(days=1),
    }.get(calibration)
    if due is not None:
        added = client.post(
            f"/api/equipment/{equipment['id']}/calibrations",
            json={
                "calibrated_on": (due - timedelta(days=365)).isoformat(),
                "next_due_on": due.isoformat(),
            },
            headers=admin.headers,
        )
        assert added.status_code == 201, added.text
    return equipment


def _test(
    client: TestClient,
    admin: Signed,
    *,
    item: str,
    attributes: list[dict[str, Any]],
) -> str:
    made = client.post(
        "/api/reliability-tests",
        json={
            "division_code": "mx",
            "name": f"현황 시험-{uuid.uuid4().hex[:6]}",
            "test_item_term_ids": [item],
            "attributes": attributes,
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def _row(client: TestClient, admin: Signed, test_id: str) -> dict[str, Any]:
    board = client.get(
        "/api/reliability-tests/coverage", params={"division": "mx"}, headers=admin.headers
    )
    assert board.status_code == 200, board.text
    found = [one for one in board.json()["rows"] if one["test_id"] == test_id]
    assert len(found) == 1, board.text[:300]
    row: dict[str, Any] = found[0]
    return row


def test_현황판은_조건과_교정으로_센다(
    client: TestClient,
    admin: Signed,
    term_factory: Callable[[str, str], str],
    condition_ids: dict[str, str],
) -> None:
    item = term_factory("test_item", f"현황 낙하-{uuid.uuid4().hex[:6]}")
    drop = condition_ids["drop_height"]
    _equipment(client, admin, item=item, limit=(0, 200), condition_id=drop)
    _equipment(client, admin, item=item, limit=(0, 200), condition_id=drop, calibration="soon")
    _equipment(
        client, admin, item=item, limit=(0, 200), condition_id=drop, calibration="expired"
    )
    _equipment(client, admin, item=item, limit=(0, 100), condition_id=drop)  # 조건 미달 — 빠짐
    _equipment(client, admin, item=item, limit=None, condition_id=drop)  # 조건 모름
    _equipment(
        client, admin, item=item, limit=(0, 200), condition_id=drop, calibration="missing"
    )
    height = _definitions(client, admin)["reliability_cond_drop_height"]
    test_id = _test(
        client,
        admin,
        item=item,
        attributes=[{"definition_id": height["id"], "num_value": 152}],
    )

    row = _row(client, admin, test_id)
    [counted] = row["items"]
    assert (counted["ready"], counted["soon"], counted["expired"], counted["check"]) == (
        2,
        1,
        1,
        2,
    )
    # 장비의 부서가 그 사업부(MX)에 속한다.
    assert counted["in_division"] == 2
    # 둘 중 하나가 곧 교정이 끝난다 — 끝나면 1대뿐이 된다.
    assert row["state"] == "soon"
    assert row["bottleneck"] == counted["value"]
    assert row["conditions_asked"] == 1


def test_병목_항목이_상태를_정한다(
    client: TestClient,
    admin: Signed,
    term_factory: Callable[[str, str], str],
    condition_ids: dict[str, str],
) -> None:
    drop = condition_ids["drop_height"]
    nobody = term_factory("test_item", f"아무도 안 함-{uuid.uuid4().hex[:6]}")
    unsure = term_factory("test_item", f"조건 모름-{uuid.uuid4().hex[:6]}")
    lonely = term_factory("test_item", f"한 대뿐-{uuid.uuid4().hex[:6]}")
    plenty = term_factory("test_item", f"여유-{uuid.uuid4().hex[:6]}")
    _equipment(client, admin, item=unsure, limit=None, condition_id=drop)
    _equipment(client, admin, item=lonely, limit=(0, 200), condition_id=drop)
    for _ in range(3):
        _equipment(client, admin, item=plenty, limit=(0, 200), condition_id=drop)
    height = _definitions(client, admin)["reliability_cond_drop_height"]
    asked = [{"definition_id": height["id"], "num_value": 152}]

    states = {
        name: _row(client, admin, _test(client, admin, item=item, attributes=asked))["state"]
        for name, item in (
            ("nobody", nobody),
            ("unsure", unsure),
            ("lonely", lonely),
            ("plenty", plenty),
        )
    }
    assert states == {"nobody": "none", "unsure": "check", "lonely": "single", "plenty": "ok"}

    board = client.get(
        "/api/reliability-tests/coverage",
        params={"division": "nowhere"},
        headers=admin.headers,
    )
    assert board.status_code == 404


def _method(client: TestClient, admin: Signed, code: str, edition: str) -> dict[str, Any]:
    made = client.post(
        "/api/methods",
        json={"code": code, "edition": edition, "title": f"{code} {edition}"},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    body: dict[str, Any] = made.json()
    return body


def test_대체된_규격을_가리키는_곳이_서고_알림과_남은_일이_말한다(
    client: TestClient,
    admin: Signed,
    term_factory: Callable[[str, str], str],
    condition_ids: dict[str, str],
) -> None:
    code = f"ASTM Q{uuid.uuid4().int % 100000}"
    old = _method(client, admin, code, "2014")
    new = _method(client, admin, code, "2022")
    retired = client.patch(
        f"/api/methods/{old['id']}",
        json={"status": "superseded", "superseded_by_id": new["id"]},
        headers=admin.headers,
    )
    assert retired.status_code == 200, retired.text

    item = term_factory("test_item", f"규격 시험-{uuid.uuid4().hex[:6]}")
    equipment = _equipment(
        client,
        admin,
        item=item,
        limit=None,
        condition_id=condition_ids["drop_height"],
        method_id=old["id"],
    )
    reference = _definitions(client, admin)["reliability_reference_method"]
    test_id = _test(
        client,
        admin,
        item=item,
        attributes=[{"definition_id": reference["id"], "method_id": old["id"]}],
    )

    refs = client.get("/api/methods/superseded-refs", headers=admin.headers)
    assert refs.status_code == 200, refs.text
    mine = [one for one in refs.json() if one["method_id"] == old["id"]]
    assert {(one["kind"], one["target_id"]) for one in mine} == {
        ("reliability_test", test_id),
        ("equipment", equipment["id"]),
    }
    assert {one["successor_label"] for one in mine} == {f"{code} 2022"}
    assert {one["method_label"] for one in mine} == {f"{code} 2014"}

    rows = {
        one["key"]: one
        for one in client.get("/api/server/maintenance", headers=admin.headers).json()
    }
    assert rows["method_superseded_refs"]["link"] == "/methods/superseded-refs"
    assert rows["method_superseded_refs"]["count"] >= 2

    # 관리자는 그 부서(MX 사업부)의 관리자이기도 하다 — 규격 하나에 한 번 운다.
    told = [
        one
        for one in client.get("/api/notifications", headers=admin.headers).json()
        if one["kind"] == "method.superseded" and code in one["title"]
    ]
    assert len(told) == 1
    assert "신뢰성 시험 1건" in told[0]["body"] and "장비 시험 항목 1건" in told[0]["body"]

    # 새 판으로 고치면 빠진다.
    fixed = client.patch(
        f"/api/equipment-test-items/{equipment['test_item_id']}",
        json={"method_id": new["id"]},
        headers=admin.headers,
    )
    assert fixed.status_code == 200, fixed.text
    after = [
        one
        for one in client.get("/api/methods/superseded-refs", headers=admin.headers).json()
        if one["method_id"] == old["id"]
    ]
    assert [one["kind"] for one in after] == ["reliability_test"]


def test_규격을_병합하면_신뢰성_시험의_참조도_옮겨_간다(
    client: TestClient,
    admin: Signed,
    term_factory: Callable[[str, str], str],
) -> None:
    number = uuid.uuid4().int % 100000
    source = _method(client, admin, f"ASTM R{number}-19", "")
    target = _method(client, admin, f"ASTM R{number}", "")
    item = term_factory("test_item", f"병합 시험-{uuid.uuid4().hex[:6]}")
    reference = _definitions(client, admin)["reliability_reference_method"]
    test_id = _test(
        client,
        admin,
        item=item,
        attributes=[{"definition_id": reference["id"], "method_id": source["id"]}],
    )
    merged = client.post(
        f"/api/methods/{source['id']}/merge",
        json={"target_id": target["id"]},
        headers=admin.headers,
    )
    assert merged.status_code == 200, merged.text
    values = client.get(f"/api/reliability-tests/{test_id}", headers=admin.headers).json()
    refs = [one for one in values["attributes"] if one.get("method_id")]
    assert [one["method_id"] for one in refs] == [target["id"]]

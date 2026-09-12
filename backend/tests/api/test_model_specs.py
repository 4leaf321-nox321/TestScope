"""모델 사양 — 정의는 통제하고, 값은 자유롭게(ADR 0005).

여기서 지키는 것 셋:

1. 종류에 안 맞는 칸으로 저장되지 않는다 — 조용히 사라지는 값이 없어야 한다.
2. 검색축에 이은 사양은 **시험 조건으로 따라 들어간다** — 같은 숫자를 두 번 안 적는다.
3. 손으로 고쳐 둔 조건은 안 덮는다 — 사양서가 실측을 지우면 안 된다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import Signed, site_id


def _definitions(client: TestClient, admin: Signed) -> dict[str, dict[str, Any]]:
    response = client.get("/api/spec-definitions", headers=admin.headers)
    assert response.status_code == 200, response.text
    return {row["key"]: row for row in response.json()}


def _model(client: TestClient, admin: Signed, **extra: object) -> dict[str, Any]:
    """기종 하나와 그것이 들어갈 계열을 함께 만든다.

    **모든 기종은 계열에 속한다.** 예외를 두면 화면이 매번 갈래를 타야 하고,
    한 곳에서 빠뜨리면 그 기종이 조용히 목록에서 사라진다(ADR 0006).
    """
    series = client.post(
        "/api/equipment-series",
        json={"name": f"계열-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert series.status_code == 201, series.text
    payload = {
        "series_id": series.json()["id"],
        "name": f"기종-{uuid.uuid4().hex[:6]}",
        **extra,
    }
    response = client.post("/api/equipment-models", json=payload, headers=admin.headers)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def _put_spec(client: TestClient, admin: Signed, model_id: str, **payload: object) -> Any:
    return client.put(
        f"/api/equipment-models/{model_id}/specs", json=payload, headers=admin.headers
    )


def test_설치가_사양_그룹과_정의를_심는다(client: TestClient, admin: Signed) -> None:
    groups = client.get("/api/spec-groups", headers=admin.headers)
    assert groups.status_code == 200, groups.text
    slugs = {row["slug"] for row in groups.json()}
    assert {"capacity", "space", "installation"} <= slugs

    definitions = _definitions(client, admin)
    # 카탈로그에서 가장 흔한 셋. 하나라도 빠지면 사양표가 반쪽이 된다.
    assert {"weight", "force_capacity", "vertical_test_space"} <= set(definitions)

    # **분류를 안 붙인 채 심는다** — 그래서 어떤 장비에서도 뜬다.
    assert definitions["weight"]["categories"] == []
    # 하중 용량만 검색축에 이어져 있다.
    assert definitions["force_capacity"]["condition_key_id"] is not None
    assert definitions["weight"]["condition_key_id"] is None


def test_종류에_안_맞는_칸은_거절한다(client: TestClient, admin: Signed) -> None:
    model = _model(client, admin)
    definitions = _definitions(client, admin)

    # 수치 사양에 값이 없다.
    response = _put_spec(client, admin, model["id"], definition_id=definitions["weight"]["id"])
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "TSC-SPEC-0008"

    # 구간 사양에 거꾸로 넣은 범위.
    response = _put_spec(
        client,
        admin,
        model["id"],
        definition_id=definitions["test_temperature"]["id"],
        num_min=300,
        num_max=-70,
    )
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "TSC-SPEC-0010"

    # 고를 수 있는 값이 아닌 것.
    response = _put_spec(
        client,
        admin,
        model["id"],
        definition_id=definitions["drive_type"]["id"],
        text_value="증기기관식",
    )
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "TSC-SPEC-0011"


def test_사양표는_그룹_순서로_오고_값이_있는_것만_준다(
    client: TestClient, admin: Signed
) -> None:
    model = _model(client, admin)
    definitions = _definitions(client, admin)

    assert (
        _put_spec(
            client,
            admin,
            model["id"],
            definition_id=definitions["weight"]["id"],
            num_value=872,
        ).status_code
        == 200
    )
    assert (
        _put_spec(
            client,
            admin,
            model["id"],
            definition_id=definitions["force_capacity"]["id"],
            num_value=300,
        ).status_code
        == 200
    )

    sheet = client.get(f"/api/equipment-models/{model['id']}/specs", headers=admin.headers)
    assert sheet.status_code == 200, sheet.text
    groups = sheet.json()["groups"]
    # 용량(10)이 설치 조건(50)보다 먼저다.
    assert [group["slug"] for group in groups] == ["capacity", "installation"]
    # **적은 둘만 온다.** 나머지 서른여섯은 정의 API 가 준다.
    assert sum(len(group["items"]) for group in groups) == 2

    item = groups[0]["items"][0]
    assert item["key"] == "force_capacity"
    assert item["display_unit"] == "kN"
    assert item["applies"] is True


def test_검색축에_이은_사양은_장비_등록에서_시험_항목_조건이_된다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    """**저장할 때가 아니라 복사할 때 반영된다.**

    시험 항목은 계열에 붙고 사양은 기종에 붙는다. 저장하는 순간 계열의 시험 항목에 써 넣으면
    같은 계열의 다른 기종까지 그 값이 된다(ADR 0006).
    """
    model = _model(client, admin)
    definitions = _definitions(client, admin)
    item = term_factory("test_item", f"인장-{uuid.uuid4().hex[:6]}")

    test_item = client.post(
        f"/api/equipment-series/{model['series_id']}/test-items",
        json={"test_item_term_id": item},
        headers=admin.headers,
    )
    assert test_item.status_code == 201, test_item.text

    saved = _put_spec(
        client,
        admin,
        model["id"],
        definition_id=definitions["force_capacity"]["id"],
        num_value=300,
    )
    assert saved.status_code == 200, saved.text
    # **검색에 쓰이는 값인지 말해 준다** — 안 말하면 사람이 알 방법이 없다.
    assert saved.json()["search_axis"] == "하중 용량"
    assert saved.json()["existing_units"] == 0

    # 계열의 시험 항목에는 안 써 넣는다. 그것이 이 설계의 요점이다.
    series = client.get(
        f"/api/equipment-series/{model['series_id']}", headers=admin.headers
    ).json()
    assert series["test_items"][0]["limits"] == []

    made = client.post(
        "/api/equipment",
        json={
            "asset_no": f"SPC-{uuid.uuid4().hex[:6]}",
            "site_term_id": site_id(client, admin),
            "location": "3동 201호",
            "name": "사양에서 조건을 받은 장비",
            "workspace_slug": admin.workspace,
            "model_id": model["id"],
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    copied = client.get(
        f"/api/equipment-test-items?equipment_id={made.json()['id']}", headers=admin.headers
    ).json()
    force = next(one for one in copied[0]["limits"] if one["condition_key"] == "force")
    assert (force["min_value"], force["max_value"]) == (None, 300)
    assert force["note"] == "사양 하중 용량에서 따옴"


def test_기종_사양이_계열_봉투를_이긴다(
    client: TestClient,
    admin: Signed,
    term_factory: Callable[[str, str], str],
    condition_ids: dict[str, str],
) -> None:
    """계열 조건은 봉투이고 기종 사양은 그 기종의 것이다.

    같은 조건이 양쪽에 있으면 기종이 이긴다 — 0.5 kN 짜리에 계열 봉투인 300 kN 이
    붙으면 검색이 없는 능력을 있다고 답한다(ADR 0006).
    """
    model = _model(client, admin)
    definitions = _definitions(client, admin)
    item = term_factory("test_item", f"인장-{uuid.uuid4().hex[:6]}")

    test_item = client.post(
        f"/api/equipment-series/{model['series_id']}/test-items",
        json={"test_item_term_id": item},
        headers=admin.headers,
    ).json()
    client.put(
        f"/api/equipment-series/{model['series_id']}/test-items/{test_item['id']}/limits",
        json={"condition_key_id": condition_ids["force"], "min_value": 0, "max_value": 300},
        headers=admin.headers,
    )
    _put_spec(
        client,
        admin,
        model["id"],
        definition_id=definitions["force_capacity"]["id"],
        num_value=0.5,
    )

    made = client.post(
        "/api/equipment",
        json={
            "asset_no": f"ENV-{uuid.uuid4().hex[:6]}",
            "site_term_id": site_id(client, admin),
            "location": "3동 201호",
            "name": "작은 기종",
            "workspace_slug": admin.workspace,
            "model_id": model["id"],
        },
        headers=admin.headers,
    )
    copied = client.get(
        f"/api/equipment-test-items?equipment_id={made.json()['id']}", headers=admin.headers
    ).json()
    force = next(one for one in copied[0]["limits"] if one["condition_key"] == "force")
    assert force["max_value"] == 0.5


def test_사양에_없는_계열_조건은_그대로_따라온다(
    client: TestClient,
    admin: Signed,
    term_factory: Callable[[str, str], str],
    condition_ids: dict[str, str],
) -> None:
    """**사양 칸으로 안 잡히는 조건이 실재한다.** 계열에 적어 둔 것이 사라지면
    그 시험 항목은 조건 없이 복사되고, 검색은 그것을 「모름」 으로 답한다(ADR 0003)."""
    model = _model(client, admin)
    item = term_factory("test_item", f"충격-{uuid.uuid4().hex[:6]}")

    test_item = client.post(
        f"/api/equipment-series/{model['series_id']}/test-items",
        json={"test_item_term_id": item},
        headers=admin.headers,
    ).json()
    client.put(
        f"/api/equipment-series/{model['series_id']}/test-items/{test_item['id']}/limits",
        json={
            "condition_key_id": condition_ids["temperature"],
            "min_value": 10,
            "max_value": 35,
        },
        headers=admin.headers,
    )

    made = client.post(
        "/api/equipment",
        json={
            "asset_no": f"KEP-{uuid.uuid4().hex[:6]}",
            "site_term_id": site_id(client, admin),
            "location": "3동 201호",
            "name": "계열 조건만 있는 장비",
            "workspace_slug": admin.workspace,
            "model_id": model["id"],
        },
        headers=admin.headers,
    )
    copied = client.get(
        f"/api/equipment-test-items?equipment_id={made.json()['id']}", headers=admin.headers
    ).json()
    temperature = next(
        one for one in copied[0]["limits"] if one["condition_key"] == "temperature"
    )
    assert (temperature["min_value"], temperature["max_value"]) == (10, 35)


def test_값이_적힌_정의는_못_지운다(client: TestClient, admin: Signed) -> None:
    model = _model(client, admin)
    definitions = _definitions(client, admin)
    _put_spec(
        client, admin, model["id"], definition_id=definitions["weight"]["id"], num_value=872
    )

    response = client.delete(
        f"/api/spec-definitions/{definitions['weight']['id']}", headers=admin.headers
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "TSC-SPEC-0007"

    # 값을 지우면 정의도 지울 수 있다 — 다만 실무에서는 끄는 쪽이 맞다.
    dropped = client.delete(
        f"/api/equipment-models/{model['id']}/specs/{definitions['weight']['id']}",
        headers=admin.headers,
    )
    assert dropped.status_code == 204, dropped.text


def test_옵션_부속_기준_사양은_장비까지_따라가고_검색이_됨이라고_안_한다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    """카탈로그가 「-180~320 °C」 를 항온조 옵션 기준으로 적는 일이 흔하다. 그것을 본체 값처럼
    두면 검색이 갖고 있지도 않은 챔버를 전제로 「80 °C 됨」 이라고 답한다 — ADR 0003 이
    막으려던 바로 그 오답. 표시가 사양 → 조건 → 판정까지 따라가야 한다."""
    model = _model(client, admin)
    definitions = _definitions(client, admin)
    item = term_factory("test_item", f"인장-{uuid.uuid4().hex[:6]}")
    client.post(
        f"/api/equipment-series/{model['series_id']}/test-items",
        json={"test_item_term_id": item},
        headers=admin.headers,
    )
    saved = _put_spec(
        client,
        admin,
        model["id"],
        definition_id=definitions["test_temperature"]["id"],
        num_min=-180,
        num_max=320,
        requires_accessory=True,
        note="항온조 TCL-N 옵션 기준",
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["value"]["requires_accessory"] is True

    made = client.post(
        "/api/equipment",
        json={
            "asset_no": f"ACC-{uuid.uuid4().hex[:6]}",
            "site_term_id": site_id(client, admin),
            "location": "3동 201호",
            "name": "챔버는 옵션인 장비",
            "workspace_slug": admin.workspace,
            "model_id": model["id"],
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    copied = client.get(
        f"/api/equipment-test-items?equipment_id={made.json()['id']}", headers=admin.headers
    ).json()
    temperature = next(
        one for one in copied[0]["limits"] if one["condition_key"] == "temperature"
    )
    assert temperature["requires_accessory"] is True
    assert "옵션 부속 기준" in temperature["note"]

    keys = {
        row["key"]: row["id"]
        for row in client.get("/api/condition-keys", headers=admin.headers).json()
    }
    found = client.post(
        "/api/search/test-items",
        json={
            "test_item_term_id": item,
            "conditions": [{"condition_key_id": keys["temperature"], "at": 80}],
        },
        headers=admin.headers,
    ).json()
    hit = next(one for one in found["hits"] if one["asset_no"] == made.json()["asset_no"])
    # 범위 안이지만 「됨」 이 아니다 — 부속이 있어야 된다.
    assert hit["verdict"] == "accessory"
    assert hit["conditions"][0]["verdict"] == "accessory"

    # 범위 밖이면 부속이 있어도 안 된다.
    missed = client.post(
        "/api/search/test-items",
        json={
            "test_item_term_id": item,
            "conditions": [{"condition_key_id": keys["temperature"], "at": 400}],
        },
        headers=admin.headers,
    ).json()
    assert all(one["asset_no"] != made.json()["asset_no"] for one in missed["hits"])

    # 그 대에 챔버가 실제로 있다면 사람이 표시를 끈다 — 그때부터 「됨」 이다.
    limit_id = temperature["id"]
    fixed = client.put(
        f"/api/equipment-test-items/{copied[0]['id']}/limits",
        json={
            "condition_key_id": keys["temperature"],
            "min_value": -180,
            "max_value": 320,
            "requires_accessory": False,
            "note": "항온조 TCL-N 보유",
        },
        headers=admin.headers,
    )
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["id"] == limit_id
    again = client.post(
        "/api/search/test-items",
        json={
            "test_item_term_id": item,
            "conditions": [{"condition_key_id": keys["temperature"], "at": 80}],
        },
        headers=admin.headers,
    ).json()
    assert (
        next(one for one in again["hits"] if one["asset_no"] == made.json()["asset_no"])[
            "verdict"
        ]
        == "match"
    )


def test_단위가_다른_사양은_환산해서_조건이_되고_못_맞추면_안_실린다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    """**500 gf 를 그대로 옮기면 500 kN 이 된다.** 1억 배 틀린 자신 있는 오답이라,
    사양 정의의 단위와 축의 단위가 다르면 곱해서 옮기고, 못 곱하는 짝은 안 옮기되
    사양표가 그렇다고 말한다."""
    from app.database import SessionLocal
    from app.modules.equipment.specs import conditions_from_specs

    tag = uuid.uuid4().hex[:6]
    model = _model(client, admin)
    groups = client.get("/api/spec-groups", headers=admin.headers).json()
    keys = {
        row["key"]: row["id"]
        for row in client.get("/api/condition-keys", headers=admin.headers).json()
    }

    # gf 로 적는 경도 시험력 → kN 인 하중 축.
    gf = client.post(
        "/api/spec-definitions",
        json={
            "key": f"test_load_gf_{tag}",
            "label": "경도 시험 하중(미소)",
            "group_id": groups[0]["id"],
            "kind": "range",
            "si_unit": "gf",
            "display_unit": "gf",
            "condition_key_id": keys["force"],
        },
        headers=admin.headers,
    )
    assert gf.status_code == 201, gf.text
    # 쇼어 경도 → kN 축. 곱할 수 없는 짝이다.
    shore = client.post(
        "/api/spec-definitions",
        json={
            "key": f"shore_a_{tag}",
            "label": "경도 (Shore A)",
            "group_id": groups[0]["id"],
            "kind": "range",
            "si_unit": "ShoreA",
            "display_unit": "ShoreA",
            "condition_key_id": keys["force"],
        },
        headers=admin.headers,
    )
    assert shore.status_code == 201, shore.text

    assert (
        _put_spec(
            client, admin, model["id"], definition_id=gf.json()["id"], num_min=10, num_max=1000
        ).status_code
        == 200
    )
    # 쇼어 값은 같은 축(하중)이라 하나만 남는다 — 먼저 넣은 gf 가 실린다(정렬은 종류·순서).

    db = SessionLocal()
    try:
        reflected = conditions_from_specs(db, uuid.UUID(model["id"]))
    finally:
        db.close()
    low, high, _label, _accessory = reflected[uuid.UUID(keys["force"])]
    # 10~1000 gf → 0.0000981~0.00981 kN. 500 kN 이 아니다.
    assert low == pytest.approx(10 * 0.00980665 / 1000)
    assert high == pytest.approx(1000 * 0.00980665 / 1000)

    other = _model(client, admin)
    assert (
        _put_spec(
            client,
            admin,
            other["id"],
            definition_id=shore.json()["id"],
            num_min=20,
            num_max=90,
        ).status_code
        == 200
    )
    db = SessionLocal()
    try:
        reflected = conditions_from_specs(db, uuid.UUID(other["id"]))
    finally:
        db.close()
    # 못 맞추는 짝은 안 실린다 — 그리고 사양표가 그렇다고 말한다.
    assert uuid.UUID(keys["force"]) not in reflected
    sheet = client.get(
        f"/api/equipment-models/{other['id']}/specs", headers=admin.headers
    ).json()
    value = next(one for group in sheet["groups"] for one in group["items"])
    assert value["axis_unit_mismatch"] is True

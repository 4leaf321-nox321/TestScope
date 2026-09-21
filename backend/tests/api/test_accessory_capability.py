"""**부속을 붙이면 되나.** 본체가 못 대는 조건을 챔버·노가 대는지 본다.

만능시험기 본체는 상온에서만 돈다. 「300 °C 에서 인장」 은 본체 사양으로는 모름이거나
안 됨이고, 지금까지 검색은 거기서 멈췄다 — 그런데 실무의 답은 대개 「노를 달면 된다」 다.

여기서 지키는 것:

1. 본체가 모르는 조건을 붙는 챔버가 대면 **`accessory`** 로 답하고, 어느 기종이 얼마까지
   내는지와 **우리가 그것을 갖고 있는지**를 함께 준다.
2. 본체로는 **안 되는**(`unmet`) 조건도 부속이 대면 살아난다 — 안 그러면 그 줄은 결과에서
   통째로 빠지고, 사람은 「그런 장비가 없다」 로 읽는다.
3. **그립·신율계는 온도를 대지 않는다.** 사양표의 내열 온도는 그 부속이 견디는 값이지
   달면 그 온도가 나온다는 말이 아니다.
4. 관계 방향이 어느 쪽이든 같은 답이다 — 카탈로그가 `본체 -> 챔버` 와 `챔버 -> 본체` 를
   섞어 쓴다.
5. 장비 검색·카탈로그 검색이 **같은 답**을 한다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import Signed, site_id


def _category(client: TestClient, admin: Signed, code: str) -> str:
    """분류 값 하나 — **code 가 판정의 열쇠다**(항온조·노만 온도를 댄다)."""
    made = client.post(
        "/api/vocabularies/equipment_category/terms",
        json={"value": f"{code}-{uuid.uuid4().hex[:6]}", "code": code},
        headers=admin.headers,
    )
    if made.status_code == 201:
        return str(made.json()["id"])
    listed = client.get("/api/vocabularies/equipment_category/terms", headers=admin.headers)
    for row in listed.json():
        if row["code"] == code:
            return str(row["id"])
    raise AssertionError(f"분류 값을 만들 수 없습니다: {made.text}")


def _series(
    client: TestClient,
    admin: Signed,
    name: str,
    *,
    kind: str = "main",
    item: str | None = None,
    category_term_id: str | None = None,
) -> str:
    body: dict[str, Any] = {"name": name, "kind": kind}
    if category_term_id:
        body["category_term_id"] = category_term_id
    made = client.post("/api/equipment-series", json=body, headers=admin.headers)
    assert made.status_code == 201, made.text
    series_id = str(made.json()["id"])
    if item:
        added = client.post(
            f"/api/equipment-series/{series_id}/test-items",
            json={"test_item_term_id": item},
            headers=admin.headers,
        )
        assert added.status_code == 201, added.text
    return series_id


def _model(client: TestClient, admin: Signed, series_id: str, name: str, **specs: Any) -> str:
    made = client.post(
        "/api/equipment-models",
        json={"series_id": series_id, "name": name},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    definitions = {
        row["key"]: row["id"]
        for row in client.get("/api/spec-definitions", headers=admin.headers).json()
    }
    for key, body in specs.items():
        put = client.put(
            f"/api/equipment-models/{made.json()['id']}/specs",
            json={"definition_id": definitions[key], **body},
            headers=admin.headers,
        )
        assert put.status_code == 200, put.text
    return str(made.json()["id"])


def _link(client: TestClient, admin: Signed, host: str, part: str, relation: str) -> None:
    made = client.post(
        f"/api/equipment-series/{host}/relations",
        json={"part_series_id": part, "relation": relation},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text


def _own(client: TestClient, admin: Signed, model_id: str, asset_no: str) -> str:
    made = client.post(
        "/api/equipment",
        json={
            "asset_no": asset_no,
            "name": asset_no,
            "workspace_slug": admin.workspace,
            "site_term_id": site_id(client, admin),
            "location": "1동",
            "model_id": model_id,
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def _catalog(client: TestClient, admin: Signed, **body: Any) -> dict[str, Any]:
    found = client.post("/api/search/catalog", json=body, headers=admin.headers)
    assert found.status_code == 200, found.text
    return dict(found.json())


def test_본체가_모르는_온도를_붙는_챔버가_대면_그_챔버를_짚어_답한다(
    client: TestClient,
    admin: Signed,
    term_factory: Callable[[str, str], str],
    condition_ids: dict[str, str],
) -> None:
    tag = uuid.uuid4().hex[:6]
    item = term_factory("test_item", f"인장-{tag}")
    host = _series(client, admin, f"UTM-{tag}", item=item)
    # 본체는 하중만 적혀 있다 — 온도는 모른다.
    machine = _model(
        client, admin, host, f"UTM-100kN-{tag}", force_capacity={"num_value": 100}
    )
    chamber = _series(
        client,
        admin,
        f"챔버-{tag}",
        kind="accessory",
        category_term_id=_category(client, admin, "environmental_chamber"),
    )
    narrow = _model(
        client,
        admin,
        chamber,
        f"C-180-{tag}",
        test_temperature={"num_min": -50, "num_max": 180},
    )
    wide = _model(
        client,
        admin,
        chamber,
        f"C-600-{tag}",
        test_temperature={"num_min": -150, "num_max": 600},
    )
    _link(client, admin, host, chamber, "compatible_accessory")

    found = _catalog(
        client,
        admin,
        test_item_term_id=item,
        conditions=[{"condition_key_id": condition_ids["temperature"], "at": 300}],
    )
    hit = next(one for one in found["hits"] if one["series_name"] == f"UTM-{tag}")
    mine = next(m for m in hit["models"] if m["model_id"] == machine)
    assert mine["verdict"] == "accessory"
    row = mine["conditions"][0]
    assert row["verdict"] == "accessory"
    # **기종을 짚는다.** 300 °C 를 내는 것은 넓은 쪽뿐이라 좁은 쪽이 오면 안 된다.
    assert row["accessory"]["model_id"] == wide
    assert row["accessory"]["model_id"] != narrow
    assert row["accessory"]["series_name"] == f"챔버-{tag}"
    assert row["accessory"]["condition_range"] == "-150 degC ~ 600 degC"
    assert row["accessory"]["relation"] == "compatible_accessory"
    # 아직 안 샀다 — 사람은 이 숫자로 「사야 하나 빌려 오나」 를 가른다.
    assert row["accessory"]["owned_units"] == 0
    # 모르는 것이 아니라 부속으로 되는 것이다 — 채우라는 말이 남아 있으면 안 된다.
    assert row["reason"] is None


def test_본체로는_안_되는_온도도_노를_달면_살아난다(
    client: TestClient,
    admin: Signed,
    term_factory: Callable[[str, str], str],
    condition_ids: dict[str, str],
) -> None:
    tag = uuid.uuid4().hex[:6]
    item = term_factory("test_item", f"고온인장-{tag}")
    host = _series(client, admin, f"UTM2-{tag}", item=item)
    # 본체 사양은 상온까지다 — 지금까지 이 기종은 결과에서 통째로 빠졌다.
    machine = _model(
        client, admin, host, f"UTM2-{tag}", test_temperature={"num_min": 10, "num_max": 40}
    )
    furnace = _series(
        client,
        admin,
        f"노-{tag}",
        kind="accessory",
        category_term_id=_category(client, admin, "furnace"),
    )
    hot = _model(client, admin, furnace, f"F-1200-{tag}", test_temperature={"num_max": 1200})
    # 관계를 **거꾸로** 건다(노 -> 본체). 카탈로그가 두 방향을 섞어 쓴다.
    _link(client, admin, furnace, host, "fits_on")

    found = _catalog(
        client,
        admin,
        test_item_term_id=item,
        conditions=[{"condition_key_id": condition_ids["temperature"], "at_least": 900}],
    )
    hit = next(one for one in found["hits"] if one["series_name"] == f"UTM2-{tag}")
    mine = next(m for m in hit["models"] if m["model_id"] == machine)
    assert mine["verdict"] == "accessory"
    assert found["unmet_models"] == 0
    assert mine["conditions"][0]["accessory"]["model_id"] == hot
    assert mine["conditions"][0]["accessory"]["relation"] == "fits_on"


def test_그립의_내열_온도는_시험_온도를_대지_않는다(
    client: TestClient,
    admin: Signed,
    term_factory: Callable[[str, str], str],
    condition_ids: dict[str, str],
) -> None:
    tag = uuid.uuid4().hex[:6]
    item = term_factory("test_item", f"인장-{tag}")
    host = _series(client, admin, f"UTM3-{tag}", item=item)
    machine = _model(client, admin, host, f"UTM3-{tag}", force_capacity={"num_value": 50})
    grip = _series(
        client,
        admin,
        f"그립-{tag}",
        kind="accessory",
        category_term_id=_category(client, admin, "grip_fixture"),
    )
    _model(client, admin, grip, f"G-{tag}", test_temperature={"num_min": -130, "num_max": 315})
    _link(client, admin, host, grip, "compatible_accessory")

    found = _catalog(
        client,
        admin,
        test_item_term_id=item,
        conditions=[{"condition_key_id": condition_ids["temperature"], "at": 200}],
    )
    hit = next(one for one in found["hits"] if one["series_name"] == f"UTM3-{tag}")
    mine = next(m for m in hit["models"] if m["model_id"] == machine)
    # 그립이 200 °C 를 견딘다는 것과 200 °C 에서 시험이 된다는 것은 다르다.
    assert mine["verdict"] == "unknown"
    assert mine["conditions"][0]["accessory"] is None
    assert mine["conditions"][0]["reason"] == "missing"


def test_장비_검색도_같은_답을_하고_가진_챔버를_말한다(
    client: TestClient,
    admin: Signed,
    term_factory: Callable[[str, str], str],
    condition_ids: dict[str, str],
) -> None:
    tag = uuid.uuid4().hex[:6]
    item = term_factory("test_item", f"인장-{tag}")
    host = _series(client, admin, f"UTM4-{tag}", item=item)
    machine = _model(client, admin, host, f"UTM4-{tag}", force_capacity={"num_value": 100})
    chamber = _series(
        client,
        admin,
        f"챔버4-{tag}",
        kind="accessory",
        category_term_id=_category(client, admin, "environmental_chamber"),
    )
    box = _model(
        client, admin, chamber, f"C4-{tag}", test_temperature={"num_min": -70, "num_max": 300}
    )
    _link(client, admin, host, chamber, "extends_temperature")
    _own(client, admin, machine, f"EQ-{tag}")
    # **챔버도 한 대 갖고 있다.** 살 것이 아니라 옆에서 가져오면 되는 경우다.
    _own(client, admin, box, f"CH-{tag}")

    found = client.post(
        "/api/search/test-items",
        json={
            "test_item_term_id": item,
            "conditions": [{"condition_key_id": condition_ids["temperature"], "at": 200}],
        },
        headers=admin.headers,
    )
    assert found.status_code == 200, found.text
    hit = next(one for one in found.json()["hits"] if one["asset_no"] == f"EQ-{tag}")
    assert hit["verdict"] == "accessory"
    offer = hit["conditions"][0]["accessory"]
    assert offer["model_id"] == box
    assert offer["owned_units"] == 1

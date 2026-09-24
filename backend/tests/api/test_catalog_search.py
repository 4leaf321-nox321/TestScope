"""카탈로그 검색 — **「이 시험을 하려면 어떤 기종이 되나 / 사야 하나」.**

장비 검색은 우리가 가진 것을 답한다. 가진 것이 없을 때 다음 물음은 늘 「그러면 무엇을
사나」 이고, 그 답은 카탈로그에 있다 — 계열의 시험 항목 607 건과 기종 사양이 지금까지
검색에 안 걸렸다.

여기서 지키는 것:

1. 판정은 **기종 단위**고, 기종 사양이 계열 봉투를 이긴다 — 장비를 만들 때와 같은 규칙.
2. 조건에 안 맞는 기종은 빠지고 그 수를 말한다. 하나도 안 남은 계열은 안 온다.
3. 옵션 부속 기준은 「됨」 이 아니라 「부속 있으면」.
4. 기종마다 **보유 대수**가 온다 — 사기 전에 있는 것을 본다.
5. 물성으로 물으면 그것을 내는 시험 항목 전부로 펼친다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import Signed, site_id


def _series(client: TestClient, admin: Signed, name: str, item: str) -> str:
    series = client.post("/api/equipment-series", json={"name": name}, headers=admin.headers)
    assert series.status_code == 201, series.text
    added = client.post(
        f"/api/equipment-series/{series.json()['id']}/test-items",
        json={"test_item_term_id": item},
        headers=admin.headers,
    )
    assert added.status_code == 201, added.text
    return str(series.json()["id"])


def _model(client: TestClient, admin: Signed, series_id: str, name: str, **specs: Any) -> str:
    model = client.post(
        "/api/equipment-models",
        json={"series_id": series_id, "name": name},
        headers=admin.headers,
    )
    assert model.status_code == 201, model.text
    definitions = {
        row["key"]: row["id"]
        for row in client.get("/api/spec-definitions", headers=admin.headers).json()
    }
    for key, body in specs.items():
        put = client.put(
            f"/api/equipment-models/{model.json()['id']}/specs",
            json={"definition_id": definitions[key], **body},
            headers=admin.headers,
        )
        assert put.status_code == 200, put.text
    return str(model.json()["id"])


def _keys(client: TestClient, admin: Signed) -> dict[str, str]:
    return {
        row["key"]: row["id"]
        for row in client.get("/api/condition-keys", headers=admin.headers).json()
    }


def test_기종_단위로_판정하고_안_맞는_기종은_빠지며_보유_대수가_온다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    tag = uuid.uuid4().hex[:6]
    item = term_factory("test_item", f"인장-{tag}")
    series = _series(client, admin, f"UTM-{tag}", item)
    small = _model(client, admin, series, f"S-5kN-{tag}", force_capacity={"num_value": 5})
    big = _model(client, admin, series, f"S-300kN-{tag}", force_capacity={"num_value": 300})
    blank = _model(client, admin, series, f"S-?-{tag}")
    # 큰 기종으로 장비 한 대를 가지고 있다.
    owned = client.post(
        "/api/equipment",
        json={
            "asset_no": f"CAT-{tag}",
            "name": "가진 것",
            "workspace_slug": admin.workspace,
            "site_term_id": site_id(client, admin),
            "location": "1동",
            "model_id": big,
        },
        headers=admin.headers,
    )
    assert owned.status_code == 201, owned.text

    keys = _keys(client, admin)
    found = client.post(
        "/api/search/catalog",
        json={
            "test_item_term_id": item,
            "conditions": [{"condition_key_id": keys["force"], "at_least": 20}],
        },
        headers=admin.headers,
    )
    assert found.status_code == 200, found.text
    body = found.json()
    assert body["total_series"] == 1
    hit = body["hits"][0]
    assert hit["series_name"] == f"UTM-{tag}"
    assert hit["test_item"] == f"인장-{tag}"
    by_model = {m["model_id"]: m for m in hit["models"]}
    # 5 kN 은 빠졌고 그 수가 적힌다. 300 kN 은 됨, 사양 없는 기종은 모름.
    assert small not in by_model
    assert body["unmet_models"] == 1
    assert by_model[big]["verdict"] == "match"
    assert by_model[blank]["verdict"] == "unknown"
    assert by_model[big]["owned_units"] == 1
    assert by_model[blank]["owned_units"] == 0
    # 조건 줄에는 기종이 적어 둔 범위가 온다.
    assert by_model[big]["conditions"][0]["condition_range"] == "제한 없음 ~ 300 kN"


def test_옵션_부속_기준은_부속_있으면_이고_물성으로도_묻는다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    tag = uuid.uuid4().hex[:6]
    item = term_factory("test_item", f"DMA-{tag}")
    series = _series(client, admin, f"DMA-{tag}", item)
    model = _model(
        client,
        admin,
        series,
        f"D-{tag}",
        test_temperature={"num_min": -150, "num_max": 600, "requires_accessory": True},
    )
    prop = client.post(
        "/api/vocabularies/property/terms",
        json={"value": f"유리전이온도-{tag}", "code": f"thermal.glass_transition_{tag}"},
        headers=admin.headers,
    ).json()
    link = client.post(
        "/api/test-item-properties",
        json={"test_item_term_id": item, "property_term_id": prop["id"]},
        headers=admin.headers,
    )
    assert link.status_code == 201, link.text

    keys = _keys(client, admin)
    found = client.post(
        "/api/search/catalog",
        json={
            "property_term_id": prop["id"],
            "conditions": [{"condition_key_id": keys["temperature"], "at": 200}],
        },
        headers=admin.headers,
    ).json()
    assert found["expanded_test_items"] == [f"DMA-{tag}"]
    hit = next(one for one in found["hits"] if one["series_name"] == f"DMA-{tag}")
    mine = next(m for m in hit["models"] if m["model_id"] == model)
    assert mine["verdict"] == "accessory"
    assert mine["conditions"][0]["verdict"] == "accessory"


def test_규격으로_물으면_그_규격을_인용한_계열만_온다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    tag = uuid.uuid4().hex[:6]
    item = term_factory("test_item", f"굽힘-{tag}")
    method = client.post(
        "/api/methods",
        json={"code": f"ISO 178-{tag}", "title": "굽힘", "test_item_term_ids": [item]},
        headers=admin.headers,
    ).json()
    cited = client.post(
        "/api/equipment-series", json={"name": f"A-{tag}"}, headers=admin.headers
    ).json()
    client.post(
        f"/api/equipment-series/{cited['id']}/test-items",
        json={"test_item_term_id": item, "method_code": method["code"]},
        headers=admin.headers,
    )
    _model(client, admin, cited["id"], f"A1-{tag}")
    plain = _series(client, admin, f"B-{tag}", item)
    _model(client, admin, plain, f"B1-{tag}")

    found = client.post(
        "/api/search/catalog",
        json={"test_item_term_id": item, "method_id": method["id"], "conditions": []},
        headers=admin.headers,
    ).json()
    assert [one["series_name"] for one in found["hits"]] == [f"A-{tag}"]
    assert found["hits"][0]["methods"] == [f"ISO 178-{tag}"]

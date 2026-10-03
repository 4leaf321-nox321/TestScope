"""소재 — **글이 아니라 온톨로지 값이다**(2026-10-02, 「소재는 나중에 온톨로지로」).

글로 두면 SUS304 · STS304 · 스테인리스304 가 다 들어와 아무도 못 거른다. 여기서 지키는 것
— 설치가 「소재」 축과 대분류를 심는다(값 고르기는 있는 값만 보여 주므로 비어 있으면 아무도
못 쓴다) · 장비의 「소재 종류」 가 그 축의 값을 고른다 · 그 값으로 장비를 거른다 · 그래프에서
장비의 이웃으로 소재가 선다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import Signed, category_id, site_id


def test_장비의_소재_종류는_소재_축의_값을_고르고_그_값으로_거른다(
    client: TestClient, admin: Signed
) -> None:
    terms = client.get("/api/vocabularies/material/terms", headers=admin.headers)
    assert terms.status_code == 200, terms.text
    by_value = {one["value"]: one["id"] for one in terms.json()}
    # 대분류만 — 세부(SUS304)는 쓰는 사람이 더한다.
    assert {"금속", "플라스틱", "고무·엘라스토머", "복합재"} <= set(by_value)

    rows = client.get(
        "/api/attribute-definitions", params={"target": "equipment"}, headers=admin.headers
    ).json()
    material: dict[str, Any] = next(one for one in rows if one["key"] == "equipment_material")
    assert (material["kind"], material["vocabulary_slug"]) == ("term", "material")

    tag = uuid.uuid4().hex[:6]
    made = client.post(
        "/api/equipment",
        json={
            "asset_no": f"MAT-{tag}",
            "name": f"금속 인장기-{tag}",
            "workspace_slug": admin.workspace,
            "site_term_id": site_id(client, admin),
            "location": "3동 201호",
            "category_term_id": category_id(client, admin),
            "attributes": [{"definition_id": material["id"], "term_id": by_value["금속"]}],
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    shown = next(
        one for one in made.json()["attributes"] if one["definition_id"] == material["id"]
    )
    assert shown["display"] == "금속"

    # 쓰임을 센다 — 축이 쓰임 표에 없으면 그 값은 영원히 「0」 으로 보인다.
    used = client.get("/api/vocabularies/material/terms", headers=admin.headers).json()
    assert next(one for one in used if one["value"] == "금속")["usage_count"] >= 1

    # 그 값으로 거른다 — 글이었으면 「금속」 과 「메탈」 이 갈렸을 자리다.
    found = client.get(
        "/api/equipment",
        params=[("attr", "equipment_material=금속"), ("limit", "200")],
        headers=admin.headers,
    )
    assert found.status_code == 200, found.text
    assert f"MAT-{tag}" in {one["asset_no"] for one in found.json()["items"]}

    # 그래프에서 장비의 이웃으로 소재가 선다 — 종류가 없는 축의 값은 그래프가 뺀다.
    near = client.get(
        "/api/graph/neighborhood",
        params={"focus": f"equipment:{made.json()['id']}", "depth": 1},
        headers=admin.headers,
    )
    assert near.status_code == 200, near.text
    assert f"material:{by_value['금속']}" in {one["id"] for one in near.json()["nodes"]}

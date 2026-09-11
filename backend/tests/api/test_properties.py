"""물성 ↔ 시험 항목 — 검색 사슬의 **앞에 붙은 한 칸.**

    물성  ⇄  시험 항목  ->  요구 조건  ->  시험법  ->  가능한 장비  ->  보유 위치
     N:M

여기서 지키는 것:

1. 한 시험이 여러 물성을 내고, 한 물성이 여러 시험에서 나온다 — **양쪽 다 N** 이다.
2. 검색이 **물성으로** 물을 수 있고, 그것을 내는 시험 항목 전부로 펼친다.
3. 연결이 없는 물성으로 물으면 결과는 **비고**, 응답이 「펼친 항목이 없다」 고 말한다 —
   전체로 풀면 「인장강도」 를 물은 사람이 염수분무 챔버를 받는다.
4. 연결은 전사 지식이라 **시스템 관리자만** 고친다. 손으로 더한 것은 그 자체가 확인이다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.auth import security
from app.modules.workspaces.models import Workspace, WorkspaceMember
from tests.api.conftest import Signed, category_id, site_id


def _property(client: TestClient, admin: Signed, value: str, code: str) -> str:
    response = client.post(
        "/api/vocabularies/property/terms",
        json={"value": value, "code": code},
        headers=admin.headers,
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _link(
    client: TestClient, admin: Signed, item: str, prop: str, **extra: Any
) -> dict[str, Any]:
    response = client.post(
        "/api/test-item-properties",
        json={"test_item_term_id": item, "property_term_id": prop, **extra},
        headers=admin.headers,
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def _equipment_with_item(client: TestClient, admin: Signed, item: str) -> str:
    equipment = client.post(
        "/api/equipment",
        json={
            "asset_no": f"UTM-{uuid.uuid4().hex[:6]}",
            "name": "만능재료시험기",
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
    return str(equipment.json()["asset_no"])


def test_한_시험이_여러_물성을_내고_한_물성이_여러_시험에서_나온다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    tag = uuid.uuid4().hex[:6]
    tensile = term_factory("test_item", f"인장-{tag}")
    dma = term_factory("test_item", f"DMA-{tag}")
    dsc = term_factory("test_item", f"DSC-{tag}")
    uts = _property(client, admin, f"인장강도-{tag}", f"mechanical.tensile_strength_{tag}")
    modulus = _property(client, admin, f"영률-{tag}", f"mechanical.youngs_modulus_{tag}")
    tg = _property(client, admin, f"유리전이온도-{tag}", f"thermal.glass_transition_{tag}")

    _link(client, admin, tensile, uts)
    _link(client, admin, tensile, modulus, note="신율계 필요")
    _link(client, admin, dma, tg)
    _link(client, admin, dsc, tg)

    # 시험에서 보면 물성 둘
    from_item = client.get(
        "/api/test-item-properties", params={"test_item": tensile}, headers=admin.headers
    ).json()
    assert {one["property_term_id"] for one in from_item} == {uts, modulus}
    # **덧붙는 조건이 남는다** — 영률은 인장기만으로는 안 나온다.
    assert next(one for one in from_item if one["property_term_id"] == modulus)["note"] == (
        "신율계 필요"
    )

    # 물성에서 보면 시험 둘 — 목록 응답이 그것을 한 줄에 준다.
    listed = client.get("/api/properties", params={"q": tag}, headers=admin.headers).json()
    by_id = {one["id"]: one for one in listed}
    assert {one["test_item_term_id"] for one in by_id[tg]["links"]} == {dma, dsc}
    assert by_id[uts]["code"] == f"mechanical.tensile_strength_{tag}"
    assert by_id[uts]["domain"] == "mechanical"


def test_물성으로_물으면_그것을_내는_시험_항목_전부로_펼친다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    tag = uuid.uuid4().hex[:6]
    dma = term_factory("test_item", f"DMA-{tag}")
    dsc = term_factory("test_item", f"DSC-{tag}")
    tg = _property(client, admin, f"유리전이온도-{tag}", f"thermal.glass_transition_{tag}")
    _link(client, admin, dma, tg)
    _link(client, admin, dsc, tg)
    on_dma = _equipment_with_item(client, admin, dma)
    on_dsc = _equipment_with_item(client, admin, dsc)

    found = client.post(
        "/api/search/test-items",
        json={"property_term_id": tg, "conditions": []},
        headers=admin.headers,
    ).json()
    assert {hit["asset_no"] for hit in found["hits"]} == {on_dma, on_dsc}
    assert sorted(found["expanded_test_items"]) == sorted([f"DMA-{tag}", f"DSC-{tag}"])

    # 시험 항목까지 주면 그 안에서 그것만.
    narrowed = client.post(
        "/api/search/test-items",
        json={"property_term_id": tg, "test_item_term_id": dsc, "conditions": []},
        headers=admin.headers,
    ).json()
    assert {hit["asset_no"] for hit in narrowed["hits"]} == {on_dsc}


def test_연결_없는_물성은_비고_그렇다고_말한다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    """전체로 풀면 「인장강도」 를 물은 사람이 염수분무 챔버를 받는다."""
    tag = uuid.uuid4().hex[:6]
    item = term_factory("test_item", f"염수분무-{tag}")
    _equipment_with_item(client, admin, item)
    orphan = _property(client, admin, f"밴드갭-{tag}", f"electrical.band_gap_{tag}")

    found = client.post(
        "/api/search/test-items",
        json={"property_term_id": orphan, "conditions": []},
        headers=admin.headers,
    ).json()
    assert found["total"] == 0
    assert found["expanded_test_items"] == []

    # 검색 화면이 고를 것만 볼 때 — 이어진 것이 없는 물성은 빠진다.
    linked_only = client.get(
        "/api/properties",
        params={"q": tag, "include_unlinked": "false"},
        headers=admin.headers,
    ).json()
    assert linked_only == []


def test_연결은_시스템_관리자만_고치고_손으로_더한_것은_확인이다(
    client: TestClient,
    db: Session,
    admin: Signed,
    workspace: Workspace,
    term_factory: Callable[[str, str], str],
) -> None:
    tag = uuid.uuid4().hex[:6]
    item = term_factory("test_item", f"인장-{tag}")
    prop = _property(client, admin, f"항복강도-{tag}", f"mechanical.yield_strength_{tag}")

    email = f"plain-{uuid.uuid4().hex[:8]}@testscope.local"
    user = User(
        email=email,
        password_hash=security.hash_password("member-password"),
        display_name="멤버",
        status="active",
        home_workspace_id=workspace.id,
    )
    db.add(user)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="member"))
    db.commit()
    token = client.post(
        "/api/auth/login", json={"email": email, "password": "member-password"}
    ).json()["access_token"]
    plain = {"Authorization": f"Bearer {token}"}

    refused = client.post(
        "/api/test-item-properties",
        json={"test_item_term_id": item, "property_term_id": prop},
        headers=plain,
    )
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "TSC-PROPERTIES-0003"

    made = _link(client, admin, item, prop)
    assert made["status"] == "confirmed"
    assert made["source"] == "manual"
    assert made["confirmed_at"]

    # 같은 짝은 둘이 될 수 없다.
    again = client.post(
        "/api/test-item-properties",
        json={"test_item_term_id": item, "property_term_id": prop},
        headers=admin.headers,
    )
    assert again.status_code == 409

    # 다른 축의 id 를 넣으면 FK 는 통과해도 여기서 막는다.
    maker = term_factory("manufacturer", f"제조사-{tag}")
    wrong = client.post(
        "/api/test-item-properties",
        json={"test_item_term_id": maker, "property_term_id": prop},
        headers=admin.headers,
    )
    assert wrong.status_code == 404

    # 제안으로 되돌렸다가 다시 확인하면 확인 시각이 다시 찍힌다.
    back = client.patch(
        f"/api/test-item-properties/{made['id']}",
        json={"status": "suggested"},
        headers=admin.headers,
    ).json()
    assert back["status"] == "suggested" and back["confirmed_at"] is None
    confirmed = client.patch(
        f"/api/test-item-properties/{made['id']}",
        json={"status": "confirmed"},
        headers=admin.headers,
    ).json()
    assert confirmed["confirmed_at"]

    gone = client.delete(f"/api/test-item-properties/{made['id']}", headers=admin.headers)
    assert gone.status_code == 204


def test_물성_축은_닫혀_있고_쓰임_수를_센다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    axes = {
        one["slug"]: one
        for one in client.get("/api/vocabularies", headers=admin.headers).json()
    }
    assert axes["property"]["entry_policy"] == "closed"
    assert axes["property"]["domain"] == "common"

    tag = uuid.uuid4().hex[:6]
    item = term_factory("test_item", f"굽힘-{tag}")
    prop = _property(client, admin, f"굽힘강도-{tag}", f"mechanical.flexural_strength_{tag}")
    _link(client, admin, item, prop)
    terms = client.get(
        "/api/vocabularies/property/terms", params={"q": tag}, headers=admin.headers
    ).json()
    assert terms[0]["usage_count"] == 1

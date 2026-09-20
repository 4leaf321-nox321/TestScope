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


def test_제안을_묶어서_확인하고_되돌린다(
    client: TestClient,
    admin: Signed,
    term_factory: Callable[[str, str], str],
) -> None:
    """**254건을 한 줄씩 누르게 두면 아무도 끝내지 못한다** — 실제로 확인 0 인 채였다.

    사람이 보는 단위는 줄(한 시험이 내는 물성들)이라 그 단위로 받고, 잘못 눌렀을 때
    되돌아갈 길을 같이 둔다.
    """
    tag = uuid.uuid4().hex[:6]
    item = term_factory("test_item", f"인장-{tag}")
    props = [
        _property(client, admin, f"물성{index}-{tag}", f"mechanical.p{index}_{tag}")
        for index in range(3)
    ]
    links = [_link(client, admin, item, one) for one in props]
    # 손으로 더한 것은 확인이므로, 묶음 확인을 보려면 제안으로 돌려놓는다(반입이 넣는 모양).
    for one in links:
        client.patch(
            f"/api/test-item-properties/{one['id']}",
            json={"status": "suggested"},
            headers=admin.headers,
        )

    got = client.patch(
        "/api/test-item-properties/bulk",
        json={"link_ids": [one["id"] for one in links], "status": "confirmed"},
        headers=admin.headers,
    )
    assert got.status_code == 200, got.text
    assert got.json()["changed"] == 3
    assert all(one["status"] == "confirmed" for one in got.json()["links"])
    assert all(one["confirmed_at"] for one in got.json()["links"])

    # **이미 그 상태인 것은 안 센다.** 「3건 확인」 이라 말해 놓고 0건이 바뀌면 사람은
    # 자기가 무엇을 한 것인지 모른다.
    again = client.patch(
        "/api/test-item-properties/bulk",
        json={"link_ids": [one["id"] for one in links], "status": "confirmed"},
        headers=admin.headers,
    )
    assert again.json()["changed"] == 0

    back = client.patch(
        "/api/test-item-properties/bulk",
        json={"link_ids": [links[0]["id"]], "status": "suggested"},
        headers=admin.headers,
    )
    assert back.json()["changed"] == 1
    assert back.json()["links"][0]["confirmed_at"] is None

    # 없는 id 는 조용히 건너뛴다 — 남이 그 사이 지웠다고 나머지를 막으면 다시 다 눌러야 한다.
    mixed = client.patch(
        "/api/test-item-properties/bulk",
        json={"link_ids": [links[0]["id"], str(uuid.uuid4())], "status": "confirmed"},
        headers=admin.headers,
    )
    assert mixed.status_code == 200, mixed.text
    assert mixed.json()["changed"] == 1

    # 「bulk」 가 연결 id 로 읽히면 안 된다 — 라우트 순서.
    assert client.get("/api/test-item-properties", headers=admin.headers).status_code == 200


def test_AI_가_낸_연결은_제안으로_들어오고_사람이_확인한다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    """손으로 더한 것은 그 자체가 확인이지만, **기계가 낸 것은 제안**이다. 확인은 「사람이
    봤다」 는 뜻이고 카탈로그 정본에 실리므로 기계가 대신 못 한다 — MCP 도구가 이 값을 고정해
    보낸다. 출처 `agent` 는 화면이 「왜 이 연결이 있나」 에 답할 때 사람 것과 구별되게 한다."""
    tag = uuid.uuid4().hex[:6]
    item = term_factory("test_item", f"인장-{tag}")
    prop = _property(client, admin, f"항복강도-{tag}", f"mechanical.yield_strength_{tag}")

    made = _link(
        client, admin, item, prop, status="suggested", source="agent", note="ISO 6892-1"
    )
    assert made["status"] == "suggested" and made["source"] == "agent"
    assert made["confirmed_at"] is None

    # 사람이 확인하면 그때 확인자·시각이 찍힌다.
    confirmed = client.patch(
        "/api/test-item-properties/bulk",
        json={"link_ids": [made["id"]], "status": "confirmed"},
        headers=admin.headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    listed = client.get(
        "/api/test-item-properties", params={"test_item": item}, headers=admin.headers
    ).json()
    assert listed[0]["status"] == "confirmed" and listed[0]["confirmed_at"]

    # 모르는 출처·상태는 거절 — 「그냥 넣어 두자」 가 정본에 흘러들지 않게.
    bad = client.post(
        "/api/test-item-properties",
        json={"test_item_term_id": item, "property_term_id": prop, "source": "guess"},
        headers=admin.headers,
    )
    assert bad.status_code in (400, 409, 422)

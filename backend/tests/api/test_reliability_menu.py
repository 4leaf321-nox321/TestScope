"""부서 하나의 시험 항목 현황 — **그 부서 장비만 센다.**

사이드바가 부서로 서던 때에 함께 있던 시험인데, 신뢰성 시험이 사업부로 옮겨 가면서
(0037) 메뉴 쪽은 `test_reliability_tests.py` 의 「사업부 목록」 이 본다. 여기 남은 것은
장비 수 세기다 — 그것은 여전히 부서 단위다(장비는 실물이라 놓인 팀이 갖는다).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.api.conftest import Signed, category_id, site_id


def _workspace(client: TestClient, admin: Signed) -> str:
    slug = f"lab-{uuid.uuid4().hex[:8]}"
    made = client.post(
        "/api/workspaces", json={"slug": slug, "name": "신뢰성팀"}, headers=admin.headers
    )
    assert made.status_code == 201, made.text
    return slug


def test_부서_하나의_현황은_그_부서_장비만_센다(client: TestClient, admin: Signed) -> None:
    tag = uuid.uuid4().hex[:6]
    other = _workspace(client, admin)
    item = client.post(
        "/api/vocabularies/test_item/terms",
        json={"value": f"충격-{tag}"},
        headers=admin.headers,
    ).json()["id"]
    equipment = client.post(
        "/api/equipment",
        json={
            "asset_no": f"IMP-{tag}",
            "name": "충격시험기",
            "workspace_slug": admin.workspace,
            "site_term_id": site_id(client, admin),
            "location": "1동",
            "category_term_id": category_id(client, admin),
        },
        headers=admin.headers,
    ).json()
    client.post(
        "/api/equipment-test-items",
        json={"equipment_id": equipment["id"], "test_item_term_id": item},
        headers=admin.headers,
    )

    def count(workspace: str) -> int:
        rows = client.get(
            "/api/test-items", params={"workspace": workspace}, headers=admin.headers
        )
        assert rows.status_code == 200, rows.text
        return int(next(one for one in rows.json() if one["id"] == item)["equipment_count"])

    assert count(admin.workspace) == 1
    assert count(other) == 0

    missing = client.get(
        "/api/test-items", params={"workspace": "no-such-team"}, headers=admin.headers
    )
    assert missing.status_code == 404


def test_사업부는_조직도를_타고_물려받는다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """**상위 부서에 붙이면 그 아래가 모두 그 사업부다**(0037).

    사업부에 한 번 붙이면 아래 수십 개 팀에 다시 붙일 일이 없고, 팀이 다른 사업부로
    옮겨 가면 **부모만 바꿔도 따라간다.** 값을 팀마다 적어 두면 개편 때마다 전부 고쳐야
    하고, 한 줄 빠뜨리면 그 팀의 시험이 엉뚱한 사업부로 올라간다.

    화면은 「직접 붙은 것」 과 「물려받은 것」 을 갈라야 한다 — 안 그러면 「여기 안 붙었네」
    하고 또 붙이고, 그 팀만 개편에서 떨어져 나간다.
    """
    tag = uuid.uuid4().hex[:6]

    def _made(slug: str, name: str, parent: str | None = None) -> dict[str, Any]:
        response = client.post(
            "/api/workspaces",
            json={"slug": slug, "name": name, "parent_slug": parent},
            headers=admin.headers,
        )
        assert response.status_code == 201, response.text
        body: dict[str, Any] = response.json()
        return body

    def _seen(slug: str) -> dict[str, Any]:
        rows = client.get(
            "/api/workspaces", params={"all": True}, headers=admin.headers
        ).json()
        return next(one for one in rows if one["slug"] == slug)

    head = _made(f"head-{tag}", "본부")["slug"]
    team = _made(f"team-{tag}", "개발팀", head)["slug"]
    part = _made(f"part-{tag}", "파트", team)["slug"]

    # 아무 데도 안 붙었으면 비어 있다.
    assert _seen(part)["division_code"] is None

    patched = client.patch(
        f"/api/workspaces/{head}", json={"division_code": "nw"}, headers=admin.headers
    )
    assert patched.status_code == 200, patched.text

    # 붙인 곳은 **제 값**, 아래는 **물려받은 값**.
    assert (_seen(head)["division_code"], _seen(head)["division_own"]) == ("nw", True)
    assert (_seen(team)["division_code"], _seen(team)["division_own"]) == ("nw", False)
    assert (_seen(part)["division_code"], _seen(part)["division_own"]) == ("nw", False)
    assert _seen(part)["division_name"] == "NW"

    # 가운데를 다른 사업부로 덮으면 그 아래만 바뀐다 — 가까운 조상이 이긴다.
    client.patch(
        f"/api/workspaces/{team}", json={"division_code": "sr"}, headers=admin.headers
    )
    assert _seen(head)["division_code"] == "nw"
    assert _seen(part)["division_code"] == "sr"

    # **빈 문자열이면 뗀다** — 그러면 다시 위에서 물려받는다.
    client.patch(f"/api/workspaces/{team}", json={"division_code": ""}, headers=admin.headers)
    assert (_seen(team)["division_code"], _seen(team)["division_own"]) == ("nw", False)
    assert _seen(part)["division_code"] == "nw"

"""사이드바 「신뢰성 시험」 아래에 서는 부서 — 관리자가 「부서 정보」 에서 고른다.

여기서 지키는 것 — 고른 부서는 소속과 무관하게 누구나 본다 · 보관한 부서는 메뉴에서
빠진다 · 부서 하나의 신뢰성 시험 현황은 그 부서 장비만 센다.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from tests.api.conftest import Signed, category_id, site_id


def _workspace(client: TestClient, admin: Signed) -> str:
    slug = f"lab-{uuid.uuid4().hex[:8]}"
    made = client.post(
        "/api/workspaces", json={"slug": slug, "name": "신뢰성팀"}, headers=admin.headers
    )
    assert made.status_code == 201, made.text
    assert made.json()["reliability_listed"] is False
    return slug


def _listed(client: TestClient, signed: Signed) -> list[str]:
    got = client.get("/api/workspaces/reliability-listed", headers=signed.headers)
    assert got.status_code == 200, got.text
    return [one["slug"] for one in got.json()]


def test_고른_부서만_메뉴에_서고_보관하면_빠진다(client: TestClient, admin: Signed) -> None:
    slug = _workspace(client, admin)
    assert slug not in _listed(client, admin)

    patched = client.patch(
        f"/api/workspaces/{slug}", json={"reliability_listed": True}, headers=admin.headers
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["reliability_listed"] is True
    assert slug in _listed(client, admin)

    # 이름만 고쳐도 표시는 그대로 — 안 보낸 칸은 안 건드린다.
    client.patch(f"/api/workspaces/{slug}", json={"name": "신뢰성2팀"}, headers=admin.headers)
    assert slug in _listed(client, admin)

    client.patch(f"/api/workspaces/{slug}", json={"is_active": False}, headers=admin.headers)
    assert slug not in _listed(client, admin)


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

"""AI 가 「보고도 못 하던」 자리 — 규격서 개정 후 다시 볼 시험 · 변경 이력 · 저장 전 판정.

1. 개정이 올라오면 **어느 시험을** 다시 봐야 하는지 목록으로 나온다(전에는 건수뿐).
2. 일괄 「개정 확인」 은 판을 안 주면 줄마다 그 시험이 아직 안 본 최신판까지.
3. 변경 이력을 대상 하나 · 통로(화면 · AI 혼자 · 사람이 확인 창에서 수락)로 거른다.
4. 저장 전 장비 판정은 읽기 토큰으로도 된다(아무것도 안 바꾼다).
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.workspaces.models import Workspace
from tests.api.conftest import Signed, division_term_id
from tests.api.test_human_confirm import _confirmed, _machine
from tests.api.test_reliability_tests import _signed_in


def _lab(db: Session, client: TestClient, tag: str) -> tuple[Signed, str]:
    lab = Workspace(
        slug=f"unr-{tag}", name="개정확인팀", division_term_id=division_term_id(db, "vd")
    )
    db.add(lab)
    db.commit()
    return _signed_in(client, db, lab, "manager"), lab.slug


def test_개정_후_다시_볼_시험이_목록으로_나오고_한_번에_확인한다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    tag = uuid.uuid4().hex[:6]
    manager, slug = _lab(db, client, tag)
    document = client.post(
        "/api/spec-documents",
        json={"workspace_slug": slug, "code": f"VD-UNR-{tag}", "title": "환경 시험 기준"},
        headers=manager.headers,
    ).json()
    first = client.post(
        f"/api/spec-documents/{document['id']}/revisions",
        json={"label": "14"},
        headers=manager.headers,
    ).json()
    batch = client.post(
        "/api/reliability-tests/batch",
        json={
            "division_code": "vd",
            "document_id": document["id"],
            "document_revision_id": first["id"],
            "tests": [{"name": f"고온-{tag}"}, {"name": f"저온-{tag}"}],
        },
        headers=manager.headers,
    )
    assert batch.status_code == 207, batch.text
    made = [one["id"] for one in batch.json()["created"]]

    def unseen() -> dict[str, dict[str, object] | None]:
        page = client.get(
            "/api/reliability-tests",
            params={"division": "vd", "unreviewed": "true", "q": tag, "status": "all"},
            headers=manager.headers,
        ).json()
        return {one["id"]: one["unreviewed_revision"] for one in page["items"]}

    # 판이 하나뿐이면 볼 것이 없다 — 그 판을 보고 적었다.
    assert unseen() == {}

    latest = client.post(
        f"/api/spec-documents/{document['id']}/revisions",
        json={"label": "18", "summary": "시험 온도 상향"},
        headers=manager.headers,
    ).json()
    assert latest["stale_test_count"] == 2
    found = unseen()
    assert set(found) == set(made)
    assert all(one and one["label"] == "18" for one in found.values())

    # 그 최신판에서 나온 줄은 다시 볼 것이 없다.
    fresh = client.post(
        "/api/reliability-tests/batch",
        json={
            "division_code": "vd",
            "document_id": document["id"],
            "document_revision_id": latest["id"],
            "tests": [{"name": f"습도-{tag}"}],
        },
        headers=manager.headers,
    )
    assert fresh.status_code == 207, fresh.text
    assert set(unseen()) == set(made)

    # 남은 일에도 선다(확인하는 사람에게).
    pending = client.get("/api/server/maintenance", headers=manager.headers).json()
    assert any(one["key"] == "reliability_unreviewed_revisions" for one in pending)

    # 판을 안 주면 줄마다 그 시험이 아직 안 본 최신판까지.
    done = client.post(
        "/api/reliability-tests/bulk",
        json={"ids": made, "action": "reviewed"},
        headers=manager.headers,
    )
    assert done.status_code == 200, done.text
    assert len(done.json()["done"]) == 2
    assert unseen() == {}
    revisions = client.get(
        f"/api/spec-documents/{document['id']}/revisions", headers=manager.headers
    ).json()
    assert revisions[0]["stale_test_count"] == 0

    # 볼 것이 없는 줄은 이유와 함께 실패한다.
    again = client.post(
        "/api/reliability-tests/bulk",
        json={"ids": made[:1], "action": "reviewed"},
        headers=manager.headers,
    ).json()
    assert [one["code"] for one in again["failed"]] == ["TSC-RELIABILITY-0019"]


def test_변경_이력을_대상과_통로로_거른다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    tag = uuid.uuid4().hex[:6]
    _lab(db, client, tag)
    machine = _machine(client, admin, ["read", "equipment:write"])
    made = [
        client.post(
            "/api/reliability-tests",
            json={"division_code": "vd", "name": f"이력-{tag}-{index}"},
            headers=machine,
        ).json()["id"]
        for index in range(2)
    ]
    # 하나는 사람이 화면에서, 하나는 AI 화면의 확인 창에서 수락해 확정.
    client.post(f"/api/reliability-tests/{made[0]}/confirm", headers=admin.headers)
    _confirmed(client, "POST", f"/api/reliability-tests/{made[1]}/confirm", machine)

    def entries(**params: str) -> list[dict[str, object]]:
        got = client.get(
            "/api/audit/entries",
            params={"action": "reliability_test.confirmed", "limit": "200", **params},
            headers=admin.headers,
        )
        assert got.status_code == 200, got.text
        rows: list[dict[str, object]] = got.json()["items"]
        return rows

    mine = entries(target_id=made[0])
    assert [one["target_id"] for one in mine] == [made[0]]
    assert mine[0]["actor_token"] is None
    confirmed = {one["target_id"] for one in entries(channel="confirmed")}
    screen = {one["target_id"] for one in entries(channel="screen")}
    assert made[1] in confirmed and made[1] not in screen
    assert made[0] in screen and made[0] not in confirmed


def test_저장_전_장비_판정은_읽기_토큰으로도_된다(client: TestClient, admin: Signed) -> None:
    reader = _machine(client, admin, ["read"])
    got = client.post(
        "/api/reliability-tests/capability-preview",
        json={"test_item_term_ids": [], "attributes": []},
        headers=reader,
    )
    assert got.status_code == 200, got.text

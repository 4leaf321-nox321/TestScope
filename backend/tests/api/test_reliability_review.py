"""신뢰성 시험의 후보와 확정 — **AI 가 올린 것은 사람이 본 뒤에 쓴다.**

여기서 지키는 것:

1. 기계 자격(PAT)으로 들어온 시험은 **후보**로 선다. 화면에서 넣은 것은 확정이다.
2. 확정된 시험은 기계 자격으로 **못 고친다** — 칸도, 그림도, 지우는 것도.
3. 확인과 「다시 후보로」 는 **사람만** 한다. AI 가 스스로 확인할 수 있으면 후보라는
   상태에 아무 뜻이 없다.
4. 전사 목록에는 확정된 것만 나온다. 후보는 그 부서 화면에서 본다.
"""

from __future__ import annotations

import io
import uuid

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEntry
from app.modules.workspaces.models import Workspace
from tests.api.conftest import Signed

#: 1x1 투명 PNG. 첨부가 형식을 보므로 진짜 바이트라야 한다.
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _machine(client: TestClient, admin: Signed) -> dict[str, str]:
    """MCP 가 쓰는 것과 같은 자격 — PAT + X-Client: mcp."""
    made = client.post(
        "/api/auth/tokens",
        json={
            "name": f"mcp-검토-{uuid.uuid4().hex[:6]}",
            "scopes": ["read", "equipment:write"],
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    token = made.json()["token"]
    return {"Authorization": f"Bearer {token}", "X-Client": "mcp"}


def _lab(db: Session) -> Workspace:
    lab = Workspace(slug=f"rev-{uuid.uuid4().hex[:6]}", name="신뢰성검토팀")
    db.add(lab)
    db.commit()
    return lab


def _make(client: TestClient, lab: Workspace, name: str, headers: dict[str, str]) -> str:
    made = client.post(
        "/api/reliability-tests",
        json={"workspace_slug": lab.slug, "name": name},
        headers=headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def test_기계가_올린_시험은_후보로_서고_화면에서_넣은_것은_확정이다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    lab = _lab(db)
    tag = uuid.uuid4().hex[:6]

    by_ai = client.post(
        "/api/reliability-tests",
        json={"workspace_slug": lab.slug, "name": f"고온고습-{tag}", "purpose": "85/85"},
        headers=_machine(client, admin),
    )
    assert by_ai.status_code == 201, by_ai.text
    assert by_ai.json()["status"] == "candidate"
    # **누가 올렸는지가 줄에 있다** — 검토하는 사람이 감사까지 뒤지게 하면 안 묻고 누른다.
    assert by_ai.json()["submitted_via"].startswith("mcp-검토-")
    assert by_ai.json()["confirmed_by"] is None

    by_hand = client.post(
        "/api/reliability-tests",
        json={"workspace_slug": lab.slug, "name": f"열충격-{tag}", "purpose": "-40/125"},
        headers=admin.headers,
    )
    assert by_hand.status_code == 201, by_hand.text
    assert by_hand.json()["status"] == "confirmed"
    assert by_hand.json()["submitted_via"] is None


def test_확정된_시험은_기계_자격으로_못_고치고_사람은_고친다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    lab = _lab(db)
    machine = _machine(client, admin)
    test_id = _make(client, lab, f"HAST-{uuid.uuid4().hex[:6]}", machine)

    # 후보인 동안은 기계도 고친다 — 제 후보를 채우는 것이 AI 가 할 일이다.
    filling = client.patch(
        f"/api/reliability-tests/{test_id}", json={"purpose": "130 degC 96h"}, headers=machine
    )
    assert filling.status_code == 200, filling.text

    confirmed = client.post(f"/api/reliability-tests/{test_id}/confirm", headers=admin.headers)
    assert confirmed.status_code == 200, confirmed.text

    blocked = client.patch(
        f"/api/reliability-tests/{test_id}", json={"purpose": "바꿔치기"}, headers=machine
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["error"]["code"] == "TSC-RELIABILITY-0005"

    # 지우는 길도 막혀 있다 — 고치기만 막으면 그 길로 가면 결과는 더 나쁘다.
    assert (
        client.delete(f"/api/reliability-tests/{test_id}", headers=machine).status_code == 409
    )

    # 사람은 된다. 그 사람의 권한이 이미 한계다.
    assert (
        client.patch(
            f"/api/reliability-tests/{test_id}",
            json={"purpose": "사람이 고침"},
            headers=admin.headers,
        ).status_code
        == 200
    )


def test_확정된_시험에는_기계가_그림도_못_붙인다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """내용을 고치는 길이 둘(칸 · 그림)인데 한 쪽만 막으면 나머지가 그대로 열려 있다."""
    lab = _lab(db)
    machine = _machine(client, admin)
    test_id = _make(client, lab, f"낙하-{uuid.uuid4().hex[:6]}", machine)

    def _upload(headers: dict[str, str]) -> httpx.Response:
        made: httpx.Response = client.post(
            "/api/attachments",
            data={"target": "reliability_test", "object_id": test_id, "caption": "치구"},
            files={"file": ("치구.png", io.BytesIO(PNG), "image/png")},
            headers=headers,
        )
        return made

    assert _upload(machine).status_code == 201, "후보에는 붙어야 한다"

    client.post(f"/api/reliability-tests/{test_id}/confirm", headers=admin.headers)

    blocked = _upload(machine)
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["error"]["code"] == "TSC-RELIABILITY-0005"
    assert _upload(admin.headers).status_code == 201, "사람은 붙인다"


def test_확인과_다시_열기는_사람만_한다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    lab = _lab(db)
    machine = _machine(client, admin)
    test_id = _make(client, lab, f"진동-{uuid.uuid4().hex[:6]}", machine)

    # **AI 가 스스로 확인하면 후보라는 상태에 아무 뜻이 없다.** MCP 에 도구를 안 만드는
    # 것만으로는 부족하다 — PAT 는 이 경로를 직접 부를 수 있다.
    refused = client.post(f"/api/reliability-tests/{test_id}/confirm", headers=machine)
    assert refused.status_code == 403, refused.text
    assert refused.json()["error"]["code"] == "TSC-RELIABILITY-0006"

    done = client.post(f"/api/reliability-tests/{test_id}/confirm", headers=admin.headers)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "confirmed"
    assert done.json()["confirmed_by"]
    assert done.json()["confirmed_at"]

    assert (
        client.post(f"/api/reliability-tests/{test_id}/reopen", headers=machine).status_code
        == 403
    )
    opened = client.post(f"/api/reliability-tests/{test_id}/reopen", headers=admin.headers)
    assert opened.status_code == 200, opened.text
    assert opened.json()["status"] == "candidate"
    # 확인한 사람은 안 지운다 — 「전에 누가 봤었나」 는 다시 볼 때 도움이 된다.
    assert opened.json()["confirmed_by"]

    # 문이 열렸으니 AI 가 다시 채운다.
    assert (
        client.patch(
            f"/api/reliability-tests/{test_id}", json={"purpose": "다시 채움"}, headers=machine
        ).status_code
        == 200
    )


def test_확인과_다시_열기는_감사에_남는다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """줄에는 **지금 상태**만 남는다. 「이 값 누가 언제 보증했어」 는 이력이라야 답한다."""
    lab = _lab(db)
    test_id = uuid.UUID(
        _make(client, lab, f"염수-{uuid.uuid4().hex[:6]}", _machine(client, admin))
    )

    client.post(f"/api/reliability-tests/{test_id}/confirm", headers=admin.headers)
    client.post(f"/api/reliability-tests/{test_id}/reopen", headers=admin.headers)

    actions = [
        one.action
        for one in db.scalars(
            select(AuditEntry)
            .where(AuditEntry.target_id == test_id)
            .order_by(AuditEntry.created_at)
        )
    ]
    assert "reliability_test.confirmed" in actions
    assert "reliability_test.reopened" in actions


def test_전사_목록은_후보를_안_내고_부서_화면은_낸다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """전사 표는 「저 부서가 무슨 시험을 하나」 에 답한다 — 확인 안 된 후보는 아직 그
    답이 아니다."""
    lab = _lab(db)
    tag = uuid.uuid4().hex[:6]
    hidden = _make(client, lab, f"후보-{tag}", _machine(client, admin))
    shown = _make(client, lab, f"확정-{tag}", admin.headers)

    def _ids(query: str) -> set[str]:
        rows = client.get(f"/api/reliability-tests{query}", headers=admin.headers)
        assert rows.status_code == 200, rows.text
        return {one["id"] for one in rows.json()}

    everyone = _ids("")
    assert shown in everyone
    assert hidden not in everyone

    # 부서 화면은 검토하는 자리다 — 후보가 보여야 하고, 먼저 와야 한다.
    theirs = client.get(
        f"/api/reliability-tests?workspace={lab.slug}", headers=admin.headers
    ).json()
    assert next(one["id"] for one in theirs) == hidden
    assert {one["id"] for one in theirs} == {hidden, shown}

    # 일부러 열면 전사에서도 보인다.
    assert hidden in _ids("?status=all")
    assert _ids(f"?workspace={lab.slug}&status=candidate") == {hidden}

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
from tests.api.conftest import Signed, division_term_id

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
    lab = Workspace(
        slug=f"rev-{uuid.uuid4().hex[:6]}",
        name="신뢰성검토팀",
        division_term_id=division_term_id(db, "vd"),
    )
    db.add(lab)
    db.commit()
    return lab


def _make(client: TestClient, lab: Workspace, name: str, headers: dict[str, str]) -> str:
    made = client.post(
        "/api/reliability-tests",
        json={"division_code": "vd", "name": name},
        headers=headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def test_기계가_올린_시험은_후보로_서고_화면에서_넣은_것은_확정이다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    # 사업부(VD)에 속한 부서를 하나 둔다 — 시험이 사업부에 살고, 올릴 자격은 그 사업부에
    # 속한 부서의 관리자다.
    _lab(db)
    tag = uuid.uuid4().hex[:6]

    by_ai = client.post(
        "/api/reliability-tests",
        json={"division_code": "vd", "name": f"고온고습-{tag}", "purpose": "85/85"},
        headers=_machine(client, admin),
    )
    assert by_ai.status_code == 201, by_ai.text
    assert by_ai.json()["status"] == "candidate"
    # **누가 올렸는지가 줄에 있다** — 검토하는 사람이 감사까지 뒤지게 하면 안 묻고 누른다.
    assert by_ai.json()["submitted_via"].startswith("mcp-검토-")
    assert by_ai.json()["confirmed_by"] is None

    by_hand = client.post(
        "/api/reliability-tests",
        json={"division_code": "vd", "name": f"열충격-{tag}", "purpose": "-40/125"},
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
        return {one["id"] for one in rows.json()["items"]}

    # **태그로 좁힌다** — 쪽이 생긴 뒤로는 전사 목록의 첫 쉰 줄에 내 줄이 없을 수 있다.
    everyone = _ids(f"?q={tag}")
    assert shown in everyone
    assert hidden not in everyone

    # 사업부 화면은 검토하는 자리다 — 후보가 보여야 하고, 먼저 와야 한다.
    # **이 시험이 만든 것만 본다** — 사업부는 시험끼리 나눠 쓰므로 옆 시험의 줄이 섞인다.
    theirs = [
        one
        for one in client.get(
            f"/api/reliability-tests?division=vd&q={tag}", headers=admin.headers
        ).json()["items"]
        if one["name"].endswith(tag)
    ]
    assert theirs[0]["id"] == hidden
    assert {one["id"] for one in theirs} == {hidden, shown}

    # 일부러 열면 전사에서도 보인다.
    assert hidden in _ids(f"?status=all&q={tag}")
    assert hidden in _ids("?division=vd&status=candidate")


def test_후보를_반려하면_사유와_함께_감사에_남는다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """**지우기와 반려는 가는 자리가 같고 뜻이 다르다.**

    지우기는 「이제 안 하는 시험」 이고 반려는 「애초에 틀린 줄」 이다. 그 차이는 감사의
    action 과 사유에만 남으므로, 거기 안 적으면 AI 가 무엇을 자주 틀리는지 영영 못 센다.
    """
    _lab(db)
    tag = uuid.uuid4().hex[:6]
    made = client.post(
        "/api/reliability-tests",
        json={"division_code": "vd", "name": f"엉뚱한 시험-{tag}"},
        headers=_machine(client, admin),
    ).json()
    assert made["status"] == "candidate"

    # 사유 없이는 안 된다.
    assert (
        client.post(
            f"/api/reliability-tests/{made['id']}/reject",
            json={"reason": ""},
            headers=admin.headers,
        ).status_code
        == 422
    )

    gone = client.post(
        f"/api/reliability-tests/{made['id']}/reject",
        json={"reason": "규격서에 없는 시험입니다"},
        headers=admin.headers,
    )
    assert gone.status_code == 204, gone.text
    assert (
        client.get(f"/api/reliability-tests/{made['id']}", headers=admin.headers).status_code
        == 404
    )

    entry = db.scalars(
        select(AuditEntry)
        .where(AuditEntry.action == "reliability_test.rejected")
        .order_by(AuditEntry.created_at.desc())
    ).first()
    assert entry is not None
    assert entry.reason == "규격서에 없는 시험입니다"


def test_확정된_것은_반려가_아니라_다시_후보로가_먼저다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """이미 사람이 보증한 줄이다. 되돌리려면 그 과정이 감사에 남아야 한다."""
    _lab(db)
    tag = uuid.uuid4().hex[:6]
    made = client.post(
        "/api/reliability-tests",
        json={"division_code": "vd", "name": f"확정된 것-{tag}"},
        headers=admin.headers,
    ).json()
    assert made["status"] == "confirmed"

    refused = client.post(
        f"/api/reliability-tests/{made['id']}/reject",
        json={"reason": "아니다"},
        headers=admin.headers,
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "TSC-RELIABILITY-0009"


def test_한_번에_확인하고_한_번에_반려한다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """**AI 가 몇천 건을 올린다.** 줄마다 창을 열어 누르는 것은 사람이 할 수 있는 일이
    아니고, 못 하면 후보가 쌓인 채로 아무도 안 본다 — 그러면 확인이라는 단계가 이름만
    남는다.

    **줄마다 결과가 온다.** 전부 되거나 전부 안 되거나로 두면 한 줄 때문에 나머지가 함께
    막힌다.
    """
    _lab(db)
    tag = uuid.uuid4().hex[:6]
    machine = _machine(client, admin)
    ids = [
        client.post(
            "/api/reliability-tests",
            json={"division_code": "vd", "name": f"무더기-{tag}-{index}"},
            headers=machine,
        ).json()["id"]
        for index in range(4)
    ]

    ok = client.post(
        "/api/reliability-tests/bulk",
        json={"ids": ids[:2], "action": "confirm"},
        headers=admin.headers,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["requested"] == 2
    assert len(ok.json()["done"]) == 2 and ok.json()["failed"] == []

    rejected = client.post(
        "/api/reliability-tests/bulk",
        json={"ids": ids[2:], "action": "reject", "reason": "중복입니다"},
        headers=admin.headers,
    )
    assert rejected.status_code == 200, rejected.text
    assert len(rejected.json()["done"]) == 2

    # 확정된 것을 또 반려하면 **그 줄만** 실패하고 왜인지 온다.
    mixed = client.post(
        "/api/reliability-tests/bulk",
        json={"ids": ids[:2], "action": "reject", "reason": "다시"},
        headers=admin.headers,
    )
    assert mixed.status_code == 200, mixed.text
    assert mixed.json()["done"] == []
    assert {one["code"] for one in mixed.json()["failed"]} == {"TSC-RELIABILITY-0009"}
    assert all(one["message"] for one in mixed.json()["failed"]), "왜인지 적혀 있어야 한다"


def test_여럿을_한_번에_다시_후보로_열고_사유를_남긴다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """**한 건씩 누르게 두면 서른 건은 아무도 안 한다.**

    기타 조건에 원문이 남은 확정본을 AI 가 다시 파싱하게 하려면 먼저 풀어야 하는데, 그것은
    줄마다 내용을 판단하는 일이 아니라 **한 가지 이유로 묶어 푸는 일**이다.

    대신 **사유를 받는다** — 서른 건이 한꺼번에 풀리면 반년 뒤에 「왜 풀렸나」 를 묻는
    사람이 반드시 있고, 감사에 「누가 열었나」 만 있으면 답할 수 없다.
    """
    tag = "a" + uuid.uuid4().hex[:5]
    lab = _lab(db)
    # 실제 경로 그대로 — **기계가 올리고 사람이 확인한** 줄을 다시 푼다.
    machine = _machine(client, admin)
    ids = [_make(client, lab, f"확정본 {at}-{tag}", machine) for at in range(3)]
    for one in ids:
        got = client.post(f"/api/reliability-tests/{one}/confirm", headers=admin.headers)
        assert got.status_code == 200, got.text
        assert got.json()["status"] == "confirmed"

    # **사유 없이는 한 줄도 안 풀린다** — 줄마다 거절하면 오백 줄이 같은 이유로 실패한다.
    bare = client.post(
        "/api/reliability-tests/bulk",
        json={"ids": ids, "action": "reopen"},
        headers=admin.headers,
    )
    assert bare.status_code == 400, bare.text
    assert "사유" in bare.json()["error"]["message"]
    still = client.get(f"/api/reliability-tests/{ids[0]}", headers=admin.headers)
    assert still.json()["status"] == "confirmed", "거절됐는데 한 줄이 풀렸습니다"

    got = client.post(
        "/api/reliability-tests/bulk",
        json={
            "ids": ids,
            "action": "reopen",
            "reason": "기타 조건의 원문을 조건 칸으로 다시 옮기려고",
        },
        headers=admin.headers,
    )
    assert got.status_code == 200, got.text
    assert len(got.json()["done"]) == 3 and got.json()["failed"] == []
    for one in ids:
        row = client.get(f"/api/reliability-tests/{one}", headers=admin.headers)
        assert row.json()["status"] == "candidate"
        # **확인을 지우지 않는다** — 「전에 누가 봤었나」 는 다시 확인할 때 도움이 된다.
        assert row.json()["confirmed_by"] is not None

    # **사유가 감사에 남는다** — 이것이 없으면 반년 뒤 「왜 풀렸나」 에 답할 수 없다.
    logs = list(
        db.scalars(
            select(AuditEntry).where(
                AuditEntry.action == "reliability_test.reopened",
                AuditEntry.target_id.in_([uuid.UUID(one) for one in ids]),
            )
        )
    )
    assert len(logs) == 3, logs
    assert all("기타 조건의 원문" in (one.reason or "") for one in logs)

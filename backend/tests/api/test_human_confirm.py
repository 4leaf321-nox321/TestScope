"""사람 확인 증표 — **AI 화면의 확인 창에서 사람이 수락한 요청만** 사람 몫의 결정을 지난다.

ADR 0013(2026-10-22 사용자 결정). 여기서 지키는 것:

1. 증표 없이 온 기계 요청은 사람 몫의 결정에서 막히고, 확인 창에 실을 내용을 받는다.
2. 증표는 **그 요청 하나**에만 맞는다 — 다른 본문 · 다른 토큰 · 지난 시각 · 두 번째
   사용은 거절.
3. 증표로 지난 것은 감사에 통로 `mcp:confirmed` 로 남는다(AI 혼자 한 것과 갈린다).
4. 관리 경로는 `admin:write` 를 고른 토큰이어야 하고, **비밀값 경로는 무엇으로도 안 열린다.**

증표는 MCP 서버의 것(`mcp_server/confirm.py`)으로 만든다 — 두 벌의 서명이 실제로 맞는지가
여기서도 드러난다.
"""

from __future__ import annotations

import importlib.util
import json
import time
import uuid
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modules.audit.models import AuditEntry
from app.modules.workspaces.models import Workspace
from app.shared import audit
from app.shared.request_context import CONFIRMED_CLIENT
from tests.api.conftest import Signed, division_term_id

_MCP_CONFIRM = Path(__file__).resolve().parents[3] / "mcp_server" / "confirm.py"


def _mcp_confirm() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mcp_confirm", _MCP_CONFIRM)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MCP = _mcp_confirm()


def _machine(client: TestClient, admin: Signed, scopes: list[str]) -> dict[str, str]:
    made = client.post(
        "/api/auth/tokens",
        json={"name": f"mcp-확인-{uuid.uuid4().hex[:6]}", "scopes": scopes},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return {"Authorization": f"Bearer {made.json()['token']}", "X-Client": "mcp"}


def _confirmed(
    client: TestClient,
    method: str,
    path: str,
    headers: dict[str, str],
    body: dict[str, Any] | None = None,
    *,
    params: dict[str, str] | None = None,
    signed_body: bytes | None = None,
    signed_token: str | None = None,
    now: float | None = None,
    proof: str | None = None,
) -> httpx.Response:
    """MCP 서버가 하는 대로 — 본문을 바이트로 만들고, 그 바이트에 서명해 함께 보낸다.

    `signed_*` 는 **서명한 것과 보낸 것을 일부러 어긋나게** 할 때 쓴다.
    """
    raw = json.dumps(body or {}, ensure_ascii=False).encode()
    url = httpx.URL("http://testserver" + path, params=params)
    token = headers["Authorization"][7:]
    key = MCP.derive_key(get_settings().jwt_secret)
    sent = {**headers, "Content-Type": "application/json"}
    sent[MCP.HEADER] = proof or MCP.proof(
        key,
        method=method,
        path=url.path,
        query=url.query.decode(),
        token=signed_token or token,
        body=signed_body if signed_body is not None else raw,
        now=now,
    )
    response: httpx.Response = client.request(method, str(url), content=raw, headers=sent)
    return response


def _lab(db: Session) -> Workspace:
    lab = Workspace(
        slug=f"cfm-{uuid.uuid4().hex[:6]}",
        name="확인시험팀",
        division_term_id=division_term_id(db, "vd"),
    )
    db.add(lab)
    db.commit()
    return lab


def _make(client: TestClient, name: str, headers: dict[str, str]) -> str:
    made = client.post(
        "/api/reliability-tests",
        json={"division_code": "vd", "name": name, "purpose": "확인 창에 실릴 목적"},
        headers=headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def test_증표_없는_기계는_확정_못하고_사람이_수락하면_확정한다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    _lab(db)
    machine = _machine(client, admin, ["read", "equipment:write"])
    name = f"고온-{uuid.uuid4().hex[:6]}"
    test_id = _make(client, name, machine)

    refused = client.post(f"/api/reliability-tests/{test_id}/confirm", headers=machine)
    assert refused.status_code == 403, refused.text
    error = refused.json()["error"]
    assert error["code"] == "TSC-RELIABILITY-0006"
    # **확인 창에 실을 내용이 온다** — 이름만이 아니라 시험 내용까지.
    assert error["details"]["needs_confirmation"] is True
    assert name in error["details"]["confirm"]
    assert "확인 창에 실릴 목적" in error["details"]["confirm"]

    done = _confirmed(client, "POST", f"/api/reliability-tests/{test_id}/confirm", machine)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "confirmed"

    entry = db.scalar(
        select(AuditEntry).where(
            AuditEntry.action == audit.RELIABILITY_TEST_CONFIRMED,
            AuditEntry.target_id == uuid.UUID(test_id),
        )
    )
    assert entry is not None
    # AI 혼자 한 것(`mcp`)과 사람이 확인 창에서 수락한 것이 갈린다.
    assert entry.actor_client == CONFIRMED_CLIENT
    assert entry.actor_token


def test_증표는_그_요청_하나에만_맞는다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    _lab(db)
    machine = _machine(client, admin, ["read", "equipment:write"])
    other = _machine(client, admin, ["read", "equipment:write"])
    path = f"/api/reliability-tests/{_make(client, f'진동-{uuid.uuid4().hex[:6]}', machine)}"

    def refused(response: httpx.Response) -> None:
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "TSC-AUTH-0108"

    # 다른 본문에 서명한 증표
    refused(_confirmed(client, "POST", path + "/confirm", machine, signed_body=b'{"x":1}'))
    # 다른 토큰에 서명한 증표 — 남의 증표를 주워 쓰지 못한다.
    refused(
        _confirmed(
            client, "POST", path + "/confirm", machine, signed_token=other["Authorization"][7:]
        )
    )
    # 지난 증표
    refused(_confirmed(client, "POST", path + "/confirm", machine, now=time.time() - 600))
    # 모양이 틀린 증표
    refused(_confirmed(client, "POST", path + "/confirm", machine, proof="v1.0.x.y"))

    # 같은 증표는 한 번만 — 두 번째는 거절(첫 번째는 지난다).
    raw = b"{}"
    url = httpx.URL("http://testserver" + path + "/confirm")
    one = MCP.proof(
        MCP.derive_key(get_settings().jwt_secret),
        method="POST",
        path=url.path,
        query="",
        token=machine["Authorization"][7:],
        body=raw,
    )
    first = _confirmed(client, "POST", path + "/confirm", machine, proof=one)
    assert first.status_code == 200, first.text
    refused(_confirmed(client, "POST", path + "/confirm", machine, proof=one))


def test_확정된_시험도_사람이_수락하면_확정을_유지한_채_고친다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    _lab(db)
    machine = _machine(client, admin, ["read", "equipment:write"])
    test_id = _make(client, f"습도-{uuid.uuid4().hex[:6]}", machine)
    assert (
        client.post(
            f"/api/reliability-tests/{test_id}/confirm", headers=admin.headers
        ).status_code
        == 200
    )

    blocked = client.patch(
        f"/api/reliability-tests/{test_id}", json={"purpose": "고친 목적"}, headers=machine
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["error"]["code"] == "TSC-RELIABILITY-0005"
    assert blocked.json()["error"]["details"]["needs_confirmation"] is True

    done = _confirmed(
        client, "PATCH", f"/api/reliability-tests/{test_id}", machine, {"purpose": "고친 목적"}
    )
    assert done.status_code == 200, done.text
    assert done.json()["purpose"] == "고친 목적"
    assert done.json()["status"] == "confirmed"


def test_묶음은_한_번_묻고_후보를_거두는_것은_안_묻는다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    _lab(db)
    machine = _machine(client, admin, ["read", "equipment:write"])
    tag = uuid.uuid4().hex[:6]
    ids = [_make(client, f"묶음-{tag}-{index}", machine) for index in range(3)]

    refused = client.post(
        "/api/reliability-tests/bulk", json={"ids": ids, "action": "confirm"}, headers=machine
    )
    assert refused.status_code == 403, refused.text
    summary = refused.json()["error"]["details"]["confirm"]
    assert "3건" in summary and f"묶음-{tag}-0" in summary

    done = _confirmed(
        client,
        "POST",
        "/api/reliability-tests/bulk",
        machine,
        {"ids": ids, "action": "confirm"},
    )
    assert done.status_code == 200, done.text
    assert len(done.json()["done"]) == 3 and done.json()["failed"] == []

    # 제가 올린 후보를 거두는 것은 AI 혼자 한다 — 묻지 않는다.
    spare = [_make(client, f"거둠-{tag}-{index}", machine) for index in range(2)]
    gone = client.post(
        "/api/reliability-tests/bulk", json={"ids": spare, "action": "delete"}, headers=machine
    )
    assert gone.status_code == 200, gone.text
    assert len(gone.json()["done"]) == 2


def test_관리_작업은_admin_write_와_사람_확인이_있어야_한다(
    client: TestClient, admin: Signed
) -> None:
    manager = _machine(client, admin, ["read", "admin:write"])
    body = {"title": f"확인공지-{uuid.uuid4().hex[:6]}", "body": "본문"}

    asked = client.post("/api/notices", json=body, headers=manager)
    assert asked.status_code == 403, asked.text
    assert asked.json()["error"]["code"] == "TSC-AUTH-0107"
    assert asked.json()["error"]["details"]["needs_confirmation"] is True

    made = _confirmed(client, "POST", "/api/notices", manager, body)
    assert made.status_code == 201, made.text
    gone = _confirmed(client, "DELETE", f"/api/notices/{made.json()['id']}", manager)
    assert gone.status_code == 204, gone.text

    # **비밀값 경로는 사람이 수락해도 안 열린다** — 토큰 발급 · 임시 비밀번호.
    for path, payload in (
        ("/api/auth/tokens", {"name": "기계가 만든 토큰"}),
        (
            "/api/accounts",
            {"email": "x@testscope.local", "display_name": "x", "workspace_slug": "x"},
        ),
    ):
        closed = _confirmed(client, "POST", path, manager, payload)
        assert closed.status_code == 403, closed.text
        assert closed.json()["error"]["code"] == "TSC-AUTH-0105"


def test_허브_토큰은_사람이_수락해도_기계로는_못_넣는다(
    client: TestClient, admin: Signed
) -> None:
    manager = _machine(client, admin, ["read", "admin:write"])
    refused = _confirmed(
        client,
        "PUT",
        "/api/hub/connection",
        manager,
        {"base_url": "https://hub.example/api", "token": "평문-비밀"},
    )
    assert refused.status_code == 403, refused.text
    assert refused.json()["error"]["code"] == "TSC-HUB-0007"


def test_MCP_의견대로_일괄_확정은_사람_확인을_받는다(
    client: TestClient, admin: Signed
) -> None:
    catalog = _machine(client, admin, ["read", "catalog:write"])
    nowhere = {"ids": [str(uuid.uuid4())]}
    asked = client.post(
        "/api/review/attribute_drafts/decide-mcp-votes", json=nowhere, headers=catalog
    )
    assert asked.status_code == 403, asked.text
    assert asked.json()["error"]["code"] == "TSC-REVIEW-0022"

    ran = _confirmed(
        client, "POST", "/api/review/attribute_drafts/decide-mcp-votes", catalog, nowhere
    )
    assert ran.status_code == 200, ran.text
    assert len(ran.json()["failed"]) == 1


def test_규격_병합과_장비_일괄_삭제도_사람_확인을_받는다(
    client: TestClient, admin: Signed
) -> None:
    """화면 전용이던 셋(규격 병합 · 시험 항목 해제 · 장비 일괄 삭제)도 같은 규칙이다."""
    catalog = _machine(client, admin, ["read", "catalog:write"])
    number = uuid.uuid4().int % 100000
    made = [
        client.post(
            "/api/methods", json={"code": code, "title": code}, headers=admin.headers
        ).json()
        for code in (f"ASTM Z{number}", f"ASTM Z{number}-20")
    ]
    body = {"target_id": made[0]["id"], "reason": "판 표시만 다름"}
    path = f"/api/methods/{made[1]['id']}/merge"

    asked = client.post(path, json=body, headers=catalog)
    assert asked.status_code == 403, asked.text
    assert asked.json()["error"]["code"] == "TSC-METHODS-0021"
    assert made[1]["code"] in asked.json()["error"]["details"]["confirm"]
    merged = _confirmed(client, "POST", path, catalog, body)
    assert merged.status_code == 200, merged.text

    equipment = _machine(client, admin, ["read", "equipment:write"])
    nowhere = {"ids": [str(uuid.uuid4())]}
    refused = client.post("/api/equipment/bulk-delete", json=nowhere, headers=equipment)
    assert refused.status_code == 403, refused.text
    assert refused.json()["error"]["code"] == "TSC-EQUIPMENT-0048"
    ran = _confirmed(client, "POST", "/api/equipment/bulk-delete", equipment, nowhere)
    assert ran.status_code == 200, ran.text
    assert len(ran.json()["failed"]) == 1

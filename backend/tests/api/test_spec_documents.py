"""사내 규격서 — **부서가 만든 시험 문서의 원본.**

## 왜 `test_methods` 가 아닌가

`test_methods` 는 공개 규격이 사는 표다(ASTM·ISO·KS 601건). 출처가 장비 카탈로그이고,
전사 공용이며, 시스템 관리자가 통제한다. 사내 규격서는 **부서가 만들고 부서가 고치고**
밖에서는 존재조차 모른다 — 섞으면 「우리가 인용하는 공개 규격」 을 세는 숫자가 틀어진다.

## 여기서 지키는 것

1. 부서가 만들고 **그 부서 관리자**가 고친다. 보는 것은 누구나.
2. 파일이 붙는다 — 원본과 개정본이 함께.
3. **판은 줄을 나누지 않는다.** 개정하면 `revision` 을 고치고 파일을 더한다 — 걸어 둔
   신뢰성 시험의 링크가 안 끊긴다.
4. 신뢰성 시험이 **드롭다운으로 가리킨다**(`kind="document"`).
5. 거는 시험이 있으면 **못 지운다.** 지우고 나면 그 시험이 무엇을 따랐는지 알 수 없다.
"""

from __future__ import annotations

import io
import uuid
from typing import Any

from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.auth import security
from app.modules.workspaces.models import Workspace, WorkspaceMember
from tests.api.conftest import Signed

PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


def _document(client: TestClient, who: Signed, **over: Any) -> Response:
    body: dict[str, Any] = {
        "workspace_slug": who.workspace,
        "code": f"MX-REL-{uuid.uuid4().hex[:6]}",
        "title": "신뢰성 시험 표준 — 환경 시험",
        "revision": "Rev.1",
        **over,
    }
    made: Response = client.post("/api/spec-documents", json=body, headers=who.headers)
    return made


def _attach(
    client: TestClient, headers: dict[str, str], document_id: str, name: str
) -> Response:
    made: Response = client.post(
        "/api/attachments",
        data={"target": "spec_document", "object_id": document_id, "caption": "원본"},
        files={"file": (name, io.BytesIO(PDF + name.encode()), "application/pdf")},
        headers=headers,
    )
    return made


def _signed(client: TestClient, db: Session, workspace: Workspace, role: str) -> Signed:
    email = f"{role}-{uuid.uuid4().hex[:8]}@testscope.local"
    user = User(
        email=email,
        password_hash=security.hash_password("pw-" + role),
        display_name=role,
        status="active",
        home_workspace_id=workspace.id,
    )
    db.add(user)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=role))
    db.commit()
    token = client.post("/api/auth/login", json={"email": email, "password": "pw-" + role})
    return Signed(email=email, token=token.json()["access_token"], workspace=workspace.slug)


def test_부서_관리자가_만들고_파일을_올린다(client: TestClient, admin: Signed) -> None:
    made = _document(client, admin)
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["file_count"] == 0, "만들자마자는 번호뿐이다"
    assert body["linked_test_count"] == 0

    first = _attach(client, admin.headers, body["id"], "MX-REL_Rev1.pdf")
    assert first.status_code == 201, first.text
    # **개정본은 파일을 더해서 쌓는다** — 줄을 새로 만들지 않는다.
    second = _attach(client, admin.headers, body["id"], "MX-REL_Rev2.pdf")
    assert second.status_code == 201, second.text

    again = client.get(f"/api/spec-documents/{body['id']}", headers=admin.headers).json()
    assert again["file_count"] == 2


def test_보는_것은_누구나_고치는_것은_그_부서(
    client: TestClient, admin: Signed, db: Session
) -> None:
    made = _document(client, admin).json()
    _attach(client, admin.headers, made["id"], "원본.pdf")

    other = Workspace(slug=f"other-{uuid.uuid4().hex[:6]}", name="남의팀")
    db.add(other)
    db.commit()
    outsider = _signed(client, db, other, "manager")

    # 보는 것은 된다 — 옆 부서가 무슨 기준으로 시험하는지가 이 플랫폼의 물음이다.
    listed = client.get("/api/spec-documents", headers=outsider.headers)
    assert listed.status_code == 200
    mine = next(one for one in listed.json() if one["id"] == made["id"])
    assert mine["can_edit"] is False

    # 고치는 것은 안 된다.
    blocked = client.patch(
        f"/api/spec-documents/{made['id']}",
        json={"title": "남이 고침"},
        headers=outsider.headers,
    )
    assert blocked.status_code == 403, blocked.text
    # 파일도 못 붙인다 — 판정이 두 벌이면 「문서는 못 고치는데 파일은 붙는」 사람이 생긴다.
    assert _attach(client, outsider.headers, made["id"], "남.pdf").status_code == 403


def test_개정해도_걸어_둔_시험의_링크가_안_끊긴다(client: TestClient, admin: Signed) -> None:
    """**판은 줄을 나누지 않는다.** 나누면 개정마다 시험 수십 건을 사람이 옮겨야 한다."""
    document = _document(client, admin).json()
    definitions = {
        one["label"]: one
        for one in client.get(
            "/api/attribute-definitions",
            params={"target": "reliability_test"},
            headers=admin.headers,
        ).json()
    }
    assert definitions["규격서"]["kind"] == "document", "드롭다운이 규격서 표를 가리킨다"

    test = client.post(
        "/api/reliability-tests",
        json={
            "workspace_slug": admin.workspace,
            "name": f"환경 시험-{uuid.uuid4().hex[:6]}",
            "attributes": [
                {"definition_id": definitions["규격서"]["id"], "document_id": document["id"]}
            ],
        },
        headers=admin.headers,
    )
    assert test.status_code == 201, test.text
    shown = next(one for one in test.json()["attributes"] if one["label"] == "규격서")
    assert shown["document_id"] == document["id"]
    assert shown["display"] == document["code"], "사람이 읽는 글자는 문서 번호다"

    # 개정 — 판을 고친다.
    bumped = client.patch(
        f"/api/spec-documents/{document['id']}",
        json={"revision": "Rev.2"},
        headers=admin.headers,
    )
    assert bumped.status_code == 200, bumped.text

    # **링크가 그대로다.**
    after = client.get(f"/api/reliability-tests/{test.json()['id']}", headers=admin.headers)
    still = next(one for one in after.json()["attributes"] if one["label"] == "규격서")
    assert still["document_id"] == document["id"]

    counted = client.get(f"/api/spec-documents/{document['id']}", headers=admin.headers)
    assert counted.json()["linked_test_count"] == 1


def test_거는_시험이_있으면_못_지운다(client: TestClient, admin: Signed) -> None:
    document = _document(client, admin).json()
    definitions = {
        one["label"]: one["id"]
        for one in client.get(
            "/api/attribute-definitions",
            params={"target": "reliability_test"},
            headers=admin.headers,
        ).json()
    }
    client.post(
        "/api/reliability-tests",
        json={
            "workspace_slug": admin.workspace,
            "name": f"거는 시험-{uuid.uuid4().hex[:6]}",
            "attributes": [
                {"definition_id": definitions["규격서"], "document_id": document["id"]}
            ],
        },
        headers=admin.headers,
    )

    blocked = client.delete(f"/api/spec-documents/{document['id']}", headers=admin.headers)
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["error"]["code"] == "TSC-DOCS-0005"
    assert blocked.json()["error"]["details"]["linked_test_count"] == 1


def test_같은_부서에_같은_번호는_하나(client: TestClient, admin: Signed) -> None:
    code = f"MX-REL-{uuid.uuid4().hex[:6]}"
    assert _document(client, admin, code=code).status_code == 201
    clash = _document(client, admin, code=code)
    assert clash.status_code == 409, clash.text
    assert clash.json()["error"]["code"] == "TSC-DOCS-0003"

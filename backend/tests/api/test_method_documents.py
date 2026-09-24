"""규격서는 **규격에 붙는 파일**이다.

## 왜 여기 붙나

601건 중 원문을 가진 것이 19건뿐이라 「이 규격으로 시험하려면 어떤 장비가 필요한가」
(요구 조건)를 채울 재료가 없었다. 번호만 있고 문서가 없으면 읽을 수가 없다.

사내 규격서도 같은 자리다. **여러 신뢰성 시험이 한 문서를 인용한다** — 시험마다 값을
고르게 두면 같은 문서 설명을 시험마다 다시 적게 되므로, 규격 하나에 파일을 두고
신뢰성 시험은 「참조 규격」(`kind=method`)으로 가리킨다.

## 여기서 지키는 것

1. 규격에 파일이 붙고 **여럿 붙는다**(원문 · 국문 번역 · 개정 이력).
2. **올리고 지우는 것은 시스템 관리자만.** 규격은 전사 공용이라 한 부서가 올린 판이
   전사의 근거가 되면 안 된다.
3. **보는 것은 누구나.** 규격을 볼 수 있으면 그 문서도 볼 수 있다.
4. 같은 문서는 파일 한 벌이다 — 규격 여럿이 같은 PDF 를 가리켜도 디스크엔 하나.
"""

from __future__ import annotations

import io
import uuid

from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.attachments.models import Attachment, StoredFile
from app.modules.auth import security
from app.modules.workspaces.models import Workspace, WorkspaceMember
from tests.api.conftest import Signed

#: 가장 짧은 유효 PDF. 형식 검사를 통과해야 하므로 진짜 바이트라야 한다.
PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


def _method(client: TestClient, admin: Signed) -> str:
    made = client.post(
        "/api/methods",
        json={"code": f"ASTM E{uuid.uuid4().hex[:5]}", "title": "Tension Testing"},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def _upload(
    client: TestClient,
    headers: dict[str, str],
    method_id: str,
    *,
    data: bytes = PDF,
    name: str = "원문.pdf",
) -> Response:
    made: Response = client.post(
        "/api/attachments",
        data={"target": "method", "object_id": method_id, "caption": "규격 원문"},
        files={"file": (name, io.BytesIO(data), "application/pdf")},
        headers=headers,
    )
    return made


def _member(client: TestClient, db: Session, workspace: Workspace) -> Signed:
    """부서 관리자 — 규격서는 못 올려야 한다."""
    email = f"mgr-{uuid.uuid4().hex[:8]}@testscope.local"
    user = User(
        email=email,
        password_hash=security.hash_password("pw-mgr"),
        display_name="부서관리자",
        status="active",
        home_workspace_id=workspace.id,
    )
    db.add(user)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="manager"))
    db.commit()
    token = client.post("/api/auth/login", json={"email": email, "password": "pw-mgr"})
    return Signed(email=email, token=token.json()["access_token"], workspace=workspace.slug)


def test_규격에_파일이_여럿_붙는다(client: TestClient, admin: Signed) -> None:
    """원문 · 국문 번역 · 개정 이력이 한 규격에 함께 선다."""
    method_id = _method(client, admin)

    first = _upload(client, admin.headers, method_id, name="원문.pdf")
    assert first.status_code == 201, first.text
    assert first.json()["target"] == "method"

    second = _upload(client, admin.headers, method_id, data=PDF + b"ko\n", name="국문번역.pdf")
    assert second.status_code == 201, second.text

    listed = client.get(
        "/api/attachments",
        params={"target": "method", "object_id": method_id},
        headers=admin.headers,
    )
    assert listed.status_code == 200, listed.text
    assert {one["original_name"] for one in listed.json()} == {"원문.pdf", "국문번역.pdf"}

    # 파일이 그대로 내려온다 — 화면이 눌러서 연다.
    got = client.get(first.json()["url"], headers=admin.headers)
    assert got.status_code == 200
    assert got.headers["content-type"] == "application/pdf"


def test_올리는_것은_시스템_관리자만_보는_것은_누구나(
    client: TestClient, admin: Signed, db: Session, workspace: Workspace
) -> None:
    """규격은 전사 공용이라 한 부서가 올린 판이 전사의 근거가 되면 안 된다."""
    method_id = _method(client, admin)
    made = _upload(client, admin.headers, method_id)
    assert made.status_code == 201, made.text

    manager = _member(client, db, workspace)
    blocked = _upload(client, manager.headers, method_id, data=PDF + b"x\n", name="남.pdf")
    assert blocked.status_code == 403, blocked.text
    assert blocked.json()["error"]["code"] == "TSC-ATTACH-0006"

    # 지우는 것도 못 한다.
    gone = client.delete(f"/api/attachments/{made.json()['id']}", headers=manager.headers)
    assert gone.status_code == 403, gone.text

    # **보는 것은 된다** — 규격을 볼 수 있으면 그 문서도 볼 수 있다.
    listed = client.get(
        "/api/attachments",
        params={"target": "method", "object_id": method_id},
        headers=manager.headers,
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert client.get(made.json()["url"], headers=manager.headers).status_code == 200


def test_같은_문서는_파일_한_벌이다(client: TestClient, admin: Signed, db: Session) -> None:
    """ISO 원문 하나를 여러 규격 줄이 가리키는 일이 있다(판이 갈린 경우)."""
    same = PDF + b"shared\n"
    one = _upload(client, admin.headers, _method(client, admin), data=same)
    two = _upload(client, admin.headers, _method(client, admin), data=same)
    assert one.status_code == 201 and two.status_code == 201, two.text

    rows = db.scalars(
        select(Attachment).where(
            Attachment.id.in_([uuid.UUID(one.json()["id"]), uuid.UUID(two.json()["id"])])
        )
    ).all()
    assert len({row.file_id for row in rows}) == 1, "같은 내용인데 파일이 둘입니다"

    # 한쪽을 지워도 파일은 남는다 — 다른 규격이 아직 쓴다.
    file_id = rows[0].file_id
    client.delete(f"/api/attachments/{one.json()['id']}", headers=admin.headers)
    db.expire_all()
    assert db.get(StoredFile, file_id) is not None


def test_없는_규격에는_못_붙인다(client: TestClient, admin: Signed) -> None:
    missing = _upload(client, admin.headers, str(uuid.uuid4()))
    assert missing.status_code == 404, missing.text

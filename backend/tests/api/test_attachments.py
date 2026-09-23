"""그림과 첨부 — **파일은 한 벌, 붙는 자리는 여럿.**

사내 시험 카드에는 그림이 들어가는데 **어느 칸에 붙는지가 문서마다 다르다.** 칸마다 그림
칸을 만들면 대부분 빈 칸으로 서고, 새 자리가 생길 때마다 스키마가 바뀐다.

여기서 지키는 것:

1. 붙는 자리는 **골라도 되고 안 골라도 된다.** 아무 칸에도 안 붙는 그림이 실제로 있다.
2. **같은 그림은 파일 한 벌이다.** 표준 치구 사진이 시험 서른에 붙어도 디스크엔 하나.
3. 지우면 붙은 줄이 가고, **파일은 참조가 0 일 때만** 간다.
4. 보는 것은 누구나, 넣고 지우는 것은 **그 시험을 고칠 수 있는 사람.**
5. 형식과 크기를 막고, **무엇이 문제인지 말한다.**
"""

from __future__ import annotations

import io
import uuid
import zlib

from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.attachments.models import Attachment, StoredFile
from app.modules.auth import security
from app.modules.workspaces.models import Workspace, WorkspaceMember
from tests.api.conftest import Signed


def _png(color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    """1픽셀 PNG. 내용이 같으면 해시도 같다 — 그것이 이 시험의 요점이다."""

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            len(body).to_bytes(4, "big")
            + kind
            + body
            + zlib.crc32(kind + body).to_bytes(4, "big")
        )

    header = chunk(
        b"IHDR", (1).to_bytes(4, "big") + (1).to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"
    )
    raw = bytes([0, *color])
    data = chunk(b"IDAT", zlib.compress(raw))
    return b"\x89PNG\r\n\x1a\n" + header + data + chunk(b"IEND", b"")


def _test(client: TestClient, admin: Signed, name: str) -> str:
    made = client.post(
        "/api/reliability-tests",
        json={"workspace_slug": admin.workspace, "name": name},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def _upload(
    client: TestClient,
    headers: dict[str, str],
    test_id: str,
    *,
    data: bytes | None = None,
    name: str = "그림.png",
    content_type: str = "image/png",
    definition_id: str | None = None,
    caption: str = "",
) -> Response:
    form = {
        "target": "reliability_test",
        "object_id": test_id,
        "caption": caption,
    }
    if definition_id:
        form["definition_id"] = definition_id
    response: Response = client.post(
        "/api/attachments",
        data=form,
        files={"file": (name, io.BytesIO(data if data is not None else _png()), content_type)},
        headers=headers,
    )
    return response


def test_붙는_자리는_골라도_되고_안_골라도_된다(client: TestClient, admin: Signed) -> None:
    tag = uuid.uuid4().hex[:6]
    test_id = _test(client, admin, f"그림 시험-{tag}")
    definitions = {
        one["label"]: one["id"]
        for one in client.get(
            "/api/attribute-definitions",
            params={"target": "reliability_test"},
            headers=admin.headers,
        ).json()
    }

    # 칸에 붙인 것.
    on_field = _upload(
        client,
        admin.headers,
        test_id,
        definition_id=definitions["시험 절차"],
        caption="시편 장착 방향",
        name="장착.png",
    )
    assert on_field.status_code == 201, on_field.text
    assert on_field.json()["definition_label"] == "시험 절차"
    assert on_field.json()["caption"] == "시편 장착 방향"

    # **아무 칸에도 안 붙는 것** — 부록·전경 사진.
    loose = _upload(client, admin.headers, test_id, data=_png((0, 255, 0)), caption="전경")
    assert loose.status_code == 201, loose.text
    assert loose.json()["definition_id"] is None
    assert loose.json()["definition_label"] is None

    listed = client.get(
        "/api/attachments",
        params={"target": "reliability_test", "object_id": test_id},
        headers=admin.headers,
    )
    assert listed.status_code == 200, listed.text
    assert [one["caption"] for one in listed.json()] == ["시편 장착 방향", "전경"]

    # 파일이 그대로 내려온다 — 화면이 <img src> 로 쓴다.
    got = client.get(on_field.json()["url"], headers=admin.headers)
    assert got.status_code == 200, got.text
    assert got.headers["content-type"] == "image/png"


def test_같은_그림은_파일_한_벌이고_참조가_0_일_때만_지워진다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    """표준 치구 사진이 시험 서른에 붙어도 디스크에는 한 벌이다."""
    tag = uuid.uuid4().hex[:6]
    same = _png((7, 7, 7))
    first = _test(client, admin, f"A-{tag}")
    second = _test(client, admin, f"B-{tag}")

    one = _upload(client, admin.headers, first, data=same, name="치구.png")
    two = _upload(client, admin.headers, second, data=same, name="같은치구.png")
    assert one.status_code == 201 and two.status_code == 201, two.text

    rows = db.scalars(
        select(Attachment).where(
            Attachment.id.in_([uuid.UUID(one.json()["id"]), uuid.UUID(two.json()["id"])])
        )
    ).all()
    assert len({row.file_id for row in rows}) == 1, "같은 내용인데 파일이 둘입니다"
    # 이름은 붙은 줄이 갖는다 — 같은 그림을 다른 이름으로 올릴 수 있다.
    assert {row.original_name for row in rows} == {"치구.png", "같은치구.png"}
    file_id = rows[0].file_id

    # 한쪽을 지워도 **파일은 남는다** — 남의 시험이 아직 쓴다.
    assert (
        client.delete(
            f"/api/attachments/{one.json()['id']}", headers=admin.headers
        ).status_code
        == 204
    )
    db.expire_all()
    assert db.get(StoredFile, file_id) is not None

    # 마지막 줄이 가면 파일도 간다.
    assert (
        client.delete(
            f"/api/attachments/{two.json()['id']}", headers=admin.headers
        ).status_code
        == 204
    )
    db.expire_all()
    assert db.get(StoredFile, file_id) is None


def test_시험을_지우면_그림도_간다(client: TestClient, admin: Signed, db: Session) -> None:
    tag = uuid.uuid4().hex[:6]
    test_id = _test(client, admin, f"지울 시험-{tag}")
    made = _upload(client, admin.headers, test_id, data=_png((3, 3, 3)))
    assert made.status_code == 201, made.text
    file_id = db.get(Attachment, uuid.UUID(made.json()["id"])).file_id  # type: ignore[union-attr]

    assert client.delete(
        f"/api/reliability-tests/{test_id}", headers=admin.headers
    ).status_code in (
        200,
        204,
    )
    db.expire_all()
    assert db.get(Attachment, uuid.UUID(made.json()["id"])) is None
    assert db.get(StoredFile, file_id) is None


def test_형식과_크기를_막고_무엇이_문제인지_말한다(client: TestClient, admin: Signed) -> None:
    tag = uuid.uuid4().hex[:6]
    test_id = _test(client, admin, f"거절 시험-{tag}")

    wrong = _upload(
        client,
        admin.headers,
        test_id,
        data=b"#!/bin/sh",
        name="x.sh",
        content_type="text/x-sh",
    )
    assert wrong.status_code == 422, wrong.text
    assert wrong.json()["error"]["code"] == "TSC-ATTACH-0002"
    # **무엇을 받는지 말해 준다** — 「안 됩니다」 만 하면 사람은 될 때까지 찔러 본다.
    assert "image/png" in wrong.json()["error"]["details"]["allowed"]

    big = _upload(
        client, admin.headers, test_id, data=b"\x89PNG\r\n\x1a\n" + b"0" * (10 * 1024 * 1024)
    )
    assert big.status_code == 422, big.text
    assert big.json()["error"]["code"] == "TSC-ATTACH-0004"


def test_보는_것은_누구나_넣는_것은_고칠_수_있는_사람(
    client: TestClient, admin: Signed, db: Session, workspace: Workspace
) -> None:
    """그림은 **플랫폼에 들어와 조회하는 사람**의 것이다 — 넣은 사람만 보면 몫이 없다."""
    tag = uuid.uuid4().hex[:6]
    test_id = _test(client, admin, f"권한 시험-{tag}")
    made = _upload(client, admin.headers, test_id, caption="합격 예시")
    assert made.status_code == 201, made.text

    email = f"member-{uuid.uuid4().hex[:8]}@testscope.local"
    person = User(
        email=email,
        password_hash=security.hash_password("member-password"),
        display_name="부서 멤버",
        status="active",
        is_system_admin=False,
        home_workspace_id=workspace.id,
    )
    db.add(person)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=person.id, role="member"))
    db.commit()
    login = client.post(
        "/api/auth/login", json={"email": email, "password": "member-password"}
    )
    assert login.status_code == 200, login.text
    member = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # 보는 것은 된다.
    listed = client.get(
        "/api/attachments",
        params={"target": "reliability_test", "object_id": test_id},
        headers=member,
    )
    assert listed.status_code == 200 and len(listed.json()) == 1
    assert client.get(made.json()["url"], headers=member).status_code == 200

    # 넣는 것은 **시험을 고칠 수 있는 사람**이다 — 신뢰성 시험은 부서 관리자.
    blocked = _upload(client, member, test_id, data=_png((9, 9, 9)))
    assert blocked.status_code == 403, blocked.text
    assert (
        client.delete(f"/api/attachments/{made.json()['id']}", headers=member).status_code
        == 403
    )

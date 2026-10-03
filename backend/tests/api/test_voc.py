"""VOC — **게시판이고 절차다.**

앱 안에 접수 경로가 없으면 문제는 구두로만 오가고 기록이 안 남는다. 그런데 「낸 사람과
관리자만 보는 카드 + 답변 한 줄」 로 두면 그것대로 세 가지가 안 된다: 같은 문제를 여럿이
따로 내는 것을 못 막고, 무엇이 고쳐졌는지 남들이 모르고, 「접수됐나 → 보고 있나 → 됐나」 가
한 줄에 뭉쳐 중간 상태가 없다.

여기서 지키는 것:

1. **로그인한 사람은 다 본다** — 게시판이다. 낸 사람만 보면 같은 건이 여러 벌 쌓인다.
2. 등록도 **이벤트로 남는다** — 흐름의 첫 줄이 비면 언제 낸 것인지가 카드 머리에만 있다.
3. **해결·반려·다시 열기에는 말이 있어야 한다.** 「해결」 만 찍힌 건은 무엇이 바뀌었는지
   아무도 모르고, 이유 없는 「반려」 는 낸 사람이 같은 것을 다시 낼 수밖에 없다.
4. **해결됐다는 말은 관리자가, 됐다는 확인은 낸 사람이** 한다. 관리자가 닫아 버리면
   「고쳐졌다는데 여전히 안 된다」 가 어디에도 안 남는다.
5. 아무나 상태를 못 옮긴다 — 그리고 **못 옮긴다는 것을 화면이 미리 안다**(`can_move`).
6. 같은 상태로 보내면 **댓글**이다. 그건 누구나.
7. **자료(화면 갈무리)는 낸 사람과 관리자가 붙이고 지운다** — 보는 것은 누구나. 그리고 붙일
   수 있는지를 화면이 미리 안다(`can_attach`).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.auth import security
from app.modules.workspaces.models import Workspace, WorkspaceMember
from tests.api.conftest import Signed
from tests.api.test_attachments import _png


def _member(client: TestClient, db: Session, workspace: Workspace) -> Signed:
    """관리자가 아닌 보통 사람. **게시판이 보이는지**를 이 사람으로 본다."""
    email = f"{uuid.uuid4().hex[:8]}@testscope.local"
    user = User(
        email=email,
        password_hash=security.hash_password("pw-voc"),
        display_name="제보자",
        status="active",
        home_workspace_id=workspace.id,
    )
    db.add(user)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="member"))
    db.commit()
    got = client.post("/api/auth/login", json={"email": email, "password": "pw-voc"})
    assert got.status_code == 200, got.text
    return Signed(email=email, token=got.json()["access_token"], workspace=workspace.slug)


def _file(client: TestClient, who: Signed, title: str) -> dict[str, Any]:
    made = client.post(
        "/api/voc",
        json={
            "title": title,
            "body": "그 화면에서 저장이 안 됩니다.",
            "page_path": "/equipment",
        },
        headers=who.headers,
    )
    assert made.status_code == 201, made.text
    out: dict[str, Any] = made.json()
    return out


def _move(
    client: TestClient, who: Signed, item_id: str, to: str, note: str | None = None
) -> Any:
    return client.post(
        f"/api/voc/{item_id}/move",
        json={"to_status": to, "note": note},
        headers=who.headers,
    )


def test_게시판이라_남이_낸_것도_보인다(
    client: TestClient, db: Session, admin: Signed, workspace: Workspace
) -> None:
    """낸 사람만 보면 같은 문제가 여러 벌 쌓이고, 무엇이 고쳐졌는지 남들이 모른다."""
    one = _member(client, db, workspace)
    other = _member(client, db, workspace)
    made = _file(client, one, f"저장이 안 됩니다-{uuid.uuid4().hex[:6]}")

    seen = client.get("/api/voc", headers=other.headers)
    assert seen.status_code == 200, seen.text
    assert made["id"] in {row["id"] for row in seen.json()["items"]}

    # 그런데 **남의 건을 옮기지는 못한다** — 보이는 것과 고치는 것은 다르다.
    detail = client.get(f"/api/voc/{made['id']}", headers=other.headers).json()
    assert detail["can_move"] == []


def test_등록도_흐름의_한_줄로_남는다(
    client: TestClient, db: Session, admin: Signed, workspace: Workspace
) -> None:
    one = _member(client, db, workspace)
    made = _file(client, one, f"첫 줄-{uuid.uuid4().hex[:6]}")
    assert len(made["events"]) == 1
    first = made["events"][0]
    # **앞 상태가 비어 있는 줄이 「등록」 이다.**
    assert first["from_status"] is None and first["to_status"] == "open"
    assert first["by_name"] == "제보자"
    assert made["status"] == "open" and made["status_label"] == "등록"
    assert made["page_path"] == "/equipment"


def test_해결과_반려에는_말이_있어야_한다(
    client: TestClient, db: Session, admin: Signed, workspace: Workspace
) -> None:
    one = _member(client, db, workspace)
    made = _file(client, one, f"말 없이-{uuid.uuid4().hex[:6]}")

    empty = _move(client, admin, made["id"], "resolved")
    assert empty.status_code == 400, empty.text
    assert empty.json()["error"]["code"] == "TSC-VOC-0004"

    done = _move(client, admin, made["id"], "resolved", "저장 단추의 권한 검사를 고쳤습니다")
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "resolved"
    assert done.json()["events"][-1]["note"] == "저장 단추의 권한 검사를 고쳤습니다"


def test_됐다는_확인은_낸_사람이_한다(
    client: TestClient, db: Session, admin: Signed, workspace: Workspace
) -> None:
    """관리자가 닫아 버리면 「고쳐졌다는데 여전히 안 된다」 가 어디에도 안 남는다."""
    one = _member(client, db, workspace)
    made = _file(client, one, f"확인-{uuid.uuid4().hex[:6]}")
    assert _move(client, admin, made["id"], "resolved", "고쳤습니다").status_code == 200

    # 낸 사람은 닫을 수도 있고, **아직 안 된다고 다시 열 수도** 있다.
    reopened = _move(client, one, made["id"], "open", "같은 자리에서 여전히 안 됩니다")
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "open"

    assert _move(client, admin, made["id"], "resolved", "이번엔 진짜").status_code == 200
    closed = _move(client, one, made["id"], "closed")
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"


def test_아무나_상태를_못_옮기고_그것을_미리_안다(
    client: TestClient, db: Session, admin: Signed, workspace: Workspace
) -> None:
    """화면이 권한을 다시 계산하면 서버와 갈라지고, 그때 사람은 눌리는 단추가 403 을
    돌려주는 것을 본다."""
    one = _member(client, db, workspace)
    other = _member(client, db, workspace)
    made = _file(client, one, f"남의 건-{uuid.uuid4().hex[:6]}")

    refused = _move(client, other, made["id"], "accepted")
    assert refused.status_code == 403, refused.text
    assert refused.json()["error"]["code"] == "TSC-VOC-0003"

    # 낸 사람도 `open` 에서는 옮길 데가 없다 — 접수는 관리자의 일이다.
    assert client.get(f"/api/voc/{made['id']}", headers=one.headers).json()["can_move"] == []
    # 관리자는 갈 곳이 있고, 그중 말이 필요한 것이 무엇인지도 함께 온다.
    seen = client.get(f"/api/voc/{made['id']}", headers=admin.headers).json()
    assert "accepted" in seen["can_move"]
    assert set(seen["note_required"]) <= set(seen["can_move"])
    assert "resolved" in seen["note_required"]


def test_같은_상태로_보내면_댓글이고_누구나_한다(
    client: TestClient, db: Session, admin: Signed, workspace: Workspace
) -> None:
    one = _member(client, db, workspace)
    other = _member(client, db, workspace)
    made = _file(client, one, f"댓글-{uuid.uuid4().hex[:6]}")

    said = _move(client, other, made["id"], "open", "저도 같은 증상입니다")
    assert said.status_code == 200, said.text
    assert said.json()["status"] == "open", "댓글이 상태를 옮기면 안 된다"
    assert said.json()["events"][-1]["note"] == "저도 같은 증상입니다"
    assert said.json()["comment_count"] == 1

    # 빈 댓글은 안 받는다 — 아무 말도 안 하는 줄이 쌓인다.
    nothing = _move(client, other, made["id"], "open")
    assert nothing.status_code == 400, nothing.text
    assert nothing.json()["error"]["code"] == "TSC-VOC-0002"


def test_기본_목록은_끝난_건을_빼고_내_것만도_본다(
    client: TestClient, db: Session, admin: Signed, workspace: Workspace
) -> None:
    """종료·반려는 쌓이기만 한다. 그리고 「내가 낸 그거 어떻게 됐지」 가 가장 흔한 물음이다."""
    one = _member(client, db, workspace)
    other = _member(client, db, workspace)
    tag = uuid.uuid4().hex[:6]
    mine = _file(client, one, f"내 것-{tag}")
    theirs = _file(client, other, f"남의 것-{tag}")
    assert _move(client, admin, theirs["id"], "rejected", "사양입니다").status_code == 200

    default = client.get("/api/voc", headers=one.headers).json()["items"]
    ids = {row["id"] for row in default}
    assert mine["id"] in ids
    assert theirs["id"] not in ids, "반려된 건이 기본 목록에 남아 있다"

    everything = client.get("/api/voc", params={"status": "all"}, headers=one.headers).json()
    assert theirs["id"] in {row["id"] for row in everything["items"]}

    only_mine = client.get("/api/voc", params={"mine": True}, headers=one.headers).json()
    assert {row["id"] for row in only_mine["items"]} == {mine["id"]}


def test_자료는_낸_사람과_관리자가_붙이고_누구나_본다(
    client: TestClient, admin: Signed, db: Session, workspace: Workspace
) -> None:
    """화면 갈무리 한 장이 「저장이 안 된다」 는 글 열 줄보다 빨리 재현된다. 그런데 남이 붙인
    그림을 지울 수 있으면 낸 사람의 근거가 사라진다."""
    author = _member(client, db, workspace)
    other = _member(client, db, workspace)
    item = _file(client, author, f"저장이 안 됩니다-{uuid.uuid4().hex[:6]}")

    def put(who: Signed) -> Any:
        return client.post(
            "/api/attachments",
            data={"target": "voc", "object_id": item["id"]},
            files={"file": ("화면.png", _png(), "image/png")},
            headers=who.headers,
        )

    # 화면이 미리 안다 — 낸 사람은 붙일 수 있고, 남은 못 붙인다.
    assert client.get(f"/api/voc/{item['id']}", headers=author.headers).json()["can_attach"]
    assert not client.get(f"/api/voc/{item['id']}", headers=other.headers).json()["can_attach"]

    mine = put(author)
    assert mine.status_code == 201, mine.text
    refused = put(other)
    assert refused.status_code == 403, refused.text
    assert refused.json()["error"]["code"] == "TSC-VOC-0006"
    assert put(admin).status_code == 201

    # 보는 것은 누구나 — 게시판이다.
    seen = client.get(
        f"/api/attachments?target=voc&object_id={item['id']}", headers=other.headers
    )
    assert seen.status_code == 200, seen.text
    assert len(seen.json()) == 2

    # 남이 지울 수도 없다.
    gone = client.delete(f"/api/attachments/{mine.json()['id']}", headers=other.headers)
    assert gone.status_code == 403, gone.text

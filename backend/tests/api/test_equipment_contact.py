"""담당자 — **찾은 다음에 연락할 사람.**

모델 주석이 「찾은 다음에 연락할 사람이 없으면 검색은 절반만 한 것」 이라고 적어 둔 칸인데,
**넣을 자리가 어느 화면에도 없었다** — API 와 상세 화면에는 있고 등록·수정 창에는 없어서,
개발 DB 에서 299대 중 295대가 비어 있었다(2026-10-02).

여기서 지키는 것:

1. 등록·수정으로 담당자를 넣고 되받는다 — 이름과 **id 둘 다**(수정 창이 미리 고르려면 id).
2. **없는 계정은 400**이다. 외래키 500 으로 터지면 「서버 오류」 로 읽혀 제 오타를 못 본다.
3. **쉰 계정은 안 받는다** — 담당자 칸의 쓸모가 「연락이 닿는다」 하나뿐이다.
4. 부서 소속까지는 안 본다 — 부서를 옮긴 사람이 계속 맡는 일이 있고, 막으면 칸을 비운다.
5. **대장 반입으로 한 번에 채운다**(`담당자` 열). 295대를 한 대씩 열어 채우는 것은 사람이
   할 수 있는 일이 아니다. 이메일이 먼저고, 이름이 여럿이면 **고르지 않고 말한다.**
6. `contact=none` 으로 **비어 있는 장비를 찾는다** — 채울 대상을 못 찾으면 안 채워진다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.auth import security
from app.modules.workspaces.models import Workspace, WorkspaceMember
from tests.api.conftest import Signed, category_id, site_id


def _person(db: Session, workspace: Workspace, name: str, *, status: str = "active") -> User:
    user = User(
        email=f"{uuid.uuid4().hex[:8]}@testscope.local",
        password_hash=security.hash_password("pw-contact"),
        display_name=name,
        status=status,
        home_workspace_id=workspace.id,
    )
    db.add(user)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="member"))
    db.commit()
    return user


def _make(client: TestClient, admin: Signed, tag: str, **extra: Any) -> dict[str, Any]:
    made = client.post(
        "/api/equipment",
        json={
            "asset_no": f"CT-{tag}-{uuid.uuid4().hex[:4]}",
            "name": f"만능기-{tag}",
            "workspace_slug": admin.workspace,
            "site_term_id": site_id(client, admin),
            "location": "3동",
            "category_term_id": category_id(client, admin),
            **extra,
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    out: dict[str, Any] = made.json()
    return out


def test_담당자를_넣고_이름과_id_를_되받는다(
    client: TestClient, db: Session, admin: Signed, workspace: Workspace
) -> None:
    tag = uuid.uuid4().hex[:6]
    person = _person(db, workspace, f"김담당-{tag}")

    one = _make(client, admin, tag, contact_user_id=str(person.id))
    assert one["contact_name"] == f"김담당-{tag}"
    # **id 도 준다** — 이름만 주면 수정 창이 그 이름으로 사람을 되찾아야 하고, 동명이인이
    # 있으면 엉뚱한 사람이 골라진다.
    assert one["contact_user_id"] == str(person.id)

    # 비우는 것도 된다 — 사람이 바뀌는 동안 틀린 이름을 두는 것보다 낫다.
    cleared = client.patch(
        f"/api/equipment/{one['id']}", json={"contact_user_id": None}, headers=admin.headers
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["contact_name"] is None


def test_없는_계정과_쉰_계정은_막는다(
    client: TestClient, db: Session, admin: Signed, workspace: Workspace
) -> None:
    tag = uuid.uuid4().hex[:6]
    gone = _person(db, workspace, f"떠난사람-{tag}", status="suspended")
    one = _make(client, admin, tag)

    missing = client.patch(
        f"/api/equipment/{one['id']}",
        json={"contact_user_id": str(uuid.uuid4())},
        headers=admin.headers,
    )
    # **외래키 500 이 아니라 400** — 500 은 「서버 오류」 로 읽혀서 제 오타를 못 본다.
    assert missing.status_code == 400, missing.text
    assert "찾을 수 없습니다" in missing.json()["error"]["message"]

    dead = client.patch(
        f"/api/equipment/{one['id']}",
        json={"contact_user_id": str(gone.id)},
        headers=admin.headers,
    )
    assert dead.status_code == 400, dead.text
    # **왜 막혔는지 말한다** — 「연락이 닿는 사람」 이 이 칸의 쓸모 전부다.
    assert "쓰지 않는 계정" in dead.json()["error"]["message"]


def test_대장_반입으로_한_번에_채운다(
    client: TestClient, db: Session, admin: Signed, workspace: Workspace
) -> None:
    """295대를 한 대씩 창을 열어 채우는 것은 사람이 할 수 있는 일이 아니다."""
    tag = uuid.uuid4().hex[:6]
    one = _person(db, workspace, f"김담당-{tag}")
    _person(db, workspace, f"겹치는이름-{tag}")
    _person(db, workspace, f"겹치는이름-{tag}")

    site = client.get("/api/vocabularies/site/terms", headers=admin.headers).json()[0]
    kind = client.get(
        "/api/vocabularies/equipment_category/terms", headers=admin.headers
    ).json()[0]
    header = "자산번호,장비명,보유부서,거점,설치위치,장비유형,담당자"
    team = db.get(Workspace, workspace.id)
    assert team is not None

    def upload(body: str, *, dry_run: bool = True) -> dict[str, Any]:
        got = client.post(
            f"/api/equipment/import?dry_run={'true' if dry_run else 'false'}",
            json={"text": body},
            headers=admin.headers,
        )
        assert got.status_code == 200, got.text
        out: dict[str, Any] = got.json()
        return out

    # 이메일로 — **이름보다 먼저다.** 동명이인이 실제로 있다.
    done = upload(
        f"{header}\n"
        f"CT-{tag}-1,만능기,{team.name},{site['value']},3동,{kind['value']},{one.email}\n"
        f"CT-{tag}-2,충격기,{team.name},{site['value']},3동,{kind['value']},김담당-{tag}\n",
        dry_run=False,
    )
    assert done["created"] == 2, done
    listed = client.get(f"/api/equipment?q=CT-{tag}", headers=admin.headers).json()["items"]
    assert {row["contact_name"] for row in listed} == {f"김담당-{tag}"}

    # 이름이 여럿이면 **고르지 않고 말한다** — 하나를 골라 넣으면 그 장비의 연락처가 남의
    # 것이 되고, 틀린 것을 아무도 모른다.
    said = upload(
        f"{header}\n"
        f"CT-{tag}-3,경도계,{team.name},{site['value']},3동,{kind['value']},겹치는이름-{tag}\n"
    )
    problems = [item["message"] for row in said["rows"] for item in row.get("problems", [])]
    assert any("여럿입니다" in one for one in problems), said["rows"]


def test_담당자가_비어_있는_장비를_찾는다(
    client: TestClient, db: Session, admin: Signed, workspace: Workspace
) -> None:
    """**채울 대상을 못 찾으면 안 채워진다.** 295대가 어디 있는지 알아야 일이 된다."""
    tag = uuid.uuid4().hex[:6]
    person = _person(db, workspace, f"김담당-{tag}")
    filled = _make(client, admin, tag, contact_user_id=str(person.id))
    blank = _make(client, admin, tag)

    got = client.get(
        "/api/equipment", params={"q": tag, "contact": "none"}, headers=admin.headers
    )
    assert got.status_code == 200, got.text
    assets = {one["asset_no"] for one in got.json()["items"]}
    assert assets == {blank["asset_no"]}
    assert filled["asset_no"] not in assets

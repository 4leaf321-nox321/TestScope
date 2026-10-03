"""HWAX 포털 게이트웨이의 사람별 위임 — **표준 위임 창구(/api/auth/sso)와 같은 모양인가.**

게이트웨이가 사람 이름으로 TestScope 를 부르려면 그 사람의 TestScope 토큰이 있어야 한다.
지금까지는 사람이 여기서 발급해 포털 「개인 토큰 → 외부 연결」 에 붙여 넣었다. 이제
게이트웨이가 공유 비밀과 이메일로 직접 받아 간다 — 계약의 정본은 포털 요청서(HWAXPortal
`docs/sso-delegation/ra-request.md`)이고, Report Archive 가 같은 계약으로 먼저 붙었다.

RA 와 **다른 것 둘**이 이 시험의 요지다:

* **계정을 만들지 않는다.** TestScope 는 가입 → 승인의 절차가 있다. 없는 사람은 403 이다.
* **읽기 전용이다.** 범위가 `read` 로 고정된다 — 포털에서 들어오는 쓰기는 우리가 프롬프트를
  못 보는 통로다.

그리고 거절은 403, 꺼짐만 404 — 게이트웨이가 404 를 「아직 안 켬」 으로 읽어 등록 토큰으로
내려가므로, 사람 하나의 거절을 404 로 내면 창구 전체가 꺼진 줄 안다(RA 가 겪고 고친 자리).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modules.accounts.models import User
from app.modules.audit.models import AuditEntry
from app.modules.auth import security
from app.modules.auth.models import PersonalAccessToken
from app.modules.workspaces.models import Workspace, WorkspaceMember
from app.shared import audit
from tests.api.conftest import Signed

SECRET = "test-gateway-secret-0123456789abcdef"
SSO = "/api/auth/sso"


@pytest.fixture
def delegation_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "heax_sso_secret", SECRET)
    monkeypatch.setattr(get_settings(), "heax_sso_allowed_ips", "")


def _person(
    db: Session,
    workspace: Workspace,
    *,
    status: str = "active",
    email: str | None = None,
    home: bool = True,
) -> User:
    user = User(
        email=email or f"gw-{uuid.uuid4().hex[:8]}@testscope.local",
        password_hash=security.hash_password("pw-gateway"),
        display_name="포털 사용자",
        status=status,
        home_workspace_id=workspace.id if home else None,
    )
    db.add(user)
    db.flush()
    if home:
        db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="member"))
    db.commit()
    return user


def _post(
    client: TestClient,
    path: str,
    email: str | None = None,
    *,
    secret: str | None = SECRET,
    client_name: str = "gateway",
) -> Any:
    headers: dict[str, str] = {"X-Heax-Client": client_name}
    if secret is not None:
        headers["X-Heax-Gateway-Secret"] = secret
    if email is not None:
        headers["X-Heax-User-Email"] = email
    return client.post(path, headers=headers)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── 표준 모양 ─────────────────────────────────────────────────────────────────


def test_세_창구_모두_기본은_꺼져_있다(client: TestClient) -> None:
    """비밀이 비면 있는지조차 흘리지 않는다 — 게이트웨이는 이 404 를 「아직 안 켬」 으로
    읽는다."""
    for path in (SSO, f"{SSO}/verify", f"{SSO}/revoke"):
        assert _post(client, path, "anyone@testscope.local").status_code == 404, path


def test_발급이_요청서_계약과_같다(
    client: TestClient, db: Session, workspace: Workspace, delegation_on: None
) -> None:
    person = _person(db, workspace)
    got = _post(client, SSO, person.email)
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["success"] is True
    data = body["data"]
    assert data["access_token"].startswith("tsc_pat_")
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 2 * 86400
    assert data["needs_workspace"] is False

    # 그 토큰으로 **그 사람**이 된다.
    me = client.get("/api/auth/me", headers=_bearer(data["access_token"]))
    assert me.status_code == 200, me.text
    assert me.json()["email"] == person.email

    # 「내 정보 → 토큰」 에 **읽기 전용**으로 선다 — client 이름이 붙는다.
    pat = db.scalar(
        select(PersonalAccessToken).where(
            PersonalAccessToken.user_id == person.id, PersonalAccessToken.revoked_at.is_(None)
        )
    )
    assert pat is not None
    assert pat.name == "HWAX 포탈 게이트웨이 (gateway)"
    assert pat.scopes == ["read"]
    assert pat.expires_at is not None


def test_읽기_전용이라_쓰기는_범위에서_막힌다(
    client: TestClient, db: Session, workspace: Workspace, delegation_on: None
) -> None:
    """포털에서 들어오는 쓰기는 우리가 프롬프트를 못 보는 통로다 — 범위로 막는다."""
    person = _person(db, workspace)
    token = _post(client, SSO, person.email).json()["data"]["access_token"]
    refused = client.post(
        "/api/equipment",
        json={"asset_no": f"GW-{uuid.uuid4().hex[:4]}", "name": "x"},
        headers=_bearer(token),
    )
    assert refused.status_code == 403, refused.text
    assert refused.json()["error"]["code"] == "TSC-AUTH-0106"
    assert refused.json()["error"]["details"]["granted"] == ["read"]


def test_verify_는_비밀만_본다(client: TestClient, delegation_on: None) -> None:
    assert _post(client, f"{SSO}/verify").status_code == 204
    assert _post(client, f"{SSO}/verify", secret="nope").status_code == 401


def test_비밀이나_자리가_틀리면_거절한다(
    client: TestClient,
    db: Session,
    workspace: Workspace,
    delegation_on: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    person = _person(db, workspace)
    assert _post(client, SSO, person.email, secret="nope").status_code == 401
    assert _post(client, SSO, person.email, secret=None).status_code == 401
    # 허용 IP 가 있으면 그 밖은 403 — 시험 클라이언트는 그 주소가 아니다.
    monkeypatch.setattr(get_settings(), "heax_sso_allowed_ips", "10.0.0.1")
    got = _post(client, SSO, person.email)
    assert got.status_code == 403, got.text
    assert got.json()["error"]["code"] == "TSC-AUTH-0201"


def test_다시_받으면_직전_것이_폐기되고_revoke_로_없앤다(
    client: TestClient, db: Session, workspace: Workspace, delegation_on: None
) -> None:
    person = _person(db, workspace)
    first = _post(client, SSO, person.email).json()["data"]["access_token"]
    second = _post(client, SSO, person.email).json()["data"]["access_token"]
    assert first != second
    # 직전 것은 죽는다 — 게이트웨이도 「새 발급이 직전 것을 회수한다」 를 전제로 한다.
    assert client.get("/api/auth/me", headers=_bearer(first)).status_code == 401
    assert client.get("/api/auth/me", headers=_bearer(second)).status_code == 200
    # **지우지 않고 폐기로 남는다** — 「언제 누가 받아 갔나」 가 목록에 남아야 한다.
    rows = db.scalars(
        select(PersonalAccessToken).where(PersonalAccessToken.user_id == person.id)
    ).all()
    assert len(rows) == 2 and sum(1 for one in rows if one.revoked_at is None) == 1

    gone = _post(client, f"{SSO}/revoke", person.email)
    assert gone.status_code == 200 and gone.json()["revoked"] == 1
    assert client.get("/api/auth/me", headers=_bearer(second)).status_code == 401
    # 다른 client 의 토큰은 안 건드린다.
    other = _post(client, SSO, person.email, client_name="hwax-portal").json()["data"]
    assert _post(client, f"{SSO}/revoke", person.email).json()["revoked"] == 0
    assert (
        client.get("/api/auth/me", headers=_bearer(other["access_token"])).status_code == 200
    )


# ── RA 와 다른 것 ─────────────────────────────────────────────────────────────


def test_없는_사람은_만들지_않고_403_이다(
    client: TestClient, db: Session, delegation_on: None
) -> None:
    """TestScope 는 가입 → 승인의 절차가 있다. 위임 창구가 그 절차를 뚫으면 안
    된다."""
    email = f"stranger-{uuid.uuid4().hex[:8]}@testscope.local"
    got = _post(client, SSO, email)
    assert got.status_code == 403, got.text
    assert got.json()["error"]["code"] == "TSC-AUTH-0205"
    assert "가입" in got.json()["error"]["message"]
    assert db.scalar(select(User).where(User.email == email)) is None, "계정이 생겼다"


def test_승인_대기와_정지는_403_이다(
    client: TestClient, db: Session, workspace: Workspace, delegation_on: None
) -> None:
    """꺼짐(404)과 갈라야 한다 — 404 로 내면 게이트웨이가 창구 전체가 꺼진 줄
    안다."""
    pending = _person(db, workspace, status="pending")
    suspended = _person(db, workspace, status="suspended")
    for person, word in ((pending, "승인 대기"), (suspended, "쓸 수 없는")):
        got = _post(client, SSO, person.email)
        assert got.status_code == 403, got.text
        assert got.json()["error"]["code"] == "TSC-AUTH-0206"
        assert word in got.json()["error"]["message"]


def test_이메일_형식이_아니면_401_이다(client: TestClient, delegation_on: None) -> None:
    """형식 검사 없이 통과시키면 쓰레기 문자열로 계정을 찾는다. `admin` 은 화면
    로그인용이다."""
    for bad in ("admin", "no-at-sign", "a@b", "x y@z.com", ""):
        got = _post(client, SSO, bad)
        if bad == "":
            assert got.status_code == 400, bad
        else:
            assert got.status_code == 401, bad
            assert got.json()["error"]["code"] == "TSC-AUTH-0204"
    assert _post(client, f"{SSO}/revoke", "admin").status_code == 401


def test_대소문자가_달라도_같은_사람이다(
    client: TestClient, db: Session, workspace: Workspace, delegation_on: None
) -> None:
    person = _person(db, workspace)
    got = _post(client, SSO, person.email.upper())
    assert got.status_code == 200, got.text
    me = client.get("/api/auth/me", headers=_bearer(got.json()["data"]["access_token"]))
    assert me.json()["email"] == person.email


def test_부서가_없는_사람은_needs_workspace_가_참이다(
    client: TestClient, db: Session, workspace: Workspace, delegation_on: None
) -> None:
    person = _person(db, workspace, home=False)
    got = _post(client, SSO, person.email)
    assert got.status_code == 200, got.text
    assert got.json()["data"]["needs_workspace"] is True


def test_발급은_감사에_그_사람_명의로_남는다(
    client: TestClient, db: Session, workspace: Workspace, delegation_on: None
) -> None:
    """「이 토큰 누가 만들었어」 에 「포털이, 이 사람 명의로」 가 답이어야 한다."""
    person = _person(db, workspace)
    _post(client, SSO, person.email)
    _post(client, SSO, person.email)  # 직전 것을 하나 폐기한다
    entries = db.scalars(
        select(AuditEntry)
        .where(
            AuditEntry.action == audit.PAT_ISSUED_FOR_GATEWAY,
            AuditEntry.actor_id == person.id,
        )
        .order_by(AuditEntry.created_at)
    ).all()
    assert len(entries) == 2
    assert entries[0].changes["scopes"] == ["read"]
    assert entries[0].changes["client"] == "gateway"
    assert entries[0].changes["replaced"] == 0
    assert entries[1].changes["replaced"] == 1


def test_관리자가_아니어도_위임은_되고_권한은_그_사람_것이다(
    client: TestClient, db: Session, workspace: Workspace, admin: Signed, delegation_on: None
) -> None:
    """토큰은 그 사람을 넘지 못한다 — 관리자만 보는 것은 보통 사람의 위임 토큰으로 안
    보인다."""
    person = _person(db, workspace)
    token = _post(client, SSO, person.email).json()["data"]["access_token"]
    assert client.get("/api/accounts", headers=_bearer(token)).status_code == 403
    boss = _post(client, SSO, admin.email).json()["data"]["access_token"]
    assert client.get("/api/accounts", headers=_bearer(boss)).status_code == 200

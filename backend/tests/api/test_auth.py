"""인증과 계정 생애 — 로그인·가입 승인·오류 봉투."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from tests.api.conftest import ADMIN_PASSWORD, Signed


def test_health_는_버전을_함께_준다(client: TestClient) -> None:
    """원격에서 "지금 서버에 뭐가 깔렸나" 를 물을 수 있는 유일한 자리다."""
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["version"]


def test_로그인하면_소속과_역할이_함께_온다(client: TestClient, admin: Signed) -> None:
    """화면이 부서 선택기와 권한 표시를 그리려면 이 한 번의 응답으로 충분해야 한다."""
    me = client.get("/api/auth/me", headers=admin.headers).json()
    assert me["email"] == admin.email
    assert me["is_system_admin"] is True
    assert [one["slug"] for one in me["memberships"]] == [admin.workspace]
    assert me["memberships"][0]["role"] == "manager"


def test_틀린_비밀번호는_같은_말로_거절한다(client: TestClient, admin: Signed) -> None:
    """계정이 있는지 없는지가 응답으로 새면 안 된다 — 둘 다 같은 코드·같은 문구다."""
    wrong = client.post("/api/auth/login", json={"email": admin.email, "password": "nope"})
    missing = client.post(
        "/api/auth/login", json={"email": "nobody@testscope.local", "password": "nope"}
    )
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json()["error"]["code"] == missing.json()["error"]["code"] == "TSC-AUTH-0001"
    assert wrong.json()["error"]["message"] == missing.json()["error"]["message"]


def test_승인_전에는_로그인할_수_없고_사유를_말한다(client: TestClient, admin: Signed) -> None:
    """**왜 안 되는지** 를 구분해 준다. '비활성 계정' 이라고만 하면 관리자에게
    무엇을 요청해야 할지 알 수 없다."""
    email = f"new-{uuid.uuid4().hex[:8]}@testscope.local"
    created = client.post(
        "/api/accounts/signup",
        json={
            "email": email,
            "password": "member-password",
            "display_name": "신청자",
            "workspace_slug": admin.workspace,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "pending"

    login = {"email": email, "password": "member-password"}
    blocked = client.post("/api/auth/login", json=login)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "TSC-AUTH-0008"

    approved = client.post(
        f"/api/accounts/{created.json()['id']}/approve", json={}, headers=admin.headers
    )
    assert approved.status_code == 200, approved.text
    # **승인이 대표 소속을 정한다.** 안 정하면 로그인이 이름순 첫 부서로 떨어진다.
    assert approved.json()["home_workspace_slug"] == admin.workspace

    ok = client.post("/api/auth/login", json=login)
    assert ok.status_code == 200, ok.text


def test_마지막_시스템_관리자는_정지할_수_없다(client: TestClient, admin: Signed) -> None:
    """잃으면 복구 경로가 서버 콘솔뿐이다. 그 상태는 실제로 일어난다."""
    summary = client.get("/api/accounts/summary", headers=admin.headers).json()
    if summary["active_system_admins"] != 1:
        return  # 다른 시험이 만든 관리자가 남아 있으면 이 시험의 전제가 아니다

    me = client.get("/api/auth/me", headers=admin.headers).json()
    blocked = client.post(f"/api/accounts/{me['id']}/suspend", headers=admin.headers)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "TSC-ACCOUNTS-0005"


def test_없는_엔드포인트도_같은_봉투로_답한다(client: TestClient) -> None:
    """프론트의 오류 파서는 봉투를 기대한다. 맨 detail 이 나가면 **오류를 읽다가
    오류가 나서** 화면에는 원인 대신 자바스크립트 예외가 뜬다."""
    response = client.get("/api/nope")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "TSC-COMMON-0404"
    # 요청 id 가 응답·로그·감사 기록을 잇는 끈이다.
    assert error["request_id"] and error["request_id"] != "-"


def test_인증_없이는_거절한다(client: TestClient) -> None:
    response = client.get("/api/equipment")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TSC-AUTH-0100"


def test_비밀번호를_바꾸면_기존_세션이_끊긴다(client: TestClient, admin: Signed) -> None:
    """바꾼 이유가 유출일 수 있다. 안 끊으면 훔친 세션이 그대로 산다."""
    changed = client.post(
        "/api/auth/change-password",
        json={"current_password": ADMIN_PASSWORD, "new_password": "another-password"},
        headers=admin.headers,
    )
    assert changed.status_code == 204, changed.text

    # 쿠키가 버려졌으므로 갱신도 안 된다.
    assert client.post("/api/auth/refresh").status_code == 401

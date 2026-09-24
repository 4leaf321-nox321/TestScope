"""API 시험이 쓰는 준비물.

**진짜 앱을 부른다.** 서비스 함수를 직접 부르면 라우터·의존성·권한 판정이 통째로
빠지는데, 실제로 깨지는 자리는 대개 거기다.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.auth import security
from app.modules.vocabulary.reference import ensure_reference_data
from app.modules.workspaces.models import Workspace, WorkspaceMember

ADMIN_PASSWORD = "test-admin-password"


@dataclass(frozen=True)
class Signed:
    """로그인한 사람. 헤더를 매번 손으로 만들지 않게 한다."""

    email: str
    token: str
    workspace: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


@pytest.fixture(scope="session", autouse=True)
def reference(schema: None) -> None:
    """온톨로지 축과 조건 정의.

    설치와 **같은 코드**로 심는다 — 시험이 자기 목록을 따로 들면 두 벌이 갈리고,
    그때 시험은 통과하는데 설치는 다른 축을 만든다.
    """
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        ensure_reference_data(db)
    finally:
        db.close()


@pytest.fixture
def workspace(db: Session) -> Workspace:
    row = Workspace(slug=f"team-{uuid.uuid4().hex[:8]}", name="시험팀")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture
def admin(client: TestClient, db: Session, workspace: Workspace) -> Signed:
    """시스템 관리자 한 명. 첫 관리자는 설치 시드처럼 직접 만든다."""
    email = f"admin-{uuid.uuid4().hex[:8]}@testscope.local"
    user = User(
        email=email,
        password_hash=security.hash_password(ADMIN_PASSWORD),
        display_name="관리자",
        status="active",
        is_system_admin=True,
        home_workspace_id=workspace.id,
    )
    db.add(user)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="manager"))
    db.commit()

    response = client.post(
        "/api/auth/login", json={"email": email, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return Signed(email=email, token=response.json()["access_token"], workspace=workspace.slug)


@pytest.fixture
def term_factory(client: TestClient, admin: Signed) -> Iterator[object]:
    """온톨로지 값을 만들어 id 를 돌려준다."""

    def make(axis: str, value: str) -> str:
        response = client.post(
            f"/api/vocabularies/{axis}/terms", json={"value": value}, headers=admin.headers
        )
        assert response.status_code == 201, response.text
        return str(response.json()["id"])

    yield make


@pytest.fixture
def condition_ids(client: TestClient, admin: Signed) -> dict[str, str]:
    """조건 키 -> id. 검색과 시험 항목 시험이 온도·하중을 이름으로 집는다."""
    response = client.get("/api/condition-keys", headers=admin.headers)
    assert response.status_code == 200, response.text
    return {row["key"]: row["id"] for row in response.json()}


def site_id(client: TestClient, admin: Signed) -> str:
    """거점 값 하나. **장비는 거점 없이 못 만든다** — 어디 있는지 모르는 장비는
    찾아도 소용이 없어서 비울 수 없게 했다(0008 마이그레이션).

    값은 없으면 만들고 있으면 그대로 쓴다 — 축이 열려 있어 같은 이름은 한 줄이다.
    """
    response = client.post(
        "/api/vocabularies/site/terms", json={"value": "본사"}, headers=admin.headers
    )
    if response.status_code == 201:
        return str(response.json()["id"])
    listed = client.get("/api/vocabularies/site/terms", headers=admin.headers)
    assert listed.status_code == 200, listed.text
    for row in listed.json():
        if row["value"] == "본사":
            return str(row["id"])
    raise AssertionError(f"거점 값을 만들 수 없습니다: {response.text}")


def category_id(client: TestClient, admin: Signed) -> str:
    """장비유형 값 하나.

    **기종을 안 고른 장비는 이것을 직접 가리켜야 한다** — 무슨 종류인지 모르는 장비는
    분류로 좁히는 모든 화면에서 통째로 빠지고, 빠진 줄은 아무도 못 찾는다.
    """
    response = client.post(
        "/api/vocabularies/equipment_category/terms",
        json={"value": "만능재료시험기"},
        headers=admin.headers,
    )
    if response.status_code == 201:
        return str(response.json()["id"])
    listed = client.get("/api/vocabularies/equipment_category/terms", headers=admin.headers)
    assert listed.status_code == 200, listed.text
    for row in listed.json():
        if row["value"] == "만능재료시험기":
            return str(row["id"])
    raise AssertionError(f"분류 값을 만들 수 없습니다: {response.text}")

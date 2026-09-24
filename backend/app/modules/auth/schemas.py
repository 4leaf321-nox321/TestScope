"""인증 API 의 요청·응답 형태.

이 파일이 프론트 타입의 원본이다 — OpenAPI 를 거쳐 schema.d.ts 가 생성된다.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.shared.schemas import Request


class LoginRequest(Request):
    email: str = Field(min_length=3, max_length=254)
    """EmailStr 을 쓰지 않는다.

    email-validator 는 .local 처럼 특수 용도로 예약된 도메인을 문법 단계에서
    거부하는데, 폐쇄망 사내 계정은 그런 주소를 쓰는 경우가 흔하다. 형식을 강하게
    검사해서 얻는 것보다 **로그인 자체가 성립하지 않는 손해**가 크다.
    """

    password: str = Field(min_length=1, max_length=200)


class WorkspaceMembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workspace_id: uuid.UUID
    slug: str
    name: str
    path: str
    """개발본부 / 재료시험팀. 부서 선택기가 이름만 보여 주면 같은 이름의 팀이
    본부마다 있을 때 어느 쪽인지 알 수 없다."""
    depth: int
    role: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    status: str
    is_system_admin: bool
    must_change_password: bool
    home_workspace_slug: str | None
    memberships: list[WorkspaceMembershipOut]


class LoginResponse(BaseModel):
    access_token: str
    expires_in: int
    """초 단위. 프론트가 만료 전에 갱신을 걸 수 있게 한다."""
    user: UserOut


class ProfileUpdateRequest(Request):
    """자기 정보 수정.

    **표시 이름만 바꾼다.** 아이디(email)는 로그인 식별자라 본인이 바꾸면 감사
    로그·알림이 가리키는 대상이 흔들린다 — 그것은 관리자의 일로 남긴다.
    """

    display_name: str = Field(min_length=1, max_length=100)


class ChangePasswordRequest(Request):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=1, max_length=200)
    """길이 하한을 두지 않는다.

    우리가 정한 숫자가 기관 규칙과 어긋나면 사람은 규칙을 지키는 대신 **우회할
    길을 찾는다**(스크립트로 직접 바꾸기 등) — 그 경로가 오히려 강제 변경을
    건너뛴다. 지키려던 것은 길이가 아니라 "이전과 다른 비밀번호" 검사와
    must_change_password 가 한다.
    """


class PatCreateRequest(Request):
    name: str = Field(min_length=1, max_length=100)
    """어디에 쓰는 토큰인지. **폐기할 때 이것만 보고 판단하게 된다** — 그리고
    감사 기록에 이 이름이 남는다."""
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)
    scopes: list[str] = Field(default_factory=lambda: ["read"])
    """이 토큰으로 할 수 있는 일: `read` · `equipment:write` · `catalog:write`.

    **안 주면 읽기뿐이다.** 기본값이 전권이면 「일단 만들고 나중에 좁히자」 가 되고,
    나중은 오지 않는다. MCP 로 카탈로그를 채울 토큰이라면 read 와 catalog:write
    둘만 주면 된다 — 계정 관리와 서버 설정은 어느 범위로도 안 열린다."""


class PatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    prefix: str
    scopes: list[str]
    """이 토큰으로 할 수 있는 일. **목록에서 보인다** — 폐기할지 판단하는 근거가
    이름과 이것뿐이다."""
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None


class PatCreateResponse(BaseModel):
    token: str
    """평문은 이 응답에서 한 번만 나온다. 다시 볼 수 없다."""
    pat: PatOut

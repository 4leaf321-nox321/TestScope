"""서버 화면의 응답 형태 — **지금 이 설치가 어떤 상태인가.**"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class DiskOut(BaseModel):
    path: str
    total_bytes: int
    free_bytes: int
    used_percent: float


class TableCountOut(BaseModel):
    label: str
    count: int


class ServerStatusOut(BaseModel):
    version: str
    app_env: str
    database_url_safe: str
    """비밀번호를 지운 접속 문자열. **어느 DB 를 보고 있는지**가 문제 추적의
    첫 물음인데, 개발과 운영이 같은 포트를 쓰면 그것을 알 방법이 없다."""
    schema_head: str | None
    schema_current: str | None
    schema_behind: bool
    """DB 가 코드보다 뒤처져 있나. **화면이 말해 주지 않으면** 사람은 그 사실을
    엉뚱한 화면의 500 으로 만난다."""
    disk: DiskOut | None
    counts: list[TableCountOut]
    started_at: datetime


class MaintenanceItemOut(BaseModel):
    """남은 일 하나. **홈이 이것을 보여 준다** — 관리 화면에 들어가야만 보이면
    아무도 안 본다."""

    key: str
    label: str
    count: int
    link: str | None
    severity: str
    """info · warning. 경고는 색이 붙는다."""


class CalibrationDueOut(BaseModel):
    equipment_id: str
    asset_no: str
    name: str
    next_due_on: date
    days_left: int
    """음수면 이미 지났다. **지난 것을 목록에서 빼지 않는다** — 빼면 만료된 장비가
    조용히 계속 쓰인다."""

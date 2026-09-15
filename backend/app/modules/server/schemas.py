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


class CatalogStateOut(BaseModel):
    """카탈로그 신선도 — 정본(파일)과 DB 에 반입된 시점이 같은가.

    **뒤졌으면 여기서 말한다.** 배포는 `source/catalog` 를 새로 놓지만 반입은 사람이
    돌리는 것이라, 안 돌리면 화면은 지난 카탈로그를 새 것처럼 보여 준다.
    """

    available: bool
    """이 설치에 정본 파일이 있나. 없으면 반입 자체가 불가능한 설치다."""
    digest: str | None
    objects: int | None
    """정본의 객체(계열 JSON) 수."""
    imported_at: datetime | None
    imported_digest: str | None
    imported_objects: int | None
    never: bool
    """한 번도 반입하지 않았다."""
    behind: bool
    """정본과 반입 시점의 지문이 다르다. 며칠 뒤졌는지는 모른다 — 정본에 날짜가 없다."""


class SemanticStateOut(BaseModel):
    """의미 검색 부품 셋(엔진·확장·표)이 어디까지 있나. 없는 것은 고장이 아니라 설정이다."""

    backend: str
    """off · mock · ollama"""
    engine_ready: bool
    engine_note: str | None
    extension: bool
    """pgvector 가 이 DB 에 켜져 있나."""
    table: bool
    chunks: int
    kinds: dict[str, int]


class JobsStateOut(BaseModel):
    """작업 큐 — 상태별 수. `failed` 가 있으면 사람이 봐야 한다."""

    queued: int
    running: int
    done: int
    failed: int


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
    catalog: CatalogStateOut
    semantic: SemanticStateOut
    jobs: JobsStateOut


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

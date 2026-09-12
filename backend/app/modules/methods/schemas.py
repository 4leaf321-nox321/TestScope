"""시험법 API 의 요청·응답 형태."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RequirementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    condition_key_id: uuid.UUID
    condition_key: str
    condition_label: str
    si_unit: str
    display_unit: str
    """**값과 단위를 함께 준다.** 숫자만 주면 화면이 조건 정의를 또 조회해야 하고,
    그 조회를 빠뜨린 화면은 20 이 N 인지 kN 인지 모른 채 그린다."""
    min_value: float | None
    max_value: float | None
    text_value: str | None
    is_mandatory: bool
    note: str | None


class CitedSeriesOut(BaseModel):
    """이 규격을 인용한 계열 하나. `pending` 이면 어느 시험 항목의 것인지 아직 안 정해졌다."""

    series_id: uuid.UUID
    series_name: str
    test_item: str | None
    pending: bool


class MethodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    edition: str | None
    title: str
    test_item: str | None
    test_item_term_id: uuid.UUID | None
    body: str | None
    status: str
    superseded_by_code: str | None
    """무엇으로 대체됐나. **끊어 두면 옛 판을 보던 사람이 다음 판을 못 찾는다.**"""
    summary: str | None
    workspace_slug: str | None
    equipment_count: int
    """이 시험법을 할 수 있다고 등록된 장비 수. 0 이면 그 규격은 **지금 우리가
    못 하는 시험**이다 — 그 사실이 목록에 보여야 한다."""
    series_count: int
    """이 규격을 시험 항목에 이어 둔 카탈로그 계열 수 — 「사면 되는 것」 의 수."""
    pending_series_count: int
    """인용은 했는데 어느 시험 항목의 규격인지 안 정해져 못 이어진 계열 수. 0 이 아니면
    「못 하는 시험」 이 아니라 **끊긴 연결**이다 — 시험 항목을 정하면 붙는다."""
    cited_series: list[CitedSeriesOut] = []
    """상세에서만 채운다 — 목록에서 계열까지 실으면 한 쪽이 커진다."""
    requirements: list[RequirementOut]
    created_at: datetime
    can_edit: bool


class MethodCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    edition: str | None = Field(default=None, max_length=30)
    title: str = Field(min_length=1, max_length=300)
    test_item_term_id: uuid.UUID | None = None
    body_term_id: uuid.UUID | None = None
    summary: str | None = None
    workspace_slug: str | None = None
    """비우면 전사 공용 — 공개 규격은 대개 이쪽이다."""


class MethodUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    edition: str | None = None
    test_item_term_id: uuid.UUID | None = None
    body_term_id: uuid.UUID | None = None
    summary: str | None = None
    status: str | None = Field(default=None, pattern="^(draft|active|superseded)$")
    superseded_by_id: uuid.UUID | None = None


class RequirementUpsertRequest(BaseModel):
    """요구 조건 하나를 넣거나 고친다. 같은 조건이 이미 있으면 덮어쓴다.

    **한쪽을 비울 수 있다.** 20 kN 이상은 min 만 있고 max 가 없다 — 0 으로 채우면
    상한이 0 인 것과 구별되지 않는다.
    """

    condition_key_id: uuid.UUID
    min_value: float | None = None
    max_value: float | None = None
    text_value: str | None = Field(default=None, max_length=200)
    is_mandatory: bool = True
    note: str | None = None


class RequirementImportRequest(BaseModel):
    """엑셀에서 복사해 붙여넣은 요구 조건 표. **머리글 줄까지 함께.** 파일이 아닌 이유는
    장비 대장 반입과 같다 — DRM 이 파일은 막고 붙여넣기는 못 막는다."""

    text: str


class RequirementImportRow(BaseModel):
    """붙여넣은 한 줄이 어떻게 읽혔나. 줄 번호는 머리글 다음이 2 — 엑셀과 같다."""

    line: int
    cells: dict[str, str]
    method_id: uuid.UUID | None
    code: str | None
    """서버가 찾은 규격의 표기 — 「JIS K7210」 이라 적어도 「JIS K 7210」 으로 잡힌다."""
    condition_label: str | None
    problems: list[str]
    replaces: bool
    """같은 규격·조건이 이미 있어 **덮어쓴다.** 미리보기가 그 사실을 말해야 한다 —
    조용히 덮으면 누가 언제 적은 값이 사라졌는지 아무도 모른다."""
    imported: bool = False


class RequirementImportSummary(BaseModel):
    total: int
    ready: int
    problems: int
    created: int
    replaced: int


class RequirementImportResult(BaseModel):
    """`dry_run` 이면 `created`·`replaced` 는 0 이고 판정만 들어 있다. 넣기로 한 것은
    전부 되거나 전부 안 되거나다."""

    dry_run: bool
    summary: RequirementImportSummary
    rows: list[RequirementImportRow]

"""온톨로지 허브의 응답 — 객체 종류 하나가 한 줄."""

from __future__ import annotations

from pydantic import BaseModel


class ObjectKindOut(BaseModel):
    key: str
    label: str
    layer: str
    """catalog(전사 공용 객체) · vocabulary(이름 사전) · operations(부서가 적는 것)."""
    storage: str
    """table(자기 표) · vocabulary(온톨로지 축의 값)."""
    count: int
    """지금 몇 건인가. 지운 것은 빼고."""
    fixed_fields: list[str]
    """코드에 박힌 칸 — 화면에서 못 더하고 못 뺀다."""
    defined_kind: str | None
    """관리자가 정의해 더하는 칸의 종류 — 검색 조건 · 사양 · 속성 · 값의 칸. 없으면 None."""
    defined_count: int
    """정의된 칸(정식) 수."""
    draft_count: int
    """초안 수 — 속성이 있는 대상만. 누가 새 이름으로 적어 둔 것."""
    list_path: str
    """목록 화면 주소."""
    define_path: str | None
    """칸을 정의하는 화면 주소."""
    note: str
    """이 종류를 한 줄로 — 무엇이고 누가 만드나."""

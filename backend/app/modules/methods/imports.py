"""규격 요구 조건 표 반입 — **규격서를 보고 적은 표를 통째로 받는다.**

검색 사슬의 둘째 칸이다:

    시험 항목 -> **요구 조건** -> 시험법 -> 가능한 장비 -> 보유 위치

요구 조건은 「이 규격대로 시험하려면 장비가 최소한 이래야 한다」 는 숫자다(ISO 6892-1:
하중 20 kN 이상, 10~35 °C). 있으면 검색에서 규격을 고르는 순간 그 숫자가 조건 칸에 들어가고,
없으면 사람이 규격서를 펴 놓고 옮겨 적는다 — 그 옮겨 적기에서 자릿수가 틀린다.

## 왜 표인가

규격 464 중 3 에만 조건이 있다. 나머지는 상세 화면에서 한 줄씩 넣게 되어 있는데, 규격서를
펴 놓고 한 화면씩 오가며 넣는 일은 아무도 안 한다. 규격서를 보는 사람은 엑셀에 적고, 그
표를 붙여넣는다 — 장비 대장 반입(`equipment.imports`)과 같은 모양이라 같은 규칙을 따른다:
붙여넣기(파일이 아니다 — DRM) · 두 걸음(미리보기 → 넣기) · 넣을 수 있는 줄은 넣는다 ·
넣기로 한 것은 전부 되거나 전부 안 되거나.

## 값은 지어내지 않는다

이 반입은 사람이 규격서를 보고 적은 것을 받는 길이다. 틀린 조건은 빈 조건보다 나쁘다 —
검색이 **자신 있게 틀린 답**을 낸다. 그래서 여기에는 기본값이 없고, 규격·조건이 하나로
안 잡히면 고르지 않고 거절한다(ADR 0003).
"""

from __future__ import annotations

import csv
import io
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.methods.models import MethodRequirement, TestMethod
from app.modules.methods.schemas import (
    RequirementImportResult,
    RequirementImportRow,
    RequirementImportSummary,
)
from app.modules.methods.services import _can_edit, visible
from app.modules.vocabulary.models import ConditionKey
from app.shared import audit
from app.shared.errors import AppError
from app.shared.text import clean, compare_key, method_key

MAX_ROWS = 2000
MAX_CHARS = 2_000_000

#: 열 이름과 별칭. 엑셀에서 사람이 손으로 적은 머리글을 받는다.
COLUMNS: dict[str, tuple[str, ...]] = {
    "code": ("규격", "규격 번호", "규격번호", "시험법", "code"),
    "edition": ("판", "연도", "edition"),
    "condition": ("조건", "조건 항목", "condition"),
    "min": ("최소", "하한", "min"),
    "max": ("최대", "상한", "max"),
    "text": ("값", "선택값", "text"),
    "mandatory": ("필수", "필수여부", "mandatory"),
    "note": ("비고", "근거", "note"),
}
REQUIRED = ("code", "condition")

YES = {"y", "yes", "예", "o", "ㅇ", "true", "1", "필수"}
NO = {"n", "no", "아니오", "아니요", "x", "false", "0", "권고"}

TEMPLATE_HEADER = [names[0] for names in COLUMNS.values()]
#: 보기 줄. **실제 규격의 값**이다 — 지어낸 숫자를 서식에 넣으면 그대로 들어온다.
TEMPLATE_SAMPLE = [
    ["ISO 6892-1", "", "하중 용량", "20", "", "", "예", "시험기 등급 ISO 7500-1 1급"],
    ["ISO 6892-1", "", "시험 온도", "10", "35", "", "예", "10.1 시험 온도"],
]

_NUMBER = re.compile(r"^[-+]?\d+(?:[.,]\d+)?")


def columns() -> list[dict[str, Any]]:
    return [
        {"key": key, "label": names[0], "required": key in REQUIRED, "aliases": list(names)}
        for key, names in COLUMNS.items()
    ]


def template_csv() -> str:
    """BOM 을 붙인다 — 안 붙이면 엑셀이 한글을 깨뜨리고 사람은 서식이 잘못된 줄 안다."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(TEMPLATE_HEADER)
    for row in TEMPLATE_SAMPLE:
        writer.writerow(row)
    return "﻿" + buffer.getvalue()


def _delimiter(first: str) -> str:
    return "\t" if "\t" in first else ","


def _header_map(fields: Sequence[str] | None) -> dict[str, str]:
    if not fields:
        raise AppError("TSC-IMPORT-0002", "머리글 줄이 없습니다.", status=400)
    known: dict[str, str] = {}
    for field, names in COLUMNS.items():
        for name in names:
            known[name.replace(" ", "").lower()] = field
    found: dict[str, str] = {}
    for raw in fields:
        key = (raw or "").replace(" ", "").replace("﻿", "").lower()
        if key in known:
            found[known[key]] = raw
    missing = [COLUMNS[one][0] for one in REQUIRED if one not in found]
    if missing:
        raise AppError(
            "TSC-IMPORT-0003",
            f"머리글에 다음 열이 없습니다: {' · '.join(missing)}. "
            f"엑셀에서 **머리글 줄까지 함께** 복사했는지 보십시오.",
            status=400,
            details={"missing": missing},
        )
    return found


@dataclass
class _Picked:
    """한 줄이 가리키는 것. 문제가 있으면 `problems` 에 남고 넣지 않는다."""

    method: TestMethod | None = None
    key: ConditionKey | None = None
    min_value: float | None = None
    max_value: float | None = None
    text_value: str | None = None
    is_mandatory: bool = True
    note: str | None = None
    replaces: bool = False

    def __post_init__(self) -> None:
        self.problems: list[str] = []


def _unit_key(unit: str) -> str:
    """단위 비교키. 사람은 「°C」 「℃」 로 적고 조건 정의는 「degC」 다 — 같은 것이다."""
    return compare_key(unit).replace(" ", "").replace("℃", "degc").replace("°", "deg")


def _number(raw: str, unit: str, field: str, picked: _Picked) -> float | None:
    """「20」 도 「20 kN」 도 받는다 — 단위가 그 조건의 것이면. 다른 단위면 거절한다:
    N 으로 적은 20 을 kN 으로 들이면 검색이 천 배 틀린다."""
    text = clean(raw)
    if not text:
        return None
    match = _NUMBER.match(text)
    if match is None:
        picked.problems.append(f"{COLUMNS[field][0]}: 숫자가 아닙니다 ({text})")
        return None
    rest = text[match.end() :].strip()
    if rest and _unit_key(rest) != _unit_key(unit):
        picked.problems.append(
            f"{COLUMNS[field][0]}: 단위가 조건의 단위({unit or '없음'})와 다릅니다 ({text})"
        )
        return None
    return float(match.group(0).replace(",", "."))


def _flag(raw: str, picked: _Picked) -> bool:
    text = compare_key(raw)
    if not text:
        return True  # 규격이 적은 숫자는 기본이 필수다.
    if text in YES:
        return True
    if text in NO:
        return False
    picked.problems.append(f"필수: 예/아니오로 적으십시오 ({clean(raw)})")
    return True


class _Lookup:
    """규격과 조건을 **한 번에** 찾아 둔다. 줄마다 물으면 2000줄이 질의 4000회다."""

    def __init__(self, db: Session, user: User) -> None:
        self.methods: dict[str, list[TestMethod]] = {}
        for row in db.scalars(visible(db, user)):
            self.methods.setdefault(method_key(row.code), []).append(row)
        self.keys: dict[str, ConditionKey] = {}
        for key in db.scalars(select(ConditionKey)):
            self.keys[compare_key(key.key)] = key
            self.keys[compare_key(key.label)] = key

    def method(self, code: str, edition: str, picked: _Picked) -> TestMethod | None:
        rows = self.methods.get(method_key(code), [])
        if edition:
            rows = [
                one for one in rows if compare_key(one.edition or "") == compare_key(edition)
            ]
        if not rows:
            picked.problems.append(
                f"규격: 등록된 규격이 아닙니다 ({code}{' ' + edition if edition else ''})"
            )
            return None
        if len(rows) > 1:
            # 판이 여럿이면 현행 하나가 있을 때만 그것으로. 아니면 사람이 판을 적어야 한다.
            current = [one for one in rows if one.status != "superseded"]
            if len(current) == 1:
                return current[0]
            picked.problems.append(
                "규격: 판이 여럿입니다 "
                f"({' · '.join(one.edition or '?' for one in rows)}) — 판 열에 적으십시오"
            )
            return None
        return rows[0]

    def key(self, name: str, picked: _Picked) -> ConditionKey | None:
        found = self.keys.get(compare_key(name))
        if found is None:
            picked.problems.append(
                f"조건: 조건 정의에 없습니다 ({name}) — "
                "온톨로지의 조건 이름(하중 용량·시험 온도 …)으로 적으십시오"
            )
        return found


def run(db: Session, user: User, text: str, *, dry_run: bool) -> RequirementImportResult:
    if len(text) > MAX_CHARS:
        raise AppError(
            "TSC-IMPORT-0004",
            f"붙여넣은 내용이 너무 깁니다 ({len(text) // 1024}천 자). 나눠 올리십시오.",
            status=400,
        )
    body = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n").lstrip("﻿")
    if not body.strip():
        raise AppError(
            "TSC-IMPORT-0006",
            "붙여넣은 내용이 없습니다. 엑셀에서 **머리글 줄까지 함께** 복사하십시오.",
            status=400,
        )
    reader = csv.DictReader(io.StringIO(body), delimiter=_delimiter(body.split("\n", 1)[0]))
    header = _header_map(reader.fieldnames)

    picked_rows: list[tuple[int, dict[str, str]]] = []
    for index, values in enumerate(reader, start=2):
        if len(picked_rows) >= MAX_ROWS:
            raise AppError(
                "TSC-IMPORT-0005",
                f"한 번에 {MAX_ROWS}줄까지 받습니다. 나눠 붙여넣으십시오.",
                status=400,
            )
        cells = {field: (values.get(column) or "") for field, column in header.items()}
        if not any(clean(one) for one in cells.values()):
            continue
        picked_rows.append((index, cells))

    look = _Lookup(db, user)
    editable: dict[uuid.UUID, bool] = {}
    rows: list[RequirementImportRow] = []
    ready: list[tuple[_Picked, int]] = []
    # 붙여넣은 것 안의 중복 — 같은 규격·조건이 두 줄이면 어느 쪽이 맞는지 모른다.
    seen: dict[tuple[uuid.UUID, uuid.UUID], int] = {}

    for index, cells in picked_rows:
        picked = _Picked()
        code = clean(cells.get("code", ""))
        condition = clean(cells.get("condition", ""))
        if not code:
            picked.problems.append("규격: 비어 있습니다")
        if not condition:
            picked.problems.append("조건: 비어 있습니다")
        if code:
            picked.method = look.method(code, clean(cells.get("edition", "")), picked)
        if condition:
            picked.key = look.key(condition, picked)
        if picked.method is not None:
            if picked.method.id not in editable:
                editable[picked.method.id] = _can_edit(db, user, picked.method)
            if not editable[picked.method.id]:
                picked.problems.append("규격: 이 규격을 고칠 권한이 없습니다")
        if picked.key is not None:
            unit = picked.key.display_unit or picked.key.si_unit
            if picked.key.kind == "choice":
                picked.text_value = clean(cells.get("text", "")) or None
                if picked.text_value is None:
                    picked.problems.append("값: 고르는 조건은 「값」 열에 적습니다")
                elif picked.key.choices and picked.text_value not in picked.key.choices:
                    picked.problems.append(
                        f"값: 고를 수 있는 값이 아닙니다 ({' · '.join(picked.key.choices)})"
                    )
            else:
                picked.min_value = _number(cells.get("min", ""), unit, "min", picked)
                picked.max_value = _number(cells.get("max", ""), unit, "max", picked)
                if (
                    picked.min_value is None
                    and picked.max_value is None
                    and not picked.problems
                ):
                    picked.problems.append(
                        "최소·최대: 둘 다 비어 있습니다 — 하나는 적으십시오"
                    )
                if (
                    picked.min_value is not None
                    and picked.max_value is not None
                    and picked.min_value > picked.max_value
                ):
                    picked.problems.append("최소·최대: 최소가 최대보다 큽니다")
        picked.is_mandatory = _flag(cells.get("mandatory", ""), picked)
        picked.note = clean(cells.get("note", "")) or None

        if picked.method is not None and picked.key is not None:
            pair = (picked.method.id, picked.key.id)
            if pair in seen:
                picked.problems.append(f"{seen[pair]}번째 줄과 같은 규격·조건입니다")
            else:
                seen[pair] = index
                picked.replaces = (
                    db.scalar(
                        select(MethodRequirement.id).where(
                            MethodRequirement.method_id == picked.method.id,
                            MethodRequirement.condition_key_id == picked.key.id,
                        )
                    )
                    is not None
                )

        rows.append(
            RequirementImportRow(
                line=index,
                cells={field: (cells.get(field) or "").strip() for field in COLUMNS},
                method_id=picked.method.id if picked.method else None,
                code=picked.method.code if picked.method else None,
                condition_label=picked.key.label if picked.key else None,
                problems=picked.problems,
                replaces=picked.replaces,
            )
        )
        if not picked.problems:
            ready.append((picked, len(rows) - 1))

    summary = RequirementImportSummary(
        total=len(rows),
        ready=len(ready),
        problems=len(rows) - len(ready),
        created=0,
        replaced=0,
    )
    if dry_run or not ready:
        return RequirementImportResult(dry_run=dry_run, summary=summary, rows=rows)

    # **넣기로 한 것은 전부 되거나 전부 안 되거나.**
    for picked, position in ready:
        assert picked.method is not None and picked.key is not None
        existing = db.scalar(
            select(MethodRequirement).where(
                MethodRequirement.method_id == picked.method.id,
                MethodRequirement.condition_key_id == picked.key.id,
            )
        )
        target = existing or MethodRequirement(
            method_id=picked.method.id, condition_key_id=picked.key.id
        )
        target.min_value = picked.min_value
        target.max_value = picked.max_value
        target.text_value = picked.text_value
        target.is_mandatory = picked.is_mandatory
        target.note = picked.note
        if existing is None:
            db.add(target)
            summary.created += 1
        else:
            summary.replaced += 1
        rows[position].imported = True
    audit.record(
        db,
        action=audit.METHOD_REQUIREMENTS_IMPORTED,
        actor=user,
        target_table="method_requirements",
        target_id=None,
        target_label=f"요구 조건 표 {len(rows)}줄",
        changes={"created": summary.created, "replaced": summary.replaced, "rows": len(rows)},
    )
    db.commit()
    return RequirementImportResult(dry_run=False, summary=summary, rows=rows)

"""보유 장비 **일괄 반입** — 부서가 들고 오는 대장을 그대로 받는다.

## 왜 있나

카탈로그는 198계열·714기종까지 찼는데 대장은 4대였다. 장비를 넣는 길이 화면에서
한 대씩뿐이라, 수백 대를 가진 부서는 시작조차 못 한다 — 그리고 대장이 비어 있으면
이 시스템은 **어떤 질문에도 못 답한다.** 카탈로그를 아무리 잘 만들어도 그렇다.

## 두 걸음이다: 미리 보고, 그 다음에 넣는다

`dry_run` 이면 아무것도 저장하지 않고 줄마다 판정만 돌려준다. 300줄짜리 대장에서
틀린 12줄을 **넣기 전에** 알아야 하고, 그 12줄이 어느 줄인지 파일의 줄 번호로
말해 줘야 사람이 엑셀에서 찾을 수 있다.

## 전부 되거나 전부 안 되거나

한 줄이라도 틀리면 아무것도 안 넣는다. 되는 것만 넣으면 사람은 파일을 고쳐 다시
올리다가 이미 들어간 288줄에서 「이미 등록된 자산번호」 를 만나고, 그때 무엇을
지워야 할지 모른다. 반쯤 들어간 대장은 안 들어간 대장보다 나쁘다.

## 이름으로 받고, 못 정하면 거절한다

사람은 UUID 를 모른다. 부서·거점·분류·기종을 이름으로 받되, 후보가 여럿이면
**고르지 않는다** — 여기서 첫 줄을 집으면 그 선택은 아무 데도 안 남고, 틀렸을 때
찾을 방법이 없다(ADR 0003). 대신 후보를 돌려주고 사람이 파일에서 고치게 한다.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.equipment import services
from app.modules.equipment.models import EQUIPMENT_STATUSES, Equipment
from app.modules.equipment.schemas import (
    EquipmentImportResult,
    EquipmentImportRow,
)
from app.modules.resolve.services import resolve
from app.modules.vocabulary.models import Vocabulary, VocabularyTerm
from app.modules.workspaces.models import Workspace
from app.shared.errors import AppError
from app.shared.text import clean

#: 한 번에 받는 줄 수. 넘으면 나눠 올리라고 말한다.
#:
#: 상한이 없으면 실수로 올린 10만 줄짜리 파일이 트랜잭션 하나를 몇 분 잡고, 그동안
#: 다른 사람의 등록이 막힌다. 부서 하나의 대장은 이 수를 거의 안 넘는다.
MAX_ROWS = 2000

#: 파일 크기 상한. 줄 수 상한과 따로 둔다 — 줄을 세려면 먼저 다 읽어야 하고,
#: 읽는 동안 메모리를 쓰는 것은 파일 크기 쪽이다.
MAX_BYTES = 4 * 1024 * 1024

#: 열 이름과 그 별칭. **엑셀에서 사람이 손으로 적은 머리글**을 받는다 — 띄어쓰기와
#: 영문 이름을 함께 받아 두지 않으면, 한 글자 다른 머리글 하나로 파일 전체가 거절된다.
COLUMNS: dict[str, tuple[str, ...]] = {
    "asset_no": ("자산번호", "자산 번호", "관리번호", "asset_no"),
    "name": ("장비명", "장비 이름", "이름", "name"),
    "workspace": ("보유부서", "보유 부서", "부서", "workspace"),
    "site": ("거점", "보유거점", "보유 거점", "site"),
    "location": ("설치위치", "설치 위치", "위치", "location"),
    "dept_asset_no": ("부서관리번호", "부서 관리번호", "dept_asset_no"),
    "model": ("기종", "기종명", "model"),
    "category": ("장비유형", "장비 유형", "분류", "category"),
    "maker_text": ("제조사", "maker"),
    "model_text": ("모델명", "모델", "model_text"),
    "serial_no": ("제조번호", "시리얼", "serial_no"),
    "shared_use": ("공용여부", "공용 여부", "공용", "shared_use"),
    "status": ("상태", "status"),
    "acquired_on": ("도입일", "취득일", "acquired_on"),
    "manufactured_year": ("제조연도", "제조 연도", "manufactured_year"),
    "calibration_required": ("교정대상", "교정 대상", "calibration_required"),
    "calibration_interval_months": (
        "교정주기",
        "교정 주기",
        "교정주기(개월)",
        "calibration_interval_months",
    ),
    "note": ("비고", "note"),
}

#: 없으면 그 줄을 못 넣는 칸. 전부 「없으면 그 장비를 못 찾는」 것들이다.
REQUIRED = ("asset_no", "name", "workspace", "site", "location")

#: 상태를 사람 말로도 받는다. 화면이 쓰는 라벨과 같아야 한다
#: (`frontend/src/modules/equipment/status.ts`).
STATUS_WORDS: dict[str, str] = {
    "입고": "incoming",
    "가동": "operational",
    "유휴": "idle",
    "점검": "maintenance",
    "점검·교정": "maintenance",
    "점검교정": "maintenance",
    "교정중": "maintenance",
    "수리": "repair",
    "고장": "repair",
    "폐기": "retired",
}

#: 예·아니오를 받는 말들. 엑셀에서 오는 모양이 제각각이다.
YES = {"y", "yes", "예", "o", "ㅇ", "true", "1", "공용", "대상", "필요"}
NO = {"n", "no", "아니오", "아니요", "x", "false", "0", "전용", "비대상", "불필요"}

#: 내려받는 서식의 머리글. **첫 이름을 쓴다** — 별칭은 받아 주되 우리가 권하는 것은
#: 하나여야 한다.
TEMPLATE_HEADER = [names[0] for names in COLUMNS.values()]

#: 서식에 넣는 보기 한 줄. 빈 서식만 주면 「공용여부에 뭘 적나」 를 사람이 물어야 한다.
TEMPLATE_SAMPLE = [
    "UTM-001",
    "3동 만능기",
    "재료시험팀",
    "본사",
    "3동 201호",
    "",
    "68FM-300",
    "",
    "",
    "",
    "SN-12345",
    "예",
    "가동",
    "2024-03-15",
    "2023",
    "예",
    "12",
    "",
]


def template_csv() -> str:
    """내려받을 서식. **BOM 을 붙인다** — 안 붙이면 엑셀이 UTF-8 을 못 알아보고
    한글이 깨져서, 사람은 서식이 잘못된 줄 안다."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(TEMPLATE_HEADER)
    writer.writerow(TEMPLATE_SAMPLE)
    return "﻿" + buffer.getvalue()


def _decoded(raw: bytes) -> str:
    """엑셀이 뱉는 인코딩을 순서대로 시도한다.

    「CSV(쉼표 분리)」 로 저장하면 한국어 윈도우 엑셀은 **cp949** 로 쓴다. UTF-8 만
    받으면 그 파일은 통째로 거절되고, 사람은 무엇이 문제인지 알 수 없다.
    """
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise AppError(
        "TSC-IMPORT-0001",
        "파일의 글자를 읽을 수 없습니다. 엑셀에서 「CSV UTF-8」 로 저장해 보세요.",
        status=400,
    )


def _header_map(fields: Sequence[str] | None) -> dict[str, str]:
    """파일의 머리글을 우리 칸 이름에 맞춘다. 띄어쓰기와 대소문자는 무시한다."""
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
            f"서식을 내려받아 그 머리글을 쓰세요.",
            status=400,
            details={"missing": missing},
        )
    return found


def _flag(text: str, field: str, problems: list[str]) -> bool | None:
    if not text:
        return None
    word = text.strip().lower()
    if word in YES:
        return True
    if word in NO:
        return False
    problems.append(f"{field}: 「{text}」 는 예/아니오로 읽을 수 없습니다")
    return None


def _date(text: str, field: str, problems: list[str]) -> date | None:
    if not text:
        return None
    body = text.strip().replace("/", "-").replace(".", "-")
    if body.isdigit() and len(body) == 8:
        body = f"{body[:4]}-{body[4:6]}-{body[6:]}"
    try:
        return date.fromisoformat(body)
    except ValueError:
        problems.append(f"{field}: 「{text}」 는 날짜가 아닙니다 (2024-03-15 처럼)")
        return None


def _int(text: str, field: str, problems: list[str]) -> int | None:
    if not text:
        return None
    try:
        return int(float(text.strip()))
    except ValueError:
        problems.append(f"{field}: 「{text}」 는 숫자가 아닙니다")
        return None


def _workspace(db: Session, user: User, text: str, problems: list[str]) -> str | None:
    """부서를 **이름이나 slug 로** 찾고, **여기서 권한까지 본다.**

    미리보기가 권한을 안 보면 「300줄 다 됩니다」 라고 해 놓고 저장에서 12줄이 403 으로
    터진다 — 그리고 전부 되돌아간다. 그 한 번으로 사람은 미리보기를 두 번 다시
    안 믿는다. **미리보기가 통과시킨 것은 저장도 통과해야 한다.**
    """
    body = clean(text)
    row = db.scalar(
        select(Workspace).where((Workspace.name == body) | (Workspace.slug == body))
    )
    if row is None:
        problems.append(f"보유부서: 「{text}」 를 찾을 수 없습니다")
        return None
    try:
        services.owner_workspace(db, user, row.slug)
    except AppError as error:
        problems.append(f"보유부서: {error.message}")
        return None
    return str(row.slug)


def _term(db: Session, axis: str, text: str, field: str, problems: list[str]) -> Any:
    """축의 값 하나를 이름으로 찾는다. **없으면 만들지 않는다.**

    반입이 값을 만들면 오타가 그대로 기준정보가 되고, 「본사」 와 「본사 」 가 서로
    다른 거점이 된다 — 그 둘은 나중에 합칠 방법이 없다.
    """
    body = clean(text)
    if not body:
        return None
    vocabulary = db.scalar(select(Vocabulary).where(Vocabulary.slug == axis))
    if vocabulary is None:
        return None
    rows = list(
        db.scalars(
            select(VocabularyTerm).where(
                VocabularyTerm.vocabulary_id == vocabulary.id,
                VocabularyTerm.value.ilike(body),
            )
        )
    )
    if len(rows) == 1:
        return rows[0].id
    if not rows:
        problems.append(
            f"{field}: 「{text}」 가 기준정보에 없습니다. 기준정보에서 먼저 만드세요"
        )
    else:
        problems.append(f"{field}: 「{text}」 가 여럿입니다 ({len(rows)}개)")
    return None


def _model(db: Session, text: str, problems: list[str]) -> Any:
    """기종을 이름으로 잇는다. **못 정하면 잇지 않는다.**

    비슷한 기종에 끼워 넣으면 그 장비의 하중·온도가 남의 것이 되고, 검색은 그
    남의 수치로 「됩니다」 라고 답한다.
    """
    body = clean(text)
    if not body:
        return None
    answer = resolve(db, {"kind": "model", "text": body, "limit": 5})
    if answer.match == "exact" and answer.id is not None:
        return answer.id
    # **후보를 계열까지 붙여 보여 준다.** 같은 이름의 기종이 두 계열에 있으면
    # 이름만으로는 「Instron 5982 · Instron 5982」 가 되어 고를 수가 없다 — 그러면
    # 그 목록은 없느니만 못하다.
    names = " · ".join(
        one.label + (f"({one.detail})" if one.detail else "") for one in answer.candidates[:3]
    )
    problems.append(
        f"기종: 「{text}」 을(를) 하나로 정할 수 없습니다"
        + (f" (비슷한 것: {names})" if names else " (카탈로그에 없습니다)")
    )
    return None


def _row_payload(
    db: Session, user: User, values: dict[str, str], problems: list[str]
) -> dict[str, Any]:
    """한 줄을 등록 요청의 모양으로. 문제는 모아서 돌려준다 — 첫 오류에서 멈추면
    사람이 파일을 고치고 올리기를 오류 수만큼 되풀이한다."""
    for field in REQUIRED:
        if not clean(values.get(field, "")):
            problems.append(f"{COLUMNS[field][0]}: 비어 있습니다")

    model_id = _model(db, values.get("model", ""), problems)
    category_term_id = _term(
        db, "equipment_category", values.get("category", ""), "장비유형", problems
    )
    if model_id is None and category_term_id is None and not values.get("model"):
        # 기종을 안 골랐으면 분류가 필수다 — 무슨 종류인지 모르는 장비는 검색에서
        # 통째로 빠진다.
        problems.append("장비유형: 기종을 안 적었으면 장비유형은 필수입니다")

    status_text = clean(values.get("status", ""))
    status = STATUS_WORDS.get(status_text, status_text) or "operational"
    if status not in EQUIPMENT_STATUSES:
        problems.append(f"상태: 「{status_text}」 는 모르는 상태입니다")
        status = "operational"

    shared = _flag(values.get("shared_use", ""), "공용여부", problems)
    calibrated = _flag(values.get("calibration_required", ""), "교정대상", problems)
    months = _int(values.get("calibration_interval_months", ""), "교정주기", problems)
    if calibrated and months is None:
        # 주기가 없으면 차기일을 계산할 수 없고, 그러면 「곧 만료」 목록이 이 장비를
        # 영원히 안 부른다.
        problems.append("교정주기: 교정 대상이면 주기(개월)를 적어야 합니다")

    return {
        "asset_no": clean(values.get("asset_no", "")),
        "name": clean(values.get("name", "")),
        "dept_asset_no": clean(values.get("dept_asset_no", "")) or None,
        "workspace_slug": _workspace(db, user, values.get("workspace", ""), problems),
        "site_term_id": _term(db, "site", values.get("site", ""), "거점", problems),
        "location": clean(values.get("location", "")),
        "model_id": model_id,
        "category_term_id": category_term_id,
        "maker_text": clean(values.get("maker_text", "")) or None,
        "model_text": clean(values.get("model_text", "")) or None,
        "serial_no": clean(values.get("serial_no", "")) or None,
        "shared_use": bool(shared),
        "status": status,
        "acquired_on": _date(values.get("acquired_on", ""), "도입일", problems),
        "manufactured_year": _int(values.get("manufactured_year", ""), "제조연도", problems),
        "calibration_required": bool(calibrated),
        "calibration_interval_months": months,
        "note": clean(values.get("note", "")) or None,
    }


def run(db: Session, user: User, raw: bytes, *, dry_run: bool) -> EquipmentImportResult:
    """대장 파일 하나를 읽어 판정하고, `dry_run` 이 아니면 넣는다."""
    if len(raw) > MAX_BYTES:
        raise AppError(
            "TSC-IMPORT-0004",
            f"파일이 너무 큽니다 ({len(raw) // 1024} KB). "
            f"{MAX_BYTES // 1024 // 1024} MB 아래로 나눠 올리세요.",
            status=400,
        )

    reader = csv.DictReader(io.StringIO(_decoded(raw)))
    header = _header_map(reader.fieldnames)

    rows: list[EquipmentImportRow] = []
    payloads: list[dict[str, Any]] = []
    # **파일 안의 중복도 잡는다.** DB 에 없더라도 같은 자산번호가 두 줄에 있으면
    # 둘째 줄에서 막히는데, 그때는 이미 첫 줄이 들어간 뒤다.
    seen: dict[str, int] = {}

    for index, values in enumerate(reader, start=2):  # 2 = 머리글 다음 줄
        if len(rows) >= MAX_ROWS:
            raise AppError(
                "TSC-IMPORT-0005",
                f"한 번에 {MAX_ROWS}줄까지 받습니다. 나눠 올리세요.",
                status=400,
            )
        picked = {field: (values.get(column) or "") for field, column in header.items()}
        if not any(clean(one) for one in picked.values()):
            continue  # 엑셀이 남긴 빈 줄

        problems: list[str] = []
        payload = _row_payload(db, user, picked, problems)

        asset_no = payload["asset_no"]
        if asset_no:
            if asset_no in seen:
                problems.append(f"자산번호: {seen[asset_no]}번째 줄과 겹칩니다")
            elif (
                db.scalar(select(Equipment).where(Equipment.asset_no == asset_no)) is not None
            ):
                problems.append("자산번호: 이미 등록된 장비입니다")
            else:
                seen[asset_no] = index

        rows.append(
            EquipmentImportRow(
                line=index,
                asset_no=asset_no or None,
                name=payload["name"] or None,
                model_linked=payload["model_id"] is not None,
                problems=problems,
            )
        )
        payloads.append(payload)

    ready = sum(1 for one in rows if not one.problems)
    result = EquipmentImportResult(
        total=len(rows),
        ready=ready,
        problems=len(rows) - ready,
        created=0,
        rows=rows,
    )
    if dry_run or result.problems or not rows:
        return result

    # **전부 되거나 전부 안 되거나.** 한 트랜잭션 안에서 넣고, 하나라도 막히면
    # 통째로 되돌린다.
    created = 0
    for row, payload in zip(rows, payloads, strict=True):
        try:
            services.create(db, user, payload, commit=False)
        except AppError as error:
            db.rollback()
            row.problems.append(error.message)
            result.problems = 1
            result.ready = len(rows) - 1
            result.created = 0
            return result
        created += 1
    db.commit()
    result.created = created
    return result

"""보유 장비 **일괄 반입** — 부서가 들고 오는 대장을 그대로 받는다.

## 왜 있나

카탈로그는 198계열·714기종까지 찼는데 대장은 4대였다. 장비를 넣는 길이 화면에서
한 대씩뿐이라, 수백 대를 가진 부서는 시작조차 못 한다 — 그리고 대장이 비어 있으면
이 시스템은 **어떤 질문에도 못 답한다.** 카탈로그를 아무리 잘 만들어도 그렇다.

## 파일이 아니라 **붙여넣기**로 받는다

문서 보안(DRM)이 걸린 환경에서는 파일을 올릴 수 없다. 실제로 그렇다 — 서식을
내려받는 것은 되는데 그 파일을 다시 고르는 것이 막힌다. 그래서 엑셀에서 **범위를
복사해 붙여넣는** 길을 쓴다. 붙여넣기는 DRM 이 막지 못한다.

엑셀이 클립보드에 넣는 것은 **탭으로 나뉜 글자**(TSV)이고, 우리가 내려주는 서식
파일은 쉼표(CSV)다. 둘 다 받는다 — 사람이 어느 쪽을 들고 올지 우리가 정할 수 없다.

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
import uuid
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
    ImportColumn,
    ImportProblem,
)
from app.modules.resolve.services import resolve
from app.modules.vocabulary.models import Vocabulary, VocabularyTerm
from app.modules.workspaces.models import Workspace
from app.shared.errors import AppError
from app.shared.text import clean

#: 한 번에 받는 줄 수. 넘으면 나눠 붙여넣으라고 말한다.
#:
#: **왜 상한이 있나 — 넣는 쪽이 줄당 10 질의이기 때문이다.** 실측으로 500줄에 2.5초고,
#: 2000줄이면 10초쯤이다. 그 대부분은 `services.create` 가 실제로 하는 일이라(중복
#: 확인·권한·삽입·계열의 시험 항목 복사) 줄일 자리가 별로 없다.
#:
#: 미리보기는 줄 수와 무관하게 질의 10회다(`Lookup`). 2000줄에 53ms — 여기는 상한이
#: 사실상 필요 없다. 상한을 정하는 것은 **넣는 쪽**이다.
#:
#: 이 수를 올리려면 먼저 재라. 웹 서버와 프록시의 응답 대기(대개 60초)를 넘기면
#: 사람은 「실패했다」 로 읽고 다시 붙여넣는데, 그때 앞의 것은 이미 들어가 있다.
MAX_ROWS = 2000

#: 붙여넣기 글자 수 상한. **줄 수를 세기 전에 막는 방어선**이다 — 줄을 세려면 먼저
#: 다 읽어야 하고, 읽는 동안 메모리를 쓰는 것은 글자 쪽이다.
#:
#: 2000줄에 열 18개면 50만 자쯤이라 넉넉하다. 진짜 제한은 줄 수다.
MAX_CHARS = 2_000_000

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


def columns() -> list[ImportColumn]:
    """표의 열. **화면이 자기 목록을 따로 들지 않게** 서버가 준다.

    두 벌로 두면 열을 하나 더한 날 한쪽만 고쳐지고, 그때 사람이 채운 칸이 조용히
    버려진다.
    """
    return [
        ImportColumn(key=key, label=names[0], required=key in REQUIRED, aliases=list(names))
        for key, names in COLUMNS.items()
    ]


def template_csv() -> str:
    """내려받을 서식. **BOM 을 붙인다** — 안 붙이면 엑셀이 UTF-8 을 못 알아보고
    한글이 깨져서, 사람은 서식이 잘못된 줄 안다."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(TEMPLATE_HEADER)
    writer.writerow(TEMPLATE_SAMPLE)
    return "﻿" + buffer.getvalue()


def _delimiter(first: str) -> str:
    """탭이냐 쉼표냐. **첫 줄로 정한다.**

    엑셀에서 범위를 복사하면 탭이고, 우리가 내려준 서식 파일의 내용을 그대로
    붙여넣으면 쉼표다. 사람이 어느 쪽을 들고 올지 우리가 정할 수 없다.

    탭이 하나라도 있으면 탭으로 본다 — 엑셀이 복사한 글자에는 쉼표가 값 안에
    들어 있을 수 있어도(「3동, 201호」) 탭은 칸 사이에만 있다.
    """
    return "\t" if "\t" in first else ","


def _header_map(fields: Sequence[str] | None) -> dict[str, str]:
    """붙여넣은 머리글을 우리 칸 이름에 맞춘다. 띄어쓰기와 대소문자는 무시한다."""
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
            f"엑셀에서 **머리글 줄까지 함께** 복사했는지 보세요.",
            status=400,
            details={"missing": missing},
        )
    return found


class Problems:
    """한 줄에서 걸린 것들. **어느 칸인지 함께 담는다.**

    화면이 그 칸을 붉게 칠하려면 열 키가 필요하다. 글자에서 되짚어 찾게 하면
    (「거점:」 으로 시작하나 보고) 말을 조금만 다듬어도 색이 사라진다.

    사람이 읽는 말은 열 라벨을 앞에 붙여 만든다 — API 를 직접 쓰는 쪽은 `field` 를
    안 보고 글자만 읽을 수도 있어서, 각자 완결적이어야 한다.
    """

    def __init__(self) -> None:
        self.items: list[ImportProblem] = []

    def add(self, field: str | None, said: str) -> None:
        label = COLUMNS[field][0] if field in COLUMNS else None
        self.items.append(
            ImportProblem(field=field, message=f"{label}: {said}" if label else said)
        )

    def __bool__(self) -> bool:
        return bool(self.items)


class Lookup:
    """이름 -> id 를 **쪽 단위로 한 번에** 찾아 둔다.

    줄마다 물으면 2000줄짜리 대장 하나가 질의를 16,000회 한다(실측). 카탈로그 목록에서
    고친 것과 같은 N+1 이다 — 그리고 여기서는 상한을 낮추는 이유가 된다.

    거점·분류는 축이 통째로 작으므로(수백) 한 번에 읽어 사전을 만든다. 부서와 기종은
    **대장에 실제로 나오는 이름만** 찾는다 — 300줄에 부서는 한둘이고 기종은 수십이라,
    고유 이름 수만큼만 물으면 된다.
    """

    def __init__(self, db: Session, user: User, values: list[dict[str, str]]) -> None:
        self.db = db
        self.user = user
        self.workspaces: dict[str, str | None] = {}
        self.workspace_problem: dict[str, str] = {}
        self.models: dict[str, tuple[uuid.UUID | None, str]] = {}
        self.terms: dict[str, dict[str, list[uuid.UUID]]] = {}

        for axis in ("site", "equipment_category"):
            self.terms[axis] = {}
            vocabulary = db.scalar(select(Vocabulary).where(Vocabulary.slug == axis))
            if vocabulary is None:
                continue
            for term in db.scalars(
                select(VocabularyTerm).where(VocabularyTerm.vocabulary_id == vocabulary.id)
            ):
                # 같은 이름이 둘이면 고르지 않는다 — 그래서 목록으로 담는다.
                self.terms[axis].setdefault(term.value.strip().lower(), []).append(term.id)

        names = {clean(one.get("workspace", "")) for one in values}
        names.discard("")
        if names:
            for row in db.scalars(
                select(Workspace).where(
                    (Workspace.name.in_(names)) | (Workspace.slug.in_(names))
                )
            ):
                # 이름과 slug 둘 다로 찾을 수 있게 담는다 — 사람이 아는 것은 이름이다.
                self.workspaces[row.name] = row.slug
                self.workspaces[row.slug] = row.slug

    def workspace(self, text: str, problems: Problems) -> str | None:
        """부서를 찾고 **권한까지 본다.**

        미리보기가 권한을 안 보면 「300줄 다 됩니다」 라고 해 놓고 저장에서 403 이
        터진다 — 그리고 전부 되돌아간다. 그 한 번으로 사람은 미리보기를 안 믿는다.

        판정은 부서마다 한 번만 한다. 대장 한 장에 부서는 대개 한둘이다.
        """
        body = clean(text)
        slug = self.workspaces.get(body)
        if slug is None:
            problems.add("workspace", f"「{text}」 를 찾을 수 없습니다")
            return None
        if slug in self.workspace_problem:
            said = self.workspace_problem[slug]
            if said:
                problems.add("workspace", said)
                return None
            return slug
        try:
            services.owner_workspace(self.db, self.user, slug)
        except AppError as error:
            self.workspace_problem[slug] = error.message
            problems.add("workspace", error.message)
            return None
        self.workspace_problem[slug] = ""
        return slug

    def term(self, axis: str, text: str, field: str, problems: Problems) -> Any:
        """축의 값 하나를 이름으로 찾는다. **없으면 만들지 않는다.**

        반입이 값을 만들면 오타가 그대로 기준정보가 되고, 「본사」 와 「본사 」 가 서로
        다른 거점이 된다 — 그 둘은 나중에 합칠 방법이 없다.
        """
        body = clean(text)
        if not body:
            return None
        found = self.terms.get(axis, {}).get(body.lower(), [])
        if len(found) == 1:
            return found[0]
        if not found:
            problems.add(
                field, f"「{text}」 가 기준정보에 없습니다. 기준정보에서 먼저 만드세요"
            )
        else:
            problems.add(field, f"「{text}」 가 여럿입니다 ({len(found)}개)")
        return None

    def model(self, text: str, problems: Problems) -> Any:
        """기종을 이름으로 잇는다. **못 정하면 잇지 않는다.**

        비슷한 기종에 끼워 넣으면 그 장비의 하중·온도가 남의 것이 되고, 검색은 그
        남의 수치로 「됩니다」 라고 답한다.

        같은 이름은 한 번만 찾는다 — 대장 300줄에 기종은 대개 수십 종이다.
        """
        body = clean(text)
        if not body:
            return None
        if body not in self.models:
            answer = resolve(self.db, {"kind": "model", "text": body, "limit": 5})
            if answer.match == "exact" and answer.id is not None:
                self.models[body] = (answer.id, "")
            else:
                # **후보를 계열까지 붙여 보여 준다.** 같은 이름의 기종이 두 계열에
                # 있으면 이름만으로는 「Instron 5982 · Instron 5982」 가 되어 고를
                # 수가 없다 — 그러면 그 목록은 없느니만 못하다.
                names = " · ".join(
                    one.label + (f"({one.detail})" if one.detail else "")
                    for one in answer.candidates[:3]
                )
                self.models[body] = (
                    None,
                    f"「{text}」 을(를) 하나로 정할 수 없습니다"
                    + (f" (비슷한 것: {names})" if names else " (카탈로그에 없습니다)"),
                )
        found, said = self.models[body]
        if said:
            problems.add("model", said)
        return found


def _flag(text: str, field: str, problems: Problems) -> bool | None:
    if not text:
        return None
    word = text.strip().lower()
    if word in YES:
        return True
    if word in NO:
        return False
    problems.add(field, f"「{text}」 는 예/아니오로 읽을 수 없습니다")
    return None


def _date(text: str, field: str, problems: Problems) -> date | None:
    if not text:
        return None
    body = text.strip().replace("/", "-").replace(".", "-")
    if body.isdigit() and len(body) == 8:
        body = f"{body[:4]}-{body[4:6]}-{body[6:]}"
    try:
        return date.fromisoformat(body)
    except ValueError:
        problems.add(field, f"「{text}」 는 날짜가 아닙니다 (2024-03-15 처럼)")
        return None


def _int(text: str, field: str, problems: Problems) -> int | None:
    if not text:
        return None
    try:
        return int(float(text.strip()))
    except ValueError:
        problems.add(field, f"「{text}」 는 숫자가 아닙니다")
        return None


def _row_payload(look: Lookup, values: dict[str, str], problems: Problems) -> dict[str, Any]:
    """한 줄을 등록 요청의 모양으로. 문제는 모아서 돌려준다 — 첫 오류에서 멈추면
    사람이 파일을 고치고 올리기를 오류 수만큼 되풀이한다."""
    for field in REQUIRED:
        if not clean(values.get(field, "")):
            problems.add(field, "비어 있습니다")

    model_id = look.model(values.get("model", ""), problems)
    category_term_id = look.term(
        "equipment_category", values.get("category", ""), "category", problems
    )
    if model_id is None and category_term_id is None and not values.get("model"):
        # 기종을 안 골랐으면 분류가 필수다 — 무슨 종류인지 모르는 장비는 검색에서
        # 통째로 빠진다.
        problems.add("category", "기종을 안 적었으면 장비유형은 필수입니다")

    status_text = clean(values.get("status", ""))
    status = STATUS_WORDS.get(status_text, status_text) or "operational"
    if status not in EQUIPMENT_STATUSES:
        problems.add("status", f"「{status_text}」 는 모르는 상태입니다")
        status = "operational"

    shared = _flag(values.get("shared_use", ""), "shared_use", problems)
    calibrated = _flag(
        values.get("calibration_required", ""), "calibration_required", problems
    )
    months = _int(
        values.get("calibration_interval_months", ""), "calibration_interval_months", problems
    )
    if calibrated and months is None:
        # 주기가 없으면 차기일을 계산할 수 없고, 그러면 「곧 만료」 목록이 이 장비를
        # 영원히 안 부른다.
        problems.add("calibration_interval_months", "교정 대상이면 주기(개월)를 적어야 합니다")

    return {
        "asset_no": clean(values.get("asset_no", "")),
        "name": clean(values.get("name", "")),
        "dept_asset_no": clean(values.get("dept_asset_no", "")) or None,
        "workspace_slug": look.workspace(values.get("workspace", ""), problems),
        "site_term_id": look.term("site", values.get("site", ""), "site", problems),
        "location": clean(values.get("location", "")),
        "model_id": model_id,
        "category_term_id": category_term_id,
        "maker_text": clean(values.get("maker_text", "")) or None,
        "model_text": clean(values.get("model_text", "")) or None,
        "serial_no": clean(values.get("serial_no", "")) or None,
        "shared_use": bool(shared),
        "status": status,
        "acquired_on": _date(values.get("acquired_on", ""), "acquired_on", problems),
        "manufactured_year": _int(
            values.get("manufactured_year", ""), "manufactured_year", problems
        ),
        "calibration_required": bool(calibrated),
        "calibration_interval_months": months,
        "note": clean(values.get("note", "")) or None,
    }


def run(db: Session, user: User, text: str, *, dry_run: bool) -> EquipmentImportResult:
    """붙여넣은 대장을 읽어 판정하고, `dry_run` 이 아니면 넣는다."""
    if len(text) > MAX_CHARS:
        raise AppError(
            "TSC-IMPORT-0004",
            f"붙여넣은 내용이 너무 깁니다 ({len(text) // 1024}천 자). 나눠 올리세요.",
            status=400,
        )
    body = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    # BOM 은 서식 파일을 텍스트 편집기로 열어 복사했을 때 딸려 온다.
    body = body.lstrip("\ufeff")
    if not body.strip():
        raise AppError(
            "TSC-IMPORT-0006",
            "붙여넣은 내용이 없습니다. 엑셀에서 **머리글 줄까지 함께** 복사하세요.",
            status=400,
        )

    reader = csv.DictReader(io.StringIO(body), delimiter=_delimiter(body.split("\n", 1)[0]))
    header = _header_map(reader.fieldnames)

    # **먼저 전부 읽는다.** 그래야 이름들을 한 번에 찾을 수 있다 — 줄마다 물으면
    # 2000줄이 질의를 16,000회 한다.
    picked_rows: list[tuple[int, dict[str, str]]] = []
    for index, values in enumerate(reader, start=2):  # 2 = 머리글 다음 줄
        if len(picked_rows) >= MAX_ROWS:
            raise AppError(
                "TSC-IMPORT-0005",
                f"한 번에 {MAX_ROWS}줄까지 받습니다. 나눠 붙여넣으세요.",
                status=400,
            )
        picked = {field: (values.get(column) or "") for field, column in header.items()}
        if not any(clean(one) for one in picked.values()):
            continue  # 엑셀이 남긴 빈 줄
        picked_rows.append((index, picked))

    look = Lookup(db, user, [one for _, one in picked_rows])
    # 이미 등록된 자산번호도 **한 번에** 본다.
    wanted = {clean(one.get("asset_no", "")) for _, one in picked_rows}
    wanted.discard("")
    taken: set[str] = set()
    if wanted:
        taken = set(
            db.scalars(select(Equipment.asset_no).where(Equipment.asset_no.in_(wanted))).all()
        )

    rows: list[EquipmentImportRow] = []
    payloads: list[dict[str, Any]] = []
    # **붙여넣은 것 안의 중복도 잡는다.** DB 에 없더라도 같은 자산번호가 두 줄에 있으면
    # 둘째 줄에서 막히는데, 그때는 이미 첫 줄이 들어간 뒤다.
    seen: dict[str, int] = {}

    for index, picked in picked_rows:
        problems = Problems()
        payload = _row_payload(look, picked, problems)

        asset_no = payload["asset_no"]
        if asset_no:
            if asset_no in seen:
                # 한 칸에 못 붙이는 문제다 — 어느 줄이 원본인지가 요점이다.
                problems.add(None, f"자산번호가 {seen[asset_no]}번째 줄과 겹칩니다")
            elif asset_no in taken:
                problems.add("asset_no", "이미 등록된 장비입니다")
            else:
                seen[asset_no] = index

        rows.append(
            EquipmentImportRow(
                line=index,
                # **서버가 읽은 그대로** 돌려준다 — 화면이 다시 파싱하면 규칙이
                # 두 벌이 되고, 그때 사람은 자기가 붙여넣은 것과 다른 표를 본다.
                cells={field: (picked.get(field) or "").strip() for field in COLUMNS},
                asset_no=asset_no or None,
                name=payload["name"] or None,
                model_linked=payload["model_id"] is not None,
                problems=problems.items,
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
            row.problems.append(ImportProblem(field=None, message=error.message))
            result.problems = 1
            result.ready = len(rows) - 1
            result.created = 0
            return result
        created += 1
    db.commit()
    result.created = created
    return result

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

## 넣을 수 있는 줄은 넣는다

문제가 있는 줄 때문에 멀쩡한 줄까지 막으면, 300줄 중 12줄이 틀렸을 때 288줄을 다시
붙여넣어야 한다.

전에는 통째로 막았다. 「되는 것만 넣으면 사람은 고쳐 다시 올리다가 이미 들어간
288줄에서 「이미 등록된 자산번호」 를 만난다」 는 이유였는데, **화면이 들어간 줄을
표에서 지우면**(`imported`) 그 일이 애초에 안 생긴다 — 다시 붙여넣을 것이 없으니까.

**넣기로 한 것은 전부 되거나 전부 안 되거나다.** 문제 없는 줄들을 한 트랜잭션에 담고,
그중 하나라도 막히면(그 사이 남이 같은 자산번호를 넣는 일이 있다) 통째로 되돌린다.

## 이미 등록된 자산번호는 갱신할 수 있다

부서는 엑셀 대장을 계속 굴린다. 300대 중 30대의 위치·상태가 바뀌었을 때 상세 화면에서
30번 고치라는 것은 무리라, 같은 대장을 다시 붙여넣어 맞출 수 있어야 한다
(`update_existing`). 기본은 거절이다 — 덮어쓰기는 명시적으로 켜야 한다.

**빈 칸은 「비운다」 가 아니라 「안 건드린다」 다.** 엑셀에 비고를 안 적었다고 기존 비고가
지워지면 그것은 갱신이 아니라 사고다.

**부서와 기종은 안 바꾼다.** 이관은 양쪽 관리자가 다 필요하고, 기종을 바꾸면 시험 항목이
다시 복사되지 않아 조건이 옛 기종의 것으로 남는다. 다르게 적혀 있으면 그 줄을 막는다.

**무엇이 바뀌는지 칸마다 보여 준다.** 「30대를 갱신합니다」 만 말하면 사람은 누르고,
그 안에 잘못 붙은 열이 있었다는 것을 나중에 안다.

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
    ImportChange,
    ImportColumn,
    ImportProblem,
)
from app.modules.resolve.services import resolve
from app.modules.vocabulary.models import Vocabulary, VocabularyTerm
from app.modules.workspaces.models import Workspace
from app.shared import audit
from app.shared.errors import AppError
from app.shared.permissions import require_owner_edit
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
    # 파일럿 대장에 실제로 적혀 있던 말들. 「폐기예정」 은 안 받는다 — 아직 폐기가 아니고,
    # 가동인지 유휴인지 그 말로는 모른다.
    "가동중": "operational",
    "정상": "operational",
    "사용": "operational",
    "사용중": "operational",
    "운영": "operational",
    "운영중": "operational",
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


def _header_map(
    fields: Sequence[str] | None, *, update_existing: bool = False
) -> dict[str, str]:
    """붙여넣은 머리글을 우리 칸 이름에 맞춘다. 띄어쓰기와 대소문자는 무시한다.

    갱신이면 **자산번호 열만 있으면 된다.** 「자산번호·설치위치·상태」 세 열만 긁어
    오는 것이 갱신의 자연스러운 모양이고, 나머지 필수 열을 요구하면 그 길이 막힌다.
    새 줄이 섞여 있으면 그 줄은 줄마다 빈 칸 검사로 걸린다.
    """
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
    needed = ("asset_no",) if update_existing else REQUIRED
    missing = [COLUMNS[one][0] for one in needed if one not in found]
    if missing:
        raise AppError(
            "TSC-IMPORT-0003",
            f"머리글에 다음 열이 없습니다: {' · '.join(missing)}. "
            f"엑셀에서 **머리글 줄까지 함께** 복사했는지 보십시오.",
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

    def add(
        self,
        field: str | None,
        said: str,
        *,
        make_axis: str | None = None,
        make_value: str | None = None,
    ) -> None:
        label = COLUMNS[field][0] if field in COLUMNS else None
        self.items.append(
            ImportProblem(
                field=field,
                message=f"{label}: {said}" if label else said,
                make_axis=make_axis,
                make_value=make_value,
            )
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
        #: 그 축이 **누구나 값을 더할 수 있는 축인가**. 열린 축이면 없는 값을
        #: 그 자리에서 만들 수 있다고 알려 준다.
        self.open_axis: set[str] = set()

        for axis in ("site", "equipment_category"):
            self.terms[axis] = {}
            vocabulary = db.scalar(select(Vocabulary).where(Vocabulary.slug == axis))
            if vocabulary is None:
                continue
            if vocabulary.entry_policy == "open":
                self.open_axis.add(axis)
            for term in db.scalars(
                select(VocabularyTerm).where(VocabularyTerm.vocabulary_id == vocabulary.id)
            ):
                # 같은 이름이 둘이면 고르지 않는다 — 그래서 목록으로 담는다.
                self.terms[axis].setdefault(term.value.strip().lower(), []).append(term.id)

        #: slug -> 부서 id. 감사 기록을 그 부서에 매달 때 쓴다.
        self.workspaces_by_slug: dict[str, uuid.UUID] = {}

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
                self.workspaces_by_slug[row.slug] = row.id

    def workspace(self, text: str, problems: Problems) -> str | None:
        """부서를 찾고 **권한까지 본다.**

        미리보기가 권한을 안 보면 「300줄 다 됩니다」 라고 해 놓고 저장에서 403 이
        터진다 — 그리고 전부 되돌아간다. 그 한 번으로 사람은 미리보기를 안 믿는다.

        판정은 부서마다 한 번만 한다. 대장 한 장에 부서는 대개 한둘이다.
        """
        body = clean(text)
        if not body:
            # 비어 있음은 필수 칸 검사가 이미 말했다(새 줄) — 갱신이면 안 건드리는 칸이다.
            # 여기서 또 「「」 를 찾을 수 없습니다」 라고 하면 한 칸에 문제가 둘 붙는다.
            return None
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
            # **열린 축이면 그 자리에서 만들 수 있다.** 창을 닫고 기준정보로 갔다
            # 오게 하면 표에서 고치던 것을 잃는다.
            can = axis in self.open_axis
            problems.add(
                field,
                f"「{text}」 가 기준정보에 없습니다"
                + ("" if can else ". 기준정보에서 먼저 만드십시오"),
                make_axis=axis if can else None,
                make_value=body if can else None,
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


def _row_payload(
    look: Lookup, values: dict[str, str], problems: Problems, *, updating: bool = False
) -> dict[str, Any]:
    """한 줄을 등록 요청의 모양으로. 문제는 모아서 돌려준다 — 첫 오류에서 멈추면
    사람이 파일을 고치고 올리기를 오류 수만큼 되풀이한다.

    `updating` 이면 **필수 칸이 비어 있어도 문제가 아니다** — 갱신은 적힌 칸만 건드리고,
    안 적힌 칸은 이미 있는 값이 그대로다.
    """
    if not updating:
        for field in REQUIRED:
            if not clean(values.get(field, "")):
                problems.add(field, "비어 있습니다")

    model_id = look.model(values.get("model", ""), problems)
    category_term_id = look.term(
        "equipment_category", values.get("category", ""), "category", problems
    )
    if (
        not updating
        and model_id is None
        and category_term_id is None
        and not values.get("model")
    ):
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


#: 갱신이 건드리는 칸. **부서와 기종은 없다** — 이관은 양쪽 관리자가 다 필요하고,
#: 기종을 바꾸면 시험 항목이 다시 복사되지 않는다. 둘 다 대장 갱신으로 조용히 일어나면
#: 안 되는 일이다.
UPDATABLE = (
    "name",
    "dept_asset_no",
    "site_term_id",
    "location",
    "serial_no",
    "shared_use",
    "status",
    "acquired_on",
    "manufactured_year",
    "calibration_required",
    "calibration_interval_months",
    "note",
    "category_term_id",
    "maker_text",
    "model_text",
)

#: 페이로드 키 -> 대장의 열 키. 바뀌는 칸을 화면이 칠하려면 열 키로 말해야 한다.
FIELD_OF = {
    "site_term_id": "site",
    "category_term_id": "category",
    **{key: key for key in UPDATABLE if not key.endswith("_term_id")},
}


#: 상태 코드 -> 사람 말. `STATUS_WORDS` 의 역이되, 코드마다 **첫 번째로 적힌 말**을 쓴다.
STATUS_LABEL: dict[str, str] = {}
for _word, _code in STATUS_WORDS.items():
    STATUS_LABEL.setdefault(_code, _word)


def _shown(db: Session, field: str, value: Any) -> str | None:
    """전후를 사람 말로. 용어 id 는 이름으로, 참·거짓은 예·아니오로, 상태는 라벨로.

    「operational → idle」 은 이 시스템을 만든 사람에게만 읽힌다. 대장을 붙이는 사람은
    「가동 → 유휴」 를 본다."""
    if value is None:
        return None
    if field.endswith("_term_id"):
        term = db.get(VocabularyTerm, value)
        return term.value if term else str(value)
    if isinstance(value, bool):
        return "예" if value else "아니오"
    if field == "status":
        return STATUS_LABEL.get(str(value), str(value))
    return str(value)


def _update_plan(
    db: Session,
    user: User,
    existing: Equipment,
    picked: dict[str, str],
    payload: dict[str, Any],
    problems: Problems,
) -> tuple[dict[str, Any], list[ImportChange]]:
    """이미 있는 장비에 **무엇을 바꿀지.** 보낼 것과 사람에게 보일 전후를 함께 만든다.

    **적힌 칸만 본다.** 빈 칸은 「안 건드린다」 다 — `payload` 는 빈 칸을 기본값으로
    채워 놓으므로(상태 「가동」, 공용 「아니오」) 그것을 그대로 보내면 안 적은 칸이
    기본값으로 덮인다.
    """
    try:
        require_owner_edit(
            db,
            user,
            existing.owner_workspace_id,
            what="장비",
            code="TSC-EQUIPMENT-0002",
            role="member",
        )
    except AppError as error:
        problems.add(None, error.message)
        return {}, []

    # **부서·기종은 다르게 적혀 있으면 막는다.** 조용히 무시하면 사람은 바뀐 줄 안다.
    if clean(picked.get("workspace", "")) and payload.get("workspace_slug"):
        owner = db.get(Workspace, existing.owner_workspace_id)
        if owner is not None and owner.slug != payload["workspace_slug"]:
            problems.add(
                "workspace",
                "반입으로는 부서를 옮길 수 없습니다. 상세 화면에서 이관하십시오",
            )
    if clean(picked.get("model", "")) and payload.get("model_id") != existing.model_id:
        problems.add(
            "model",
            "반입으로는 기종을 바꿀 수 없습니다. 상세 화면에서 바꾸십시오",
        )

    changes: dict[str, Any] = {}
    shown: list[ImportChange] = []
    for key in UPDATABLE:
        column = FIELD_OF[key]
        if not clean(picked.get(column, "")):
            continue  # 안 적은 칸은 안 건드린다
        if existing.model_id is not None and key in (
            "category_term_id",
            "maker_text",
            "model_text",
        ):
            continue  # 카탈로그에 이어진 장비의 그 셋은 카탈로그가 갖는다
        after = payload.get(key)
        if after is None:
            continue  # 못 읽은 값(문제로 이미 적혔다)
        before = getattr(existing, key)
        if before == after:
            continue
        changes[key] = after
        shown.append(
            ImportChange(
                field=column, before=_shown(db, key, before), after=_shown(db, key, after)
            )
        )
    return changes, shown


def run(
    db: Session, user: User, text: str, *, dry_run: bool, update_existing: bool = False
) -> EquipmentImportResult:
    """붙여넣은 대장을 읽어 판정하고, `dry_run` 이 아니면 넣는다."""
    if len(text) > MAX_CHARS:
        raise AppError(
            "TSC-IMPORT-0004",
            f"붙여넣은 내용이 너무 깁니다 ({len(text) // 1024}천 자). 나눠 올리십시오.",
            status=400,
        )
    body = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    # BOM 은 서식 파일을 텍스트 편집기로 열어 복사했을 때 딸려 온다.
    body = body.lstrip("\ufeff")
    if not body.strip():
        raise AppError(
            "TSC-IMPORT-0006",
            "붙여넣은 내용이 없습니다. 엑셀에서 **머리글 줄까지 함께** 복사하십시오.",
            status=400,
        )

    reader = csv.DictReader(io.StringIO(body), delimiter=_delimiter(body.split("\n", 1)[0]))
    header = _header_map(reader.fieldnames, update_existing=update_existing)

    # **먼저 전부 읽는다.** 그래야 이름들을 한 번에 찾을 수 있다 — 줄마다 물으면
    # 2000줄이 질의를 16,000회 한다.
    picked_rows: list[tuple[int, dict[str, str]]] = []
    for index, values in enumerate(reader, start=2):  # 2 = 머리글 다음 줄
        if len(picked_rows) >= MAX_ROWS:
            raise AppError(
                "TSC-IMPORT-0005",
                f"한 번에 {MAX_ROWS}줄까지 받습니다. 나눠 붙여넣으십시오.",
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
    taken: dict[str, Equipment] = {}
    if wanted:
        taken = {
            one.asset_no: one
            for one in db.scalars(
                select(Equipment).where(
                    Equipment.asset_no.in_(wanted), Equipment.deleted_at.is_(None)
                )
            )
        }

    rows: list[EquipmentImportRow] = []
    payloads: list[dict[str, Any]] = []
    # **붙여넣은 것 안의 중복도 잡는다.** DB 에 없더라도 같은 자산번호가 두 줄에 있으면
    # 둘째 줄에서 막히는데, 그때는 이미 첫 줄이 들어간 뒤다.
    seen: dict[str, int] = {}

    plans: list[dict[str, Any] | None] = []

    for index, picked in picked_rows:
        problems = Problems()
        asset_no = clean(picked.get("asset_no", ""))
        existing = taken.get(asset_no) if asset_no else None
        updating = existing is not None and update_existing

        payload = _row_payload(look, picked, problems, updating=updating)
        plan: dict[str, Any] | None = None
        shown: list[ImportChange] = []

        if asset_no:
            if asset_no in seen:
                # 한 칸에 못 붙이는 문제다 — 어느 줄이 원본인지가 요점이다.
                problems.add(None, f"자산번호가 {seen[asset_no]}번째 줄과 겹칩니다")
            elif existing is not None and not update_existing:
                problems.add("asset_no", "이미 등록된 장비입니다")
            elif existing is not None:
                plan, shown = _update_plan(db, user, existing, picked, payload, problems)
                seen[asset_no] = index
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
                model_linked=(
                    existing.model_id is not None
                    if existing is not None
                    else payload["model_id"] is not None
                ),
                problems=problems.items,
                exists=existing is not None,
                changes=shown,
            )
        )
        payloads.append(payload)
        plans.append(plan if updating else None)

    ready = sum(1 for one in rows if not one.problems)
    unchanged = sum(1 for one in rows if not one.problems and one.exists and not one.changes)
    result = EquipmentImportResult(
        total=len(rows),
        ready=ready,
        problems=len(rows) - ready,
        created=0,
        unchanged=unchanged,
        rows=rows,
    )
    if dry_run or not ready:
        return result

    # **넣을 수 있는 줄만.** 문제가 있는 줄 때문에 멀쩡한 줄까지 막으면 300줄 중
    # 12줄이 틀렸을 때 288줄을 다시 붙여넣어야 한다.
    #
    # 그 288줄은 **한 트랜잭션**이다. 넣다가 하나가 막히면(그 사이 남이 같은
    # 자산번호를 넣는 일이 있다) 통째로 되돌린다 — 반쯤 들어간 채로 끝나지 않는다.
    going = [
        (row, payload, plan)
        for row, payload, plan in zip(rows, payloads, plans, strict=True)
        if not row.problems
    ]
    created = updated = 0
    for row, payload, plan in going:
        try:
            if row.exists:
                # 대장과 같은 줄은 손댈 것이 없다 — 처리된 것으로 쳐서 표에서 사라진다.
                if plan:
                    existing = taken[payload["asset_no"]]
                    services.update(db, user, existing.id, plan, commit=False)
                    updated += 1
            else:
                services.create(db, user, payload, commit=False)
                created += 1
        except AppError as error:
            db.rollback()
            row.problems.append(ImportProblem(field=None, message=error.message))
            # 되돌렸으니 **아무 줄도 안 들어갔다.** 판정을 다시 센다.
            for one, _, _ in going:
                one.imported = False
            result.ready = sum(1 for one in rows if not one.problems)
            result.problems = len(rows) - result.ready
            result.created = 0
            result.updated = 0
            return result
        row.imported = True

    if created or updated:
        # **반입 한 번에 감사 한 줄.** 대마다 남기면 300줄이 생겨 정작 찾을 것을 가린다.
        # 갱신은 전후를 붙인다 — 「이 위치 누가 바꿨어」 에 답하는 자리가 여기다.
        fresh = [row.asset_no for row, _, plan in going if not row.exists and row.asset_no]
        changed = {
            row.asset_no: {
                one.field: {"before": one.before, "after": one.after} for one in row.changes
            }
            for row, _, plan in going
            if row.exists and plan and row.asset_no
        }
        owners = {
            taken[payload["asset_no"]].owner_workspace_id
            if row.exists
            else look.workspaces_by_slug.get(payload.get("workspace_slug") or "")
            for row, payload, _ in going
        }
        owners.discard(None)
        audit.record(
            db,
            action=audit.EQUIPMENT_IMPORTED,
            actor=user,
            target_table="equipment",
            target_id=None,
            target_label=f"대장 반입: 새로 {created} · 갱신 {updated}",
            # 한 부서의 대장이면 그 부서에 매단다 — 부서 이력 화면에서 보인다.
            workspace_id=next(iter(owners)) if len(owners) == 1 else None,
            changes={
                "created": created,
                "updated": updated,
                "unchanged": result.unchanged,
                "created_asset_nos": fresh,
                "updated_rows": changed,
            },
        )

    db.commit()
    result.created = created
    result.updated = updated
    return result

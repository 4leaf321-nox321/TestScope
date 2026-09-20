"""속성 값으로 거르기 — **적어 둔 것을 찾을 수 있어야 적는다.**

속성은 「열이 아니라 행」 이라 유연한 대신, 값이 색인 카드와 상세 화면에만 뜨면 쌓아 둔
것을 **되찾을 길이 없다**. 「투자 연도 2020 이후 장비」 「-40 °C 이하로 내려가는 시험」 을
못 물으면 사람은 목록을 내려받아 엑셀에서 거르고, 그 순간 이 시스템은 입력 창구일 뿐이다.

## 문법

목록 엔드포인트에 `attr` 을 여러 번 준다. 여러 개면 **모두** 만족해야 한다(AND).

    attr=invest_year>=2020      수치 · 날짜
    attr=purpose~고온           문장 포함(대소문자 무시)
    attr=reserve_url*           값이 적혀 있기만 하면
    attr=sample_form=시편       선택지 · 기준정보 값 · 참(true)/거짓(false)
    attr=holder!=3동            같지 않다

연산자는 `>=` `<=` `>` `<` `!=` `=` `~` `*` 여덟이고, 왼쪽은 정의의 `key` 다(이름이 아니라).
이름은 관리자가 고치면 바뀌고, 그때 저장해 둔 링크가 조용히 빈 결과를 낸다.

## 수치는 파이썬에서 판정한다

값마다 단위가 다르다(정식으로 올리기 전에는 사람마다 kN·N·kgf 로 적는다). SQL 안에서
환산할 방법이 없으므로, 그 정의의 값 행만 읽어 **환산해 비교하고** 남은 대상 id 로 거른다.
행 수는 대상 객체 수 규모라 이 방식으로 충분하다 — 장비 찾기가 조건 판정을 파이썬에서 하는
것과 같은 이유·같은 규모다. 못 바꾸는 단위의 값은 **빠진다**: 틀린 자리에 놓느니 안 보이는
편이 낫고, 화면은 그 정의의 단위를 함께 보여 준다.

## 0건은 네 가지 다른 상황이다

빈 목록은 「그 속성에 값을 적은 것이 하나도 없다」 「값은 있는데 조건이 좁다」 「단위를 못
바꿔 다 빠졌다」 「조건 하나씩은 걸리는데 함께 걸면 없다」 를 똑같이 생겼다. 그 넷을 사람도
AI 도 구별 못 하면 답은 늘 「그런 것 없습니다」 가 된다 — 실제로는 「아무도 안 적었다」 인데.
그래서 `diagnose` 가 조건마다 값이 적힌 수 · 단위 못 바꾼 수 · 그 조건 하나로 걸리는 수를
세고, 그것으로 한 줄을 만든다(장비 찾기의 `diagnosis` 와 같은 발상).

## 범위는 「닿나」 로 읽는다

범위 값(-40 ~ 125)에 `>=100` 을 물으면 **위쪽 끝**이 100 이상인지 본다(닿는다), `<=-20` 은
아래쪽 끝을 본다. `=0` 은 그 값이 범위 안에 드는지다. 빈 끝은 제한 없음이라 언제나 닿는다
(ADR 0003).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session

from app.modules.attributes.models import AttributeDefinition, AttributeValue
from app.modules.equipment.models import EquipmentSeries
from app.modules.methods.models import TestMethod
from app.modules.reliability.models import ReliabilityTest
from app.modules.vocabulary.models import VocabularyTerm
from app.shared.errors import AppError
from app.shared.units import convert

#: 한 번에 걸 수 있는 속성 조건 수. 넘으면 사람이 쓴 것이 아니라 기계가 만든 것이고,
#: 그때는 값마다 쿼리가 늘어 목록이 느려진다.
MAX_FILTERS = 10

_OPS = ("<=", ">=", "!=", "<", ">", "=", "~", "*")
_PATTERN = re.compile(
    r"^(?P<key>[A-Za-z0-9_\-.]{1,60})(?P<op>\*|<=|>=|!=|<|>|=|~)(?P<raw>.*)$"
)

#: 대상 → 값이 그 대상을 가리키는 열. 새 대상은 여기에 한 줄.
TARGET_COLUMN = {
    "reliability_test": AttributeValue.reliability_test_id,
    "equipment": AttributeValue.equipment_id,
    "series": AttributeValue.series_id,
    "method": AttributeValue.method_id,
}


@dataclass(frozen=True)
class AttributeFilter:
    """푼 조건 하나 — 어느 정의를, 어떤 연산으로, 무엇과."""

    definition: AttributeDefinition
    op: str
    raw: str


def _number(raw: str, label: str) -> float:
    try:
        return float(raw.strip())
    except ValueError:
        raise AppError(
            "TSC-ATTR-0120", f"「{label}」 는 수치 속성입니다. 숫자로 물어 주세요."
        ) from None


def _date(raw: str, label: str) -> date:
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        raise AppError(
            "TSC-ATTR-0121", f"「{label}」 는 날짜 속성입니다. 2024-05-01 꼴로 물어 주세요."
        ) from None


def parse(db: Session, target: str, raw_filters: list[str]) -> list[AttributeFilter]:
    """`attr` 문자열들을 정의에 붙인다. **모르는 key 는 조용히 넘기지 않는다** — 오타 하나로
    「없음」 이 돌아오면 사람은 값이 안 적힌 줄 안다."""
    if not raw_filters:
        return []
    if len(raw_filters) > MAX_FILTERS:
        raise AppError("TSC-ATTR-0122", f"속성 조건은 한 번에 {MAX_FILTERS}개까지입니다.")
    out: list[AttributeFilter] = []
    for one in raw_filters:
        matched = _PATTERN.match(one.strip())
        if matched is None:
            raise AppError(
                "TSC-ATTR-0123",
                f"속성 조건 「{one}」 를 못 읽었습니다."
                f" 「키{'·'.join(_OPS)}값」 꼴로 적어 주세요.",
            )
        key = matched.group("key")
        definition = db.scalar(
            select(AttributeDefinition).where(
                AttributeDefinition.target == target, AttributeDefinition.key == key
            )
        )
        if definition is None:
            raise AppError("TSC-ATTR-0124", f"「{key}」 라는 속성이 이 대상에 없습니다.")
        out.append(
            AttributeFilter(
                definition=definition, op=matched.group("op"), raw=matched.group("raw")
            )
        )
    return out


def _numeric_match(one: AttributeFilter, bottom: float | None, top: float | None) -> bool:
    """이 값이 물음에 닿나. **빈 끝은 제한 없음**이라 언제나 닿는다(ADR 0003)."""
    want = _number(one.raw, one.definition.label)
    reaches_up = top is None or top >= want
    reaches_down = bottom is None or bottom <= want
    if one.op == ">=":
        return reaches_up
    if one.op == ">":
        return top is None or top > want
    if one.op == "<=":
        return reaches_down
    if one.op == "<":
        return bottom is None or bottom < want
    if one.op == "=":
        return reaches_up and reaches_down
    if one.op == "!=":
        return not (reaches_up and reaches_down)
    raise AppError(
        "TSC-ATTR-0125",
        f"「{one.definition.label}」 는 수치 속성이라 「포함」 으로 못 묻습니다.",
    )


def _numeric_ids(db: Session, column: Any, one: AttributeFilter) -> set[uuid.UUID]:
    """수치·범위 — 단위를 정의의 단위로 맞춰 파이썬에서 잰다."""
    rows = db.execute(
        select(
            column,
            AttributeValue.num_value,
            AttributeValue.num_min,
            AttributeValue.num_max,
            AttributeValue.unit,
        ).where(AttributeValue.definition_id == one.definition.id, column.is_not(None))
    ).all()

    found: set[uuid.UUID] = set()
    for owner, num, low, high, wrote_unit in rows:
        verdict = _numeric_row(one, num, low, high, wrote_unit)
        if verdict is True:
            found.add(owner)
    return found


def _numeric_row(
    one: AttributeFilter,
    num: float | None,
    low: float | None,
    high: float | None,
    wrote_unit: str,
) -> bool | None:
    """값 행 하나의 판정 — True 닿음 · False 안 닿음 · **None 은 단위를 못 바꿔 뺀 것.**

    셋을 가르는 이유: 진단이 「안 닿아서 빠진 것」 과 「단위 때문에 빠진 것」 을 따로 세야
    사람이 무엇을 고칠지(조건인지 값인지) 안다.
    """
    unit = one.definition.unit
    source = wrote_unit or unit
    point = convert(num, source, unit) if num is not None else None
    if num is not None and point is None:
        return None  # 못 바꾸는 단위 — 지어서 옮기지 않는다.
    bottom = point if point is not None else convert(low, source, unit) if low else None
    top = point if point is not None else convert(high, source, unit) if high else None
    if bottom is None and top is None and point is None:
        return None if (low is not None or high is not None) else False
    return _numeric_match(one, bottom, top)


def _value_predicate(one: AttributeFilter) -> Any:
    """수치가 아닌 종류의 비교 — SQL 에서 한다."""
    kind = one.definition.kind
    raw = one.raw.strip()
    negate = one.op == "!="
    if one.op == "*":
        return None  # 값 행이 있기만 하면 된다.

    if kind == "boolean":
        want = raw.lower() in ("true", "1", "y", "yes", "예", "참")
        return AttributeValue.bool_value.is_(want)
    if kind == "date":
        want_date = _date(raw, one.definition.label)
        on_day = AttributeValue.date_value
        by_op = {
            ">=": on_day >= want_date,
            ">": on_day > want_date,
            "<=": on_day <= want_date,
            "<": on_day < want_date,
            "=": on_day == want_date,
            "!=": on_day != want_date,
        }
        if one.op == "~":
            raise AppError(
                "TSC-ATTR-0125",
                f"「{one.definition.label}」 는 날짜 속성이라 「포함」 으로 못 묻습니다.",
            )
        return by_op[one.op]
    if kind == "term":
        # 값의 글자로 묻는다 — 화면은 id 를 알지만 사람이 손으로 적은 주소는 이름이다.
        term = select(VocabularyTerm.id).where(
            VocabularyTerm.id == AttributeValue.term_id,
            VocabularyTerm.value.ilike(f"%{raw}%" if one.op == "~" else raw),
        )
        return ~term.exists() if negate else term.exists()
    if kind == "method":
        method = select(TestMethod.id).where(
            TestMethod.id == AttributeValue.ref_method_id,
            or_(
                TestMethod.code.ilike(f"%{raw}%" if one.op == "~" else raw),
                TestMethod.title.ilike(f"%{raw}%" if one.op == "~" else raw),
            ),
        )
        return ~method.exists() if negate else method.exists()

    column = AttributeValue.text_value
    if one.op == "~":
        return column.ilike(f"%{raw}%")
    if negate:
        return or_(column.is_(None), column != raw)
    return column == raw


def apply[T: tuple[Any, ...]](
    db: Session, stmt: Select[T], target: str, id_column: Any, filters: list[AttributeFilter]
) -> Select[T]:
    """거른 목록 쿼리. 조건마다 하나씩 좁힌다 — 모두 만족해야 남는다."""
    if not filters:
        return stmt
    column = TARGET_COLUMN[target]
    for one in filters:
        if one.definition.kind in ("number", "range", "condition"):
            found = _numeric_ids(db, column, one)
            # 빈 집합을 그대로 넘기면 `IN ()` 이 되어 아무것도 안 남는다 — 맞는 답이다.
            stmt = stmt.where(id_column.in_(found))
            continue
        where = [AttributeValue.definition_id == one.definition.id, column == id_column]
        predicate = _value_predicate(one)
        if predicate is not None:
            where.append(predicate)
        exists = select(AttributeValue.id).where(and_(*where)).exists()
        stmt = stmt.where(exists)
    return stmt


# --- 빈 결과 진단 ----------------------------------------------------------------

NUMERIC_KINDS = ("number", "range", "condition")


@dataclass(frozen=True)
class FilterDiagnosis:
    """조건 하나가 왜 아무것도 못 걸렀나 — 세 수와 한 줄."""

    key: str
    label: str
    status: str
    with_value: int
    """이 속성에 값이 적힌 대상 수. 0 이면 조건이 문제가 아니라 **아무도 안 적은 것**이다."""
    unconvertible: int
    """단위를 정의의 단위로 못 바꿔 판정에서 뺀 값 수. 있으면 조건이 아니라 값을 고칠
    일이다."""
    matched: int
    """이 조건 **하나만** 걸었을 때 남는 수. 0 이면 조건이 좁은 것이고, 0 이 아닌데 전체가
    비었으면 다른 조건과 함께 걸어서 빈 것이다."""
    hint: str


def _base_ids(target: str) -> Select[tuple[uuid.UUID]]:
    """대상 전부의 id — 지워진 것은 뺀다. 장비는 부르는 쪽이 가시성으로 좁혀 준다."""
    if target == "reliability_test":
        return select(ReliabilityTest.id).where(ReliabilityTest.deleted_at.is_(None))
    if target == "series":
        return select(EquipmentSeries.id).where(EquipmentSeries.deleted_at.is_(None))
    if target == "method":
        return select(TestMethod.id).where(TestMethod.deleted_at.is_(None))
    raise AppError("TSC-ATTR-0126", f"모르는 대상입니다: {target}")


def _hint(one: AttributeFilter, with_value: int, unconvertible: int, matched: int) -> str:
    label = one.definition.label
    if with_value == 0:
        return (
            f"「{label}」 에 값이 적힌 것이 없습니다 — 조건이 아니라 적힌 값이 없는 것입니다."
        )
    parts: list[str] = []
    if unconvertible:
        parts.append(
            f"단위를 「{one.definition.unit or '정의 단위'}」 로 못 바꿔 뺀 값이 "
            f"{unconvertible}건 있습니다"
        )
    if matched == 0:
        parts.append(
            f"값은 {with_value}건 있지만 이 조건에 든 것이 없습니다 — 조건을 넓혀 보세요"
        )
    else:
        parts.append(
            f"이 조건만으로는 {matched}건이 걸립니다 — 다른 조건과 함께 걸어서 비었습니다"
        )
    if one.definition.status == "draft":
        parts.append("초안 속성이라 값이 사람마다 다르게 적혔을 수 있습니다")
    return ". ".join(parts) + "."


def diagnose(
    db: Session,
    target: str,
    filters: list[AttributeFilter],
    *,
    base: Select[tuple[uuid.UUID]] | None = None,
) -> list[FilterDiagnosis]:
    """조건마다 「왜 0건인가」. 결과가 비었을 때 부른다 — 빈 목록만 돌려주면 사람도 AI 도
    「그런 것 없습니다」 로 옮기고, 실제로는 「아무도 안 적었다」 인 경우가 가장 흔하다."""
    column = TARGET_COLUMN[target]
    ids = base if base is not None else _base_ids(target)
    scope = column.in_(ids)
    out: list[FilterDiagnosis] = []
    for one in filters:
        rows = db.execute(
            select(
                column,
                AttributeValue.num_value,
                AttributeValue.num_min,
                AttributeValue.num_max,
                AttributeValue.unit,
            ).where(AttributeValue.definition_id == one.definition.id, scope)
        ).all()
        with_value = len({row[0] for row in rows})
        unconvertible = 0
        matched = 0
        if one.definition.kind in NUMERIC_KINDS and one.op != "*":
            for _owner, num, low, high, wrote_unit in rows:
                verdict = _numeric_row(one, num, low, high, wrote_unit)
                if verdict is None:
                    unconvertible += 1
                elif verdict:
                    matched += 1
        else:
            where = [AttributeValue.definition_id == one.definition.id, scope]
            predicate = _value_predicate(one)
            if predicate is not None:
                where.append(predicate)
            matched = int(
                db.scalar(select(func.count()).select_from(AttributeValue).where(*where)) or 0
            )
        out.append(
            FilterDiagnosis(
                key=one.definition.key,
                label=one.definition.label,
                status=one.definition.status,
                with_value=with_value,
                unconvertible=unconvertible,
                matched=matched,
                hint=_hint(one, with_value, unconvertible, matched),
            )
        )
    return out

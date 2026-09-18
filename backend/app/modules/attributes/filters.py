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

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import Session

from app.modules.attributes.models import AttributeDefinition, AttributeValue
from app.modules.methods.models import TestMethod
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
    unit = one.definition.unit
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
        source = wrote_unit or unit
        point = convert(num, source, unit) if num is not None else None
        if num is not None and point is None:
            continue  # 못 바꾸는 단위 — 지어서 옮기지 않는다.
        bottom = point if point is not None else convert(low, source, unit) if low else None
        top = point if point is not None else convert(high, source, unit) if high else None
        if bottom is None and top is None and point is None:
            continue
        if _numeric_match(one, bottom, top):
            found.add(owner)
    return found


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

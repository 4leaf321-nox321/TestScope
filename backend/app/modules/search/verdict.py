"""조건 하나를 **되나 / 안 되나 / 모르나** 로 가르는 규칙 — 이 저장소에 한 벌뿐이다.

장비 검색(`services`)·카탈로그 검색(`catalog_search`)·신뢰성 「가능한 장비」·MCP 가 전부
여기를 탄다. 규칙이 두 벌이면 「카탈로그에서는 되는데 등록하니 안 된다」 가 생기고, 그때
사람은 둘 다 안 믿는다.

`services.py` 에서 갈라 나왔다(2026-09-21) — 부속 판정(`accessories`)이 같은 규칙을 써야
하는데, 그것을 `services` 에 두면 `services -> accessories -> services` 로 돈다. 글자는
그대로, 자리만 옮겼다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.modules.search.schemas import ConditionMatch, ConditionQuery
from app.modules.vocabulary.models import ConditionKey


class Limit(Protocol):
    """조건 한 칸이 갖는 것. 장비 조건(`EquipmentTestCondition`)과 카탈로그 검색이 기종
    사양에서 만든 칸이 같은 판정 함수를 타게 하는 계약 — 판정이 두 벌이면 「카탈로그에서는
    되는데 등록하니 안 된다」 가 생긴다."""

    @property
    def min_value(self) -> float | None: ...

    @property
    def max_value(self) -> float | None: ...

    @property
    def text_value(self) -> str | None: ...

    @property
    def requires_accessory(self) -> bool: ...


@dataclass(frozen=True)
class Bound:
    """조건 한 칸 — 장비 조건과 같은 모양이라 같은 판정 함수를 탄다."""

    min_value: float | None
    max_value: float | None
    text_value: str | None
    requires_accessory: bool


def _fmt(value: float | None, unit: str) -> str:
    """숫자를 사람이 읽는 꼴로. **단위를 빼지 않는다** — 20 만 적으면 N 인지
    kN 인지 알 수 없고, 그 둘은 자릿수가 셋 다르다."""
    if value is None:
        return "제한 없음"
    text = f"{value:g}"
    return f"{text} {unit}".strip()


def _asked(query: ConditionQuery, key: ConditionKey) -> str:
    unit = key.display_unit or key.si_unit
    if query.at is not None:
        return f"{_fmt(query.at, unit)} 에서"
    if query.at_least is not None:
        return f"{_fmt(query.at_least, unit)} 이상"
    if query.at_most is not None:
        return f"{_fmt(query.at_most, unit)} 이하"
    if query.text:
        return query.text
    return "지정 없음"


def _range_text(limit: Limit | None, key: ConditionKey) -> str | None:
    if limit is None:
        return None
    if limit.text_value:
        return limit.text_value
    unit = key.display_unit or key.si_unit
    return f"{_fmt(limit.min_value, unit)} ~ {_fmt(limit.max_value, unit)}"


def _verdict(query: ConditionQuery, limit: Limit | None) -> str:
    """조건 하나의 판정. met · accessory · unmet · unknown. 이유는 `_judge` 가 준다."""
    return _judge(query, limit)[0]


def _judge(query: ConditionQuery, limit: Limit | None) -> tuple[str, str | None]:
    """조건 하나의 판정과 **모르면 왜 모르는지.** (verdict, reason).

    **비어 있는 한쪽은 "제한 없음" 이다.** 0 으로 취급하면 상한을 안 적은 장비가
    전부 탈락한다 — 실제로 사람들은 아는 쪽만 적는다.

    범위는 맞는데 그 범위가 **옵션 부속 기준**이면 「됨」 이 아니라 `accessory` 다.
    부속을 사거나 빌려야 되는 것이고, 그 사실을 사람이 알아야 한다.

    「모른다」 만 말하면 사람은 채울 자리를 못 찾는다. 조건이 아예 없는 것(`missing`)과
    상한만 없는 것(`no_max`)은 채우는 칸이 다르다.
    """
    if limit is None:
        return "unknown", "missing"
    verdict, reason = _range_verdict(query, limit)
    if verdict == "met" and limit.requires_accessory:
        return "accessory", None
    return verdict, reason


def _range_verdict(query: ConditionQuery, limit: Limit) -> tuple[str, str | None]:

    if query.text is not None:
        if limit.text_value is None:
            return "unknown", "no_range"
        return ("met" if limit.text_value.strip() == query.text.strip() else "unmet"), None

    if query.at is not None:
        if limit.min_value is not None and query.at < limit.min_value:
            return "unmet", None
        if limit.max_value is not None and query.at > limit.max_value:
            return "unmet", None
        # 양쪽 다 비어 있으면 범위를 안 적은 것이다 — 통과가 아니라 모름이다.
        if limit.min_value is None and limit.max_value is None:
            return "unknown", "no_range"
        return "met", None

    if query.at_least is not None:
        if limit.max_value is None:
            # 상한을 안 적었다. 무제한이라는 뜻일 수도, 안 적은 것일 수도 있다 —
            # **구별할 수 없으면 모른다고 답한다.** 된다고 답했다가 틀리면 그
            # 한 번으로 시스템 전체가 안 믿긴다.
            return "unknown", "no_max"
        return ("met" if limit.max_value >= query.at_least else "unmet"), None

    if query.at_most is not None:
        if limit.min_value is None:
            return "unknown", "no_min"
        return ("met" if limit.min_value <= query.at_most else "unmet"), None

    return "unknown", "no_range"


def _hit_verdict(matches: list[ConditionMatch]) -> str | None:
    """시험 항목 하나의 종합 판정. None 이면 결과에서 뺀다.

    **하나라도 안 되면 뺀다.** 안 되는 장비를 목록에 남기는 것은 답이 아니라
    소음이고, 사람은 목록이 길면 위에서부터 읽다가 틀린 것을 고른다.
    """
    if any(one.verdict == "unmet" for one in matches):
        return None
    if not matches:
        return "match"
    if all(one.verdict == "unknown" for one in matches):
        return "unknown"
    if any(one.verdict == "unknown" for one in matches):
        return "partial"
    if any(one.verdict == "accessory" for one in matches):
        return "accessory"
    return "match"


#: 결과 정렬 우선순위. **확실한 것이 위로 온다.** 부속이 있어야 되는 것은 확실히 되는 것
#: 다음이고, 모르는 것보다는 앞이다 — 사면 되는 것과 모르는 것은 다르다.
VERDICT_RANK = {"match": 0, "accessory": 1, "partial": 2, "unknown": 3}

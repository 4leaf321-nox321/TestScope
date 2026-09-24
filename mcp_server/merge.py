"""속성 값을 **겹치는 줄만** 갈아 끼운다.

`PATCH /reliability-tests/{id}` 의 `attributes` 는 통째로 갈아 끼운다. 카드에 칸이 스물
넘게 서면서 「온도 하나를 고치려고 스물둘을 다시 보내다 하나를 빠뜨리는」 일이 현실이
됐고, 빠뜨린 값은 조용히 사라진다 — 지운 기억이 없으니 아무도 못 찾는다.

**`server.py` 가 아니라 여기 있는 이유**: 저쪽은 `mcp` 패키지를 들여오므로 시험이 그것까지
깔아야 한다. 이 판단은 HTTP 도 MCP 도 아닌 **순수한 병합**이라 따로 두면 시험이 값싸다.
"""

from __future__ import annotations

from typing import Any

#: 값 한 줄에서 **되돌려 보낼 수 있는 칸**만. 읽을 때 오는 `label` · `kind` · `display`
#: 같은 것은 서버가 만들어 주는 글자라 도로 보내면 안 된다(지금은 무시되지만, 무시되는
#: 것에 기대면 오타도 같이 조용해진다).
VALUE_FIELDS = (
    "num_value",
    "num_min",
    "num_max",
    "unit",
    "text_value",
    "bool_value",
    "date_value",
    "json_value",
    "term_id",
    "method_id",
    "document_id",
    "note",
)


def as_input(row: dict[str, Any]) -> dict[str, Any]:
    """읽어 온 값 한 줄을 **다시 보낼 수 있는 모양**으로."""
    kept = {key: row[key] for key in VALUE_FIELDS if row.get(key) is not None}
    kept["definition_id"] = str(row["definition_id"])
    return kept


def merge(
    current: list[dict[str, Any]], incoming: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """지금 있는 것 위에 보낸 줄만 얹는다.

    * `definition_id` 가 같으면 **갈아 끼운다** — 반만 보내도 그 칸 전체가 그 값이 된다
      (한 칸 안에서 `num_min` 만 바꾸고 `num_max` 를 남기는 일은 없다: 구간은 한 값이다).
    * `remove: true` 면 그 칸을 **뺀다.** 빈 값을 보내는 것으로는 안 지워진다 — 빈 문자열과
      「안 적음」 은 다르다.
    * `definition_id` 가 없는 줄(`new_label`)은 겹칠 자리가 없으니 뒤에 더한다.

    **순서를 지킨다.** 지금 있는 줄의 순서가 먼저고 새 줄이 뒤다 — 카드가 매번 다른 순서로
    읽히면 사람이 「뭐가 바뀌었지」 를 눈으로 못 찾는다.
    """
    kept: dict[str, dict[str, Any]] = {
        str(row["definition_id"]): as_input(row)
        for row in current
        if row.get("definition_id")
    }
    fresh: list[dict[str, Any]] = []
    for row in incoming:
        key = str(row.get("definition_id") or "")
        if not key:
            fresh.append({one: value for one, value in row.items() if one != "remove"})
            continue
        if row.get("remove"):
            kept.pop(key, None)
            continue
        kept[key] = {
            one: value for one, value in row.items() if one != "remove"
        } | {"definition_id": key}
    return [*kept.values(), *fresh]

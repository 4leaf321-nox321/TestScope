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
    "set_label",
    "step_order",
    "step_label",
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
    # **원문 근거 셋.** 안 실으면 한 칸을 고칠 때 **안 건드린 줄 전부**의 근거가 날아간다 —
    # `set_values` 가 통째로 지우고 다시 넣으므로, 되돌려 보내지 않은 칸은 그 자리에서
    # 사라진다. 운영에서 그렇게 잃었다(2026-10-03).
    #
    # 그리고 이것은 **되찾을 수 없는 종류**다: `note` 는 옮긴 사람의 해석이라 다시 쓸 수
    # 있지만, 원문은 문서를 다시 열어야 나온다. 환산을 남기지 않으면 `70 degC` 가 문서의
    # 값인지 158 °F 를 옮긴 값인지 알 길이 없다.
    "source_text",
    "original_value",
    "original_unit",
)


def as_input(row: dict[str, Any]) -> dict[str, Any]:
    """읽어 온 값 한 줄을 **다시 보낼 수 있는 모양**으로."""
    kept = {key: row[key] for key in VALUE_FIELDS if row.get(key) is not None}
    kept["definition_id"] = str(row["definition_id"])
    return kept


def key_of(row: dict[str, Any]) -> tuple[str, str, int]:
    """겹치는 자리는 **칸 하나가 아니라 (칸, 묶음, 차례)다.**

    동작 -15 ~ 45 와 저장 -40 ~ 25 는 같은 「시험 온도」 두 줄이다. 칸 이름만 보고 겹친다고
    치면 둘 중 하나가 조용히 사라지고, 그 시험은 저장 조건이 없는 시험이 된다 — 지운 기억이
    없으니 아무도 못 찾는다. 묶음을 안 적은 줄끼리는 예전처럼 칸 하나에 하나다.
    """
    return (
        str(row.get("definition_id") or ""),
        str(row.get("set_label") or ""),
        int(row["step_order"]) if row.get("step_order") is not None else -1,
    )


def merge(
    current: list[dict[str, Any]], incoming: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """지금 있는 것 위에 보낸 줄만 얹는다.

    * **(칸, 묶음, 차례)가 같으면 갈아 끼운다** — 반만 보내도 그 줄 전체가 그 값이 된다
      (한 줄 안에서 `num_min` 만 바꾸고 `num_max` 를 남기는 일은 없다: 구간은 한 값이다).
      묶음(`set_label`)을 안 적으면 **이름 없는 한 벌**을 가리킨다 — 동작/저장처럼 묶음이
      있는 시험에서 묶음 없이 보내면 그 둘이 아니라 세 번째 줄이 생긴다.
    * `remove: true` 면 그 칸을 **뺀다.** 빈 값을 보내는 것으로는 안 지워진다 — 빈 문자열과
      「안 적음」 은 다르다.
    * `definition_id` 가 없는 줄(`new_label`)은 겹칠 자리가 없으니 뒤에 더한다.

    **순서를 지킨다.** 지금 있는 줄의 순서가 먼저고 새 줄이 뒤다 — 카드가 매번 다른 순서로
    읽히면 사람이 「뭐가 바뀌었지」 를 눈으로 못 찾는다.
    """
    kept: dict[tuple[str, str, int], dict[str, Any]] = {
        key_of(row): as_input(row) for row in current if row.get("definition_id")
    }
    fresh: list[dict[str, Any]] = []
    for row in incoming:
        if not row.get("definition_id"):
            fresh.append({one: value for one, value in row.items() if one != "remove"})
            continue
        key = key_of(row)
        if row.get("remove"):
            kept.pop(key, None)
            continue
        kept[key] = {one: value for one, value in row.items() if one != "remove"} | {
            "definition_id": key[0]
        }
    return [*kept.values(), *fresh]

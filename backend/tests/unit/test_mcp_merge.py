"""속성 값 병합 — **통째 교체가 값을 조용히 지우는 것을 막는다.**

신뢰성 시험 카드에는 칸이 스물 넘게 선다. `PATCH` 의 `attributes` 는 보낸 것으로 통째로
갈아 끼우므로, 온도 하나를 고치려고 스물둘을 다시 보내다 하나를 빠뜨리면 그 값이 사라진다
— **지운 기억이 없으니 아무도 못 찾는다.** MCP 의 `set_reliability_attributes` 는 지금 있는
것을 읽어 겹치는 줄만 갈아 끼우고, 그 판단이 여기 있다.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

_PATH = Path(__file__).resolve().parents[3] / "mcp_server" / "merge.py"
_SPEC = importlib.util.spec_from_file_location("mcp_merge", _PATH)
assert _SPEC and _SPEC.loader
merge_module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(merge_module)

merge = merge_module.merge
as_input = merge_module.as_input


def _value(definition_id: str, **over: Any) -> dict[str, Any]:
    """읽을 때 오는 모양 — 서버가 만들어 주는 글자까지 함께 온다."""
    return {
        "definition_id": definition_id,
        "label": "시험 온도",
        "kind": "condition",
        "status": "standard",
        "unit": "degC",
        "display": "-40 ~ 125 degC",
        "num_value": None,
        "num_min": -40,
        "num_max": 125,
        "text_value": None,
        "bool_value": None,
        "date_value": None,
        "term_id": None,
        "term_value": None,
        "method_id": None,
        "method_code": None,
        "document_id": None,
        "document_code": None,
        "json_value": None,
        "note": None,
        **over,
    }


def test_안_보낸_칸은_그대로_남는다() -> None:
    now = [
        _value("d-temp"),
        _value("d-proc", text_value="1. 안정화한다", num_min=None, num_max=None),
        _value("d-doc", document_id="doc-1", num_min=None, num_max=None),
    ]
    after = merge(now, [{"definition_id": "d-temp", "num_min": -55, "num_max": 125}])

    assert len(after) == 3, "하나를 고쳤는데 나머지가 사라지면 안 된다"
    by_id = {row["definition_id"]: row for row in after}
    assert by_id["d-temp"]["num_min"] == -55
    assert by_id["d-proc"]["text_value"] == "1. 안정화한다"
    # **다른 표를 가리키는 값도 살아남는다** — 사내 규격서 링크가 조용히 끊기면 그 시험이
    # 무엇을 따랐는지 알 수 없게 된다.
    assert by_id["d-doc"]["document_id"] == "doc-1"


def test_서버가_만들어_준_글자는_되돌려_보내지_않는다() -> None:
    """`label` · `kind` · `display` 는 읽기용이다. 지금은 무시되지만, 무시되는 것에
    기대면 **오타도 같이 조용해진다**."""
    sent = as_input(_value("d-temp"))
    assert set(sent) == {"definition_id", "unit", "num_min", "num_max"}
    assert "display" not in sent and "kind" not in sent
    # 안 적힌 칸은 아예 안 싣는다 — `None` 을 보내면 「비우라」 는 뜻이 된다.
    assert "text_value" not in sent


def test_지우려면_그렇게_말한다() -> None:
    now = [_value("d-temp"), _value("d-proc", text_value="절차")]
    after = merge(now, [{"definition_id": "d-temp", "remove": True}])
    assert [row["definition_id"] for row in after] == ["d-proc"]
    # **빈 값으로는 안 지워진다** — 빈 문자열과 「안 적음」 은 다르다.
    kept = merge(now, [{"definition_id": "d-proc", "text_value": ""}])
    assert len(kept) == 2
    assert next(row for row in kept if row["definition_id"] == "d-proc")["text_value"] == ""
    # 표식은 서버로 새어 나가지 않는다.
    assert all("remove" not in row for row in after)


def test_새_이름은_뒤에_더한다() -> None:
    """`new_label` 은 겹칠 `definition_id` 가 없다 — 초안이 하나 생긴다."""
    now = [_value("d-temp")]
    after = merge(now, [{"new_label": "시료 수", "new_kind": "number", "num_value": 8}])
    assert len(after) == 2
    assert after[0]["definition_id"] == "d-temp", "있던 것이 앞이다"
    assert after[1]["new_label"] == "시료 수"


def test_순서가_안_흔들린다() -> None:
    """카드가 매번 다른 순서로 읽히면 「뭐가 바뀌었지」 를 눈으로 못 찾는다."""
    now = [_value(f"d-{index}") for index in range(5)]
    after = merge(now, [{"definition_id": "d-3", "num_min": 0, "num_max": 10}])
    assert [row["definition_id"] for row in after] == [f"d-{index}" for index in range(5)]

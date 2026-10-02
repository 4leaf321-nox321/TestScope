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
        "set_label": None,
        "step_order": None,
        "step_label": None,
        # **원문 근거.** 비워 두면 떨어뜨려도 시험이 모른다 — 실제로 그래서 운영에서
        # 잃었다(2026-10-03).
        "source_text": "Operating temperature: -40 to 257 degF",
        "original_value": "-40 to 257",
        "original_unit": "degF",
        **over,
    }


def test_원문_근거를_떨어뜨리지_않는다() -> None:
    """**되찾을 수 없는 것부터 지킨다.**

    `as_input` 이 안 싣는 칸은 `PATCH` 가 통째로 갈아 끼울 때 그 자리에서 사라진다. 한 칸을
    고치면 **안 건드린 줄 전부**가 그렇게 된다 — 운영에서 그렇게 잃었다(2026-10-03).

    `note` 는 옮긴 사람의 해석이라 다시 쓸 수 있지만 원문은 문서를 다시 열어야 나온다.
    `70 degC` 만 남으면 그것이 문서의 값인지 158 °F 를 옮긴 값인지 알 길이 없다.
    """
    sent = as_input(_value("d-temp"))
    assert sent["source_text"] == "Operating temperature: -40 to 257 degF"
    assert sent["original_value"] == "-40 to 257"
    assert sent["original_unit"] == "degF"

    # 겹치지 않는 줄을 고칠 때도 남아 있어야 한다 — 그게 이 고장의 모양이었다.
    done = merge(
        [_value("d-temp"), _value("d-proc")], [{"definition_id": "d-proc", "note": "고침"}]
    )
    kept = next(one for one in done if one["definition_id"] == "d-temp")
    assert kept["original_unit"] == "degF", "안 건드린 줄의 원문 근거가 사라졌다"


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
    assert set(sent) == {
        "definition_id",
        "unit",
        "num_min",
        "num_max",
        # 원문 근거는 **되돌려 보낸다** — 서버가 만들어 준 글자가 아니라 사람이 적은 증거다.
        "source_text",
        "original_value",
        "original_unit",
    }
    assert "display" not in sent and "kind" not in sent
    # 서버가 계산해 주는 것도 안 싣는다 — 판은 값에 붙지만 보내는 쪽이 정하는 것이 아니다.
    assert "document_revision_id" not in sent and "is_current" not in sent
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


def test_묶음이_다르면_다른_줄이다() -> None:
    """동작 -15 ~ 45 와 저장 -40 ~ 25 는 **같은 칸 두 줄**이다.

    칸 이름만 보고 겹친다고 치면 둘 중 하나가 조용히 사라지고, 그 시험은 저장 조건이 없는
    시험이 된다 — 카드에는 온도가 한 줄만 서니 사람은 그것이 전부인 줄 안다.
    """
    now = [
        _value("d-temp", set_label="동작", num_min=-15, num_max=45),
        _value("d-temp", set_label="저장", num_min=-40, num_max=25),
        _value("d-proc", text_value="절차", num_min=None, num_max=None),
    ]
    after = merge(now, [{"definition_id": "d-temp", "set_label": "저장", "num_min": -50}])

    assert len(after) == 3, "묶음이 다른 줄까지 덮으면 안 된다"
    by_set = {row.get("set_label"): row for row in after if row["definition_id"] == "d-temp"}
    assert by_set["동작"]["num_max"] == 45, "동작은 안 건드렸다"
    assert by_set["저장"]["num_min"] == -50 and "num_max" not in by_set["저장"]


def test_차례가_다르면_다른_줄이다() -> None:
    """프로파일 한 벌 — 70 °C 1h -> 25 °C 1h -> 30 °C 1h -> 25 °C 1h."""
    now = [
        _value(
            "d-temp",
            set_label="온도 사이클",
            step_order=step,
            num_value=value,
            num_min=None,
            num_max=None,
        )
        for step, value in enumerate([70, 25, 30, 25], 1)
    ]
    after = merge(
        now,
        [
            {
                "definition_id": "d-temp",
                "set_label": "온도 사이클",
                "step_order": 3,
                "num_value": 35,
            },
        ],
    )
    assert len(after) == 4
    assert [row["num_value"] for row in after] == [70, 25, 35, 25]


def test_묶음_없이_보내면_이름_없는_한_벌이다() -> None:
    """묶음이 있는 시험에 묶음 없이 보내면 **그 둘이 아니라 세 번째 줄**이다.

    묶음을 안 적은 것을 「아무거나 하나」 로 받아 주면, 동작에 걸릴지 저장에 걸릴지 보낸
    쪽이 모르는 채로 값이 들어간다.
    """
    now = [
        _value("d-temp", set_label="동작", num_min=-15, num_max=45),
        _value("d-temp", set_label="저장", num_min=-40, num_max=25),
    ]
    after = merge(now, [{"definition_id": "d-temp", "num_min": 0, "num_max": 60}])
    assert len(after) == 3
    assert after[2].get("set_label") is None


def test_묶음은_되돌려_보내는_칸이다() -> None:
    """`set_label` 을 안 실으면, 고칠 때마다 묶음이 풀려 한 줄로 뭉개진다."""
    sent = as_input(_value("d-temp", set_label="동작", step_order=2, step_label="유지"))
    assert sent["set_label"] == "동작"
    assert sent["step_order"] == 2 and sent["step_label"] == "유지"


def test_묶음까지_같아야_지워진다() -> None:
    now = [
        _value("d-temp", set_label="동작", num_min=-15, num_max=45),
        _value("d-temp", set_label="저장", num_min=-40, num_max=25),
    ]
    after = merge(now, [{"definition_id": "d-temp", "set_label": "동작", "remove": True}])
    assert len(after) == 1 and after[0]["set_label"] == "저장"

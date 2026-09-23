"""항목 값을 사람이 읽는 한 줄로 — 화면·MCP·의미 색인 카드가 **같은 글자**를 쓴다.

모듈(`attributes`)이 아니라 여기 있는 이유: 의미 색인(`shared/semantic.py`)도 이 글자를
카드에 넣어야 하고, shared 는 모듈을 부르지 않는다.
"""

from __future__ import annotations

from datetime import date
from typing import Any


def _number(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


def display_attribute(
    kind: str,
    *,
    num_value: float | None = None,
    num_min: float | None = None,
    num_max: float | None = None,
    unit: str = "",
    text_value: str | None = None,
    bool_value: bool | None = None,
    date_value: date | None = None,
    term_value: str | None = None,
    method_code: str | None = None,
    json_value: Any | None = None,
) -> str:
    """「-40 ~ 125 degC」 「85 %」 「ISO 6892-1」 「있음」. 비어 있으면 빈 글자."""
    suffix = f" {unit}" if unit else ""
    if kind == "number":
        return f"{_number(num_value)}{suffix}" if num_value is not None else ""
    if kind in ("range", "condition"):
        low = _number(num_min) if num_min is not None else ""
        high = _number(num_max) if num_max is not None else ""
        if low and high:
            return f"{low} ~ {high}{suffix}"
        if low:
            return f"{low}{suffix} 이상"
        return f"{high}{suffix} 이하" if high else ""
    if kind in ("text", "choice"):
        return text_value or ""
    if kind == "boolean":
        if bool_value is None:
            return ""
        return "있음" if bool_value else "없음"
    if kind == "date":
        return date_value.isoformat() if date_value else ""
    if kind == "term":
        return term_value or ""
    if kind == "method":
        return method_code or ""
    if kind == "pairs":
        return _pairs_text(json_value, suffix)
    if kind == "matrix":
        rows = json_value if isinstance(json_value, list) else []
        parts = [
            f"{clean_label(one)}: {_pairs_text(one.get('entries'), suffix)}"
            for one in rows
            if isinstance(one, dict) and _pairs_text(one.get("entries"), suffix)
        ]
        return " | ".join(parts)
    return ""


def clean_label(row: dict[str, Any]) -> str:
    return str(row.get("label") or "").strip()


def _pairs_text(rows: Any, suffix: str) -> str:
    """「A등급 4개 · B등급 4개」. **글자를 서버가 만든다** — 화면·MCP·색인 카드가 같은 말을
    쓰게 하려는 것이고, 찾기도 이 글자를 훑는다."""
    if not isinstance(rows, list):
        return ""
    parts = []
    for one in rows:
        if not isinstance(one, dict):
            continue
        label = clean_label(one)
        value = one.get("value")
        if not label or value is None:
            continue
        parts.append(f"{label} {_number(float(value))}{suffix}")
    return " · ".join(parts)

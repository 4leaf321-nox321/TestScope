"""도구 호출 자취 — **AI 가 무엇을, 어떤 순서로, 빈손으로 몇 번 불렀나.**

답이 맞았는지는 답만 보면 되지만, AI 가 헤맸는지는 **자취**를 봐야 안다. 「인장 되는 장비
있나」 에 도구를 셋 부르는 것과 열둘 부르는 것은 답이 같아도 다른 일이다 — 열둘 부르는 동안
컨텍스트를 태우고, 도중에 엉뚱한 도구를 누를 확률이 는다. 이 자취가 `eval/score.py` 의 재료다.

켜는 법: `TESTSCOPE_MCP_TRACE` 환경변수. `1` 이면 `logs/calls.jsonl`, 경로를 주면 그 파일.
기본은 **꺼짐** — 운영에서 파일이 끝없이 자라면 안 된다. 켜면 호출마다 한 줄(JSONL):

    {"ts": …, "session": …, "tool": "resolve", "args": {...}, "ms": 41,
     "ok": true, "empty": false, "error": null}

`empty` 는 「불렀는데 아무것도 못 얻었다」 — 목록이 비었거나, resolve 가 none 이거나, 검색이
0건. 빈손 호출이 많다는 것은 AI 가 무엇을 물어야 할지 모른 채 더듬고 있다는 뜻이다.

토큰·비밀번호는 인자에 안 온다(자격은 헤더로 가고 여기 안 적는다). 긴 인자는 잘라 적는다 —
대장 반입의 2000줄을 자취에 남길 일이 아니다.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: 인자 값 하나를 자취에 적을 때의 길이 상한. 붙여넣은 표(import_equipment) 같은 것은
#: 앞머리만 남긴다 — 무엇을 불렀는지는 그것으로 충분히 보인다.
ARG_LIMIT = 200

_SESSION = (
    os.environ.get("TESTSCOPE_MCP_SESSION")
    or datetime.now(UTC).strftime("%Y%m%dT%H%M%S-") + uuid.uuid4().hex[:4]
)


def trace_path() -> Path | None:
    """자취를 적을 파일. 꺼져 있으면 None."""
    raw = os.environ.get("TESTSCOPE_MCP_TRACE", "").strip()
    if not raw or raw.lower() in ("0", "off", "false"):
        return None
    if raw in ("1", "on", "true"):
        return Path(__file__).parent / "logs" / "calls.jsonl"
    return Path(raw)


def _shorten(value: Any) -> Any:
    if isinstance(value, str) and len(value) > ARG_LIMIT:
        return value[:ARG_LIMIT] + f"…(+{len(value) - ARG_LIMIT}자)"
    if isinstance(value, list):
        return [_shorten(one) for one in value[:20]] + (["…"] if len(value) > 20 else [])
    if isinstance(value, dict):
        return {key: _shorten(one) for key, one in value.items()}
    return value


def looks_empty(result: Any) -> bool:
    """불렀는데 아무것도 못 얻었나 — 도구 응답의 모양으로 판단한다.

    `_listed` 는 {key: [...], count}, 쪽 목록은 {items, total}, resolve 는 {match},
    검색은 {hits, total}. 오류 봉투는 빈손이 아니라 **오류**로 따로 센다.
    """
    if not isinstance(result, dict) or "error" in result:
        return False
    if result.get("match") == "none":
        return True
    if "total" in result and result.get("total") == 0:
        return True
    if "count" in result and result.get("count") == 0:
        return True
    for key in ("items", "hits", "candidates"):
        if key in result and isinstance(result[key], list) and not result[key]:
            return True
    return False


def record(
    tool: str, arguments: dict[str, Any], result: Any, started: float, *, path: Path | None
) -> None:
    """한 줄 적는다. 적다 실패해도 도구 호출을 죽이지 않는다 — 자취는 덤이다."""
    if path is None:
        return
    error = result.get("error") if isinstance(result, dict) and "error" in result else None
    row = {
        "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "session": _SESSION,
        "tool": tool,
        "args": _shorten(arguments),
        "ms": int((time.perf_counter() - started) * 1000),
        "ok": error is None,
        "empty": looks_empty(result),
        "error": str(error)[:ARG_LIMIT] if error is not None else None,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as out:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


def mark(event: str, **fields: Any) -> None:
    """물음의 경계 같은 **표식** 한 줄 — 채점기가 자취를 물음별로 자르는 데 쓴다.

    실행기(eval/run.py)가 물음마다 하나씩 적고, 사람이 손으로 물을 때는 `eval/mark.py` 로
    적는다. 표식이 없으면 채점기는 시간 간격으로 자른다(덜 정확하다).
    """
    path = trace_path()
    if path is None:
        return
    row = {
        "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "session": _SESSION,
        "event": event,
        **fields,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as out:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass

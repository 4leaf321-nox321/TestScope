r"""자취를 채점한다 — **답이 아니라 도구 호출의 자취를.**

「인장 되는 장비 있나」 에 도구를 셋 부르는 것과 열둘 부르는 것은 답이 같아도 다른 일이다.
열둘 부르는 동안 컨텍스트를 태우고, 도중에 엉뚱한 도구를 누를 확률이 는다. 답만 채점하면
이 차이가 안 보인다. 그래서 물음마다 **기대하는 자취**를 두고(questions.json) 실제 자취
(logs/calls.jsonl)를 그것에 견준다.

    .\.venv\Scripts\python.exe eval\score.py                    # logs\calls.jsonl 전체
    .\.venv\Scripts\python.exe eval\score.py --session 2026…    # 그 세션만
    .\.venv\Scripts\python.exe eval\score.py --save             # eval\runs\ 에 남긴다

물음의 경계는 자취 속 표식(`{"event": "question", "id": "q07"}`)으로 자른다 — 실행기
(run.py)가 적고, 사람이 손으로 물을 때는 `mark.py q07` 로 적는다. 표식이 없으면 시간 간격
(`--gap` 초, 기본 90)으로 자르고 물음 순서대로 붙인다: 덜 정확하니 결과에 그렇다고 적는다.

## 점수

물음마다 다섯 항목, 항목당 1점.

    호출 수      max_calls 안인가
    시작        첫 두 호출 중 하나가 start_with 에 있나 — 길잡이가 먹혔나
    필수        must_call 을 전부 거쳤나
    금지        must_not_call 을 하나도 안 눌렀나
    빈손        빈손 호출(empty)이 호출 수의 절반 미만인가

이 점수는 **오르내림을 보는 자**다. 한 번에 1~2점은 LLM 이 매번 조금씩 다르게 답해서
생기는 흔들림이고, 그래서 CI 에 안 넣는다. 도구 설명·길잡이·resolve 를 고친 뒤 다시 돌려
지난 기록(eval/runs, baseline.json)과 견준다.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
QUESTIONS = HERE / "questions.json"
DEFAULT_LOG = HERE.parent / "logs" / "calls.jsonl"
RUNS = HERE / "runs"

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(errors="replace")


@dataclass
class Episode:
    """물음 하나에 대한 자취 — 호출 줄들."""

    question_id: str | None
    calls: list[dict[str, Any]] = field(default_factory=list)


def load_questions(path: Path = QUESTIONS) -> list[dict[str, Any]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = doc["questions"]
    return rows


def load_rows(path: Path, session: str | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if session and row.get("session") != session:
            continue
        rows.append(row)
    return rows


def _parse_ts(raw: str) -> datetime:
    return datetime.fromisoformat(raw)


def split_episodes(
    rows: list[dict[str, Any]], *, gap_seconds: float
) -> tuple[list[Episode], bool]:
    """자취를 물음별로 자른다. 표식이 있으면 표식으로, 없으면 시간 간격으로.

    돌려주는 둘째 값은 「표식으로 잘랐나」 — 아니면 결과에 「덜 정확함」 을 적는다.
    """
    marked = any(row.get("event") == "question" for row in rows)
    episodes: list[Episode] = []
    if marked:
        current: Episode | None = None
        for row in rows:
            if row.get("event") == "question":
                current = Episode(question_id=row.get("id"))
                episodes.append(current)
            elif "tool" in row and current is not None:
                current.calls.append(row)
        return episodes, True

    last: datetime | None = None
    for row in rows:
        if "tool" not in row:
            continue
        now = _parse_ts(row["ts"])
        if last is None or (now - last).total_seconds() > gap_seconds:
            episodes.append(Episode(question_id=None))
        episodes[-1].calls.append(row)
        last = now
    return episodes, False


def score_episode(question: dict[str, Any], episode: Episode) -> dict[str, Any]:
    tools = [one["tool"] for one in episode.calls]
    head = set(tools[:2])
    empties = sum(1 for one in episode.calls if one.get("empty"))
    checks = {
        "호출 수": len(tools) <= int(question.get("max_calls", 99)),
        "시작": bool(head & set(question.get("start_with", []))) if tools else False,
        "필수": all(one in tools for one in question.get("must_call", [])),
        "금지": not any(one in tools for one in question.get("must_not_call", [])),
        "빈손": (empties * 2 < len(tools)) if tools else False,
    }
    return {
        "id": question["id"],
        "text": question["text"],
        "calls": len(tools),
        "empty": empties,
        "trace": tools,
        "checks": checks,
        "score": sum(1 for ok in checks.values() if ok),
        "max": len(checks),
    }


def score(
    rows: list[dict[str, Any]], questions: list[dict[str, Any]], *, gap_seconds: float
) -> dict[str, Any]:
    episodes, marked = split_episodes(rows, gap_seconds=gap_seconds)
    by_id = {one["id"]: one for one in questions}
    results: list[dict[str, Any]] = []
    if marked:
        for episode in episodes:
            question = by_id.get(episode.question_id or "")
            if question is None:
                continue
            results.append(score_episode(question, episode))
    else:
        # 표식이 없다 — 물음 순서대로 붙인다. 하나라도 건너뛰었으면 그 뒤가 다 밀린다.
        for question, episode in zip(questions, episodes, strict=False):
            results.append(score_episode(question, episode))
    total = sum(one["score"] for one in results)
    possible = sum(one["max"] for one in results)
    return {
        "at": datetime.now().isoformat(timespec="seconds"),
        "marked": marked,
        "answered": len(results),
        "of": len(questions),
        "score": total,
        "possible": possible,
        "calls_total": sum(one["calls"] for one in results),
        "empty_total": sum(one["empty"] for one in results),
        "results": results,
    }


def render(report: dict[str, Any]) -> str:
    lines = [
        f"물음 {report['answered']}/{report['of']}"
        f" · 점수 {report['score']}/{report['possible']}"
        f" · 호출 {report['calls_total']}회 · 빈손 {report['empty_total']}회"
        + ("" if report["marked"] else " · (표식 없음 — 시간 간격으로 잘라 덜 정확함)")
    ]
    for one in report["results"]:
        failed = [name for name, ok in one["checks"].items() if not ok]
        mark = "  ok" if not failed else "실패"
        lines.append(
            f"  {mark} {one['id']} {one['score']}/{one['max']}  호출 {one['calls']}"
            f"  {' · '.join(failed) if failed else ''}"
        )
        lines.append(f"       {' -> '.join(one['trace']) or '(호출 없음)'}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP 도구 자취 채점")
    parser.add_argument("--log", default=str(DEFAULT_LOG))
    parser.add_argument("--session", default=None)
    parser.add_argument("--gap", type=float, default=90.0)
    parser.add_argument(
        "--save", action="store_true", help="eval/runs/<시각>.json 으로 남긴다"
    )
    parser.add_argument(
        "--baseline", action="store_true", help="eval/baseline.json 으로 굳힌다"
    )
    args = parser.parse_args()

    log = Path(args.log)
    if not log.exists():
        print(
            f"자취가 없습니다: {log} — 서버를 -Trace 로 띄우고 물음을 던진 뒤 다시 돌리세요."
        )
        return 1
    report = score(load_rows(log, args.session), load_questions(), gap_seconds=args.gap)
    print(render(report))

    baseline = HERE / "baseline.json"
    if baseline.exists() and not args.baseline:
        before = json.loads(baseline.read_text(encoding="utf-8"))
        delta = report["score"] - before["score"]
        print(
            f"\n기준선 {before['score']}/{before['possible']} ({before['at']}) 대비 "
            f"{'+' if delta >= 0 else ''}{delta}"
        )
    if args.save or args.baseline:
        RUNS.mkdir(exist_ok=True)
        target = baseline if args.baseline else RUNS / f"{report['at'].replace(':', '')}.json"
        target.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"저장: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

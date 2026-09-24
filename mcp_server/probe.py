r"""MCP 도구를 **진짜 클라이언트처럼** 왕복해 본다.

HTTP 로 같은 엔드포인트를 부르면 멀쩡한데 도구로는 죽는 어긋남이 있다(반환 표기
검증). 그런 것은 이렇게 한 번 돌려 봐야만 드러난다.

    .\.venv\Scripts\python.exe probe.py
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys
from typing import Any

import server

# **못 쓰는 글자를 만나도 출력이 죽지 않게 한다.** CP949 콘솔은 em dash 를 못 찍는데,
# 백엔드 안내문에는 그것이 들어 있다 — 그러면 다 끝난 확인이 traceback 으로 끝난다
# (backend/scripts/_console.py 와 같은 처방. 인코딩은 그대로 두고 errors 만 푼다).
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(errors="replace")


class _Ctx:
    """Context 대신. 도구가 보는 것은 헤더뿐이다."""

    def __init__(self, token: str) -> None:
        self.headers = {"Authorization": f"Bearer {token}"}


def _short(value: Any, limit: int = 90) -> str:
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + "…"


def token() -> str | None:
    """개인 토큰 — 환경변수 `TESTSCOPE_PAT` 가 먼저, 다음이 `.pat` 파일.

    CI 는 환경변수로 준다(러너에 파일을 남기지 않게). 개발 PC 는 파일이 편하다.
    """
    given = os.environ.get("TESTSCOPE_PAT", "").strip()
    if given:
        return given
    pat = pathlib.Path(__file__).parent / ".pat"
    return pat.read_text(encoding="utf-8").strip() if pat.exists() else None


async def main() -> int:
    raw = token()
    if raw is None:
        print("개인 토큰이 없습니다. TESTSCOPE_PAT 환경변수나 .pat 파일에 넣으세요.")
        return 1
    ctx = _Ctx(raw)

    print(f"백엔드 {server.API_BASE}\n")
    print("안내", len(server.get_guide()), "자")

    # **닿는지 먼저 본다.** 백엔드가 꺼져 있으면 도구마다 같은 오류가 스무 줄 찍히고,
    # 그 뒤 응답을 기대하는 자리에서 KeyError 로 죽는다 — 원인(서버가 안 떠 있다)은
    # 그 스무 줄과 traceback 사이에 묻힌다. 그러면 확인하려던 것은 아무것도 못 본다.
    reachable = await server.list_conditions(ctx)
    if isinstance(reachable, dict) and "error" in reachable:
        print(f"\n  {reachable['error']}")
        print("  백엔드를 먼저 띄우세요 — backend\\run.py (개발은 PORT+1).")
        return 1

    checks: list[tuple[str, Any]] = [
        (
            "resolve(series, 6800)",
            server.resolve(ctx, "series", "6800 Series Universal Testing Systems"),
        ),
        ("resolve(term, 인장)", server.resolve(ctx, "term", "인장", axis="test_item")),
        ("list_conditions", server.list_conditions(ctx)),
        ("search_series(6800)", server.search_series(ctx, q="6800", limit=2)),
        ("search_models(68FM)", server.search_models(ctx, q="68FM", limit=3)),
        ("search_equipment", server.search_equipment(ctx, limit=3)),
        ("list_pending_work", server.list_pending_work(ctx)),
        ("list_spec_sources", server.list_spec_sources(ctx, q="instron")),
        ("list_reference", server.list_reference(ctx)),
        ("list_axes", server.list_axes(ctx)),
        ("list_terms(test_item)", server.list_terms(ctx, "test_item", q="인장")),
        ("list_reliability_tests", server.list_reliability_tests(ctx)),
        (
            "list_attribute_definitions",
            server.list_attribute_definitions(ctx, "reliability_test"),
        ),
        ("list_review_queues", server.list_review_queues(ctx)),
        ("graph_overview", server.graph_overview(ctx)),
        ("graph_search(인장)", server.graph_search(ctx, "인장")),
    ]
    bad = 0
    for label, coro in checks:
        got = await coro
        failed = isinstance(got, dict) and "error" in got
        bad += failed
        # **기호를 쓰지 않는다.** CP949 콘솔이 ✓ 를 못 찍어 거기서 죽는다.
        print(f"  {'실패' if failed else '  ok'} {label:34s} {_short(got)}")

    # 검색 — 이 시스템이 존재하는 이유. **축이 없으면 그렇다고 말하고 끝낸다** —
    # 그 설치는 온톨로지를 아직 안 심은 것이고, 그것은 오류가 아니라 상태다.
    force = next(
        (one for one in reachable.get("conditions", []) if one["key"] == "force"), None
    )
    items = await server.resolve(ctx, "term", "인장", axis="test_item")
    if force is None:
        print("\n  조건축 force 가 없습니다 — 검색 확인은 건너뜁니다(온톨로지를 심으세요).")
    elif items.get("match") == "exact":
        found = await server.search_test_items(
            ctx,
            test_item_term_id=items["id"],
            conditions=[{"condition_key_id": force["id"], "at_least": 20}],
        )
        hits = found.get("hits", [])
        print(f"\n  검색 「인장 · 20 kN 이상」 -> {len(hits)}건")
        for hit in hits[:3]:
            print(f"    {hit['equipment_name'][:26]:26s} {hit['verdict']}")

        # 그래프 — 검색이 준 노드 id 가 이웃 도구에 그대로 먹히나.
        near = await server.graph_neighbors(ctx, f"test_item:{items['id']}")
        if "error" in near:
            bad += 1
            print(f"\n  실패 graph_neighbors {_short(near)}")
        else:
            print(
                f"\n  그래프 「인장」 이웃 -> 노드 {len(near['nodes'])}"
                f" · 관계 {len(near['edges'])}"
            )
    else:
        print(
            f"\n  시험 항목 「인장」 을 못 찾아 검색 확인은 건너뜁니다({items.get('match')})."
        )
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

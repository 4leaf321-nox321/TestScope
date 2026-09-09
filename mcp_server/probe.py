"""MCP 도구를 **진짜 클라이언트처럼** 왕복해 본다.

HTTP 로 같은 엔드포인트를 부르면 멀쩡한데 도구로는 죽는 어긋남이 있다(반환 표기
검증). 그런 것은 이렇게 한 번 돌려 봐야만 드러난다.

    .\.venv\Scripts\python.exe probe.py
"""

from __future__ import annotations

import asyncio
import json
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


async def main() -> int:
    pat = pathlib.Path(__file__).parent / ".pat"
    if not pat.exists():
        print("개인 토큰이 없습니다. .pat 파일에 넣으세요.")
        return 1
    ctx = _Ctx(pat.read_text(encoding="utf-8").strip())

    print(f"백엔드 {server.API_BASE}\n")
    print("안내", len(server.get_guide()), "자")

    checks: list[tuple[str, Any]] = [
        ("resolve(series, 6800)", server.resolve(ctx, "series", "6800 Series Universal Testing Systems")),
        ("resolve(term, 인장)", server.resolve(ctx, "term", "인장", axis="test_item")),
        ("list_conditions", server.list_conditions(ctx)),
        ("search_series(6800)", server.search_series(ctx, q="6800", limit=2)),
        ("search_models(68FM)", server.search_models(ctx, q="68FM", limit=3)),
        ("search_equipment", server.search_equipment(ctx, limit=3)),
        ("list_pending_work", server.list_pending_work(ctx)),
        ("list_spec_sources", server.list_spec_sources(ctx, q="instron")),
    ]
    bad = 0
    for label, coro in checks:
        got = await coro
        failed = isinstance(got, dict) and "error" in got
        bad += failed
        # **기호를 쓰지 않는다.** CP949 콘솔이 ✓ 를 못 찍어 거기서 죽는다.
        print(f"  {'실패' if failed else '  ok'} {label:34s} {_short(got)}")

    # 검색 — 이 시스템이 존재하는 이유.
    conditions = await server.list_conditions(ctx)
    force = next(one for one in conditions["conditions"] if one["key"] == "force")
    items = await server.resolve(ctx, "term", "인장", axis="test_item")
    if items.get("match") == "exact":
        found = await server.search_capabilities(
            ctx,
            test_item_term_id=items["id"],
            conditions=[{"condition_key_id": force["id"], "at_least": 20}],
        )
        hits = found.get("hits", [])
        print(f"\n  검색 「인장 · 20 kN 이상」 -> {len(hits)}건")
        for hit in hits[:3]:
            print(f"    {hit['equipment_name'][:26]:26s} {hit['verdict']}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

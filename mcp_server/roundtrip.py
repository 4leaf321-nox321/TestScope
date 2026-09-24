r"""MCP 도구를 **진짜로 불러** 한 바퀴 — 읽고, 넣고, 되찾고, 판정까지. CI 가 매 푸시 돌린다.

curl 로는 멀쩡한데 도구로는 죽는 고장(반환 모양 검증 · 경로 오타)은 이렇게 불러 봐야만
드러난다. 도구가 41개일 때 넷이 죽어 있던 것이 그 예다 — 실제로 부른 사람에게만 드러났다.

    $env:TESTSCOPE_PAT = python backend\scripts\mcp_probe_account.py mint
    .\.venv\Scripts\python.exe roundtrip.py            # 읽기만
    .\.venv\Scripts\python.exe roundtrip.py --write    # 쓰기 사슬까지 (cleanup 이 지운다)

읽기 묶음은 probe.py 의 것을 그대로 쓴다 — 두 벌이면 한쪽만 고쳐진다. 쓰기 사슬이 만드는
것에는 전부 「MCP확인」 표가 붙고, `mcp_probe_account.py cleanup` 이 그것으로 찾아 지운다.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from typing import Any

import probe
import server

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(errors="replace")


class _Ctx:
    def __init__(self, token: str) -> None:
        self.headers = {"Authorization": f"Bearer {token}"}


def _short(value: Any, limit: int = 100) -> str:
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + "…"


async def _write_chain(ctx: _Ctx) -> int:
    """넣고 → 되찾고 → 판정 → 그래프. 하나라도 오류면 1."""
    tag = uuid.uuid4().hex[:6]
    bad = 0

    def step(label: str, got: Any, keys: list[str] | None = None) -> Any:
        nonlocal bad
        failed = isinstance(got, dict) and "error" in got
        bad += failed
        view = {key: got.get(key) for key in keys} if keys and not failed else got
        print(f"  {'실패' if failed else '  ok'} {label:34s} {_short(view)}")
        return None if failed else got

    def expect_refusal(label: str, got: Any) -> None:
        nonlocal bad
        refused = isinstance(got, dict) and "error" in got
        bad += not refused
        print(f"  {'  ok' if refused else '실패'} {label:34s} {_short(got, 70)}")

    print(f"\n쓰기 사슬 (표 {tag})")
    # 1. 기준정보 값 — 만들기 전에 찾고, 같은 이름은 거절되어야 한다.
    step(
        "resolve(없는 값)",
        await server.resolve(ctx, "term", f"MCP확인 인장-{tag}", axis="test_item"),
        ["match"],
    )
    term = step(
        "create_term",
        await server.create_term(ctx, "test_item", f"MCP확인 인장-{tag}"),
        ["id"],
    )
    if term is None:
        return 1
    expect_refusal(
        "create_term(중복) -> 거절",
        await server.create_term(ctx, "test_item", f"MCP확인 인장-{tag}"),
    )

    # 2. 조건 축에 이어진 속성 정의 — 이것이 있어야 판정이 된다.
    conditions = await server.list_conditions(ctx)
    temperature = next(
        (one for one in conditions.get("conditions", []) if one["key"] == "temperature"), None
    )
    if temperature is None:
        print("  실패 조건축 temperature 가 없습니다 — seed_install.py 를 먼저 돌리세요.")
        return 1
    definition = step(
        "create_attribute_definition",
        await server.create_attribute_definition(
            ctx,
            target="reliability_test",
            label=f"MCP확인 시험 온도-{tag}",
            kind="condition",
            key=f"mcp_temp_{tag}",
            unit="degC",
            condition_key_id=temperature["id"],
            status="standard",
        ),
        ["key"],
    )
    if definition is None:
        return 1

    # 3. 신뢰성 시험 — 시험 항목과 조건을 함께.
    workspaces = step("list_workspaces", await server.list_workspaces(ctx), ["count"])
    if not workspaces or not workspaces.get("workspaces"):
        return 1
    slug = workspaces["workspaces"][0]["slug"]
    test = step(
        "create_reliability_test",
        await server.create_reliability_test(
            ctx,
            workspace_slug=slug,
            name=f"MCP확인 열충격-{tag}",
            purpose="MCP 왕복 확인",
            test_item_term_ids=[term["id"]],
            attributes=[
                {
                    "definition_id": definition["id"],
                    "num_min": -40,
                    "num_max": 125,
                    "unit": "degC",
                }
            ],
        ),
        ["name"],
    )
    if test is None:
        return 1
    shown = [one["display"] for one in test["attributes"]]
    if shown != ["-40 ~ 125 degC"]:
        bad += 1
        print(f"  실패 속성 표시가 다릅니다: {shown}")
    # **기계 자격으로 올린 것은 후보다**(ADR 0009). 확정으로 서면 사람 확인을 건너뛴
    # 것이므로 그 자체가 고장이다.
    if test.get("status") != "candidate":
        bad += 1
        print(f"  실패 후보로 서야 하는데 status={test.get('status')!r}")

    # 4. 되찾기 — 걸려야 할 것은 걸리고, 안 걸릴 것은 진단이 온다.
    #
    # `status="all"` 을 준다: 전사 목록은 **확정된 것만** 내고 방금 만든 것은 후보라
    # 안 나온다. 이것을 안 주면 왕복이 「못 찾았다」 로 끝난다(실측 2026-09-24, CI).
    hot = step(
        "list_reliability_tests(>=100)",
        await server.list_reliability_tests(
            ctx, attr=[f"mcp_temp_{tag}>=100"], status="all"
        ),
        ["count"],
    )
    if hot is not None and hot.get("count", 0) < 1:
        bad += 1
        print("  실패 속성 조건으로 되찾지 못했습니다")
    cold = step(
        "list_reliability_tests(>=200)",
        await server.list_reliability_tests(
            ctx, attr=[f"mcp_temp_{tag}>=200"], status="all"
        ),
        ["count"],
    )
    diagnosis = cold.get("diagnosis") if cold is not None else None
    if cold is not None and not (isinstance(diagnosis, list) and diagnosis):
        # 진단 자리에 오류 봉투가 오면(옛 서버 — /diagnose 가 없다) 그것도 실패다.
        bad += 1
        print(f"  실패 0건인데 진단이 안 붙었습니다: {_short(diagnosis, 80)}")
    elif isinstance(diagnosis, list):
        print(f"       진단: {diagnosis[0]['hint']}")

    # 5. 판정 · 6. 그래프 · 7. 고치기.
    step(
        "test_capability",
        await server.test_capability(ctx, test["id"]),
        ["conditions_asked", "skipped"],
    )
    step(
        "graph_node(새 시험)",
        await server.graph_node(ctx, f"reliability_test:{test['id']}"),
        ["label", "related_total"],
    )
    fixed = step(
        "update_reliability_test",
        await server.update_reliability_test(ctx, test["id"], purpose="고침 확인"),
        ["purpose"],
    )
    if fixed is not None and len(fixed.get("test_items", [])) != 1:
        bad += 1
        print("  실패 안 보낸 칸(시험 항목)이 바뀌었습니다")

    # 8. 규격과 요구 조건 — 표기만 다른 중복은 거절되어야 한다.
    method = step(
        "create_method",
        await server.create_method(ctx, code=f"MCP {tag}", title="MCP확인 규격"),
        ["code"],
    )
    if method is not None:
        force = next((one for one in conditions["conditions"] if one["key"] == "force"), None)
        if force is not None:
            step(
                "set_requirement",
                await server.set_requirement(ctx, method["id"], force["id"], min_value=20000),
                ["min_value"],
            )
        expect_refusal(
            "create_method(표기만 다른 중복)",
            await server.create_method(ctx, code=f"MCP  {tag}", title="중복"),
        )

    # 9. 물성 연결은 제안으로만 들어가야 한다.
    prop = await server.create_term(ctx, "property", f"MCP확인 항복강도-{tag}")
    if "error" not in prop:
        link = step(
            "suggest_property_link",
            await server.suggest_property_link(ctx, term["id"], prop["id"], note="ISO 6892-1"),
            ["status", "source"],
        )
        if link is not None and (link.get("status"), link.get("source")) != (
            "suggested",
            "agent",
        ):
            bad += 1
            print("  실패 AI 가 낸 연결이 제안이 아닙니다")
    return 1 if bad else 0


async def main() -> int:
    token = probe.token()
    if token is None:
        print("개인 토큰이 없습니다. TESTSCOPE_PAT 환경변수나 .pat 파일에 넣으세요.")
        return 1
    # 읽기 묶음 — probe 의 것 그대로. 두 벌이면 한쪽만 고쳐진다.
    code = await probe.main()
    if code != 0:
        return code
    if "--write" in sys.argv:
        return await _write_chain(_Ctx(token))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

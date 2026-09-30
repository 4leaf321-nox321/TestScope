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
import io
import json
import sys
import uuid
import zipfile
from typing import Any

import httpx
import probe
import server

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(errors="replace")


#: 그림 한 장이 든 워드 한 벌 — 진짜 .docx 의 최소 모양(zip + document.xml + media).
_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d4944415478da6364f8cf000000030101002718e3660000000049454e44ae426082"
)


def _docx() -> bytes:
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    r = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    body = (
        '<w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr>'
        "<w:r><w:t>MCP확인 절차</w:t></w:r></w:p>"
        f'<w:p><w:r><w:t>시편 장착</w:t></w:r><w:r><w:drawing><wp:inline xmlns:wp="x">'
        f'<a:graphic xmlns:a="{a}"><a:blip r:embed="rId9"/></a:graphic>'
        "</wp:inline></w:drawing></w:r></w:p>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "word/document.xml",
            f'<?xml version="1.0"?><w:document xmlns:w="{w}" xmlns:r="{r}">'
            f"<w:body>{body}</w:body></w:document>",
        )
        archive.writestr(
            "word/_rels/document.xml.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org'
            '/package/2006/relationships"><Relationship Id="rId9" Target="media/a.png"/>'
            "</Relationships>",
        )
        archive.writestr("word/media/a.png", _PNG)
    return buffer.getvalue()


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
    # 1. 온톨로지 값 — 만들기 전에 찾고, 같은 이름은 거절되어야 한다.
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
    #
    # **시험은 부서가 아니라 사업부에 산다**(0037). 올릴 수 있는 사업부를 먼저 묻는다 —
    # 지어낸 코드를 주면 404 이고, 못 올리는 사업부를 주면 403 이다.
    divisions = step("list_divisions", await server.list_divisions(ctx), ["count"])
    if not divisions or not divisions.get("divisions"):
        return 1
    mine = [one for one in divisions["divisions"] if one.get("can_register")]
    if not mine:
        print("  실패 올릴 수 있는 사업부가 없습니다 — 부서에 사업부가 안 붙었습니다")
        return 1
    code = mine[0]["code"]
    test = step(
        "create_reliability_test",
        await server.create_reliability_test(
            ctx,
            division_code=code,
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
        await server.list_reliability_tests(ctx, attr=[f"mcp_temp_{tag}>=100"], status="all"),
        ["count"],
    )
    if hot is not None and hot.get("count", 0) < 1:
        bad += 1
        print("  실패 속성 조건으로 되찾지 못했습니다")
    cold = step(
        "list_reliability_tests(>=200)",
        await server.list_reliability_tests(ctx, attr=[f"mcp_temp_{tag}>=200"], status="all"),
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
    # 7-1. 규격서 반입 사슬 — **바이트가 모델을 안 거치는 길**이 실제로 도는지.
    #
    # 티켓으로 올리고 · 서버가 zip 을 풀고 · id 로 가리킨다. 셋 다 살아 있는 서버에서만
    # 드러나는 자리다(원시 몸통 스트리밍 · zip 풀기 · 첨부 공유).
    ticket = step(
        "create_upload_ticket", await server.create_upload_ticket(ctx), ["expires_in_seconds"]
    )
    if ticket is not None and ticket.get("ticket"):
        put = httpx.post(
            f"{server.API_BASE}/attachments/upload-with-ticket",
            params={
                "target": "reliability_test",
                "object_id": test["id"],
                "filename": "MCP확인.docx",
            },
            content=_docx(),
            headers={"X-Upload-Ticket": ticket["ticket"]},
            timeout=30.0,
        )
        ok = put.status_code == 201
        bad += not ok
        print(f"  {'  ok' if ok else '실패'} {'티켓으로 올리기':34s} {put.status_code}")
        if ok:
            pulled = step(
                "extract_document_images",
                await server.extract_document_images(ctx, put.json()["id"]),
                ["extracted"],
            )
            images = (pulled or {}).get("images") or []
            if pulled is not None and len(images) != 1:
                bad += 1
                print(f"  실패 그림 한 장이 나와야 하는데 {len(images)}장입니다")
            elif images:
                # **설명이 붙어 와야 한다** — AI 는 그림을 못 보고 이 글자만 읽는다.
                if "MCP확인 절차" not in (images[0].get("caption") or ""):
                    bad += 1
                    print(f"  실패 그림에 설명이 안 붙었습니다: {_short(images[0], 80)}")
                # 미리보기 → 진짜. **미리보기는 아무것도 안 걸어야** 한다.
                rows = [
                    {
                        "attachment_id": images[0]["id"],
                        "target": "reliability_test",
                        "object_id": test["id"],
                    }
                ]
                looked = step(
                    "attach_references(미리보기)",
                    await server.attach_references(ctx, rows),
                    ["dry_run", "attached"],
                )
                if looked is not None and looked.get("dry_run") is not True:
                    bad += 1
                    print("  실패 미리보기인데 dry_run 이 아닙니다")
                step(
                    "attach_references(거는 것)",
                    await server.attach_references(ctx, rows, dry_run=False),
                    ["attached", "refused"],
                )

    fixed = step(
        "update_reliability_test",
        await server.update_reliability_test(ctx, test["id"], purpose="고침 확인"),
        ["purpose"],
    )
    if fixed is not None and len(fixed.get("test_items", [])) != 1:
        bad += 1
        print("  실패 안 보낸 칸(시험 항목)이 바뀌었습니다")

    # 7-2. **칸 몇 개만 고치기** — 나머지가 살아남아야 한다.
    #
    # `update_reliability_test` 는 속성을 통째로 갈아 끼운다. 카드에 칸이 스물 넘게 서는
    # 지금, 하나를 고치려다 나머지를 지우는 것이 실제 위험이라 `set_reliability_attributes`
    # 가 읽어서 겹치는 줄만 바꾼다. 그 병합은 **MCP 안에서** 일어나므로, 서버가 살아 있는
    # 여기서만 실제로 확인된다.
    added = step(
        "set_reliability_attributes(더하기)",
        await server.set_reliability_attributes(
            ctx,
            test["id"],
            [{"new_label": f"MCP확인 비고-{tag}", "new_kind": "text", "text_value": "메모"}],
        ),
        ["name"],
    )
    if added is not None and len(added.get("attributes", [])) != 2:
        bad += 1
        print(f"  실패 더했는데 칸이 {len(added.get('attributes', []))}개입니다")

    narrowed = step(
        "set_reliability_attributes(한 칸만)",
        await server.set_reliability_attributes(
            ctx,
            test["id"],
            [{"definition_id": definition["id"], "num_min": -55, "num_max": 125}],
        ),
        ["name"],
    )
    if narrowed is not None:
        values = {one["label"]: one["display"] for one in narrowed["attributes"]}
        if len(values) != 2:
            bad += 1
            print(f"  실패 한 칸을 고쳤는데 나머지가 사라졌습니다: {_short(values, 80)}")
        elif values.get(f"MCP확인 시험 온도-{tag}") != "-55 ~ 125 degC":
            bad += 1
            print(f"  실패 고친 값이 안 들어갔습니다: {_short(values, 80)}")

    if narrowed is not None:
        extra = next(
            (one for one in narrowed["attributes"] if one["label"] == f"MCP확인 비고-{tag}"),
            None,
        )
        if extra is not None:
            emptied = step(
                "set_reliability_attributes(빼기)",
                await server.set_reliability_attributes(
                    ctx,
                    test["id"],
                    [{"definition_id": extra["definition_id"], "remove": True}],
                ),
                ["name"],
            )
            if emptied is not None and len(emptied.get("attributes", [])) != 1:
                bad += 1
                print("  실패 뺐는데 칸이 그대로입니다")

    # 7-1. 조건 묶음 — **같은 칸이 묶음마다 한 줄**이다.
    #
    # 동작 -15 ~ 45 와 저장 -40 ~ 25 는 두 줄인데, 병합이 칸 이름만 보면 하나가 조용히
    # 사라진다. 그 병합은 MCP 안에서 일어나므로 살아 있는 서버가 있는 여기서만 잡힌다.
    grouped = step(
        "set_reliability_attributes(묶음 둘)",
        await server.set_reliability_attributes(
            ctx,
            test["id"],
            [
                {
                    "definition_id": definition["id"],
                    "set_label": "동작",
                    "num_min": -15,
                    "num_max": 45,
                    "unit": "degC",
                },
                {
                    "definition_id": definition["id"],
                    "set_label": "저장",
                    "num_min": -40,
                    "num_max": 25,
                    "unit": "degC",
                },
            ],
        ),
        ["name"],
    )
    if grouped is not None:
        sets = {
            one["set_label"]: one["display"]
            for one in grouped["attributes"]
            if one["definition_id"] == definition["id"]
        }
        if sets != {None: "-55 ~ 125 degC", "동작": "-15 ~ 45 degC", "저장": "-40 ~ 25 degC"}:
            bad += 1
            print(f"  실패 묶음 두 줄이 제대로 안 섰습니다: {_short(sets, 120)}")

    if grouped is not None:
        # 묶음 하나만 고친다 — 나머지 묶음은 그대로여야 한다.
        moved = step(
            "set_reliability_attributes(묶음 하나만)",
            await server.set_reliability_attributes(
                ctx,
                test["id"],
                [
                    {
                        "definition_id": definition["id"],
                        "set_label": "저장",
                        "num_min": -50,
                        "num_max": 25,
                        "unit": "degC",
                    }
                ],
            ),
            ["name"],
        )
        if moved is not None:
            sets = {
                one["set_label"]: one["display"]
                for one in moved["attributes"]
                if one["definition_id"] == definition["id"]
            }
            if sets.get("동작") != "-15 ~ 45 degC":
                bad += 1
                print(f"  실패 안 건드린 묶음이 바뀌었습니다: {_short(sets, 120)}")
            if sets.get("저장") != "-50 ~ 25 degC":
                bad += 1
                print(f"  실패 고친 묶음이 안 바뀌었습니다: {_short(sets, 120)}")

        # 점으로 적은 조건 — 폭이 없다. 「-40 이상」 으로 읽히면 없는 여유가 생긴다.
        pointed = step(
            "set_reliability_attributes(점)",
            await server.set_reliability_attributes(
                ctx,
                test["id"],
                [
                    {
                        "definition_id": definition["id"],
                        "set_label": "시험 점",
                        "step_order": 1,
                        "num_value": 85,
                        "unit": "degC",
                    }
                ],
            ),
            ["name"],
        )
        if pointed is not None:
            point = next(
                (one for one in pointed["attributes"] if one["set_label"] == "시험 점"), None
            )
            if point is None or point["display"] != "85 degC":
                bad += 1
                print(f"  실패 점이 제대로 안 섰습니다: {_short(point, 120)}")

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

    # 8-1. 규격서 한 권 -> 시험 묶음 -> 문서로 모아 보기.
    #
    # 한 건씩 올리는 길만 있으면 스무 건을 스무 번 부르다 중간에 끊기고, 그때 무엇이
    # 올라갔는지 부른 쪽도 사람도 모른다. 그리고 그 스무 건이 한 문서에서 나왔다는 사실이
    # 안 남아 **문서 단위로 검토할 수 없다.**
    teams = step("list_workspaces", await server.list_workspaces(ctx), ["count"])
    # **빈 목록을 기본값이 못 막는다.** `.get(키, [{}])` 는 키가 *없을* 때만 기본값을 쓰는데,
    # 서버는 키를 주고 목록만 비운다 — 부서가 하나도 없는 설치에서 `[0]` 이 IndexError 로
    # 터졌다. 확인 스크립트가 터지면 무엇이 되는지 안 되는지도 못 알린다.
    listed = (teams or {}).get("workspaces") or []
    slug = listed[0].get("slug") if listed else None
    if slug:
        paper = step(
            "create_spec_document",
            await server.create_spec_document(
                ctx, workspace_slug=slug, code=f"MCP-DOC-{tag}", title="MCP확인 규격서"
            ),
            ["code"],
        )
        if paper is not None:
            batch = step(
                "create_reliability_tests(묶음)",
                await server.create_reliability_tests(
                    ctx,
                    division_code=code,
                    document_id=paper["id"],
                    tests=[
                        {"name": f"MCP확인 묶음 하나-{tag}"},
                        {"name": f"MCP확인 묶음 둘-{tag}"},
                        # **같은 이름인데 규격서가 다르다 — 들어가야 한다.** 위에서 만든
                        # 시험은 규격서가 없고 이 줄은 이 문서의 것이다. 이름만으로
                        # 유일하게 두었더니 실제 문서와 부딪혔다(634장 중 202장).
                        {"name": f"MCP확인 열충격-{tag}"},
                        # **같은 시험을 다시 보낸다** — 이름도 규격서도 같다. 막히지 않고
                        # 그 시험의 값에 판이 붙어야 한다(0046): 개정본을 올리는 것은 새
                        # 시험이 아니라 있던 시험의 새 시점이다.
                        {"name": f"MCP확인 묶음 하나-{tag}"},
                    ],
                ),
                ["requested"],
            )
            if batch is not None:
                made = [one["name"] for one in batch.get("created", [])]
                folded = [one["name"] for one in batch.get("merged", [])]
                if len(made) != 3:
                    bad += 1
                    print(f"  실패 묶음에서 세 줄이 들어가야 하는데 {len(made)}줄입니다")
                if f"MCP확인 열충격-{tag}" not in made:
                    bad += 1
                    print("  실패 규격서가 다른 동명이 막혔습니다 — 별개의 시험이다")
                if folded != [f"MCP확인 묶음 하나-{tag}"]:
                    bad += 1
                    print(f"  실패 같은 시험을 다시 보낸 줄이 안 접혔습니다: {folded}")
                if batch.get("failed"):
                    bad += 1
                    print(f"  실패 막힌 줄이 있습니다: {_short(batch.get('failed'), 120)}")
                # 줄마다 규격서가 걸렸나 — 안 걸리면 문서 단위로 못 모은다.
                for one in batch.get("created", []):
                    codes = [
                        each["document_code"]
                        for each in one.get("attributes", [])
                        if each.get("document_code")
                    ]
                    if codes != [f"MCP-DOC-{tag}"]:
                        bad += 1
                        print(f"  실패 묶음이 규격서를 안 걸었습니다: {_short(codes, 80)}")
                        break

    # 8-2. 카탈로그에 없는 기종 — **못 고르는 쪽에 말할 자리가 있나.**
    #
    # 기종을 비우고 등록하는 길은 있었는데, 비운 다음에 왜 비었는지가 아무 데도 안 남았다.
    # 「원문은 비고에 남겨라」 가 설명이었지만 비고에 적힌 것은 아무도 일감으로 안 센다.
    if slug:
        sites = await server.list_terms(ctx, "site")
        site_rows = (sites or {}).get("terms") or []
        kinds = await server.list_terms(ctx, "equipment_category")
        kind_rows = (kinds or {}).get("terms") or []
        if site_rows and kind_rows:
            unit = step(
                "register_equipment(기종 없이)",
                await server.register_equipment(
                    ctx,
                    asset_no=f"MCP-{tag}",
                    name=f"MCP확인 만능기-{tag}",
                    workspace_slug=slug,
                    site_term_id=site_rows[0]["id"],
                    location="3동 201호",
                    category_term_id=kind_rows[0]["id"],
                    maker_text="Instron",
                    model_text=f"68FM-{tag}",
                ),
                ["asset_no"],
            )
            if unit is not None:
                asked = step(
                    "propose_equipment_model",
                    await server.propose_equipment_model(
                        ctx,
                        unit["id"],
                        model_text=f"68FM-{tag}",
                        maker_text="Instron",
                        note="6800 시리즈는 있는데 이 모델만 없음",
                    ),
                    ["status", "text"],
                )
                # **기종은 아직 안 걸려야 한다** — 요청은 카탈로그를 안 건드린다.
                if asked is not None and asked.get("status") != "open":
                    bad += 1
                    print(f"  실패 요청이 open 이 아닙니다: {_short(asked, 70)}")
                # 같은 요청을 두 번 내도 막히지 않는다 — 반입을 다시 돌리는 일이 흔하다.
                twice = step(
                    "propose_equipment_model(다시)",
                    await server.propose_equipment_model(
                        ctx, unit["id"], model_text=f"68FM-{tag}", maker_text="Instron"
                    ),
                    ["status"],
                )
                if asked is not None and twice is not None and twice["id"] != asked["id"]:
                    bad += 1
                    print("  실패 같은 요청이 두 줄로 쌓였습니다")

                # 8-3. **장비 자료 발췌** — AI 가 읽은 것을 적으면 의미 검색의 카드에
                # 실린다. 이 칸에 못 적으면 자료는 붙어 있어도 아무도 못 찾는다.
                defs = await server.list_attribute_definitions(ctx, target="equipment")
                digest = next(
                    (
                        one
                        for one in (defs or {}).get("definitions", [])
                        if one.get("key") == "equipment_document_digest"
                    ),
                    None,
                )
                if digest is not None:
                    wrote = step(
                        "set_equipment_attributes",
                        await server.set_equipment_attributes(
                            ctx,
                            unit["id"],
                            [
                                {
                                    "definition_id": digest["id"],
                                    "text_value": "MCP확인: 만능시험기, 하중 300 kN,"
                                    " 시편 두께 0.1~20 mm",
                                }
                            ],
                        ),
                        ["asset_no"],
                    )
                    # **적은 것이 되돌아와야 한다** — 통째로 갈아 끼우는 길로 잘못 가면
                    # 다른 칸이 조용히 사라지고, 그 손실은 여기서만 보인다.
                    if wrote is not None:
                        kept = [
                            one
                            for one in wrote.get("attributes", [])
                            if one.get("definition_id") == digest["id"]
                        ]
                        if not kept:
                            bad += 1
                            print("  실패 장비 자료 발췌가 안 들어갔습니다")

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

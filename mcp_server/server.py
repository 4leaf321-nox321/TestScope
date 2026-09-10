"""TestScope MCP 서버 — **AI 가 시험 항목을 직접 묻고, 카탈로그를 채운다.**

MatNexus 의 MCP 서버를 본떴다. 그쪽에서 실측으로 얻은 것 넷을 그대로 가져온다:

    권한을 판정하지 않는다   받은 Authorization 을 백엔드로 나르기만 한다
    얇은 프록시다            DB 를 직접 안 읽는다. 필요하면 백엔드에 엔드포인트를 만든다
    안내는 서버가 든다       guide/GUIDE.md — 클라이언트에 복사하면 옛 사본이 남는다
    목록은 스스로 막는다     상한이 없으면 한 번의 호출이 대화를 끊는다

## 이 서버는 권한을 판정하지 않는다

**만능 토큰을 두지 않는다.** 서버가 자기 자격으로 부르면 그 순간 모든 사용자가 같은
권한을 갖는다. 부서 가시성·범위(scopes)·편집 권한은 지금 있는 코드가 판정한다 —
규칙이 두 벌이 되면 갈라지고, 갈라진 쪽이 MCP 면 그것은 권한 우회다.

호출자는 TestScope 화면의 「내 정보 → 토큰」 에서 발급한 개인 토큰을 쓴다. 카탈로그를
채울 토큰이라면 범위는 `read` 와 `catalog:write` 둘이면 된다.

## 만들기 전에 찾는다

`resolve` 가 이 서버의 첫 도구다. 같은 계열이 두 줄로 갈리면 보유 장비가 어느 쪽을
가리켰는지에 따라 검색 결과가 나뉜다 — 그리고 그 갈림은 아무 데도 안 적힌다.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
from mcp.server.mcpserver import Context, MCPServer

#: 백엔드 API. 같은 기계에서 도는 것이 기본이다(개발 8021 · 운영 8020).
API_BASE = os.environ.get("TESTSCOPE_API_BASE", "http://127.0.0.1:8021/api").rstrip("/")

#: 한 번에 돌려주는 목록의 상한. **도구가 스스로 막는다** — 상한이 없으면 한 번의
#: 호출이 수만 자가 되어 대화가 끊긴다.
MAX_LIMIT = 50

GUIDE_PATH = Path(__file__).parent / "guide" / "GUIDE.md"

mcp = MCPServer(
    name="testscope",
    instructions=(
        "TestScope 시험 장비 지도. 「이 시험이 가능한 장비가 우리 조직에 있나」 에"
        " 답한다. 카탈로그는 계열(무슨 시험이 되나)과 기종(어디까지 되나) 두 층이고,"
        " 보유 장비는 기종을 가리킨다. 먼저 get_guide() 를 읽어라 — 특히 「만들기"
        " 전에 resolve 로 찾는다」 와 「모르면 비운다」 는 규약이 있다."
    ),
)


# ── 백엔드 호출 ────────────────────────────────────────────────────────────────


def _headers(ctx: Context) -> dict[str, str]:
    """호출자의 자격을 그대로 나른다. **여기서 토큰을 만들지 않는다.**

    `X-Client` 는 감사 표식이지 보안 경계가 아니다 — 백엔드가 「이 변경은 MCP 로
    들어왔다」 를 기록할 수 있게 붙인다. 누구나 적을 수 있고, 그래도 값은 있다.
    """
    got = dict(ctx.headers or {})
    out = {"X-Client": "mcp"}
    for name in ("authorization", "Authorization"):
        if got.get(name):
            out["Authorization"] = got[name]
            break
    return out


def _failed(got: httpx.Response) -> dict[str, Any]:
    """오류 봉투를 **자세한 내용까지** 옮긴다.

    `details` 를 버리면 「후보를 보세요」 같은 안내가 가리키는 곳이 사라진다 —
    백엔드는 거기에 후보 id 를 실어 보낸다.
    """
    try:
        body = got.json()["error"]
    except Exception:
        return {"error": f"요청이 실패했습니다(HTTP {got.status_code})."}
    out: dict[str, Any] = {"error": f"{body.get('message')} ({body.get('code')})"}
    if body.get("details"):
        out["details"] = body["details"]
    return out


def _auth_error(status: int) -> dict[str, Any] | None:
    if status == 401:
        return {
            "error": (
                "인증에 실패했습니다. TestScope 화면의 「내 정보 → 토큰」 에서 발급한"
                " 개인 토큰을 Authorization 헤더로 등록했는지 확인하세요."
            )
        }
    if status == 403:
        return {
            "error": (
                "권한이 없습니다 — 계정 권한이 모자라거나, 토큰에 그 범위가 없습니다."
                " 카탈로그를 고치려면 catalog:write, 장비를 고치려면 equipment:write"
                " 범위가 필요합니다."
            )
        }
    return None


async def _get(ctx: Context, path: str, params: dict[str, Any] | None = None) -> Any:
    """GET 하나. 오류는 **한국어 한 줄**로 바꿔 돌려준다.

    예외를 그대로 던지면 대화가 스택트레이스로 끊긴다 — 무엇이 잘못됐는지 사람에게
    옮길 수 있는 문장이어야 한다.
    """
    clean = {key: value for key, value in (params or {}).items() if value is not None}
    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
            got = await client.get(path, params=clean, headers=_headers(ctx))
    except httpx.RequestError as failed:
        return {"error": f"백엔드에 닿지 못했습니다({API_BASE}): {failed}"}
    problem = _auth_error(got.status_code)
    if problem is not None:
        return problem
    if got.status_code >= 400:
        return _failed(got)
    return got.json()


async def _send(
    ctx: Context, method: str, path: str, body: dict[str, Any] | None = None
) -> Any:
    """POST·PATCH·PUT 하나. **쓰기는 이 함수만 지난다** — 오류 모양을 한 곳에 둔다."""
    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=60.0) as client:
            got = await client.request(
                method, path, json=body or {}, headers=_headers(ctx)
            )
    except httpx.RequestError as failed:
        return {"error": f"백엔드에 닿지 못했습니다({API_BASE}): {failed}"}
    problem = _auth_error(got.status_code)
    if problem is not None:
        return problem
    if got.status_code >= 400:
        return _failed(got)
    return got.json() if got.content else {"ok": True}


def _listed(payload: object, key: str) -> dict[str, object]:
    """목록을 dict 로 **감싼다.**

    **감싸지 않으면 그 도구는 통째로 죽는다.** mcp 2.x 는 도구가 돌려준 값을 함수의
    반환 표기(`-> dict[str, Any]`)로 검증하는데, 목록 엔드포인트는 배열을 준다 —
    그러면 pydantic 이 막고 클라이언트에는 `Error executing tool …` 만 간다.
    HTTP 로 같은 엔드포인트를 부르면 멀쩡하므로 화면이나 curl 로는 영영 안 보인다
    (MatNexus 실측).

    오류 봉투(`{"error": …}`)는 이미 dict 이므로 그대로 흘려보낸다.
    """
    if isinstance(payload, dict):
        return payload
    rows = list(payload) if isinstance(payload, list) else []
    return {key: rows, "count": len(rows)}


# ── 안내 ──────────────────────────────────────────────────────────────────────


@mcp.tool()
def get_guide() -> str:
    """**무엇을 하기 전에 이것을 먼저 읽어라.**

    카탈로그의 두 층(계열·기종), 「만들기 전에 찾는다」 규약, 모르는 값을 다루는
    방법이 적혀 있다. 서버가 파일을 매 호출 읽으므로 안내를 고치면 재시작 없이
    반영된다 — 클라이언트 쪽에 복사해 두면 고쳐도 옛 사본을 쓰는 사람에게는
    전달되지 않는다.
    """
    try:
        return GUIDE_PATH.read_text(encoding="utf-8")
    except OSError as failed:
        return f"안내를 읽지 못했습니다({GUIDE_PATH}): {failed}"


# ── 찾기 ──────────────────────────────────────────────────────────────────────


@mcp.tool()
async def resolve(
    ctx: Context,
    kind: str,
    text: str,
    axis: str | None = None,
    maker: str | None = None,
) -> dict[str, Any]:
    """이름으로 계열·기종·기준정보 값·시험법을 찾는다. **만들기 전에 반드시 부른다.**

    `kind` 는 `series` · `model` · `term` · `method` 중 하나. `term` 이면 `axis` 를
    함께 준다(manufacturer · equipment_category · test_item · site · standard_body).

    응답의 `match` 가 셋이다.

        exact       하나로 정해졌다. `id` 를 그대로 쓴다
        candidates  여럿이다. **고르지 말고 사람에게 묻는다**
        none        없다. 새로 만들거나 비워 둔다 — **지어내지 않는다**

    못 찾은 것은 실패가 아니다. `hint` 에 다음에 할 일이 한 줄로 적혀 있다.
    """
    return await _send(
        ctx,
        "POST",
        "/resolve",
        {"kind": kind, "text": text, "axis": axis, "maker": maker},
    )


# ── 검색: 이 시스템이 존재하는 이유 ────────────────────────────────────────────


@mcp.tool()
async def search_test_items(
    ctx: Context,
    test_item_term_id: str | None = None,
    method_id: str | None = None,
    conditions: list[dict[str, Any]] | None = None,
    site_term_id: str | None = None,
    include_unavailable: bool = False,
) -> dict[str, Any]:
    """**「80도에서 20 kN 이상 인장 되는 장비 있나」 에 답한다.**

    `conditions` 는 조건마다 하나씩, **셋 중 하나만** 채운다:
    `{"condition_key_id": …, "at": 353.15}` (그 값에서 되나) ·
    `{"…", "at_least": 20}` (그 이상) · `{"…", "at_most": …}`.

    조건 키 id 는 `list_conditions()` 가 준다. 시험 항목 id 는 `resolve` 로 찾는다.

    ## 판정을 셋으로 읽어라

        met      된다
        unmet    안 된다
        unknown  **모른다** — 그 장비에 그 조건이 안 적혀 있다

    **unknown 을 met 으로 옮기지 마라.** 「가능합니다」 로 옮기면 그 답을 믿고 일정을
    짠 사람이 막힌다. 「그 장비에 그 조건이 적혀 있지 않다」 고 그대로 말하라.
    """
    return await _send(
        ctx,
        "POST",
        "/search/test-items",
        {
            "test_item_term_id": test_item_term_id,
            "method_id": method_id,
            "conditions": conditions or [],
            "site_term_id": site_term_id,
            "include_unavailable": include_unavailable,
        },
    )


@mcp.tool()
async def list_conditions(ctx: Context) -> dict[str, Any]:
    """검색이 묻는 조건 축들 — 온도·하중·속도·주파수·시편 두께·습도·항온조.

    각 조건의 `si_unit` 과 `display_unit` 이 함께 온다. **값은 저장 단위로 보낸다.**
    """
    return _listed(await _get(ctx, "/condition-keys"), "conditions")


# ── 카탈로그: 계열 ─────────────────────────────────────────────────────────────


@mcp.tool()
async def search_series(
    ctx: Context, q: str | None = None, kind: str = "main", limit: int = 20
) -> dict[str, Any]:
    """계열을 찾아 훑는다. `kind` 는 `main`(본체) · `accessory`(부속) · 빈 문자열(전체).

    **하나로 정하려면 `resolve` 를 쓴다.** 이 도구는 「무엇이 있나」 를 볼 때다.
    """
    return await _get(
        ctx,
        "/equipment-series",
        {"q": q, "kind": kind or None, "limit": min(limit, MAX_LIMIT)},
    )


@mcp.tool()
async def get_series(ctx: Context, series_id: str) -> dict[str, Any]:
    """계열 하나 — 무슨 시험이 되나(test_items) · 어느 부속이 붙나(relations) ·
    기종이 몇 개인가 · 우리가 몇 대 가졌나.

    사양을 채우려면 여기서 `category_term_id` 를 얻어 `list_spec_definitions` 에
    넘긴다 — 분류를 주면 그 분류의 칸과 공통 칸이 함께 온다.
    """
    return await _get(ctx, f"/equipment-series/{series_id}")


@mcp.tool()
async def create_series(
    ctx: Context,
    name: str,
    name_ko: str | None = None,
    maker: str | None = None,
    category: str | None = None,
    kind: str = "main",
    summary: str | None = None,
) -> dict[str, Any]:
    """계열을 만든다. **먼저 `resolve(kind="series", …)` 로 찾아라.**

    같은 계열이 두 줄로 갈리면 보유 장비가 어느 쪽을 가리켰는지에 따라 검색 결과가
    나뉜다. 이미 있으면 409 와 함께 `details.series_id` 가 온다 — **409 는 실패가
    아니라 답이다.** 그 id 를 쓰면 된다.

    `maker`·`category` 는 이름으로 준다. 기준정보에 **하나로 정해질 때만** 받고,
    없으면 거절한다 — 오타가 새 제조사가 되면 그 계열은 목록에서 혼자 선다.

    챔버·퍼니스·신율계 같은 부속도 계열이다(`kind="accessory"`).
    """
    return await _send(
        ctx,
        "POST",
        "/equipment-series",
        {
            "name": name,
            "name_ko": name_ko,
            "maker": maker,
            "category": category,
            "kind": kind,
            "summary": summary,
        },
    )


@mcp.tool()
async def add_test_item(
    ctx: Context,
    series_id: str,
    test_item: str | None = None,
    test_item_term_id: str | None = None,
    method_code: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """이 계열이 무슨 시험을 하나. **조건 수치는 여기 적지 않는다.**

    여기 적는 조건은 계열 전체가 만족하는 것뿐이고, 기종마다 갈리는 값은 그 기종의
    사양(`set_spec`)에 적으면 보유 장비를 만들 때 합쳐진다 — 한 계열 안에서 하중이
    중앙값 60배 갈리기 때문이다.

    시험 항목은 **닫힌 축**이다. 없는 이름은 안 받는다 — 오타가 값이 되면 그 계열의
    장비는 영영 검색에 안 걸린다.
    """
    return await _send(
        ctx,
        "POST",
        f"/equipment-series/{series_id}/test-items",
        {
            "test_item": test_item,
            "test_item_term_id": test_item_term_id,
            "method_code": method_code,
            "note": note,
        },
    )


@mcp.tool()
async def link_series(
    ctx: Context, series_id: str, part_series_id: str, relation: str, note: str | None = None
) -> dict[str, Any]:
    """계열끼리 잇는다 — 부속 호환·계보.

    `relation` 은 원본 카탈로그가 쓰는 이름 그대로다: `compatible_accessory` ·
    `fits_on` · `requires` · `extends_temperature` · `successor_of` · `same_family_as`.

    **`extends_temperature` 에는 note 를 적어라** — 「-150 ~ +600 °C」 처럼 무엇이
    어떻게 바뀌는지가 그 칸에만 남는다.
    """
    return await _send(
        ctx,
        "POST",
        f"/equipment-series/{series_id}/relations",
        {"part_series_id": part_series_id, "relation": relation, "note": note},
    )


# ── 카탈로그: 기종과 사양 ──────────────────────────────────────────────────────


@mcp.tool()
async def search_models(
    ctx: Context,
    q: str | None = None,
    series_id: str | None = None,
    series: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """기종을 찾아 훑는다. **보유 장비가 가리키는 것이 이 기종이다.**

    ## 계열로 먼저 좁혀라

    사람이 아는 것은 대개 **계열까지**다 — 「인스트론 6800 시리즈」 는 알아도
    `68FM-300` 은 라벨을 봐야 안다. 계열을 알면 `series`(이름) 나 `series_id` 로
    좁혀서 **그 계열의 기종을 전부** 받아라. 그래야 라벨과 대조할 수 있다.

    `series` 이름이 하나로 안 정해지면 후보를 돌려준다 — 그때는 `resolve` 로 정하고
    `series_id` 로 다시 부른다.

    `q` 만 주면 기종명·계열명·제조사를 다 뒤진다. 하나로 정하려면 `resolve` 를 쓴다.
    """
    if series_id is None and series:
        answer = await _send(
            ctx, "POST", "/resolve", {"kind": "series", "text": series, "limit": 8}
        )
        if isinstance(answer, dict) and answer.get("error"):
            return answer
        if answer.get("match") != "exact":
            return {
                "error": f"계열 「{series}」 을(를) 하나로 정할 수 없습니다.",
                "match": answer.get("match"),
                "candidates": answer.get("candidates", []),
                "hint": answer.get("hint"),
            }
        series_id = answer["id"]
    return await _get(
        ctx,
        "/equipment-models",
        {"q": q, "series_id": series_id, "limit": min(limit, MAX_LIMIT)},
    )


@mcp.tool()
async def create_model(
    ctx: Context,
    name: str,
    series: str | None = None,
    series_id: str | None = None,
    maker: str | None = None,
    form_factor: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    """기종을 만든다. **계열이 먼저 있어야 한다.**

    계열은 id 나 이름으로 준다. 이름이 하나로 정해지지 않으면 거절하고 후보를
    돌려준다 — **비슷한 계열에 끼워 넣지 마라.** 단품이라도 기종 하나짜리 계열을
    먼저 만든다.

    기종명에 계열 이름을 섞지 마라. `6800 68FM-300` 과 `68FM-300` 이 별개 기종으로
    갈리고, 그 둘을 나중에 묶을 방법이 없다.
    """
    return await _send(
        ctx,
        "POST",
        "/equipment-models",
        {
            "name": name,
            "series": series,
            "series_id": series_id,
            "maker": maker,
            "form_factor": form_factor or "",
            "summary": summary,
        },
    )


@mcp.tool()
async def list_spec_definitions(
    ctx: Context, category_term_id: str | None = None
) -> dict[str, Any]:
    """이 기종에 **적을 수 있는 칸**들. 분류를 주면 그 분류의 것과 공통이 함께 온다.

    `kind` 가 값의 모양을 정한다: `number`(수치 하나) · `range`(구간) · `choice` ·
    `boolean` · `text`. `condition_key_id` 가 채워진 사양은 **검색축**이라, 그 값이
    보유 장비의 시험 조건이 된다.

    **없는 사양은 만들지 말고 보류하라.** 정의를 늘리는 것은 사람의 판단이다 —
    원본에 사양 키가 562종 있는데 76%가 단 한 곳에만 나온다.
    """
    return _listed(
        await _get(ctx, "/spec-definitions", {"category_term_id": category_term_id}),
        "definitions",
    )


@mcp.tool()
async def get_specs(ctx: Context, model_id: str) -> dict[str, Any]:
    """이 기종에 **적힌** 사양. 빈 칸은 `list_spec_definitions` 가 준다.

    둘을 겹쳐 봐야 「무엇이 아직 안 적혔나」 가 보인다 — 여기에 빈 칸까지 실으면
    한 기종을 볼 때마다 수백 줄이 오간다.

    **정의가 없는 값은 여기 안 온다.** 카탈로그 원문 전체는 `get_model` 의
    `raw_specs` 에 있다 — 사양을 채우기 전에 그것을 먼저 읽어라.
    """
    return await _get(ctx, f"/equipment-models/{model_id}/specs")


@mcp.tool()
async def get_model(ctx: Context, model_id: str) -> dict[str, Any]:
    """기종 하나 — 계열·분류·보유 대수, 그리고 **카탈로그 원문**(`raw_specs`).

    원문은 제조사 카탈로그에 적힌 그대로다. 정의가 있는 칸만 사양표(`get_specs`)에
    들어가고, 정의가 없는 것은 여기에만 있다 — 원본에 950종 넘는 키가 있고 대부분이
    한 카탈로그에만 나온다.

    **사양을 채울 때 이것을 먼저 읽어라.** 원문에 값이 있는데 사양표가 비어 있으면,
    그 값에 맞는 정의가 아직 없다는 뜻이다. 그때는 지어내지 말고 사람에게 알려라.
    """
    return await _get(ctx, f"/equipment-models/{model_id}")


@mcp.tool()
async def set_spec(
    ctx: Context,
    model_id: str,
    definition_id: str,
    num_value: float | None = None,
    num_min: float | None = None,
    num_max: float | None = None,
    text_value: str | None = None,
    bool_value: bool | None = None,
    note: str | None = None,
    source_id: str | None = None,
    source_page: int | None = None,
) -> dict[str, Any]:
    """사양 한 칸을 넣거나 덮어쓴다. **정의의 종류에 맞는 칸만 채운다.**

        number   num_value
        range    num_min · num_max   (한쪽을 비우면 「제한 없음」 — 0 이 아니다)
        choice   text_value          (정의의 choices 안에 있어야 한다)
        boolean  bool_value
        text     text_value          (원문 그대로. 조건절을 버리지 마라)

    틀린 칸에 담긴 값은 저장은 되지만 화면이 못 그린다.

    **비고를 아끼지 마라.** 「챔버 장착 시」 처럼 값이 언제 성립하는지가 비고에만
    남는다. 카탈로그가 조건을 달아 적은 것을 버리면 값만 남고 뜻이 사라진다.

    응답의 `search_axis` 가 채워져 있으면 이 값은 앞으로 이 기종으로 등록하는 장비의
    시험 조건이 된다. `existing_units` 는 **이미 등록된 대수**이고 그들에게는
    반영되지 않는다 — 개체의 값은 개체가 갖는다.
    """
    return await _send(
        ctx,
        "PUT",
        f"/equipment-models/{model_id}/specs",
        {
            "definition_id": definition_id,
            "num_value": num_value,
            "num_min": num_min,
            "num_max": num_max,
            "text_value": text_value,
            "bool_value": bool_value,
            "note": note,
            "source_id": source_id,
            "source_page": source_page,
        },
    )


@mcp.tool()
async def list_spec_sources(ctx: Context, q: str | None = None) -> dict[str, Any]:
    """사양값의 출처가 될 제조사 문서들. **값을 적을 때 출처를 함께 대라** —
    반년 뒤 「이 300 kN 어디서 나왔나」 를 물을 사람은 반드시 있다."""
    return await _get(ctx, "/spec-sources", {"q": q, "limit": MAX_LIMIT})


# ── 보유 장비 ─────────────────────────────────────────────────────────────────


@mcp.tool()
async def search_equipment(
    ctx: Context,
    q: str | None = None,
    model_id: str | None = None,
    workspace: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """우리가 가진 장비. 각 줄에 **시험 항목**과 계열·기종이 함께 온다.

    `test_items` 가 비어 있으면 그 장비는 **검색에 절대 안 걸린다** — 시험 항목이 안
    적혀 있다는 뜻이다.
    """
    return await _get(
        ctx,
        "/equipment",
        {
            "q": q,
            "model_id": model_id,
            "workspace": workspace,
            "limit": min(limit, MAX_LIMIT),
        },
    )


@mcp.tool()
async def get_equipment(ctx: Context, equipment_id: str) -> dict[str, Any]:
    """보유 장비 한 대 — 자산번호·자리·상태·담당자, 그리고 어느 기종인가.

    `test_items` 가 비어 있으면 **검색에 절대 안 걸린다.** `series_name` 이 비어
    있으면 카탈로그에 아직 안 이어진 장비다.
    """
    return await _get(ctx, f"/equipment/{equipment_id}")


@mcp.tool()
async def register_equipment(
    ctx: Context,
    asset_no: str,
    name: str,
    workspace_slug: str,
    site_term_id: str,
    location: str,
    model_id: str | None = None,
    category_term_id: str | None = None,
    serial_no: str | None = None,
    dept_asset_no: str | None = None,
    shared_use: bool = False,
    status: str = "operational",
    acquired_on: str | None = None,
    manufactured_year: int | None = None,
    calibration_required: bool = False,
    calibration_interval_months: int | None = None,
    maker_text: str | None = None,
    model_text: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """보유 장비 한 대를 등록한다.

    **기종을 고르면 그 계열의 시험 항목이 이 장비로 복사되고, 조건은 그 기종의 사양에서
    온다.** 상속이 아니라 복사라, 그 뒤로는 이 장비가 진실이다 — 챔버를 뗀 대는
    여기서 고친다.

    ## 기종을 고르는 순서

    **계열부터 좁혀라.** `search_models(series="인스트론 6800 시리즈")` 로 그 계열의
    기종을 전부 받아 라벨과 대조한다 — 기종명만으로 찾으면 비슷한 이름의 다른 계열
    것을 집을 수 있다.

    ## 못 찾았으면 비워라

    카탈로그에 없는 기종이면 `model_id` 를 **비운 채로 등록하라.** 비슷한 기종을
    골라 넣지 마라 — 그 순간 그 장비의 하중·온도가 남의 것이 된다.

    비워 두면 「카탈로그 미연결」 로 표시되고 홈의 「남은 일」 이 그것을 센다. 원문
    (`Instron 5982` 같은 것)은 `note` 에 그대로 남겨라 — 나중에 이을 유일한 끈이다.

    자산번호가 이미 있으면 409 다. **덮어쓰지 않는다** — 같은 번호의 다른 장비일
    수도 있고, 그때 덮으면 있던 이력이 사라진다.

    ## 등록으로 끝이 아니다

    기종을 골랐으면 계열의 시험 항목이 복사된다. **비웠으면 시험 항목이 0 건이고,
    0 건이면 검색에 절대 안 걸린다** — 이어서 `add_equipment_test_item` 으로 채워라.
    안 채우면 그 장비는 대장에만 있고 아무도 못 찾는다.

    ## 비울 수 없는 것

    보유 부서·거점(`site_term_id`)·상세위치(`location`), 그리고 **무슨 종류인가.**
    어디 있고 무슨 종류인지 모르는 장비는 찾아도 소용이 없다.

    종류는 기종을 고르면 따라온다(계열이 갖는다). 기종을 못 찾아 비웠다면
    `category_term_id` 를 직접 골라라 — `resolve(axis="equipment_category", …)` 로
    찾는다. 둘 다 없으면 400 이다.

    미연결 장비의 제조사·모델명은 `maker_text`·`model_text` 에 적는다. **표시용이라
    검색이 안 본다** — 그래서 기종을 찾는 편이 언제나 낫다. 나중에 기종에 연결하면
    서버가 이 두 칸을 비운다.

    ## 상태

    `incoming` 입고 · `operational` 가동 · `idle` 유휴 · `maintenance` 점검·교정 ·
    `repair` 고장 · `retired` 폐기. **모르면 지어내지 마라** — 기본값 `operational`
    보다 사람에게 묻는 편이 낫다. 검색이 「쓸 수 있다」 로 세는 것은 가동과 유휴다.

    ## 교정

    `calibration_required` 가 참이면 `calibration_interval_months` 를 함께 줘야 한다.
    주기가 없으면 차기일을 계산할 수 없고, 그러면 「곧 만료」 목록이 이 장비를 영원히
    안 부른다. **모르면 대상 여부를 비워 두고 사람에게 물어라.**
    """
    return await _send(
        ctx,
        "POST",
        "/equipment",
        {
            "asset_no": asset_no,
            "name": name,
            "workspace_slug": workspace_slug,
            "site_term_id": site_term_id,
            "location": location,
            "model_id": model_id,
            "category_term_id": category_term_id,
            "serial_no": serial_no,
            "dept_asset_no": dept_asset_no,
            "shared_use": shared_use,
            "status": status,
            "acquired_on": acquired_on,
            "manufactured_year": manufactured_year,
            "calibration_required": calibration_required,
            "calibration_interval_months": calibration_interval_months,
            "maker_text": maker_text,
            "model_text": model_text,
            "note": note,
        },
    )


@mcp.tool()
async def get_equipment_specs(ctx: Context, equipment_id: str) -> dict[str, Any]:
    """이 **장비 한 대**의 사양 — 카탈로그 값과 실측이 한 줄에 함께 온다.

    기종 사양(`get_specs`)은 「제조사가 그렇게 적었다」 이고, 여기 `measured` 는
    「우리가 이 대를 재 보니 그렇더라」 다. **둘 다 보고 답하라** — 실측이 있으면
    그쪽이 이 장비의 진실이고, 없으면 카탈로그 값은 이 대를 재 본 값이 아니다.
    """
    return await _get(ctx, f"/equipment/{equipment_id}/specs")


@mcp.tool()
async def set_equipment_spec(
    ctx: Context,
    equipment_id: str,
    definition_id: str,
    num_value: float | None = None,
    num_min: float | None = None,
    num_max: float | None = None,
    text_value: str | None = None,
    bool_value: bool | None = None,
    measured_on: str | None = None,
    note: str | None = None,
    source_id: str | None = None,
    source_page: int | None = None,
) -> dict[str, Any]:
    """이 장비의 **실측** 사양 한 칸을 적는다 — 카탈로그 값 위에 덮는다.

    **기종 사양과 헷갈리지 마라.** `set_spec` 은 그 기종을 쓰는 모든 장비의 기준이
    되고, 이것은 이 한 대의 값이다. 우리가 잰 값·성적서에 적힌 이 대의 값은 여기다.

    정의의 종류에 맞는 칸만 채운다 — 수치는 `num_value`, 구간은 `num_min`/`num_max`,
    고른 값과 문장은 `text_value`, 참거짓은 `bool_value`.

    **언제 잰 값인지 적어라**(`measured_on`). 3년 전 실측은 사양서보다 나을 것이
    없고, 날짜가 없으면 사람이 그것을 판단할 수 없다.

    응답의 `reflected` 가 참이면 이 장비의 시험 조건이 함께 갱신됐다는 뜻이다.
    거짓이면 그 조건은 **사람이 손으로 적어 둔 것**이라 안 덮었다 — 덮고 싶으면
    사람에게 물어라.
    """
    return await _send(
        ctx,
        "PUT",
        f"/equipment/{equipment_id}/specs",
        {
            "definition_id": definition_id,
            "num_value": num_value,
            "num_min": num_min,
            "num_max": num_max,
            "text_value": text_value,
            "bool_value": bool_value,
            "measured_on": measured_on,
            "note": note,
            "source_id": source_id,
            "source_page": source_page,
        },
    )


@mcp.tool()
async def add_equipment_test_item(
    ctx: Context,
    equipment_id: str,
    test_item_term_id: str,
    method_id: str | None = None,
    confidence: str = "catalog",
    note: str | None = None,
) -> dict[str, Any]:
    """이 **장비**가 하는 시험 항목 하나를 더한다.

    ## 언제 쓰나 — 안 쓰면 그 장비는 영영 안 걸린다

    기종을 골라 등록하면 계열의 시험 항목이 복사되므로 대개 이것을 부를 일이 없다.
    그런데 **카탈로그에 없어서 `model_id` 를 비운 채 등록한 장비는 시험 항목이 0 건**
    이고, 0 건이면 검색에 절대 안 걸린다. 그런 장비를 만들었으면 여기서 채워라.

    `confidence` 는 그 값을 어디까지 믿을 수 있나다:

        catalog   사양서에서 온 값. **해 본 것이 아니다**(기본)
        verified  실제로 돌려 봤다
        limited   되기는 하는데 조건이 붙는다 — 그 조건을 note 에 적어라

    **`verified` 를 함부로 쓰지 마라.** 사양서를 옮긴 것이라면 그것은 `catalog` 다.

    시험 항목은 **닫힌 축**이라 없는 값은 만들어지지 않는다(거절된다). `resolve` 로
    먼저 찾아라 — 그것이 맞다: 오타가 값이 되면 그 장비는 영영 검색에 안 걸린다.
    """
    return await _send(
        ctx,
        "POST",
        "/equipment-test-items",
        {
            "equipment_id": equipment_id,
            "test_item_term_id": test_item_term_id,
            "method_id": method_id,
            "confidence": confidence,
            "note": note,
        },
    )


@mcp.tool()
async def set_test_condition(
    ctx: Context,
    equipment_test_item_id: str,
    condition_key_id: str,
    min_value: float | None = None,
    max_value: float | None = None,
    text_value: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """그 시험 항목이 **어디까지 되나**를 적는다. 조건 한 칸은 덮어쓰기다.

    조건 축은 `list_conditions` 가 준다.

    ## 값은 **저장 단위(SI)** 로 준다 — 서버가 안 바꾼다

    `list_conditions` 의 `si_unit` 이 그 단위다(N·K·m·s·Hz). `display_unit` 은 사람에게
    보여 줄 때 쓰는 실무 단위(kN·degC·mm)라, 그것으로 보내면 **자릿수가 셋 틀린다** —
    20 kN 을 20 으로 보내면 20 N 으로 저장되고, 그 장비는 검색에서 조용히 빠진다.

    환산은 부르는 쪽이 한다: 20 kN 이면 `max_value=20000`, 80 degC 면 `353.15`.

    ## 비운 쪽은 「제한 없음」 이다

    0 으로 채우지 마라. 하한이 0 인 장비와 구별되지 않고, 검색이 그 차이로 갈린다.
    「20 kN 까지」 는 `max_value=20` 이고 `min_value` 는 비운다.

    ## 모르면 적지 마라

    안 적힌 조건은 검색이 `unknown` 으로 답한다 — 그것이 맞는 답이다. 지어낸 숫자는
    「가능합니다」 가 되어, 그 답을 믿고 일정을 짠 사람이 막힌다.
    """
    return await _send(
        ctx,
        "PUT",
        f"/equipment-test-items/{equipment_test_item_id}/limits",
        {
            "condition_key_id": condition_key_id,
            "min_value": min_value,
            "max_value": max_value,
            "text_value": text_value,
            "note": note,
        },
    )


@mcp.tool()
async def update_equipment(
    ctx: Context,
    equipment_id: str,
    status: str | None = None,
    location: str | None = None,
    site_term_id: str | None = None,
    contact_user_id: str | None = None,
    shared_use: bool | None = None,
    calibration_required: bool | None = None,
    calibration_interval_months: int | None = None,
    retired_on: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """보유 장비 한 대를 고친다. **안 보낸 칸은 안 바뀐다.**

    상태는 여섯이다: `incoming` 입고 · `operational` 가동 · `idle` 유휴 ·
    `maintenance` 점검·교정 · `repair` 고장 · `retired` 폐기.

    **폐기일은 상태가 `retired` 일 때만** 받는다. 되돌리면 서버가 비운다.

    보유 부서·거점·상세위치는 **비울 수 없다** — 어디 있는지 모르는 장비는 찾아도
    소용이 없다. 부서 이관은 양쪽 다 관리자여야 해서 이 도구로는 안 한다.
    """
    body = {
        "status": status,
        "location": location,
        "site_term_id": site_term_id,
        "contact_user_id": contact_user_id,
        "shared_use": shared_use,
        "calibration_required": calibration_required,
        "calibration_interval_months": calibration_interval_months,
        "retired_on": retired_on,
        "note": note,
    }
    # **안 보낸 것과 비운 것을 구별한다.** 전부 실어 보내면 상태 하나 바꾸려다
    # 담당자와 위치가 지워지고, 그 손실은 부른 사람 눈에 안 보인다.
    return await _send(
        ctx, "PATCH", f"/equipment/{equipment_id}",
        {key: value for key, value in body.items() if value is not None},
    )


@mcp.tool()
async def add_calibration(
    ctx: Context,
    equipment_id: str,
    calibrated_on: str,
    next_due_on: str | None = None,
    certificate_no: str | None = None,
    provider_term_id: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """교정 이력 한 줄을 더한다. 날짜는 `YYYY-MM-DD`.

    **성적서에 적힌 차기일(`next_due_on`)이 있으면 반드시 넣어라.** 기관이 정한 날이
    진실이고, 없으면 시스템이 교정 주기로 계산해 보여 준다 — 계산값은 그렇다고 표시되지만
    성적서가 있는데 안 넣으면 그 표시가 거짓이 된다.

    교정 기관은 **축의 값**이다(`resolve(axis="calibration_provider", …)`). 자유 문자열로
    두면 같은 기관이 「한국계량측정협회」 와 「(주)한국계량측정협회」 로 갈리고, 그 둘은
    서로 다른 기관이 된다.

    이력을 넣어도 그 장비가 **교정 대상으로 표시돼 있지 않으면** 「곧 만료」 목록에는
    안 뜬다 — `update_equipment(calibration_required=True, calibration_interval_months=…)`
    를 함께 불러라.
    """
    return await _send(
        ctx,
        "POST",
        f"/equipment/{equipment_id}/calibrations",
        {
            "calibrated_on": calibrated_on,
            "next_due_on": next_due_on,
            "certificate_no": certificate_no,
            "provider_term_id": provider_term_id,
            "note": note,
        },
    )

@mcp.tool()
async def list_pending_work(ctx: Context) -> dict[str, Any]:
    """**채울 자리.** 우리가 가진 것 중 비어 있는 것만 센다.

    시험 항목이 안 적힌 장비 · 사양이 안 적힌 보유 기종 · 시험 항목이 안 적힌 보유 계열 ·
    원본 확인이 필요한 기종 · 교정 기한이 지난 장비.

    **여기부터 채워라.** 카탈로그 전체를 채우려 들면 끝이 없어 보여서 아무도
    시작하지 않는다.
    """
    return _listed(await _get(ctx, "/server/maintenance"), "items")


if __name__ == "__main__":
    # stdio 로 뜬다. HTTP 로 띄우려면 run_mcp.ps1 을 쓴다.
    mcp.run()

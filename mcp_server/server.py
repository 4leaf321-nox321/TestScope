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
import time
from pathlib import Path
from typing import Any

import calltrace
import httpx
from mcp.server.mcpserver import Context, MCPServer

#: 백엔드 API. 같은 기계에서 도는 것이 기본이다(개발 8021 · 운영 8020).
API_BASE = os.environ.get("TESTSCOPE_API_BASE", "http://127.0.0.1:8021/api").rstrip("/")

#: 한 번에 돌려주는 목록의 상한. **도구가 스스로 막는다** — 상한이 없으면 한 번의
#: 호출이 수만 자가 되어 대화가 끊긴다.
MAX_LIMIT = 50

#: 무엇을 싣나 — `all`(기본) · `read`(읽기만).
#:
#: **도구 목록은 매 턴 통째로 실린다.** 예순 개가 넘으면 그것만으로 수만 자이고, 그만큼
#: 대화가 짧아진다(실측: 전부 48,000자 · 읽기만 22,000자). 읽기 전용 토큰을 쓰는 사람에게
#: 쓰기 도구 스물다섯을 보여 줄 이유가 없다 — 어차피 403 이다. 그래서 **부를 수 없는 것은
#: 아예 안 싣는다**: 고르는 일이 쉬워지고 자리도 는다.
#:
#: 기본을 `all` 로 두는 이유: 켜는 것을 잊으면 「그 도구가 없다」 가 되고, 없는 것과 안
#: 실은 것을 쓰는 쪽에서는 구별할 수 없다.
TOOL_PROFILE = os.environ.get("TESTSCOPE_MCP_TOOLS", "all").strip().lower()
READ_ONLY = TOOL_PROFILE == "read"

GUIDE_PATH = Path(__file__).parent / "guide" / "GUIDE.md"

#: 물음 -> 첫 도구. **도구가 예순 개가 넘으면 이름을 훑어 고르는 것이 안 된다** —
#: 비슷한 이름이 여럿이라(search_test_items · search_catalog · search_semantic) 고르는
#: 데 실패하면 그 다음 행동이 통째로 틀린다. 그래서 「무엇을 물었나」 로 들어가는 문을
#: 하나 둔다. 이 글은 도구 목록과 함께 **항상** 실리므로 짧아야 한다 — 줄마다 첫 도구
#: 하나씩이고, 나머지는 그 도구의 설명과 get_guide(주제) 가 말한다.
ROUTING = """무엇을 물었나 -> 여기서 시작한다 (자세한 것은 그 도구의 설명과 get_guide):

  이 시험 되는 장비 있나      search_test_items   (물성으로 물으면 search_properties 먼저)
  이 규격/조건으로 되나        search_test_items(conditions=…) · list_conditions
  말로만 아는 것을 찾기         resolve · search_semantic · graph_search
  이름 하나를 id 로            resolve (계열·기종·값·규격·시험·장비·부서 전부)
  우리 부서 시험 절차           list_reliability_tests · test_capability
  장비 대장 넣기               import_equipment (한 대면 register_equipment)
  장비 한 대 고치기            get_equipment · update_equipment · add_equipment_test_item
  교정 언제였나/언제 만료     get_calibrations · list_calibrations_due
  규격이 없다/조건을 적자      resolve(method) -> create_method · set_requirement
  계열/기종/사양 채우기         search_series · search_models · get_specs · set_spec
  이 값을 어디 적나            list_reference · list_axes · list_terms
  무슨 칸을 적을 수 있나        list_attribute_definitions
  무엇이 무엇과 이어지나        graph_search -> graph_node
  사람이 정할 것이 뭐가 남았나   list_review_queues (확정은 사람이 화면에서)
  어디부터 채우나              list_pending_work"""

mcp = MCPServer(
    name="testscope",
    instructions=(
        "TestScope 시험 장비 지도. 「이 시험이 가능한 장비가 우리 조직에 있나」 에"
        " 답한다. 카탈로그는 계열(무슨 시험이 되나)과 기종(어디까지 되나) 두 층이고,"
        " 보유 장비는 기종을 가리킨다. 규약 둘이 모든 도구에 걸린다 — **만들기 전에"
        " resolve 로 찾는다**, **모르면 비운다**(지어낸 값은 검색이 「됩니다」 로"
        " 답한다), **응답의 next 가 「이것이 답이다」 면 멈춘다**(거점별·장비별로 다시"
        " 부르거나 사양을 열어 재확인하지 않는다 — 판정은 서버가 했다). 처음이면"
        " get_guide() 를 읽어라.\n\n" + ROUTING
    ),
)


# ── 자취 ──────────────────────────────────────────────────────────────────────

_TRACE_PATH = calltrace.trace_path()
_call_tool_plain = mcp.call_tool


async def _call_tool_traced(
    name: str, arguments: dict[str, Any], context: Context | None = None
) -> Any:
    """모든 도구 호출이 지나는 자리 — 자취 한 줄을 남긴다(`TESTSCOPE_MCP_TRACE` 가 켜졌을 때).

    SDK 의 `call_tool` 을 인스턴스에서 덮는다. 도구마다 데코레이터를 하나 더 다는 것보다
    빠뜨릴 곳이 없고, 미들웨어 API 는 아직 「바뀔 수 있다」 고 적혀 있어 피했다.
    """
    started = time.perf_counter()
    outcome = await _call_tool_plain(name, arguments, context)
    if _TRACE_PATH is not None:
        # 도구가 돌려준 값은 CallToolResult 로 감싸여 온다 — 구조화된 것이 있으면 그것으로
        # 빈손인지 본다(우리 도구는 전부 dict 나 str 을 돌려준다).
        payload = getattr(outcome, "structured_content", None)
        calltrace.record(name, arguments, payload, started, path=_TRACE_PATH)
    return outcome


if _TRACE_PATH is not None:
    mcp.call_tool = _call_tool_traced  # type: ignore[method-assign]


# ── 도구 등록 ─────────────────────────────────────────────────────────────────


def writes(func: Any) -> Any:
    """**바꾸는 도구**임을 표시한다. `TESTSCOPE_MCP_TOOLS=read` 면 안 싣는다.

    표시를 빠뜨리면 읽기 전용 프로필에서도 그 도구가 실리고, 부르면 403 이 온다 — 그
    403 은 「범위가 없다」 로 읽혀 사람이 토큰을 다시 만들게 만든다. 그래서 새 쓰기
    도구에는 반드시 붙인다(`tests/architecture/test_mcp_tools.py` 가 본다).
    """
    if READ_ONLY:
        return func
    return mcp.tool()(func)


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
    ctx: Context,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    """POST·PATCH·PUT 하나. **쓰기는 이 함수만 지난다** — 오류 모양을 한 곳에 둔다.

    쿼리는 `params` 로 준다. 경로에 `?` 를 붙이면 「도구가 부르는 경로가 실재하나」 를
    보는 구조 시험이 그 경로를 못 찾는다.
    """
    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=60.0) as client:
            got = await client.request(
                method, path, json=body or {}, params=params, headers=_headers(ctx)
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


#: 검색 도구가 한 번에 돌려주는 줄 수. 서버는 200건까지 주지만 그것을 통째로 넘기면 도구
#: 응답 한도(클라이언트마다 다르다 — Claude Code 는 8만 자 안팎)를 넘겨 **잘린 채** 도착한다.
#: 측정(2026-09-20, q03)에서 AI 가 「결과가 한도를 넘어 거점별로 쪼갰다」 고 스스로 적었다 —
#: 그래서 검색 한 번이 다섯 번이 됐다. 확실한 것이 위로 오게 정렬돼 있으니 앞 몇 십 건이면
#: 답하기에 충분하고, 나머지는 판정별 수로 요약한다.
SEARCH_HITS = 20
SEARCH_HITS_MAX = 50


def _trim_hits(found: Any, limit: int, key: str = "hits") -> Any:
    """긴 목록을 앞 `limit` 건으로 자르고 판정별 수(`by_verdict`)와 `shown` 을 붙인다."""
    if not isinstance(found, dict) or "error" in found or not isinstance(found.get(key), list):
        return found
    rows = found[key]
    counts: dict[str, int] = {}
    for one in rows:
        verdict = str(one.get("verdict") or "?")
        counts[verdict] = counts.get(verdict, 0) + 1
    found["by_verdict"] = counts
    found["shown"] = min(len(rows), limit)
    found[key] = rows[:limit]
    return found


def _then(payload: Any, advice: str) -> Any:
    """응답 끝에 「다음에 할 것」 한 줄을 얹는다(`next`).

    길잡이는 **첫 도구**를 맞히게 했지만 그다음 걸음이 길었다 — 측정(2026-09-20)에서 AI 는
    검색 한 번 뒤에 거점마다 같은 검색을 네 번 더 돌렸고(q01·q03), 판정이 0대라 하자 다른
    이름으로 장비를 뒤졌다(q11). 「이 응답이 답이다, 여기서 멈춰라」 가 응답에 없어서다. 도구
    설명은 부르기 전에 읽는 글이고, 이 줄은 **결과를 손에 든 순간** 읽는 글이다.

    오류 봉투에는 안 얹는다 — 오류가 곧 다음 할 일이다.
    """
    if isinstance(payload, dict) and "error" not in payload:
        payload["next"] = advice
    return payload


# ── 안내 ──────────────────────────────────────────────────────────────────────


def _guide_text() -> str:
    try:
        return GUIDE_PATH.read_text(encoding="utf-8")
    except OSError as failed:
        return f"안내를 읽지 못했습니다({GUIDE_PATH}): {failed}"


def _sections(text: str) -> list[tuple[str, str]]:
    """`## 제목` 으로 자른 조각들. 머리말은 제목 없이 맨 앞에 둔다."""
    out: list[tuple[str, str]] = []
    title = ""
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            out.append((title, "\n".join(lines).strip()))
            title = line[3:].strip()
            lines = []
        else:
            lines.append(line)
    out.append((title, "\n".join(lines).strip()))
    return [one for one in out if one[1]]


def _matches(topic: str, title: str) -> bool:
    """대목 이름을 **사람이 부르는 말로** 찾게 한다.

    제목은 문장이라(「장비를 등록할 때 — 비울 수 없는 것이 있다」) 글자 그대로 물으면
    아무도 못 맞힌다. 「장비 등록」 처럼 조각으로 물어도 걸리게, 물은 말의 낱말이 전부
    제목 안에 있으면 그 대목으로 본다. 못 맞히면 안내가 통째로 안 읽히고, 그러면
    규약(만들기 전에 찾는다 · 모르면 비운다)이 전달되지 않는다.
    """
    lowered = title.casefold()
    words = [one for one in topic.casefold().split() if one]
    if not words:
        return False
    if all(one in lowered for one in words):
        return True
    # 「장비 등록」 vs 「장비를 등록할 때」 — 조사·어미가 붙어 낱말이 그대로는 안 맞는다.
    # **낱말이 둘 이상일 때만** 느슨하게 본다: 한 낱말로 느슨하게 맞히면 「없는것」 이
    # 「비울 수 없는 것」 에 걸려, 엉뚱한 대목을 조용히 돌려준다.
    if len(words) < 2:
        return False
    return all(len(one) >= 2 and one[:2] in lowered for one in words)


@mcp.tool()
def get_guide(topic: str | None = None) -> str:
    """**무엇을 하기 전에 이것을 먼저 읽어라.** 그다음엔 필요한 대목만.

    `topic` 없이 부르면 머리말(이 시스템이 답하는 물음 · 세 층 · 규약 넷)과 **대목의
    목록**이 온다. 대목 이름의 한 조각을 `topic` 으로 주면 그 대목만 온다 —
    `get_guide("장비 등록")` · `get_guide("기준정보")` · `get_guide("권한")`.

    통째로 받고 싶으면 `topic="전부"`. 안내는 길어서(수천 자) 매번 다 받으면 정작
    도구를 부를 자리가 줄어든다 — 그래서 대목으로 나눠 준다.

    서버가 파일을 매 호출 읽으므로 안내를 고치면 재시작 없이 반영된다 — 클라이언트
    쪽에 복사해 두면 고쳐도 옛 사본을 쓰는 사람에게는 전달되지 않는다.
    """
    text = _guide_text()
    if text.startswith("안내를 읽지"):
        return text
    if topic in ("전부", "all", "*"):
        return text
    sections = _sections(text)
    if topic:
        found = [body for title, body in sections if _matches(topic, title)]
        if found:
            return "\n\n".join(found)
        titles = " · ".join(title for title, _ in sections if title)
        return f"「{topic}」 라는 대목이 없습니다. 있는 대목: {titles}"
    # 머리말 + 대목 목록 — 어디를 더 읽을지 고르는 데 필요한 만큼만.
    head = sections[0][1] if sections and not sections[0][0] else ""
    intro = [body for title, body in sections if title in ("층이 셋이다", "규약 넷")]
    titles = "\n".join(f"  {title}" for title, _ in sections if title)
    return "\n\n".join(
        [head, *intro, f'더 읽을 대목 — get_guide("이름의 한 조각"):\n{titles}']
    )


# ── 찾기 ──────────────────────────────────────────────────────────────────────


@mcp.tool()
async def resolve(
    ctx: Context,
    kind: str,
    text: str,
    axis: str | None = None,
    maker: str | None = None,
    workspace: str | None = None,
) -> dict[str, Any]:
    """이름 하나를 id 로. **만들거나 고치기 전에 반드시 부른다.**

    `kind` — `series` · `model` · `term`(+`axis`) · `method` · `reliability_test` ·
    `equipment` · `workspace`. `term` 의 축은 manufacturer · equipment_category ·
    test_item · property · site · standard_body 이고, 별칭까지 찾는다(「Rp0.2」 로 쳐도 된다).

    응답의 `match` 가 셋이다.

        exact       하나로 정해졌다. `id` 를 그대로 쓴다
        candidates  여럿이다. **고르지 말고 사람에게 묻는다**
        none        없다. 새로 만들거나 비워 둔다 — **지어내지 않는다**

    **부서가 가진 것은 이름이 겹친다.** 「고온고습 1000h」 는 거의 모든 부서에 하나씩
    있으므로 이름이 같아도 둘이면 `candidates` 다 — `workspace`(slug)를 함께 주면 하나로
    줄어든다. slug 를 모르면 `resolve(kind="workspace", …)` 로 먼저 찾는다. 장비는
    자산번호가 유일해서 그것만 exact 이고, 이름은 대개 여럿이다.

    못 찾은 것은 실패가 아니다. `hint` 에 다음에 할 일이 한 줄로 적혀 있다.
    """
    return await _send(
        ctx,
        "POST",
        "/resolve",
        {
            "kind": kind,
            "text": text,
            "axis": axis,
            "maker": maker,
            "workspace": workspace,
        },
    )


# ── 검색: 이 시스템이 존재하는 이유 ────────────────────────────────────────────


@mcp.tool()
async def search_test_items(
    ctx: Context,
    test_item_term_id: str | None = None,
    property_term_id: str | None = None,
    method_id: str | None = None,
    conditions: list[dict[str, Any]] | None = None,
    site_term_id: str | None = None,
    include_unavailable: bool = False,
    limit: int = SEARCH_HITS,
) -> dict[str, Any]:
    """**「80도에서 20 kN 이상 인장 되는 장비 있나」 에 답한다.**

    `conditions` 는 조건마다 하나씩, **셋 중 하나만** 채운다:
    `{"condition_key_id": …, "at": 353.15}` (그 값에서 되나) ·
    `{"…", "at_least": 20}` (그 이상) · `{"…", "at_most": …}`.

    조건 키 id 는 `list_conditions()` 가 준다. 시험 항목 id 는 `resolve` 로 찾는다.
    **어떤 조건을 물어야 하는지는 시험 항목이 정한다** — `get_test_item` 의
    `condition_keys` 가 그 시험에 뜻이 있는 축(인장 → 하중·속도·온도)이다. 그 축 밖의 조건
    (인장에 습도)을 붙이면 대개 `unknown` 만 늘어난다. 축이 비어 있으면 아직 안 정해진
    것이니, 조건을 물을 때 그렇다고 말하라.
    **물성으로 물으면** `property_term_id` 를 준다(`search_properties` 가 id 를 준다) —
    서버가 그 물성을 내는 시험 항목 전부로 펼쳐 찾고, 응답의 `expanded_test_items` 에
    무엇으로 펼쳤는지 적어 준다. 그것이 비어 있으면 결과 0 건은 「장비가 없다」 가 아니라
    「그 물성에 이어진 시험 항목이 없다」 다.

    ## 판정을 셋으로 읽어라

        met        된다
        accessory  **부속(챔버·노)을 달면 된다** — 「됨」 으로 옮기지 마라
        unmet      안 된다
        unknown    **모른다** — 그 장비에 그 조건이 안 적혀 있다

    `accessory` 조건의 `accessory` 칸이 **무엇을 달면 되는지** 짚어 준다(부속 기종·범위·
    보유 대수). 보유가 0 이 아니면 사는 이야기가 아니다 — 부속을 다시 뒤지지 마라, 답에 있다.

    **unknown 을 met 으로 옮기지 마라.** 「그 장비에 그 조건이 적혀 있지 않다」 고 그대로
    말하라 — `reason` 이 왜 모르는지를 준다. 채우려면 `set_test_condition` 이다.

    결과가 비면 `diagnosis` 를 읽어라: `equipment_with_item` 이 0 이면 조건이 좁은 것이
    아니라 그 시험을 등록한 장비가 없는 것이고, `catalog_series_with_item` 이 0 이 아니면
    `search_catalog` 로 「사면 되는 것」 을 찾을 수 있으며, `unlinked_equipment` 는 기종에 안
    이어져 검색에 안 걸리는 장비 수다.

    **이 응답이 답이다.** 줄마다 거점·부서·위치·담당자가 이미 있다 — 거점별로 다시 부르거나
    장비마다 사양을 열어 재확인하지 마라(판정은 서버가 사양을 보고 한 것이다).

    줄은 확실한 것(match)이 먼저다. `total` 이 `shown` 보다 크면 나머지는 **나열하지 말고**
    `by_verdict`(판정별 수)로 요약하라 — 「match 3대, 모름 40대」. 전부 봐야 할 때만 `limit`
    을 올린다(최대 50).
    """
    found = await _send(
        ctx,
        "POST",
        "/search/test-items",
        {
            "test_item_term_id": test_item_term_id,
            "property_term_id": property_term_id,
            "method_id": method_id,
            "conditions": conditions or [],
            "site_term_id": site_term_id,
            "include_unavailable": include_unavailable,
        },
    )
    empty = isinstance(found, dict) and not found.get("hits")
    found = _trim_hits(found, max(1, min(limit, SEARCH_HITS_MAX)))
    return _then(
        found,
        (
            "0건이다 — diagnosis 를 그대로 말하라. 사면 되는 것은 search_catalog 한 번이고,"
            " 다른 이름·거점·장비로 다시 뒤지지 마라."
            if empty
            else "이것이 답이다. 확실한 것(match)이 먼저이고 줄마다 거점·부서·위치·담당자가"
            " 있다. 나머지는 by_verdict 로 요약하라 — 거점별로 다시 부르거나 장비마다 사양을"
            " 열어 재확인하지 마라(판정은 서버가 사양을 보고 한 것이다)."
        ),
    )


@mcp.tool()
async def search_catalog(
    ctx: Context,
    test_item_term_id: str | None = None,
    property_term_id: str | None = None,
    method_id: str | None = None,
    conditions: list[dict[str, Any]] | None = None,
    limit: int = SEARCH_HITS,
) -> dict[str, Any]:
    """**「이 시험을 하려면 어떤 기종이 되나 / 사야 하나」** — 카탈로그에서 찾는다.

    `search_test_items` 가 **우리가 가진 것**을 답할 때 이것은 **세상에 있는 것**을 답한다.
    같은 물음(시험 항목 · 물성 · 규격 · 조건)을 받는다. 가진 것이 없다고 답하기 전에 이것을
    한 번 더 물어라 — 그다음 물음은 늘 「그러면 무엇을 사나」 다.

    답은 계열마다 **기종 단위**다(계열 봉투 0.5~600 kN 은 답이 못 된다). 기종마다
    `verdict`(match · accessory · partial · unknown)와 `owned_units`(이미 등록된 보유 대수)가
    온다. **owned_units 가 0 이 아니면 사기 전에 그 장비를 먼저 말하라.** `accessory` 는
    **챔버·노를 달면 되는 것**이고, 그 조건 줄의 `accessory` 칸이 어느 부속 기종을 얼마까지
    쓰는지와 그것의 보유 대수를 짚어 준다 — 본체와 부속을 따로 세어 말하라. `unmet_models` 는
    조건에 걸려 빠진 기종 수다 — 0 건일 때 「없어서」 와 「조건이 좁아서」 를 가른다.
    """
    found = await _send(
        ctx,
        "POST",
        "/search/catalog",
        {
            "test_item_term_id": test_item_term_id,
            "property_term_id": property_term_id,
            "method_id": method_id,
            "conditions": conditions or [],
        },
    )
    found = _trim_hits(found, max(1, min(limit, SEARCH_HITS_MAX)))
    return _then(
        found,
        "이것이 답이다. 줄마다 판정과 보유 대수(owned_units)가 있으니 기종마다 장비를 다시"
        " 찾거나 사양을 열지 마라. 보유 대수가 0 이 아니면 사기 전에 그 장비부터 말하고,"
        " total 이 shown 보다 크면 나머지는 by_verdict 로 요약하라.",
    )


@mcp.tool()
async def search_semantic(
    ctx: Context, q: str, kind: list[str] | None = None, limit: int = 10
) -> dict[str, Any]:
    """**글자가 안 겹쳐도 뜻이 가까운 것** — 자유 문장으로 물을 때의 첫 손잡이.

    「HAST」 「thermal shock」 「얇은 판 잡아당길 때 쓰는 규격」 「-40~150도 왔다갔다 하는
    챔버」 처럼 사람 말 그대로 넣는다. 돌아오는 것은 **후보**다 — 시험 항목·물성·계열·기종·
    규격·보유 장비·신뢰성 시험 중 뜻이 가까운 것들과 유사도(`score`, bge-m3 실측으로 0.5 위가
    맞는 것, 0.4 안팎은 우연). 벡터가 장비를 직접 답하지 않는다: 시험 항목이 정해지면
    `search_test_items(test_item_term_id=…)` 로 조건을 붙여 장비를 찾고, 이름이 하나로
    정해졌는지는 `resolve` 가 말한다 — `resolve` 도 글자로 못 찾으면 이 결과를 후보로 준다.

    `kind` 로 종류를 거른다 — `test_item` · `property` · `series` · `model` · `method` ·
    `equipment` · `reliability_test`. 보유 장비는 이 토큰의 사람이 볼 수 있는 것만 온다.

    `available=false` 면 부품(pgvector·Ollama)이 없는 설치다 — 오류가 아니다. 그때는
    `search_properties`·`resolve`·`search_series(q=…)` 처럼 이름으로 찾는 도구를 쓴다.
    """
    return _listed(
        await _get(ctx, "/search/semantic", {"q": q, "kind": kind, "limit": limit}),
        "hits",
    )


@mcp.tool()
async def search_properties(
    ctx: Context, q: str | None = None, linked_only: bool = True
) -> dict[str, Any]:
    """물성으로 묻기 전에 — **「인장강도」 가 어느 시험 항목으로 나오나.**

    사람은 「인장 되는 장비」 가 아니라 「인장강도 재는 장비」 라고 묻는다. 이 도구가 그
    물성(기준정보 축 `property`, code 가 `mechanical.tensile_strength` 같은 MaterialTwin
    키)과 그것을 내는 시험 항목들(`links`)을 준다 — **N:M** 이다. 유리전이온도는
    DSC·DMA·TMA 셋에서 나오고, 인장은 강도·항복·영률·연신율을 낸다.

    받은 물성의 `id` 를 `search_test_items(property_term_id=…)` 에 넣으면 서버가 그 시험
    항목 전부로 펼쳐 찾는다. 시험 항목 하나로 좁히려면 `links[].test_item_term_id` 를
    `test_item_term_id` 로 함께 준다.

    `linked_only=True`(기본)면 시험 항목이 이어진 물성만 온다. 이어진 것이 없는 물성은
    검색해도 늘 비므로, 그것을 「장비가 없다」 로 옮기지 마라 — 「아직 연결이 없다」 다.

    `links[].status` 가 `suggested` 면 기계가 제안한 연결이고 사람이 아직 확인하지
    않았다. 그대로 써도 되지만, 답할 때 그렇다고 말하라.
    """
    return _listed(
        await _get(ctx, "/properties", {"q": q, "include_unlinked": not linked_only}),
        "properties",
    )


@mcp.tool()
async def list_conditions(ctx: Context) -> dict[str, Any]:
    """검색이 묻는 조건 축들 — 온도·하중·속도·주파수·시편 두께·습도·항온조.

    각 조건의 `si_unit` 과 `display_unit` 이 함께 온다. **값은 저장 단위로 보낸다.**
    """
    return _listed(await _get(ctx, "/condition-keys"), "conditions")


# ── 부서 ──────────────────────────────────────────────────────────────────────


@mcp.tool()
async def list_workspaces(ctx: Context) -> dict[str, Any]:
    """부서 목록 — slug · 이름 · 조직도 경로(「개발본부 / 재료시험팀」).

    쓰기 API 가 요구하는 것은 이름이 아니라 **slug** 다(`create_reliability_test` 의
    `workspace_slug`, `register_equipment` 의 `workspace_slug`). 이 목록 없이 이름으로
    짐작해 넣으면 대개 404 이거나 남의 부서다. **같은 이름의 팀이 본부마다 있을 수 있다** —
    경로(`path`)로 가른다. 이름 하나만 알면 `resolve(kind="workspace", …)` 가 더 빠르다.
    """
    return _listed(await _get(ctx, "/workspaces/options"), "workspaces")


# ── 카탈로그: 계열 ─────────────────────────────────────────────────────────────


@mcp.tool()
async def search_series(
    ctx: Context,
    q: str | None = None,
    kind: str = "main",
    category_term_id: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """계열을 찾아 훑는다. `kind` 는 `main`(본체) · `accessory`(부속) · 빈 문자열(전체).

    **하나로 정하려면 `resolve` 를 쓴다.** 이 도구는 「무엇이 있나」 를 볼 때다.

    `category_term_id` 로 분류를 좁힌다(`resolve(axis="equipment_category", …)`). 분류는
    군/유형 두 층이라 **군(「정적 기계 시험기」)을 주면 아래 유형 전부**가 걸린다 —
    「기계 시험기 전부」 를 보려고 유형 여덟을 하나씩 부르지 않아도 된다.

    ## 여기 오는 것은 요약이다

    시험 항목은 **개수**(`test_item_count`)로만 온다. 무슨 시험이 되는지와 조건 수치는
    `get_series` 가 준다 — 목록에 다 실으면 한 쪽이 191 KB 다.

    그러니 **`test_item_count` 가 0 이 아닌 것을 「조건을 모른다」 고 답하지 마라.**
    아직 안 물어본 것이다.
    """
    return await _get(
        ctx,
        "/equipment-series",
        {
            "q": q,
            "kind": kind or None,
            "category_term_id": category_term_id,
            "limit": min(limit, MAX_LIMIT),
        },
    )


@mcp.tool()
async def get_series(ctx: Context, series_id: str) -> dict[str, Any]:
    """계열 하나 — 무슨 시험이 되나(test_items) · 어느 부속이 붙나(relations) ·
    기종이 몇 개인가 · 우리가 몇 대 가졌나.

    사양을 채우려면 여기서 `category_term_id` 를 얻어 `list_spec_definitions` 에
    넘긴다 — 분류를 주면 그 분류의 칸과 공통 칸이 함께 온다.
    """
    return await _get(ctx, f"/equipment-series/{series_id}")


@writes
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


@writes
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

    ## 여기 오는 것은 요약이다

    시험 항목은 **이름만** 오고(`test_items`), 사양은 그 기종을 가르는 대표 두어 칸
    (`headline_specs`)만 온다. 조건 수치와 사양 전부는 `get_model` ·
    `get_model_specs` 가 준다.

    **안 온 것을 「없다」 고 답하지 마라.** `spec_count` 가 실제로 몇 칸 적혔는지를
    말해 주므로, 그 수가 0 이 아니면 값은 있고 아직 안 물어본 것이다.
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


@writes
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


@writes
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
    requires_accessory: bool = False,
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

    **옵션 부속 기준이면 `requires_accessory=True`.** 카탈로그가 「-180~320 °C」 를 항온조
    옵션으로 적으면 그것은 본체 값이 아니다. 비고에만 적으면 검색은 글자를 못 읽고 「됨」
    이라고 답한다 — 표시로 둬야 검색이 「부속 있으면」 으로 가른다.

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
            "requires_accessory": requires_accessory,
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


@writes
async def import_equipment(
    ctx: Context,
    text: str,
    dry_run: bool = True,
    update_existing: bool = False,
) -> dict[str, Any]:
    """부서 대장을 **통째로** 넣는다. 한 대씩 `register_equipment` 를 300번 부르지 마라.

    `text` 는 엑셀에서 복사한 것 그대로다 — 탭이나 쉼표로 나뉜 표, **첫 줄이 머리글**.
    머리글은 한국어다(`import_columns` 가 받아 주는 이름을 준다):

        자산번호  장비명  보유부서  거점  설치위치  기종  장비유형  제조번호  상태  …

    부서·거점·장비유형·기종은 **이름**으로 적는다. 하나로 정해지지 않으면 그 줄이
    거절되고 후보가 온다 — **고르지 말고 사람에게 물어라.** 비슷한 기종에 끼워 넣으면
    그 장비의 하중·온도가 남의 것이 되고, 검색은 그 남의 수치로 「됩니다」 라고 답한다.

    ## 두 번 부른다

    `dry_run=True`(기본)는 **아무것도 저장하지 않고** 줄마다 판정을 돌려준다. 줄마다
    `problems` 가 비어 있으면 넣을 수 있고, 있으면 어느 칸(`field`)이 왜 틀렸는지가
    적혀 있다. 그것을 사람에게 보여 주고 확인받은 뒤 `dry_run=False` 로 다시 보낸다.

    **넣을 수 있는 줄은 넣고, 못 넣은 줄은 `imported=False` 로 남는다.** 못 넣은 줄만
    고쳐서 다시 보내면 된다 — 들어간 줄을 또 보내면 「이미 등록된 장비」 로 거절된다.

    ## 이미 등록된 자산번호

    기본은 거절이다. `update_existing=True` 면 **적힌 칸만** 갱신한다 — 빈 칸은 안
    건드리고, 부서와 기종은 안 바꾼다. 미리보기가 줄마다 `changes` 로 전후를 돌려주니
    **그것을 사람에게 보여 주고 나서** 넣어라. 30대의 위치가 조용히 바뀌는 일은 없어야 한다.

    ## 기종이 카탈로그에 없으면

    기종을 만들지 마라(시스템 관리자만 만들고, 사양 없는 기종은 검색을 망친다). 기종
    칸을 비우고 **모델명 칸에 적어 둔다.** 그 장비는 시험 항목이 0 건이라 검색에 안 걸리지만
    홈의 「카탈로그에 안 이어진 장비」 에 남아 나중에 잇는다.

    한 번에 2000줄까지다.
    """
    return await _send(
        ctx,
        "POST",
        "/equipment/import",
        {"text": text, "update_existing": update_existing},
        params={"dry_run": "true" if dry_run else "false"},
    )


@mcp.tool()
async def import_columns(ctx: Context) -> dict[str, Any]:
    """`import_equipment` 가 받는 열. 머리글에 어떤 이름을 쓸 수 있는지(별칭 포함)와
    어느 열이 필수인지를 준다 — 대장을 만들기 전에 한 번 본다."""
    return _listed(await _get(ctx, "/equipment/import/columns"), "columns")


@writes
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


@writes
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


@writes
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


@writes
async def set_test_condition(
    ctx: Context,
    equipment_test_item_id: str,
    condition_key_id: str,
    min_value: float | None = None,
    max_value: float | None = None,
    text_value: str | None = None,
    note: str | None = None,
    requires_accessory: bool = False,
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

    ## 부속이 있어야 나오는 범위면 `requires_accessory=True`

    챔버·노 옵션 기준 온도가 그렇다. 검색이 「됨」 대신 「부속 있으면」(`accessory`)으로
    답한다. 그 대에 부속이 실제로 있으면 False 로 다시 저장한다.
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
            "requires_accessory": requires_accessory,
        },
    )


@writes
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
        ctx,
        "PATCH",
        f"/equipment/{equipment_id}",
        {key: value for key, value in body.items() if value is not None},
    )


@mcp.tool()
async def get_calibrations(ctx: Context, equipment_id: str) -> dict[str, Any]:
    """이 장비의 **교정 이력** — 언제, 누가(기관), 결과, 차기일. 최근 것이 먼저.

    「마지막 교정이 언제였나」 「지금 유효한가」 의 답. 이력이 비어 있는데 장비가 교정
    대상(`calibration_required`)이면 그것은 「모른다」 가 아니라 **채워야 할 자리**다 —
    그렇게 말하라.
    """
    return _listed(await _get(ctx, f"/equipment/{equipment_id}/calibrations"), "calibrations")


@mcp.tool()
async def list_calibrations_due(ctx: Context) -> dict[str, Any]:
    """곧 만료되거나 **이미 지난** 교정 — 전사, 내가 볼 수 있는 장비.

    지난 것을 빼지 않는다. 빼면 만료된 장비가 조용히 계속 쓰이고, 그것으로 낸 값은
    나중에 통째로 못 믿게 된다. 「이달 교정 받아야 할 장비」 를 물으면 여기서 시작한다.
    """
    return _listed(await _get(ctx, "/server/calibrations-due"), "due")


@writes
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
async def get_catalog_state(ctx: Context) -> dict[str, Any]:
    """카탈로그가 **정본보다 뒤졌나.** 「카탈로그에 없다」 고 답하기 전에 이것을 본다.

    반입은 사람이 돌리고 배포는 파일만 새로 놓는다. `behind` 가 참이면 이 설치의
    카탈로그는 정본(`objects` 객체)보다 오래된 것(`imported_objects` 객체, `imported_at`)이라
    「없다」 는 답이 「아직 안 들어왔다」 일 수 있다 — 그렇게 말하고, 관리자에게
    `scripts/import_catalog.py` 를 돌리라고 하라. `never` 는 한 번도 반입 안 한 설치다.
    """
    return await _get(ctx, "/server/catalog")


@mcp.tool()
async def list_pending_work(ctx: Context) -> dict[str, Any]:
    """**채울 자리.** 우리가 가진 것 중 비어 있는 것만 센다.

    시험 항목이 안 적힌 장비 · 사양이 안 적힌 보유 기종 · 시험 항목이 안 적힌 보유 계열 ·
    원본 확인이 필요한 기종 · 교정 기한이 지난 장비.

    **여기부터 채워라.** 카탈로그 전체를 채우려 들면 끝이 없어 보여서 아무도
    시작하지 않는다.
    """
    return _listed(await _get(ctx, "/server/maintenance"), "items")


# ── 시험 항목 카탈로그 — 사슬의 가운데 ──────────────────────────────────────────


@mcp.tool()
async def list_test_items(ctx: Context, gap: str | None = None) -> dict[str, Any]:
    """**시험 항목 96종, 한 줄에 사슬 전체의 수.** 0 이 곧 공백이다.

        물성  ⇄  시험 항목  →  규격  →  계열/기종  →  보유 장비

    줄마다 `properties_total`(그중 `properties_confirmed`) · `methods_total`(그중
    `methods_with_requirements`) · `series_count` / `model_count` · `equipment_count`(내가
    볼 수 있는 보유 장비) · `condition_keys`(검색축 라벨) 가 온다.

    `gap` 으로 공백만 거른다: `properties`(물성 없음) · `methods`(규격 없음) · `series`(되는
    계열 없음) · `equipment`(보유 장비 없음) · `axes`(검색축 없음). 각각 채우는 사람이
    다르다 — 물성은 재료 쪽, 규격은 시험실, 검색축은 시스템 관리자.

    「이 시험 우리가 할 수 있나」 는 `equipment_count` 가 답하고, 「사면 되나」 는
    `series_count` 가 답한다. 둘 다 0 이면 그 장비가 카탈로그에도 없는 것이다.
    """
    rows = await _get(ctx, "/test-items")
    if isinstance(rows, list) and gap:
        gaps = {
            "properties": lambda r: r.get("properties_total", 0) == 0,
            "methods": lambda r: r.get("methods_total", 0) == 0,
            "series": lambda r: r.get("series_count", 0) == 0,
            "equipment": lambda r: r.get("equipment_count", 0) == 0,
            "axes": lambda r: not r.get("condition_keys"),
        }
        if gap not in gaps:
            return {"error": f"gap 은 {' · '.join(gaps)} 중 하나입니다"}
        rows = [r for r in rows if gaps[gap](r)]
    return _listed(rows, "test_items")


@mcp.tool()
async def get_test_item(ctx: Context, test_item_term_id: str) -> dict[str, Any]:
    """시험 항목 하나 — **얻는 물성 · 규격 · 되는 계열 · 보유 장비 · 검색축**을 한 자리에.

    `condition_keys` 가 이 시험에 뜻이 있는 조건 축이다(인장 → 하중·속도·온도). 검색에
    조건을 붙일 때 이것을 먼저 보라 — 축 밖의 조건은 대개 `unknown` 만 늘린다. 비어
    있으면 아직 안 정해진 것이다(`set_test_item_axes` 로 정한다, 시스템 관리자).

    `properties[].status` 가 `suggested` 면 기계의 제안이다. `methods` 는 이 시험의
    규격으로 정해진 것이고, `series[].method_codes` 는 그 계열이 이 시험에 인용한 규격이다.
    `equipment` 는 내가 볼 수 있는 보유 장비만이다.
    """
    return await _get(ctx, f"/test-items/{test_item_term_id}")


@writes
async def set_test_item_axes(
    ctx: Context, test_item_term_id: str, condition_key_ids: list[str]
) -> dict[str, Any]:
    """시험 항목에 **뜻이 있는 조건 축**을 정한다(통째로 바꾼다). 시스템 관리자.

    인장은 하중·속도·온도, 챔버는 온도·습도. 카탈로그가 갖고 있지 않은 지식이라 사람이
    정한다 — **AI 가 짐작으로 정하지 마라.** 사람이 「인장은 하중·속도·온도」 라고 말했을
    때만 옮겨 적어라. 조건 키 id 는 `list_conditions()` 가 준다.
    """
    return await _send(
        ctx,
        "PUT",
        f"/test-items/{test_item_term_id}/condition-keys",
        {"condition_key_ids": condition_key_ids},
    )


# ── 규격 — 항목 미정과 요구 조건 ─────────────────────────────────────────────


@mcp.tool()
async def list_methods(
    ctx: Context,
    q: str | None = None,
    test_item: str | None = None,
    requirement: str | None = None,
    cited: str | None = None,
    used: str | None = None,
    include_superseded: bool = False,
    limit: int = 50,
) -> dict[str, Any]:
    """규격 목록 — **못 하는 시험과 끊긴 연결을 가른다.**

    줄마다 `test_item`(이 규격이 무슨 시험의 것인지) · `series_count`(이어진 계열) ·
    `pending_series_count`(인용은 했는데 시험 항목이 안 정해져 못 이어진 계열) ·
    `equipment_count`(가능 장비) · `requirements`(요구 조건) 가 온다.

    **`series_count` 가 0 인데 `pending_series_count` 가 0 이 아니면 못 하는 시험이 아니라
    끊긴 연결이다** — `set_method_test_item` 으로 시험 항목을 정하면 붙는다.

    거르기: `test_item` 은 값 id 또는 `none`(안 정해진 것만) · `requirement=none`(요구
    조건 없는 것만) · `cited=none`(어느 계열에도 안 이어진 것만) · `used=owned`(보유 장비가
    실제로 가리키는 것만 — 요구 조건은 여기부터 채운다).
    """
    return await _get(
        ctx,
        "/methods",
        {
            "q": q,
            "test_item": test_item,
            "requirement": requirement,
            "cited": cited,
            "used": used,
            "include_superseded": include_superseded,
            "limit": limit,
        },
    )


@writes
async def create_method(
    ctx: Context,
    code: str,
    title: str,
    edition: str | None = None,
    test_item_term_id: str | None = None,
    body_term_id: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    """규격 하나를 등록한다. **먼저 `resolve(kind="method", text=code)` 로 찾아라.**

    규격 번호는 표기가 갈린다(「JIS B 0601」/「JIS B0601」) — 서버가 공백을 지워 견주므로
    이미 있으면 409 가 오고, 그것은 실패가 아니라 답이다(그 id 를 쓴다).

    `edition` 은 판(「2019」 「Ed.3」). 같은 규격의 다른 판은 **다른 줄**이다 — 요구 조건이
    판마다 바뀐다. `test_item_term_id` 는 이 규격이 어느 시험의 것인지(`resolve(kind="term",
    axis="test_item")`), `body_term_id` 는 제정기관(`axis="standard_body"`). **둘 다 모르면
    비운다** — 항목 미정 규격은 검토함이 사람에게 묻는다. 전사 공용으로 만들어진다.
    """
    return await _send(
        ctx,
        "POST",
        "/methods",
        {
            "code": code,
            "title": title,
            "edition": edition,
            "test_item_term_id": test_item_term_id,
            "body_term_id": body_term_id,
            "summary": summary,
        },
    )


@writes
async def set_requirement(
    ctx: Context,
    method_id: str,
    condition_key_id: str,
    min_value: float | None = None,
    max_value: float | None = None,
    text_value: str | None = None,
    is_mandatory: bool = True,
    note: str | None = None,
) -> dict[str, Any]:
    """규격의 **요구 조건 한 줄** — 규격서를 읽다 조건 하나를 발견했을 때. 표로 여럿이면
    `import_requirements`.

    `condition_key_id` 는 `list_conditions` 가 준다. **값은 그 축의 `si_unit` 으로** —
    `list_conditions` 가 축마다 알려 준다(하중 축은 kN 이라 20 kN 이면 20 이다; 축의 단위를
    지어내지 말고 읽어라). 같은 조건이 이미 있으면 덮어쓴다. **한쪽을 비울 수 있다**:
    「20 kN 이상」 은 min 만 있고 max 는 None 이다 — 0 으로 채우면 상한이 0 인 것과 구별되지
    않는다.

    이 조건이 곧 검색 물음이 된다(`search_test_items(method_id=…)`). 그래서 규격서에 적힌
    것만 적고, 관례로 아는 값은 `note` 에 그렇다고 적는다.
    """
    return await _send(
        ctx,
        "PUT",
        f"/methods/{method_id}/requirements",
        {
            "condition_key_id": condition_key_id,
            "min_value": min_value,
            "max_value": max_value,
            "text_value": text_value,
            "is_mandatory": is_mandatory,
            "note": note,
        },
    )


@writes
async def set_method_test_item(
    ctx: Context, method_id: str, test_item_term_id: str
) -> dict[str, Any]:
    """규격에 **시험 항목을 정한다.** 정하는 순간 그 규격을 항목 미정으로 인용해 둔 계열의
    그 시험 항목에 자동으로 붙는다 — 사람이 계열마다 다시 잇지 않는다.

    **지어서 정하지 마라.** ASTM D638 이 인장이라는 것은 규격 번호를 아는 사람의 판단이다.
    모르면 `get_method` 의 `cited_series`(어느 계열이 인용했나)를 보고 사람에게 물어라.

    **검토함에 물음이 열려 있는 규격은 여기서 정하지 않는다** — 검토함의 확정은 사람이
    화면에서 하고, 이 도구로 같은 결과를 내면 확정을 우회한 것이다(서버가 409 로 막는다).
    「검토함 첫 줄 확정해줘」 에는 「화면에서 하시라」 고 답한다.
    """
    return await _send(
        ctx, "PATCH", f"/methods/{method_id}", {"test_item_term_id": test_item_term_id}
    )


@mcp.tool()
async def get_method(ctx: Context, method_id: str) -> dict[str, Any]:
    """규격 하나 — 시험 항목 · 요구 조건 · **인용한 계열**(`cited_series`, `pending` 이면 어느
    시험 항목의 것인지 미정) · 가능 장비 수."""
    return await _get(ctx, f"/methods/{method_id}")


@writes
async def import_requirements(ctx: Context, text: str, dry_run: bool = True) -> dict[str, Any]:
    """규격의 **요구 조건을 표로** 넣는다 — 규격서를 보고 적은 것을 통째로.

    `text` 는 머리글 줄까지 있는 표(탭 또는 쉼표): 열은 규격 · 판 · 조건 · 최소 · 최대 ·
    값 · 필수 · 비고. 값은 조건의 단위(kN · °C)로 적되 단위를 같이 적어도 된다 —
    **다른 단위면 거절한다**(20 N 을 kN 으로 들이면 천 배 틀린다).

    `dry_run=True`(기본)면 저장하지 않고 줄마다 판정만 준다. 사람이 확인한 뒤 같은 글자로
    `dry_run=False`. 같은 규격·조건이 이미 있으면 `replaces` 로 미리 말한다.

    **값을 지어내지 마라.** 이 도구는 사람이 규격서를 보고 적은 표를 옮기는 길이다. 틀린
    조건은 빈 조건보다 나쁘다 — 검색이 자신 있게 틀린 답을 낸다.
    """
    return await _send(
        ctx,
        "POST",
        "/methods/requirements/import",
        {"text": text},
        params={"dry_run": "true" if dry_run else "false"},
    )


# ── 물성 연결 — 묶음 확인 ─────────────────────────────────────────────────────


@writes
async def suggest_property_link(
    ctx: Context, test_item_term_id: str, property_term_id: str, note: str | None = None
) -> dict[str, Any]:
    """시험 항목 → 물성 연결을 **제안**한다. 확인이 아니다.

    「인장에서 항복강도가 나온다」 처럼 규격·문헌을 읽고 알게 된 연결을 적는 자리다. 들어가는
    상태는 언제나 `suggested`, 출처는 `agent` — **AI 가 알아서 확인하지 않는다.** 확인은
    「사람이 봤다」 는 뜻이고 카탈로그 정본에 실리므로, 사람이 물성 화면이나
    `confirm_property_links` 로 한다.

    둘 다 id 다(`resolve(kind="term", axis="test_item"|"property")`). 이미 이어져 있으면 409.
    `note` 에는 덧붙는 조건(「신율계 필요」)이나 근거(규격 번호)를 적는다.
    """
    return await _send(
        ctx,
        "POST",
        "/test-item-properties",
        {
            "test_item_term_id": test_item_term_id,
            "property_term_id": property_term_id,
            "note": note,
            "status": "suggested",
            "source": "agent",
        },
    )


@writes
async def confirm_property_links(
    ctx: Context, link_ids: list[str], status: str = "confirmed"
) -> dict[str, Any]:
    """물성↔시험 항목 제안을 **묶어서 확인**하거나(`confirmed`) 되돌린다(`suggested`).

    사람이 「인장이 내는 것은 이 다섯 개, 맞다」 고 했을 때 그 줄의 `link_id` 들을 한 번에
    올린다(`search_properties` 의 `links[].id`, 또는 `get_test_item` 의
    `properties[].link_id`). 이미 그 상태인 것은 안 세고 `changed` 로 실제 바뀐 수를 준다.

    **AI 가 알아서 확인하지 마라.** 확인은 「사람이 봤다」 는 뜻이고, 내보내기가 카탈로그
    정본에 싣는 값이다. 사람이 말한 것만 옮겨라.
    """
    return await _send(
        ctx, "PATCH", "/test-item-properties/bulk", {"link_ids": link_ids, "status": status}
    )


# ── 이 기종만의 사양 — 정의 없이 붙는 값 ───────────────────────────────────────


@writes
async def add_free_spec(
    ctx: Context,
    model_id: str,
    label: str,
    value_text: str,
    unit: str | None = None,
    note: str | None = None,
    source_id: str | None = None,
    source_page: int | None = None,
) -> dict[str, Any]:
    """**이 기종만의 사양** 한 줄 — 정의 없이 이름·값·단위로 붙인다.

    `list_spec_definitions` 에 맞는 칸이 없을 때 여기 둔다(카탈로그 키 950종 중 803종이 한
    기종에만 나온다 — 그것을 정의로 세우면 「사양 추가」 목록이 못 쓰게 된다). 값은 글자
    그대로(「LV 4종」 「0 ~ 600」). 같은 이름이 여러 기종에 쌓이면 `promote_free_spec` 으로
    정의로 올린다. `get_model` 의 `free_specs` 가 있는 줄을 준다.
    """
    return await _send(
        ctx,
        "POST",
        f"/equipment-models/{model_id}/free-specs",
        {
            "label": label,
            "value_text": value_text,
            "unit": unit,
            "note": note,
            "source_id": source_id,
            "source_page": source_page,
        },
    )


@writes
async def promote_free_spec(
    ctx: Context,
    model_id: str,
    free_id: str,
    key: str,
    label: str,
    group_id: str,
    kind: str,
    unit: str = "",
    apply_same_key: bool = True,
) -> dict[str, Any]:
    """이 기종만의 사양을 **정의로 세운다.** 시스템 관리자.

    `key`(소문자·밑줄, 만든 뒤 못 바꿈) · `label` · `group_id`(`/spec-groups`) · `kind`
    (`range` · `number` · `text` · `boolean`) · `unit` 을 사람이 정한다 — **이름을 기계가
    지어내면 그것이 진실이 된다.** 정의는 그 기종의 분류에 붙고, `apply_same_key` 면 같은
    원본 키를 가진 다른 기종의 줄도 함께 옮긴다. 수치로 못 읽는 줄(「약 300」)은 그대로
    남고 `left` 로 센다.

    `get_model` 의 `free_specs[].same_key_models` 가 0 이 아닐 때가 올릴 때다.
    """
    return await _send(
        ctx,
        "POST",
        f"/equipment-models/{model_id}/free-specs/{free_id}/promote",
        {
            "key": key,
            "label": label,
            "group_id": group_id,
            "kind": kind,
            "unit": unit,
            "apply_same_key": apply_same_key,
        },
    )


# ── 기준정보 — 축과 값 ────────────────────────────────────────────────────────


@mcp.tool()
async def list_reference(ctx: Context) -> dict[str, Any]:
    """**이 시스템의 기준정보가 무엇인가** — 객체 종류마다 한 줄.

    종류(시험 항목·물성·장비 계열·기종·보유 장비·신뢰성 시험 …)마다 저장 방식(축의 값인지
    제 표를 가진 객체인지) · 건수 · 고정 칸 · 관리자가 정의한 칸(검색 조건·사양·속성)이 온다.
    **무엇을 어디에 적어야 하는지 모를 때 여기부터 본다** — 「이 값은 축에 더하는 것인가,
    객체로 만드는 것인가」 의 답이 여기 있다.
    """
    return _listed(await _get(ctx, "/reference/overview"), "kinds")


@mcp.tool()
async def list_axes(ctx: Context) -> dict[str, Any]:
    """기준정보 **축**의 목록 — slug · 이름 · 소속 · 값 수 · 등록 정책.

    `entry_policy` 가 `open` 이면 값은 **누구나 더한다**(`create_term`). `closed` 면 시스템
    관리자만 — 제정기관·조건처럼 뜻이 계약인 축이다. 값이 0인 축은 아직 아무도 안 채운
    축이고, 거기에 값을 넣으면 그 축을 쓰는 화면이 그날부터 답을 한다.
    """
    return _listed(await _get(ctx, "/vocabularies"), "axes")


@mcp.tool()
async def list_terms(
    ctx: Context, axis: str, q: str | None = None, include_inactive: bool = False
) -> dict[str, Any]:
    """한 축의 값 — 이름 · 코드 · 별칭 · 상위 값 · 상태.

    `axis` 는 `list_axes` 의 slug(`test_item` · `property` · `site` ·
    `equipment_category` · `maker` · `standard_body` …). **값을 만들기 전에 이걸로
    찾는다** — 같은 뜻의 값이 이미 있는데 새로 만들면 검색이 절반만 답한다. 이름이
    갈릴 것 같으면 `resolve(kind="term", axis=…)` 가 별칭까지 본다.
    """
    return _listed(
        await _get(
            ctx,
            f"/vocabularies/{axis}/terms",
            {"q": q, "include_inactive": "true" if include_inactive else None},
        ),
        "terms",
    )


@writes
async def create_axis(
    ctx: Context,
    slug: str,
    label: str,
    domain: str = "common",
    description: str | None = None,
    entry_policy: str = "open",
    parent_slug: str | None = None,
    attribute_schema: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """기준정보 **축**을 새로 세운다. 시스템 관리자. **웬만하면 만들지 마라.**

    **먼저 `list_axes` 로 본다.** 뜻이 닿는 축이 있으면 그 축에 값을 더하는 것(`create_term`)
    이 맞다. 축이 둘로 갈리면 값도 둘로 갈리고, 합치는 길이 없다 — 값 병합(`merge_terms`)은
    같은 축 안에서만 된다. 「불량 모드」 와 「불량 유형」 이 따로 서면 그대로 굳는다.

    **여기서 만든 축은 서랍일 뿐이다.** 기존 축(`manufacturer` 같은)은 화면과 코드가 그
    slug 를 걸고 있어서 값이 쓰인다. 새 축에는 그런 자리가 없으므로 검색·판정·반입 어디에도
    저절로 끼지 않는다 — 값을 담아 두고 사람이 보는 목록이 된다. 그래도 **뜻이 다른 값을
    남의 축에 넣는 것보다는 낫다**(제정기관 축에 회사 이름이 들어가는 일이 실제로 있다).

    `domain` 은 화면이 묶는 자리 — `equipment` · `catalog` · `method` · `common`.
    `entry_policy` 가 `closed` 면 값도 시스템 관리자만 더한다.

    `attribute_schema` 는 **이 축의 값이 갖는 칸**이다(물성 값의 기호·단위처럼):
    `[{"key": "symbol", "label": "기호", "kind": "text"}]` — `kind` 는 `text`·`number`·`list`.
    **축에 한 번 적는다** — 값마다 물으면 같은 답을 수백 번 저장하는 셈이다. 나중에 고치는
    것은 `update_axis`.

    **이 설치에만 산다.** 설치 시드(`ensure_reference_data`)가 심는 축이 정본이라, 여기서
    만든 축은 새로 설치하는 서버에 안 생긴다. 계속 쓸 축이면 사람이 시드에 더해야 한다고
    말해 줘라.
    """
    return await _send(
        ctx,
        "POST",
        "/vocabularies",
        {
            "slug": slug,
            "label": label,
            "domain": domain,
            "description": description,
            "entry_policy": entry_policy,
            "parent_slug": parent_slug,
            "attribute_schema": attribute_schema or [],
        },
    )


@writes
async def update_axis(
    ctx: Context,
    axis: str,
    label: str | None = None,
    description: str | None = None,
    entry_policy: str | None = None,
    attribute_schema: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """축의 **이름·설명·정책·값이 갖는 칸**을 고친다. 시스템 관리자. 안 보낸 것은 그대로.

    **`slug` 와 소속은 못 바꾼다** — 코드가 그 이름을 걸고 있다.

    `attribute_schema` 는 **통째로 갈린다.** 칸 하나를 더하려면 `list_axes` 로 지금 있는
    것을 받아 **전부** 보낸다 — 빠뜨린 칸은 정의에서 사라지고, 그러면 화면이 그 칸을 안
    그린다(값에 적힌 내용은 남는다. 「그 밖의 속성」 으로 보인다).

    `entry_policy` 를 `open` -> `closed` 로 잠그는 일은 실제로 있다(값이 흩어지기 시작한
    축). 반대로 여는 것도 되지만, 검색의 첫 축이면 오타가 값이 된다.
    """
    body: dict[str, Any] = {}
    if label is not None:
        body["label"] = label
    if description is not None:
        body["description"] = description
    if entry_policy is not None:
        body["entry_policy"] = entry_policy
    if attribute_schema is not None:
        body["attribute_schema"] = attribute_schema
    return await _send(ctx, "PATCH", f"/vocabularies/{axis}", body)


@writes
async def create_condition_key(
    ctx: Context,
    key: str,
    label: str,
    kind: str = "range",
    dimension: str = "",
    si_unit: str = "",
    display_unit: str = "",
    choices: list[str] | None = None,
    help: str | None = None,
) -> dict[str, Any]:
    """**검색 조건 축**을 새로 만든다(온도·하중처럼 판정에 쓰이는 칸). 시스템 관리자.

    **먼저 `list_conditions` 로 본다.** 같은 뜻의 축이 있으면 그것을 쓴다 — 「시험 온도」 와
    「온도」 가 따로 서면 장비마다 다른 축에 적히고, 검색은 그때부터 절반만 답한다.

    ## 단위를 틀리면 조용히 틀린 답이 나온다

    `si_unit` 은 **저장 단위**, `display_unit` 은 화면이 쓰는 실무 단위다. 하중은
    `si_unit="kN"`, 온도는 `si_unit="degC"` 처럼 이 저장소가 실제로 쓰는 값을 따른다 —
    `list_conditions` 로 옆 축이 무엇을 쓰는지 보고 맞춰라. `dimension` 이 같은 축끼리만
    환산이 성립한다(temperature · force · length · time · frequency).

    **만든 뒤 `si_unit` 은 못 바꾸는 것으로 여겨라.** 고치는 API 는 있지만, 그 순간 이미
    저장된 숫자 전부가 다른 값이 된다.

    `kind` 는 `range`(구간 — 대부분) · `choice`(고른 값, `choices` 필요) · `boolean`.

    ## 만든 다음이 중요하다

    축만 만들면 아무 일도 안 일어난다. **시험 항목에 걸어야**(`set_test_item_axes`) 그
    시험을 물을 때 조건으로 뜨고, 장비·기종에 값이 적혀야 판정이 된다.
    """
    return await _send(
        ctx,
        "POST",
        "/condition-keys",
        {
            "key": key,
            "label": label,
            "kind": kind,
            "dimension": dimension,
            "si_unit": si_unit,
            "display_unit": display_unit,
            "choices": choices or [],
            "help": help,
        },
    )


@writes
async def create_term(
    ctx: Context,
    axis: str,
    value: str,
    code: str | None = None,
    parent_term_id: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """기준정보 값 하나를 더한다. **만들기 전에 반드시 찾는다.**

    `resolve(kind="term", axis=…, name=…)` 나 `list_terms` 로 먼저 보고, 같은 뜻의 값이
    있으면 **그것을 쓴다**. 이미 있는 이름이면 409 가 오는데 그것은 실패가 아니라 답이다
    — 별칭까지 보고 막으므로, 409 가 오면 그 값의 id 를 쓰면 된다.

    **`resolve` 가 `candidates` 를 주면 만들지도, 별칭으로 잇지도 말고 사람에게 묻는다.**
    「크리프」 가 「크리프 파단」 의 후보로 잡혔을 때 그것을 별칭으로 붙이면 다른 시험이
    한 이름이 된다 — 실측에서 AI 가 정확히 그렇게 했다. 같은 것인지는 사람만 안다.

    `code` 는 정본·반입이 거는 이름이다(시험 항목의 `tensile` 처럼). **모르면 비운다** —
    지어내면 다음 반입이 다른 코드로 같은 값을 또 만든다. `parent_term_id` 는 계층이
    있는 축(장비 분류의 군 → 유형)에서만.

    `entry_policy` 가 `closed` 인 축(제정기관·조건 …)은 시스템 관리자만 더할 수 있다 —
    거절되면 사람에게 넘긴다.

    `attributes` 는 **그 축이 정한 칸**을 채운다(`list_axes` 의 `attribute_schema` 가
    무슨 칸인지 말한다): 물성이면 `{"symbol": "σ", "unit": "MPa"}`. 스키마에 없는 키를
    넣어도 지워지지는 않지만 화면이 「그 밖의 속성」 으로 밀어 둔다 — **칸 이름을 지어내지
    말고 스키마를 먼저 봐라.** 모르는 칸은 비운다.
    """
    return await _send(
        ctx,
        "POST",
        f"/vocabularies/{axis}/terms",
        {
            "value": value,
            "code": code,
            "parent_term_id": parent_term_id,
            "attributes": attributes or {},
        },
    )


@writes
async def update_term(
    ctx: Context,
    term_id: str,
    value: str | None = None,
    code: str | None = None,
    status: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """기준정보 값을 고친다. **안 보낸 칸은 그대로.**

    **이름을 바꾸는 것은 그 값을 쓰는 모든 화면의 글자를 바꾸는 일이다.** 오타를 고치는
    것이라면 맞다. 뜻이 다른 값이면 고치지 말고 새로 만들어라 — 「인장」 을 「고온 인장」 으로
    고치면 그 값을 쓰던 장비 전부가 조용히 다른 시험을 하는 장비가 된다.

    `attributes` 는 **보낸 키만 바뀐다**(축의 `attribute_schema` 가 무슨 칸인지 말한다).
    `status` 는 `active` · `deprecated` — **폐기해도 지워지지 않는다.** 쓰던 곳은 그대로
    남고 새로 고를 때만 안 보인다. 값을 합치려면 `merge_terms` 다.
    """
    body: dict[str, Any] = {}
    if value is not None:
        body["value"] = value
    if code is not None:
        body["code"] = code
    if status is not None:
        body["status"] = status
    if attributes is not None:
        body["attributes"] = attributes
    return await _send(ctx, "PATCH", f"/vocabularies/terms/{term_id}", body)


@writes
async def add_term_alias(ctx: Context, term_id: str, value: str) -> dict[str, Any]:
    """기준정보 값에 **다른 이름**을 붙인다. 시스템 관리자.

    별칭은 찾기(`resolve`)가 이름보다 먼저 보는 것이라, 「thermal shock」 으로 물어도
    「열충격」 을 찾게 만든다. **사람이 「이 표기는 저 값이다」 라고 말했을 때만** 붙인다 —
    `resolve` 가 후보로 잡아 줬다는 이유로 붙이지 않는다(후보는 「비슷하다」 지 「같다」 가
    아니다). **같은 축의 다른 값이 쓰는 표기는 못 붙인다**(409) — 그러면
    한 이름이 두 값을 가리켜 찾기가 갈린다. 실제로 갈려 들어온 표기만 붙이고, 있을 법한
    표기를 지어 붙이지 않는다.
    """
    return await _send(ctx, "POST", f"/vocabularies/terms/{term_id}/aliases", {"value": value})


@writes
async def merge_terms(ctx: Context, term_id: str, into_term_id: str) -> dict[str, Any]:
    """같은 뜻으로 갈린 값 둘을 하나로. 시스템 관리자.

    `term_id` 의 쓰임이 `into_term_id` 로 옮겨 가고, 원래 이름은 **별칭으로 남는다** —
    지우지 않는 이유는 같은 오타가 또 들어오는 것을 막기 위해서다.

    **사람이 「이 둘은 같은 것」 이라고 말했을 때만** 부른다. 비슷해 보인다는 이유로 합치면
    (「인장」 과 「고온 인장」) 서로 다른 시험이 한 줄이 되고, 그 뒤로는 갈랐던 사실조차
    안 남는다. 먼저 `get_term_references` 로 무엇이 옮겨 가는지 보여 주고 확인받는다.
    """
    return await _send(
        ctx, "POST", f"/vocabularies/terms/{term_id}/merge", {"target_term_id": into_term_id}
    )


# ── 기준정보 — 쓰임과 연결 해제 ──────────────────────────────────────────────


@mcp.tool()
async def get_term_references(ctx: Context, term_id: str) -> dict[str, Any]:
    """기준정보 값 하나가 **어디에 쓰이나** — 계열·기종·장비·규격·물성 연결 등, 종류마다
    수와 줄. 값을 지우거나 합치기 전에 본다: 쓰이는 값은 못 지우고, 쓰임을 풀거나 다른
    값으로 옮긴 뒤에 지운다(`detach_term_reference`)."""
    return _listed(await _get(ctx, f"/vocabularies/terms/{term_id}/references"), "groups")


@writes
async def detach_term_reference(
    ctx: Context,
    term_id: str,
    kind: str,
    row_id: str,
    reassign_to_term_id: str | None = None,
) -> dict[str, Any]:
    """기준정보 값의 쓰임 하나를 **풀거나 다른 값으로 옮긴다.** 시스템 관리자.

    `kind` 와 `row_id` 는 `get_term_references` 가 준다. `reassign_to_term_id` 를 주면
    그 값으로 옮기고, 안 주면 푼다(종류에 따라 비우거나 지운다 — 응답의 `detach` 가 말한다).
    **사람이 「이 장비의 분류를 저것으로 바꿔라」 고 했을 때만** 쓴다.
    """
    if reassign_to_term_id:
        return await _send(
            ctx,
            "POST",
            f"/vocabularies/terms/{term_id}/references/{kind}/{row_id}/reassign",
            {"target_term_id": reassign_to_term_id},
        )
    return await _send(
        ctx, "DELETE", f"/vocabularies/terms/{term_id}/references/{kind}/{row_id}"
    )


# ── 신뢰성 시험 — 부서가 수행하는 절차 ────────────────────────────────────────


@mcp.tool()
async def list_reliability_tests(
    ctx: Context, workspace: str | None = None, attr: list[str] | None = None
) -> dict[str, Any]:
    """부서가 수행하는 **신뢰성 시험**(고온고습 1000h · 열충격 500 cycle …).

    「시험 항목」(장비가 하는 측정 — 인장·경도)과 **다른 층**이다: 신뢰성 시험 하나가 시험
    항목 하나 이상을 써서 돌고, 그 항목이 장비로 이어진다. `workspace` 를 주면 그 부서 것만,
    안 주면 전사 전부 — 「저 부서는 무슨 시험을 하나」 를 가로질러 본다.

    줄마다 쓰는 시험 항목과 **그 항목이 되는 그 부서 장비 수**가 온다. 0 이면 시험은 정했는데
    돌릴 장비가 그 부서에 없다는 뜻이다(다른 부서에는 있을 수 있다 — `test_capability`).

    `attr` 은 속성 값 조건이다 — 왼쪽은 `list_attribute_definitions` 가 주는 `key` 다
    (`["temp_x>=100"]`). 여러 개면 **모두** 만족해야 한다.

    조건을 걸었는데 0건이면 `diagnosis` 가 함께 온다 — 조건마다 값이 적힌 수 · 단위 못
    바꾼 수 · 그 조건 하나로 걸리는 수와 한 줄. **「그런 시험 없습니다」 로 뭉개지 말고 그
    줄을 그대로 말하라.** 가장 흔한 실제는 「아무도 안 적었다」 다.
    """
    found = _listed(
        await _get(ctx, "/reliability-tests", {"workspace": workspace, "attr": attr}),
        "tests",
    )
    if attr and found.get("count") == 0:
        # 빈 목록만 돌려주면 AI 는 「없다」 로 옮긴다. 진단은 서버가 세고 서버가 말한다 —
        # 화면도 같은 엔드포인트를 쓴다.
        found["diagnosis"] = await _get(
            ctx,
            "/attribute-definitions/diagnose",
            {"target": "reliability_test", "attr": attr},
        )
    return found


@mcp.tool()
async def get_reliability_test(ctx: Context, test_id: str) -> dict[str, Any]:
    """신뢰성 시험 하나 — 목적 · 쓰는 시험 항목 · 속성 값 전부.

    속성의 `status` 가 `draft` 면 **초안**이다: 표시와 수집만 하고 검색·판정·색인 카드에는
    안 들어간다. 초안 값을 근거로 「이 조건으로 검색됩니다」 라고 말하지 마라.
    """
    return await _get(ctx, f"/reliability-tests/{test_id}")


@mcp.tool()
async def list_attachments(ctx: Context, target: str, object_id: str) -> dict[str, Any]:
    """붙은 **그림과 첨부**의 목록 — 무엇이 어느 칸에 붙어 있나.

    `target` 은 지금 `reliability_test` 뿐이다. 줄마다 `caption`(무엇을 찍었나) ·
    `definition_label`(어느 칸에 붙었나, 비면 카드 전체) · 형식 · 크기가 온다.

    **너는 그림을 못 본다.** 읽을 수 있는 것은 `caption` 뿐이다 — 설명이 비어 있으면 그
    그림은 너에게 없는 것과 같으니, 「그림 3장이 있고 설명은 없습니다」 라고 그대로 말하고
    **내용을 짐작하지 마라.** 「시편 장착 방향」 이라고 적힌 그림을 보고 방향을 말하는 것도
    짐작이다 — 적힌 글자까지만 옮긴다.

    사람에게 보이려면 화면의 그 시험을 열라고 말한다. 파일 주소(`url`)는 자격이 있어야
    열리므로 그대로 건네도 브라우저에서 안 열린다.
    """
    return _listed(
        await _get(ctx, "/attachments", {"target": target, "object_id": object_id}),
        "attachments",
    )


@writes
async def create_reliability_test(
    ctx: Context,
    workspace_slug: str,
    name: str,
    purpose: str = "",
    test_item_term_ids: list[str] | None = None,
    attributes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """신뢰성 시험 하나를 등록한다. **그 부서의 관리자**(또는 시스템 관리자)만.

    먼저 `resolve(kind="reliability_test", text=…, workspace=…)` 로 **같은 시험이 이미
    있는지** 본다. 부서마다 같은 이름이 있는 표라, 안 보고 만들면 한 부서에 「고온고습
    1000h」 가 둘이 되고 그 뒤로는 어느 쪽이 정본인지 아무도 모른다.

    `test_item_term_ids` 는 이 시험이 쓰는 **시험 항목**의 값 id 다 — `resolve(kind="term",
    axis="test_item", name=…)` 로 찾는다. **모르면 비운다**: 비슷한 항목을 끼워 넣으면 그
    시험이 엉뚱한 장비로 이어지고, 검색은 그 장비로 「됩니다」 라고 답한다.

    `attributes` 는 칸 하나가 한 줄이다(`list_attribute_definitions(target="reliability_test")`
    가 정의를 준다):

        {"definition_id": "…", "num_min": -40, "num_max": 125, "unit": "degC"}   구간·조건
        {"definition_id": "…", "num_value": 5}                                    수치
        {"definition_id": "…", "text_value": "외관 이상 없음"}                     문장
        {"definition_id": "…", "term_id": "…"}          기준정보(유형·적용군)
        {"definition_id": "…", "method_id": "…"}        규격(참조 규격)
        {"definition_id": "…", "json_value": [{"label": "A등급", "value": 4}]}   이름별 수량
        {"new_label": "시료 수", "new_kind": "number", "num_value": 5}      새 이름 → 초안

    **새 이름을 만들기 전에 정의 목록을 본다.** `new_label` 로 적으면 초안 속성이 새로 생기고,
    초안은 온톨로지 밖이라 검색·판정에 안 쓰인다 — 같은 뜻의 정식 속성이 있으면 그 쪽
    `definition_id` 를 쓴다.

    **조건 속성(`kind="condition"`)은 그대로 장비 판정이 된다** — -40~125 degC 로 적어 두면
    `test_capability` 가 그 온도를 내는 장비만 답한다. 그래서 조건은 문장이 아니라 수치로
    적는 것이 중요하다.
    """
    return await _send(
        ctx,
        "POST",
        "/reliability-tests",
        {
            "workspace_slug": workspace_slug,
            "name": name,
            "purpose": purpose,
            "test_item_term_ids": test_item_term_ids or [],
            "attributes": attributes or [],
        },
    )


@writes
async def update_reliability_test(
    ctx: Context,
    test_id: str,
    name: str | None = None,
    purpose: str | None = None,
    test_item_term_ids: list[str] | None = None,
    attributes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """신뢰성 시험을 고친다. **안 보낸 칸은 그대로.**

    `test_id` 는 `resolve(kind="reliability_test", …)` 로 정한다 — 목록에서 이름만 보고
    고르면 같은 이름의 **다른 부서 시험**을 고치게 된다.

    `test_item_term_ids` 와 `attributes` 는 보내면 **통째로 바뀐다** — 하나를 더하려면 지금
    있는 것(`get_reliability_test`)에 더해서 **전부** 보낸다. 빠뜨리면 조용히 지워진다.
    """
    body: dict[str, Any] = {}
    if name is not None:
        body["name"] = name
    if purpose is not None:
        body["purpose"] = purpose
    if test_item_term_ids is not None:
        body["test_item_term_ids"] = test_item_term_ids
    if attributes is not None:
        body["attributes"] = attributes
    return await _send(ctx, "PATCH", f"/reliability-tests/{test_id}", body)


@mcp.tool()
async def test_capability(ctx: Context, test_id: str) -> dict[str, Any]:
    """**이 시험을 돌릴 수 있는 장비.** 이 시스템이 답하려는 물음의 마지막 한 걸음.

    `test_id` 는 `resolve(kind="reliability_test", …)` 가 준 것을 쓴다.

    이 시험의 조건 속성이 그대로 검색 조건이 되어(범위 하나는 「위로 얼마까지」 와 「아래로
    얼마까지」 두 물음이다) 시험 항목마다 장비를 판정한다. 부서로 안 좁힌다 — 옆 부서에
    있으면 빌리러 간다.

    읽는 법:

    * `conditions_asked` — 실제로 물은 조건 수. 0 이면 조건 속성이 없어 **시험 항목만으로**
      본 것이다. 그때의 「가능」 은 온도·하중을 안 본 답이므로 그렇게 말해야 한다.
    * `skipped` — 단위를 못 옮겨 **뺀** 조건과 그 이유. 있으면 조건을 다 본 것이 아니다.
    * `unmet_count` — 조건이 안 맞아 빠진 장비 수. 0대라는 답이 「그 항목이 되는 장비가
      없어서」 인지 「조건이 안 맞아서」 인지를 이것이 가른다.
    * 줄의 `verdict` — `match` 다 충족 · `accessory` **부속(챔버·노)을 달면 됨** · `partial`
      일부는 **모른다** · `unknown` 전부 모른다. **`unknown` 을 「가능합니다」 로 옮기지 마라.**
    * 조건 줄의 `accessory` 칸 — 무엇을 달면 되나(`model_name`), 얼마까지(`condition_range`),
      **우리가 갖고 있나**(`owned_units`). 0 이 아니면 사는 이야기가 아니다.

    **0대면 그것이 답이다.** 「그 시험 항목이 적힌 장비가 없다」(unmet_count 0) 또는 「조건이
    안 맞는다」(unmet_count > 0) 로 말하고 멈춰라 — 챔버·항온항습 같은 다른 이름으로 장비를
    뒤지지 마라. 그 장비는 시험 항목이 안 적혀 있어 검색에 안 걸리는 것이고, 그것을 적는 일은
    사람의 몫이다. 사면 되는 것은 `search_catalog` 한 번.
    """
    found = await _get(ctx, f"/reliability-tests/{test_id}/equipment")
    total = (
        sum(int(one.get("total") or 0) for one in found.get("items", []))
        if isinstance(found, dict)
        else 0
    )
    return _then(
        found,
        (
            "0대다 — 이것이 답이다. unmet_count 로 이유(항목 안 적힘 / 조건 미달)를 말하고"
            " 멈춰라. 다른 이름으로 장비를 뒤지지 말고, 사면 되는 것은 search_catalog 한 번."
            if total == 0
            else "이것이 답이다. 줄마다 부서·위치·담당자·판정이 있다 — 장비를 다시 검색하거나"
            " 사양을 열어 재확인하지 마라."
        ),
    )


# ── 속성 — 열이 아니라 행으로 붙는 칸 ─────────────────────────────────────────


@mcp.tool()
async def list_attribute_definitions(
    ctx: Context, target: str, include_inactive: bool = False
) -> dict[str, Any]:
    """어떤 객체에 **무슨 칸을 적을 수 있나** — 속성 정의 목록.

    `target` 은 `reliability_test` · `equipment` · `series` · `method`. 줄마다 `key`(거르기
    조건에 쓰는 이름) · `label` · `kind` · `unit` · `status` · `value_count` 가 온다.

    `status` 가 `standard` 면 정식이고 검색·판정·색인 카드에 들어간다. `draft` 는 **초안**
    이다 — 값을 적는 사람이 새 이름을 써서 생긴 것이고 온톨로지 밖이다. 값을 적을 때는
    **정식부터 찾아 쓰고**, 없을 때만 새 이름을 만든다.

    `kind` 가 `condition` 인 것은 검색축에 이어진 조건이다 — 그 칸에 수치를 적으면
    `test_capability` 가 그 조건으로 장비를 판정한다.
    """
    return _listed(
        await _get(
            ctx,
            "/attribute-definitions",
            {
                "target": target,
                "include_inactive": "true" if include_inactive else None,
            },
        ),
        "definitions",
    )


@writes
async def create_attribute_definition(
    ctx: Context,
    target: str,
    label: str,
    kind: str = "text",
    key: str | None = None,
    unit: str = "",
    condition_key_id: str | None = None,
    vocabulary_id: str | None = None,
    choices: list[str] | None = None,
    status: str = "draft",
) -> dict[str, Any]:
    """새 속성 칸을 정의한다. **시스템 관리자만**, 그리고 사람이 시켰을 때만.

    `kind` 는 number(수치) · range(구간) · text(문장) · boolean · date · choice(선택지) ·
    condition(검색축에 이어진 조건) · term(기준정보 값) · method(규격). 조건은
    `condition_key_id`(`list_conditions`), 기준정보는 `vocabulary_id`, 선택은 `choices` 가
    필요하다.

    `key` 는 **거르기 조건에 그대로 실리는 이름**이라 영문·숫자·`_.-` 만 된다. 비우면 서버가
    임의로 만든다 — 코드나 반입이 걸 이름이면 직접 준다.

    **먼저 `list_attribute_definitions` 로 본다.** 같은 뜻의 칸을 하나 더 만들면 값이 두
    군데로 쌓이고, 그 뒤 어느 쪽이 맞는지 알 방법이 없다. `status="standard"` 로 바로
    정식으로 세우는 것은 **사람이 그 이름으로 굳히기로 했을 때만** — 확신이 없으면
    초안으로 두고 검토함의 「초안 속성 정리」 가 묻게 한다.
    """
    return await _send(
        ctx,
        "POST",
        "/attribute-definitions",
        {
            "target": target,
            "label": label,
            "kind": kind,
            "key": key,
            "unit": unit,
            "condition_key_id": condition_key_id,
            "vocabulary_id": vocabulary_id,
            "choices": choices or [],
            "status": status,
        },
    )


# ── 검토함 — 사람이 정할 것 (읽기) ────────────────────────────────────────────


@mcp.tool()
async def list_review_queues(ctx: Context) -> dict[str, Any]:
    """검토함의 물음별 남은 수 — 어느 물음이 얼마나 밀렸나.

    반입이 못 정한 것(어느 시험의 규격인가 · 무슨 조건을 묻나 · 이 물성이 나오나 · 초안
    속성을 합칠까)이 여기 쌓인다. **AI 는 정하지 않는다** — 확정은 사람이 화면에서 하고,
    기계 자격으로는 아예 막혀 있다. 여기서 할 일은 **근거를 모아 사람 앞에 놓는 것**이다.
    """
    return _listed(await _get(ctx, "/review"), "queues")


@mcp.tool()
async def list_review_items(
    ctx: Context, queue: str, status: str = "open", limit: int = 20, offset: int = 0
) -> dict[str, Any]:
    """한 물음의 줄들 — 대상 · 물음 문장 · 근거 자료 · 후보 · 추천과 그 이유.

    `queue` 는 `list_review_queues` 의 `key`. `status` 는 open · voted · decided · skipped ·
    gone · all.

    줄의 `question` 은 그 줄이 정확히 무엇을 묻는지 완전한 문장이고, `facts` 는 판단에
    필요한 사실이다. **추천(`recommended`)은 정답이 아니다** — 근거(`reason`)를 함께 읽고,
    사람에게 옮길 때도 둘을 같이 옮긴다. 확정은 사람이 화면에서 한다.
    """
    return await _get(
        ctx, f"/review/{queue}", {"status": status, "limit": limit, "offset": offset}
    )


# ── 지식 그래프 — 무엇이 무엇과 이어지나 (읽기) ──────────────────────────────


@mcp.tool()
async def graph_overview(ctx: Context) -> dict[str, Any]:
    """이 저장소의 **구조** — 객체 종류와 관계 종류, 각각 실제 건수.

    「이 시스템에 무엇이 들어 있고 무엇이 무엇과 이어지나」 를 한 번에 본다. 건수가 0인
    관계는 정의만 있고 아직 아무도 안 이은 것이다 — 채울 자리가 어디인지 그것이 말한다.
    """
    return await _get(ctx, "/graph/overview")


@mcp.tool()
async def graph_search(ctx: Context, q: str) -> dict[str, Any]:
    """그래프의 시작점을 **종류를 가리지 않고** 찾는다 — 이름·코드·별칭·자산번호.

    돌려주는 `id` 가 `graph_neighbors` · `graph_node` 에 넣는 노드 id 다. 무엇을 물어야 할지
    모를 때, 사람이 말한 이름 하나로 어느 종류의 무엇인지부터 가른다.
    """
    return _listed(await _get(ctx, "/graph/search", {"q": q}), "hits")


@mcp.tool()
async def graph_neighbors(
    ctx: Context, node_id: str, depth: int = 1, fanout: int = 30, limit: int = 100
) -> dict[str, Any]:
    """한 객체의 **이웃** — 무엇과 어떻게 이어져 있나.

    `node_id` 는 `"<종류>:<uuid>"` 꼴이다(`test_item:…` · `series:…` · `method:…` ·
    `equipment:…` · `reliability_test:…`). 종류 없이 uuid 만으로는 어느 표인지 모르므로
    `graph_search` 가 준 id 를 그대로 쓴다.

    **서버가 상한을 강제한다.** 노드에 `truncated` 가 붙어 있으면 그 노드의 이웃이 다 온
    것이 아니다(`degree` 가 실제 수) — 「이것이 전부입니다」 라고 말하지 말고, 더 봐야 하면
    그 노드를 중심으로 다시 부른다.
    """
    return await _get(
        ctx,
        "/graph/neighborhood",
        {"focus": node_id, "depth": depth, "fanout": fanout, "limit": limit},
    )


@mcp.tool()
async def graph_node(ctx: Context, node_id: str) -> dict[str, Any]:
    """한 객체의 요약과 **관계 목록** — 어느 관계로 무엇과 이어져 있는지 이름까지.

    `related_total` 이 목록보다 크면 잘린 것이다. 상세 화면 주소(`detail_path`)가 함께 오니
    사람에게 옮길 때 그 링크를 준다 — id 만 주면 사람은 그것으로 아무것도 못 한다.
    """
    return await _get(ctx, "/graph/node", {"id": node_id})


if __name__ == "__main__":
    # stdio 로 뜬다. HTTP 로 띄우려면 run_mcp.ps1 을 쓴다.
    mcp.run()

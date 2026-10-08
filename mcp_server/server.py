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
import re
import time
from pathlib import Path
from typing import Any

import shlex
from pathlib import Path
from urllib.parse import quote

import bind
import calltrace
import httpx
from merge import merge
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings


def _load_env_defaults() -> None:
    """`backend\\.env` 의 값을 **환경변수가 비어 있을 때만** 채운다.

    창으로 띄울 때는 `run_mcp.ps1` 이 .env 를 읽어 `TESTSCOPE_*` 를 준다. 서비스로 띄우면
    (`scripts\\deploy\\service.ps1`) 그 스크립트를 안 거치므로 여기서 같은 일을 한다 —
    등록할 때 값을 박아 두면 .env 를 고쳐도 서비스는 옛 포트를 본다. 이미 있는 환경변수가
    이긴다(인자로 준 것이 파일보다 세다).

        PORT · APP_ENV      → TESTSCOPE_API_BASE  (개발은 PORT+1, 운영은 PORT)
        MCP_PORT            → TESTSCOPE_MCP_PORT
        MCP_HOST            → TESTSCOPE_MCP_HOST
        MCP_ALLOWED_HOSTS   → TESTSCOPE_MCP_ALLOWED_HOSTS
    """
    env_file = Path(__file__).resolve().parent.parent / "backend" / ".env"
    if not env_file.exists():
        return
    values: dict[str, str] = {}
    for raw in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    if "TESTSCOPE_API_BASE" not in os.environ and values.get("PORT", "").isdigit():
        # run.py 가 개발에서 PORT+1 을 쓴다. 그 규칙을 여기서도 따른다 — 두 벌로 두면
        # 개발에서만 주소가 어긋나고, 그것은 도구가 전부 실패하고 나서야 드러난다.
        port = int(values["PORT"])
        if values.get("APP_ENV", "development") == "development":
            port += 1
        os.environ["TESTSCOPE_API_BASE"] = f"http://127.0.0.1:{port}/api"
    for source, target in (
        ("MCP_PORT", "TESTSCOPE_MCP_PORT"),
        ("MCP_HOST", "TESTSCOPE_MCP_HOST"),
        ("MCP_ALLOWED_HOSTS", "TESTSCOPE_MCP_ALLOWED_HOSTS"),
    ):
        if target not in os.environ and values.get(source):
            os.environ[target] = values[source]


_load_env_defaults()

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
ROUTING = """물음별 첫 도구 (상세는 각 도구 설명과 get_guide):

  이 시험이 가능한 보유 장비     search_test_items   (물성으로 물으면 search_properties 먼저)
  이 규격/조건으로 가능 여부     search_test_items(conditions=…) · list_conditions
  말로만 아는 대상 찾기          resolve · search_semantic · graph_search
  이름 하나를 id로               resolve (계열·기종·값·규격·시험·장비·부서 전부)
  우리 부서 시험 절차            list_reliability_tests · test_capability
  장비 대장 반입                 import_equipment (한 대면 register_equipment)
  장비 한 대 수정                get_equipment · update_equipment · add_equipment_test_item
  교정 이력/만료 시점            get_calibrations · list_calibrations_due
  규격 없음/조건 기록            resolve(method) -> create_method · set_requirement
  계열/기종/사양 채우기          search_series · search_models · get_specs · set_spec
  값을 적을 자리                 list_reference · list_axes · list_terms
  기재 가능한 칸                 list_attribute_definitions
  대상 간 연결 관계              graph_search -> graph_node
  검토함 미결 조회·결정          list_review_items -> decide_review_item (지시 후)
  카탈로그에 없는 기종 요청      list_model_requests -> decide_model_request (사람 확인 후)
  축에 없는 시험 항목 요청       list_test_item_requests -> decide_test_item_request
  전용 도구 없는 수정·삭제·생성  update_record · delete_record(확인 후 confirm) · create_record
  남은 일·우선순위               list_pending_work"""

mcp = MCPServer(
    name="testscope",
    instructions=(
        "TestScope 시험 장비 지도. 이 시험을 수행할 장비가 조직에 있는지에 대한 답."
        " 카탈로그는 계열(가능한 시험)과 기종(가능 범위) 두 층이며, 보유 장비는 기종을"
        " 가리킴. 모든 도구 공통 규약: **만들기 전 resolve로 확인 필수**, **모르면 비워"
        " 둠**(지어낸 값이 있으면 검색이 가능으로 답함), **응답의 `next`가 `이것이 답`으로"
        " 시작하면 멈춤**(거점별·장비별 재호출, 사양 재확인 금지. 판정은 서버가 완료)."
        " 처음이면 get_guide() 먼저 읽기.\n\n" + ROUTING
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
        return {"error": f"요청 실패(HTTP {got.status_code})."}
    out: dict[str, Any] = {"error": f"{body.get('message')} ({body.get('code')})"}
    if body.get("details"):
        out["details"] = body["details"]
    return out


def _auth_error(got: httpx.Response) -> dict[str, Any] | None:
    """401·403 을 사람이 고칠 수 있는 문장으로.

    **서버가 한 말을 버리지 않는다.** 예전에는 고정 문구만 돌려줬는데, 403 의 이유는 여러
    가지다 — 토큰 범위가 없는 것과 남의 사업부에 올리는 것과 확정된 줄을 기계가 고치려는
    것이 전부 403 이고, 그 셋은 **할 일이 완전히 다르다.** 고정 문구를 읽은 쪽은 셋 다
    「토큰을 다시 발급」 으로 읽고, 다시 발급해도 안 되니 거기서 멈춘다.

    그래서 서버의 말과 `details` 를 먼저 싣고, 그 뒤에 범위 이야기를 **덧붙인다**.
    """
    if got.status_code not in (401, 403):
        return None
    said, details = "", None
    try:
        body = got.json()["error"]
        said = f"{body.get('message')} ({body.get('code')})"
        details = body.get("details") or None
    except Exception:
        said = ""
    if got.status_code == 401:
        hint = (
            "인증 실패. TestScope 화면의 내 정보 → 토큰에서 발급한 개인 토큰을"
            " Authorization 헤더로 등록했는지 확인 필요."
        )
    else:
        hint = (
            "권한 없음. 원인은 계정 권한 부족, 토큰 범위 부족, 등록 불가 대상(남의 사업부 ·"
            " 확정된 줄) 중 하나. 필요 범위: 카탈로그는 catalog:write, 장비·규격서·신뢰성"
            " 시험은 equipment:write."
        )
    out: dict[str, Any] = {"error": f"{said} {hint}".strip() if said else hint}
    if details:
        out["details"] = details
    return out


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
        return {"error": f"백엔드 연결 실패({API_BASE}): {failed}"}
    problem = _auth_error(got)
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
        return {"error": f"백엔드 연결 실패({API_BASE}): {failed}"}
    problem = _auth_error(got)
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
        return f"안내를 읽지 못함({GUIDE_PATH}): {failed}"


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
    """TestScope 사용 안내. **작업 전 먼저 읽기 필수**, 이후에는 필요한 대목만 조회.

    `topic` 없이 호출하면 머리말(이 시스템이 답하는 물음 · 세 층 · 규약 넷)과 **대목 목록**
    반환. 대목 이름의 한 조각을 `topic`으로 주면 그 대목만 반환: `get_guide("장비 등록")` ·
    `get_guide("온톨로지")` · `get_guide("권한")`.

    전체는 `topic="전부"`. 안내가 수천 자라 매번 전체를 받으면 도구 호출 여유가 줄어듦(대목
    단위 조회 권장).

    서버가 매 호출 파일을 읽으므로 안내 수정은 재시작 없이 반영됨. 클라이언트 쪽 사본은 수정이
    반영되지 않으므로 사본 보관 금지.
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
        return f"'{topic}' 대목 없음. 있는 대목: {titles}"
    # 머리말 + 대목 목록 — 어디를 더 읽을지 고르는 데 필요한 만큼만.
    head = sections[0][1] if sections and not sections[0][0] else ""
    intro = [body for title, body in sections if title in ("층이 셋이다", "규약 넷")]
    titles = "\n".join(f"  {title}" for title, _ in sections if title)
    return "\n\n".join(
        [head, *intro, f'다른 대목은 get_guide("이름의 한 조각")로 조회:\n{titles}']
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
    """이름 하나를 id로 확정. **생성·수정 전 호출 필수.**

    `kind`: `series` · `model` · `term`(+`axis`) · `method` · `reliability_test` · `equipment`
    · `workspace`. `term`의 축은 manufacturer · equipment_category · test_item · property ·
    site · standard_body. 별칭까지 검색(`Rp0.2`로 입력해도 됨).

    응답의 `match` 세 가지:

        exact       하나로 확정. `id`를 그대로 사용
        candidates  여럿. **임의 선택 금지, 사람에게 확인**
        none        없음. 새로 만들거나 비워 둠. 지어내기 금지

    부서 소유 대상은 이름이 겹침. 고온고습 1000h는 거의 모든 부서에 하나씩 있어 이름이 같아도
    `candidates`. `workspace`(slug)를 함께 주면 하나로 좁혀짐. slug를 모르면
    `resolve(kind="workspace", …)`로 먼저 조회. 장비는 자산번호만 유일해 exact, 이름은 대개
    여럿.

    못 찾음은 실패가 아님. `hint`에 다음 할 일 한 줄 기재.
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
    """보유 장비 중 조건을 만족하는 장비 검색(예: 80도에서 20 kN 이상 인장 가능 장비).

    `conditions`는 조건마다 하나, **셋 중 하나만** 지정: `{"condition_key_id": …, "at": 80}`(그
    값에서 가능) · `{"…", "at_least": 20}`(그 이상) · `{"…", "at_most": …}`. 값은 그 축의
    `unit`으로 기재(`list_conditions`가 축마다 제공: 온도 degC · 하중 kN · 낙하 높이 cm).

    조건 키 id는 `list_conditions()`, 시험 항목 id는 `resolve`로 조회. 물을 조건은 시험 항목이
    결정: `get_test_item`의 `condition_keys`가 그 시험에 뜻이 있는 축(인장 → 하중·속도·온도).
    축 밖 조건(인장에 습도)은 대개 `unknown`만 늘림. 축이 비어 있으면 미정 상태이므로 조건 질의
    시 그 사실을 함께 전달.

    물성으로 물으면 `property_term_id` 지정(id는 `search_properties`). 서버가 그 물성을 내는
    시험 항목 전부로 펼쳐 검색하고 `expanded_test_items`에 펼친 내역 기재. 이것이 비어 있으면
    0건의 뜻은 장비 없음이 아니라 그 물성에 이어진 시험 항목 없음.

    ## 판정

        met        가능
        accessory  부속(챔버·노) 장착 시 가능. 가능(met)으로 옮기기 금지
        unmet      불가
        unknown    모름. 그 장비에 그 조건이 기록되지 않음

    `accessory` 조건의 `accessory` 칸에 장착할 부속(부속 기종·범위·보유 대수) 기재. 보유가 0이
    아니면 구매 대상 아님. 부속 재조회 불필요(답에 포함).

    **unknown을 met으로 옮기기 금지.** 그 장비에 그 조건이 기록되지 않았다고 그대로 전달.
    이유는 `reason`, 채우는 도구는 `set_test_condition`.

    결과가 비면 `diagnosis` 확인: `equipment_with_item`이 0이면 조건이 좁은 것이 아니라 그
    시험을 등록한 장비 없음. `catalog_series_with_item`이 0이 아니면 `search_catalog`로 구매
    후보 조회 가능. `unlinked_equipment`는 기종 미연결로 검색에 안 걸리는 장비 수.

    **이 응답이 최종 답.** 줄마다 거점·부서·위치·담당자 포함. 거점별 재호출, 장비별 사양 재확인
    금지(판정은 서버가 사양 기준으로 완료).

    확실한 것(match)이 먼저 정렬. `total`이 `shown`보다 크면 나머지는 나열 대신
    `by_verdict`(판정별 수)로 요약(예: match 3대, 모름 40대). 전체가 필요할 때만 `limit`
    상향(최대 50).
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
            "0건. diagnosis를 그대로 전달. 구매 후보는 search_catalog 한 번이며,"
            " 다른 이름·거점·장비로 재검색 금지."
            if empty
            else "이것이 답. 확실한 것(match)이 먼저이며 줄마다 거점·부서·위치·담당자 포함."
            " 나머지는 by_verdict로 요약. 거점별 재호출, 장비별 사양 재확인 금지(판정은"
            " 서버가 사양 기준으로 완료)."
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
    """카탈로그 기종 검색: 이 시험이 가능한 기종, 구매 후보 조회.

    `search_test_items`는 보유 장비, 이 도구는 카탈로그 전체(보유 여부 무관)를 답함. 같은
    물음(시험 항목 · 물성 · 규격 · 조건)을 받음. 보유 장비가 없다고 답하기 전 한 번 더
    조회(다음 물음은 늘 무엇을 사야 하는가).

    답은 계열별 기종 단위(계열 범위 0.5~600 kN은 답이 아님). 기종마다 `verdict`(match ·
    accessory · partial · unknown)와 `owned_units`(이미 등록된 보유 대수) 포함. **owned_units가
    0이 아니면 구매보다 그 장비를 먼저 안내.** `accessory`는 챔버·노 장착 시 가능이며, 그 조건
    줄의 `accessory` 칸에 쓸 부속 기종, 가능 범위, 그 부속의 보유 대수 기재. 본체와 부속은 따로
    세어 전달. `unmet_models`는 조건 미달로 빠진 기종 수(0건일 때 기종 없음과 조건이 좁음을
    구분).
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
        "이것이 답. 줄마다 판정과 보유 대수(owned_units) 포함. 기종별 장비 재검색, 사양"
        " 열람 금지. 보유 대수가 0이 아니면 구매보다 그 장비를 먼저 안내. total이 shown보다"
        " 크면 나머지는 by_verdict로 요약.",
    )


@mcp.tool()
async def search_semantic(
    ctx: Context, q: str, kind: list[str] | None = None, limit: int = 10
) -> dict[str, Any]:
    """의미 검색: 글자가 겹치지 않아도 뜻이 가까운 대상 조회. 자유 문장 질문의 첫 도구.

    사람 말 그대로 입력(예: `HAST`, `thermal shock`, `얇은 판 잡아당길 때 쓰는 규격`,
    `-40~150도 왔다갔다 하는 챔버`). 반환은 **후보**: 시험 항목·물성·계열·기종·규격·보유
    장비·신뢰성 시험 중 뜻이 가까운 것과 유사도(`score`; bge-m3 실측 기준 0.5 이상이 적중, 0.4
    안팎은 우연). 장비를 직접 답하지 않음: 시험 항목이 정해지면
    `search_test_items(test_item_term_id=…)`에 조건을 붙여 장비 조회. 이름 확정 여부는
    `resolve`가 판단(`resolve`도 글자로 못 찾으면 이 결과를 후보로 제시).

    `kind`로 종류 필터: `test_item` · `property` · `series` · `model` · `method` · `equipment`
    · `reliability_test`. 보유 장비는 토큰 소유자가 볼 수 있는 것만 반환.

    `available=false`는 부품(pgvector·Ollama)이 없는 설치이며 오류 아님. 이때는 이름 기반
    도구(`search_properties` · `resolve` · `search_series(q=…)`) 사용.
    """
    return _listed(
        await _get(ctx, "/search/semantic", {"q": q, "kind": kind, "limit": limit}),
        "hits",
    )


@mcp.tool()
async def search_properties(
    ctx: Context, q: str | None = None, linked_only: bool = True
) -> dict[str, Any]:
    """물성(예: 인장강도)을 내는 시험 항목 조회. 물성으로 장비를 묻기 전 사용.

    사람은 인장 가능 장비가 아니라 인장강도 측정 장비로 물음. 이 도구가 그 물성(온톨로지 축
    `property`, code는 `mechanical.tensile_strength` 같은 MaterialTwin 키)과 그것을 내는 시험
    항목(`links`)을 반환. 관계는 N:M: 유리전이온도는 DSC·DMA·TMA 셋에서 나오고, 인장은
    강도·항복·영률·연신율을 냄.

    받은 물성 `id`를 `search_test_items(property_term_id=…)`에 넣으면 서버가 그 시험 항목
    전부로 펼쳐 검색. 시험 항목 하나로 좁히려면 `links[].test_item_term_id`를
    `test_item_term_id`로 함께 지정.

    `linked_only=True`(기본)면 시험 항목이 이어진 물성만 반환. 연결 없는 물성은 검색 결과가 늘
    비므로 **장비 없음으로 옮기기 금지**(아직 연결 없음으로 전달).

    `links[].status`가 `suggested`면 기계 제안 연결로 사람 미확인. 사용은 가능하나 답할 때 그
    사실 명시.
    """
    return _listed(
        await _get(ctx, "/properties", {"q": q, "include_unlinked": not linked_only}),
        "properties",
    )


@mcp.tool()
async def list_conditions(ctx: Context) -> dict[str, Any]:
    """검색 조건 축 목록: 온도·하중·속도·주파수·시편 두께·습도·항온조.

    축마다 `unit` 포함: **값을 보내고 받는 단위**(온도 degC · 하중 kN · 낙하 높이 cm).
    `si_unit`·`display_unit`은 참고용이며, `unit`은 display_unit, 없으면 si_unit.
    """
    return _listed(await _get(ctx, "/condition-keys"), "conditions")


# ── 부서 ──────────────────────────────────────────────────────────────────────


@mcp.tool()
async def list_workspaces(ctx: Context) -> dict[str, Any]:
    """부서 목록: slug · 이름 · 조직도 경로(예: 개발본부 / 재료시험팀).

    장비·규격서 등록 도구는 이름이 아니라 **slug**를 요구(`register_equipment`의
    `workspace_slug`). 이 목록 없이 이름으로 짐작하면 대개 404 또는 남의 부서. 같은 이름의 팀이
    본부마다 있을 수 있으므로 경로(`path`)로 구분. 이름 하나만 알면 `resolve(kind="workspace",
    …)`가 더 빠름.

    **신뢰성 시험은 부서가 아니라 사업부 소속**: 이 목록 대신 `list_divisions`의 사업부 코드
    사용.
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
    """계열 목록 조회. `kind`: `main`(본체) · `accessory`(부속) · 빈 문자열(전체).

    **하나로 확정할 때는 `resolve` 사용.** 이 도구는 어떤 계열이 있는지 훑을 때 사용.

    `category_term_id`로 분류 좁히기(`resolve(axis="equipment_category", …)`). 분류는 군/유형
    두 층이라 군(예: 정적 기계 시험기)을 주면 하위 유형 전부 포함. 기계 시험기 전체를 보려고
    유형 여덟 개를 하나씩 호출할 필요 없음.

    ## 요약 응답

    시험 항목은 개수(`test_item_count`)만 반환. 가능한 시험과 조건 수치는 `get_series`가
    제공(목록에 전부 실으면 한 쪽이 191 KB).

    **`test_item_count`가 0이 아니면 조건을 모른다고 답하기 금지.** 아직 조회하지 않은 상태.
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
    """계열 하나의 상세: 가능 시험(test_items) · 호환 부속(relations) · 기종 수 · 보유 대수.

    사양을 채우려면 여기서 `category_term_id`를 얻어 `list_spec_definitions`에 전달. 분류를
    주면 그 분류의 칸과 공통 칸이 함께 반환.
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
    """계열 생성. **먼저 `resolve(kind="series", …)`로 조회 필수.**

    같은 계열이 두 줄로 갈리면 보유 장비가 어느 쪽을 가리키는지에 따라 검색 결과가 나뉨. 이미
    있으면 409와 `details.series_id` 반환: 409는 실패가 아니라 답이며 그 id를 사용.

    `maker`·`category`는 이름으로 지정. 온톨로지에서 하나로 확정될 때만 받고 아니면 거절(오타가
    새 제조사가 되면 그 계열이 목록에서 고립됨).

    챔버·퍼니스·신율계 같은 부속도 계열(`kind="accessory"`).
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
    """계열에 가능 시험 항목 추가. **조건 수치는 여기 기재 금지.**

    여기 적는 조건은 계열 전체가 만족하는 것뿐. 기종마다 갈리는 값은 그 기종의
    사양(`set_spec`)에 기재하며 보유 장비 생성 시 합쳐짐(한 계열 안에서 하중이 중앙값 60배까지
    갈림).

    시험 항목은 닫힌 축: 없는 이름은 거절(오타가 값이 되면 그 계열 장비가 검색에서 영구 누락).
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


@writes
async def link_series(
    ctx: Context, series_id: str, part_series_id: str, relation: str, note: str | None = None
) -> dict[str, Any]:
    """계열 간 연결: 부속 호환·계보.

    `relation`은 원본 카탈로그 이름 그대로: `compatible_accessory` · `fits_on` · `requires` ·
    `extends_temperature` · `successor_of` · `same_family_as`.

    **`extends_temperature`에는 note 기재 필수**(예: -150 ~ +600 °C). 무엇이 어떻게 바뀌는지는
    그 칸에만 남음.
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
    """기종 목록 조회. **보유 장비가 가리키는 대상이 기종.**

    ## 계열로 먼저 좁히기

    사람이 아는 것은 대개 계열까지(인스트론 6800 시리즈는 알아도 `68FM-300`은 라벨을 봐야 앎).
    계열을 알면 `series`(이름)나 `series_id`로 좁혀 그 계열의 기종 전부를 받아 라벨과 대조.

    `series` 이름이 하나로 확정되지 않으면 후보 반환. 이때 `resolve`로 확정 후 `series_id`로
    재호출.

    `q`만 주면 기종명·계열명·제조사 전체 검색. 하나로 확정할 때는 `resolve` 사용.

    ## 요약 응답

    시험 항목은 이름만(`test_items`), 사양은 기종을 가르는 대표 두어 칸(`headline_specs`)만
    반환. 조건 수치와 사양 전체는 `get_model` · `get_specs`가 제공.

    **반환되지 않은 값을 없다고 답하기 금지.** `spec_count`가 실제 기재된 칸 수이므로 0이
    아니면 값은 있고 아직 조회하지 않은 상태.
    """
    if series_id is None and series:
        answer = await _send(
            ctx, "POST", "/resolve", {"kind": "series", "text": series, "limit": 8}
        )
        if isinstance(answer, dict) and answer.get("error"):
            return answer
        if answer.get("match") != "exact":
            return {
                "error": f"계열 '{series}'을(를) 하나로 확정할 수 없음.",
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
    form_factor_term_id: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    """기종 생성. **계열이 먼저 있어야 함.**

    계열은 id나 이름으로 지정. 이름이 하나로 확정되지 않으면 거절하고 후보 반환. **비슷한
    계열에 끼워 넣기 금지.** 단품이라도 기종 하나짜리 계열을 먼저 생성.

    기종명에 계열 이름 혼합 금지: `6800 68FM-300`과 `68FM-300`이 별개 기종으로 갈리고 나중에
    묶을 방법이 없음.

    형태(`form_factor_term_id`)는 축의 값 id: `resolve(kind="term", axis="form_factor",
    text="탁상형")`. 자유 문자열 아님.
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
            "form_factor_term_id": form_factor_term_id,
            "summary": summary,
        },
    )


@mcp.tool()
async def list_spec_definitions(
    ctx: Context, category_term_id: str | None = None
) -> dict[str, Any]:
    """기종에 **기재 가능한 사양 칸** 목록. 분류를 주면 그 분류의 칸과 공통 칸을 함께 반환.

    `kind`가 값의 형태를 결정: `number`(수치 하나) · `range`(구간) · `choice` · `boolean` ·
    `text`. `condition_key_id`가 채워진 사양은 검색축이며 그 값이 보유 장비의 시험 조건이 됨.

    **없는 사양은 만들지 말고 보류.** 정의 추가는 사람의 판단(원본 사양 키 562종 중 76%가 단 한
    곳에만 등장).
    """
    return _listed(
        await _get(ctx, "/spec-definitions", {"category_term_id": category_term_id}),
        "definitions",
    )


@mcp.tool()
async def get_specs(ctx: Context, model_id: str) -> dict[str, Any]:
    """기종에 **기재된** 사양. 빈 칸 목록은 `list_spec_definitions`가 제공.

    둘을 겹쳐 봐야 미기재 칸이 보임(빈 칸까지 실으면 기종마다 수백 줄).

    **정의 없는 값은 여기 없음.** 카탈로그 원문 전체는 `get_model`의 `raw_specs`. 사양을 채우기
    전 원문 먼저 확인.
    """
    return await _get(ctx, f"/equipment-models/{model_id}/specs")


@mcp.tool()
async def get_model(ctx: Context, model_id: str) -> dict[str, Any]:
    """기종 하나: 계열·분류·보유 대수와 **카탈로그 원문**(`raw_specs`).

    원문은 제조사 카탈로그 기재 그대로. 정의가 있는 칸만 사양표(`get_specs`)에 들어가고 정의
    없는 값은 여기에만 있음(원본 키 950종 이상, 대부분 한 카탈로그에만 등장).

    **사양을 채울 때 먼저 확인.** 원문에 값이 있는데 사양표가 비어 있으면 맞는 정의가 아직
    없다는 뜻. 이때 지어내지 말고 사람에게 알림.
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
    replace: bool = False,
) -> dict[str, Any]:
    """기종 사양 한 칸 입력. **정의의 종류에 맞는 칸만 채움.**

        number   num_value
        range    num_min · num_max   (한쪽을 비우면 제한 없음, 0 아님)
        choice   text_value          (정의의 choices 안의 값만)
        boolean  bool_value
        text     text_value          (원문 그대로, 조건절 유지)

    틀린 칸에 담긴 값은 저장은 되나 화면 표시 불가.

    비고를 충분히 기재: 값의 성립 조건(예: 챔버 장착 시)은 비고에만 남음. 카탈로그가 조건을
    달아 적은 값에서 조건을 버리면 뜻이 사라짐.

    옵션 부속 기준 값이면 `requires_accessory=True`. 카탈로그가 -180~320 °C를 항온조 옵션으로
    적었다면 본체 값이 아님. 비고에만 적으면 검색이 글자를 읽지 못해 가능으로 답함. 표시해야
    검색이 부속 있으면 가능(`accessory`)으로 구분.

    **AI가 넣지 않은 값은 조용히 덮어쓰기 불가.** 사람 · 반입 · 기록 전 값이면 409로 거절하고
    현재 값과 출처(`origin`)를 반환. 그 값을 사람에게 보여 주고 확인. 사람이 사양서가 다르다고
    하면 `replace=True`. 빈 칸 채우기와 AI가 넣은 값(`origin="agent"`) 수정은 그대로 진행(백필
    용도).

    응답의 `search_axis`가 채워져 있으면 이 값은 이후 이 기종으로 등록하는 장비의 시험 조건이
    됨. `existing_units`는 이미 등록된 대수이며 그 장비에는 미반영(개체의 값은 개체 소유).
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
            "replace": replace,
        },
    )


@mcp.tool()
async def list_spec_sources(ctx: Context, q: str | None = None) -> dict[str, Any]:
    """사양값 출처가 될 제조사 문서 목록.

    **값을 적을 때 출처 함께 기재 필수**(반년 뒤 이 300 kN의 근거를 묻는 경우 대비).
    """
    return await _get(ctx, "/spec-sources", {"q": q, "limit": MAX_LIMIT})


# ── 보유 장비 ─────────────────────────────────────────────────────────────────


@mcp.tool()
async def search_equipment(
    ctx: Context,
    q: str | None = None,
    model_id: str | None = None,
    workspace: str | None = None,
    attr: list[str] | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """보유 장비 목록. 줄마다 시험 항목과 계열·기종 포함.

    `test_items`가 비어 있으면 시험 항목 미기재로 **검색에 절대 안 걸림.**

    `attr`은 기재된 속성 값으로 필터. 여러 개면 모두 만족해야 함. 왼쪽은
    `list_attribute_definitions(target="equipment")`의 `key`(이름 아님: 관리자가 이름을 바꾸면
    저장해 둔 물음이 조용히 빈 답을 냄).

        ["invest_year>=2020"]   수치 · 날짜
        ["purpose~고온"]         문장 포함
        ["reserve_url*"]        값이 기재되어 있기만 하면
        ["reserve_url!*"]       미기재(채울 칸 찾기)
        ["holder!=3동"]          같지 않음

    `!*`와 `!=`는 다름: `!=`는 *기재되어 있으나* 그 값이 아닌 것, `!*`는 줄 자체가 없는 것.
    미기재 항목을 물을 때는 목록을 받아 세지 말고 이 조건 사용.

    **조건으로 가능한 장비를 찾는 도구는 이것이 아님**: `search_test_items(conditions=…)` 사용.
    여기는 기재된 칸 값으로 거르는 곳이라 온도 범위 같은 능력은 보지 않음(능력은 사양이며
    사양은 기종에 있음).
    """
    return await _get(
        ctx,
        "/equipment",
        {
            "q": q,
            "model_id": model_id,
            "workspace": workspace,
            "attr": attr,
            "limit": min(limit, MAX_LIMIT),
        },
    )


@mcp.tool()
async def get_equipment(ctx: Context, equipment_id: str) -> dict[str, Any]:
    """보유 장비 한 대: 자산번호·위치·상태·담당자와 연결 기종.

    `test_items`가 비어 있으면 **검색에 절대 안 걸림.** `series_name`이 비어 있으면 카탈로그
    미연결 장비.
    """
    return await _get(ctx, f"/equipment/{equipment_id}")


@writes
async def import_equipment(
    ctx: Context,
    text: str,
    dry_run: bool = True,
    update_existing: bool = False,
) -> dict[str, Any]:
    """부서 장비 대장 **일괄** 반입. `register_equipment`를 한 대씩 300번 호출 금지.

    `text`는 엑셀에서 복사한 그대로: 탭 또는 쉼표로 나뉜 표, 첫 줄은 머리글. 머리글은
    한국어(허용 이름은 `import_columns`가 제공):

        자산번호  장비명  보유부서  거점  설치위치  기종  장비유형  제조번호  상태
        상태근거  담당자  …

    담당자는 이메일로 기재. 이름도 받지만 동명이인이면 그 줄 거절(임의로 고르면 연락처가 남의
    것이 되고 아무도 모름). `update_existing`과 함께 쓰면 비어 있는 담당자를 일괄 채우는
    방법(자산번호와 담당자 두 열만 있는 표도 가능).

    부서·거점·장비유형·기종은 이름으로 기재. 하나로 확정되지 않으면 그 줄은 거절되고 후보 반환:
    **임의 선택 금지, 사람에게 확인.** 비슷한 기종에 끼워 넣으면 그 장비의 하중·온도가 남의
    것이 되고 검색이 그 수치로 가능이라 답함.

    ## 두 번 호출

    `dry_run=True`(기본)는 저장 없이 줄마다 판정 반환. `problems`가 비어 있으면 반입 가능,
    있으면 틀린 칸(`field`)과 이유 기재. 그 결과를 사람에게 보여 주고 확인받은 뒤
    `dry_run=False`로 재전송.

    반입 가능한 줄은 반입되고 실패한 줄은 `imported=False`로 남음. 실패한 줄만 고쳐 재전송(이미
    들어간 줄을 다시 보내면 이미 등록된 장비로 거절).

    ## 이미 등록된 자산번호

    기본은 거절. `update_existing=True`면 기재된 칸만 갱신(빈 칸은 유지, 부서와 기종은 변경 안
    함). 미리보기가 줄마다 `changes`로 전후 값을 반환하므로 **사람에게 보여 준 뒤 반입**(30대의
    위치가 확인 없이 바뀌는 일 방지).

    ## 기종이 카탈로그에 없을 때

    기종 생성 금지(시스템 관리자 전용이며, 사양 없는 기종은 검색을 망침). 기종 칸을 비우고
    모델명 칸에 기재. 그 장비는 시험 항목 0건이라 검색에 안 걸리지만 홈의 카탈로그에 안 이어진
    장비 목록에 남아 나중에 연결.

    한 번에 최대 2000줄.
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
    """`import_equipment`가 받는 열 목록. 대장 작성 전 한 번 확인.

    머리글에 쓸 수 있는 이름(별칭 포함)과 필수 열 여부 제공.
    """
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
    status_reason: str | None = None,
    maker_text: str | None = None,
    model_text: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """보유 장비 한 대 등록.

    기종을 고르면 그 계열의 시험 항목이 이 장비로 복사되고 조건은 그 기종의 사양에서 옴. 상속이
    아니라 복사라 이후로는 이 장비의 값이 기준(챔버를 뗀 장비는 여기서 수정).

    ## 기종 선택 순서

    계열부터 좁히기. `search_models(series="인스트론 6800 시리즈")`로 라벨과 대조(기종명만으로
    찾으면 비슷한 이름의 다른 계열 기종을 집음).

    ## 못 찾으면 비움

    카탈로그에 없는 기종이면 **`model_id`를 비운 채 등록.** 비슷한 기종 선택 금지(그 장비의
    하중·온도가 남의 것이 됨).

    라벨 글자는 `maker_text` · `model_text`에 그대로 기재하고, 등록 후
    `propose_equipment_model` 호출. 두 칸은 표시용이라 아무도 일감으로 세지 않음. 요청으로
    남겨야 기종이 등록될 때 이 장비가 자동 연결됨.

    자산번호가 이미 있으면 409. 덮어쓰지 않음(같은 번호의 다른 장비일 수 있고, 덮으면 기존 이력
    소실).

    ## 등록 후 할 일

    기종을 골랐으면 계열의 시험 항목이 복사됨. **비웠으면 0건이고 0건이면 검색에 절대 안
    걸림**: 이어서 `add_equipment_test_item`으로 채움.

    상태가 `operational`이 아니면 `status_reason`에 사유 기재(예: 제어보드 고장, 부품 대기).
    비고 기재 금지(비고는 여러 내용이 섞여 상태 근거로 읽히지 않음).

    ## 필수 항목

    보유 부서·거점(`site_term_id`)·상세위치(`location`), 그리고 장비 종류. 위치와 종류를 모르는
    장비는 찾아도 쓸모없음.

    종류는 기종을 고르면 따라옴(계열 소유). 기종을 못 찾아 비웠다면 `category_term_id`를 직접
    지정(`resolve(axis="equipment_category", …)`로 조회). 둘 다 없으면 400.

    미연결 장비의 제조사·모델명은 `maker_text`·`model_text`에 기재. 표시용이라 검색이 보지
    않음(기종을 찾는 편이 항상 나음). 나중에 기종에 연결하면 서버가 이 두 칸을 비움.

    ## 상태

    아홉 가지: `incoming` · `operational` · `stopped` · `idle` · `maintenance` · `repair` ·
    `retired` · `struck` · `unknown`. 모르면 지어내기 금지: 고르기 어려우면 `unknown`(미기재)이
    정직한 답. 뜻과 검색이 세는 네 가지는 `get_guide("보유 장비")`.

    ## 교정

    `calibration_required`가 참이면 `calibration_interval_months`도 필수. 주기가 없으면 차기일
    계산 불가, 곧 만료 목록에서 영구 누락. 모르면 대상 여부를 비워 두고 사람에게 확인.
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
            "status_reason": status_reason,
            "maker_text": maker_text,
            "model_text": model_text,
            "note": note,
        },
    )


@mcp.tool()
async def get_equipment_specs(ctx: Context, equipment_id: str) -> dict[str, Any]:
    """**장비 한 대**의 사양: 카탈로그 값과 실측값을 한 줄에 함께 반환.

    기종 사양(`get_specs`)은 제조사 기재값, 여기 `measured`는 이 장비의 실측값. **둘 다 보고
    답변**: 실측이 있으면 그것이 이 장비의 기준이고, 없으면 카탈로그 값은 이 장비를 잰 값이
    아님.
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
    """장비 한 대의 **실측** 사양 한 칸 기록. 카탈로그 값 위에 덮어씀.

    **기종 사양과 혼동 금지.** `set_spec`은 그 기종을 쓰는 모든 장비의 기준이고, 이 도구는 이
    한 대의 값. 직접 잰 값, 성적서에 적힌 이 장비의 값은 여기에 기록.

    정의의 종류에 맞는 칸만 채움: 수치 `num_value`, 구간 `num_min`/`num_max`, 선택값·문장
    `text_value`, 참거짓 `bool_value`.

    측정일(`measured_on`) 기재. 3년 전 실측은 사양서보다 나을 것이 없고, 날짜가 없으면 사람이
    판단 불가.

    응답의 `reflected`가 참이면 이 장비의 시험 조건도 함께 갱신됨. 거짓이면 그 조건은 사람이
    직접 기재한 값이라 덮지 않음(덮으려면 사람에게 확인).
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
    """**장비**의 시험 항목 하나 추가.

    ## 사용 시점 (누락 시 그 장비는 검색에서 영구 누락)

    기종을 골라 등록하면 계열의 시험 항목이 복사되므로 대개 호출 불필요. 단 **카탈로그에 없어
    `model_id`를 비운 채 등록한 장비는 시험 항목 0건**이고, 0건이면 검색에 절대 안 걸림. 그런
    장비를 만들었으면 여기서 채움.

    `confidence`는 값의 신뢰 수준:

        catalog   사양서에서 온 값. 실제 수행 아님(기본)
        verified  실제로 수행해 봄
        limited   가능하나 조건이 붙음. 그 조건을 note에 기재

    **`verified` 남용 금지.** 사양서를 옮긴 값이면 `catalog`.

    시험 항목은 닫힌 축이라 없는 값은 생성되지 않음(거절). `resolve`로 먼저 조회(오타가 값이
    되면 그 장비가 검색에서 영구 누락).
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
    """시험 항목의 **가능 범위**(조건 한 칸) 기록. 조건 한 칸은 덮어쓰기.

    조건 축은 `list_conditions`가 제공.

    ## 값은 그 축의 `unit`으로, 서버는 환산하지 않음

    `list_conditions`의 `unit`이 그 단위(하중 kN · 온도 degC · 낙하 높이 cm). `si_unit` 아님:
    낙하 높이의 si_unit은 m이지만 값은 cm로 저장. 다른 단위로 보내면 **자릿수가 틀림**: 152
    cm를 1.52로 보내면 1.52 cm짜리 장비가 되어 검색에서 조용히 누락.

    환산은 호출하는 쪽 몫: 1.5 m 낙하면 `max_value=150`, 20 kN이면 `20`.

    ## 비운 쪽은 제한 없음

    0으로 채우기 금지(하한이 0인 장비와 구별되지 않고 검색이 그 차이로 갈림). 20 kN까지는
    `max_value=20`, `min_value`는 비움.

    ## 모르면 기재 금지

    미기재 조건은 검색이 `unknown`으로 답하며 그것이 맞는 답. 지어낸 숫자는 가능으로 답하게
    되어, 그 답을 믿고 일정을 짠 사람이 막힘.

    ## 부속이 있어야 나오는 범위면 `requires_accessory=True`

    챔버·노 옵션 기준 온도가 해당. 검색이 가능 대신 부속 있으면 가능(`accessory`)으로 답함. 그
    장비에 부속이 실제로 있으면 False로 재저장.
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
    model_id: str | None = None,
    status: str | None = None,
    status_reason: str | None = None,
    location: str | None = None,
    site_term_id: str | None = None,
    contact_user_id: str | None = None,
    shared_use: bool | None = None,
    calibration_required: bool | None = None,
    calibration_interval_months: int | None = None,
    retired_on: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """보유 장비 한 대 수정. **보내지 않은 칸은 변경 없음.**

    기종 연결은 `model_id`(카탈로그 미연결 장비를 기종에 잇는 곳). `search_models`로 찾아
    **라벨의 모델명과 글자로 일치할 때만** 연결: 비슷한 기종을 고르면 그 장비의 하중·온도가
    남의 것이 되고 조건 검색 화면이 그 수치로 답함. 못 찾으면 연결하지 말고
    `propose_equipment_model`로 요청 등록. 연결하면 개체에 적힌 분류·제조사·모델명은 서버가
    비우고, 시험 항목은 다시 복사되지 않음(이미 이 장비의 값이 된 것을 사양서로 덮지 않음).

    상태 아홉 가지: `incoming` 입고 · `operational` 가동 · `stopped` 미가동 · `idle` 미사용 ·
    `maintenance` 점검·교정 · `repair` 고장 수리중 · `retired` 폐기 · `struck` 취소선 ·
    `unknown` 미기재.

    검색이 사용 가능으로 세는 것은 `operational`·`idle`·`stopped`·`unknown` 네 가지(미사용이
    사용 불가를 뜻하지 않음). 고장·점검·입고·폐기·취소선은 제외.

    폐기일은 상태가 `retired`일 때만 받음. 상태를 되돌리면 서버가 비움.

    `status_reason`은 그 상태의 사유(예: 제어보드 고장, 부품 대기). 상태를 바꿀 때 함께 전송:
    보내지 않으면 서버가 비움(사유는 상태에 붙는 값이라, 고친 장비에 옛 고장 사유가 남으면
    목록에 그대로 표시됨).

    보유 부서·거점·상세위치는 비울 수 없음(위치를 모르는 장비는 찾아도 쓸모없음). 부서 이관은
    양쪽 관리자 권한이 필요해 이 도구로는 불가.

    `contact_user_id`는 장비를 찾은 뒤 연락할 사람. 없는 계정이나 비활성 계정은 400. 계정 id를
    조회하는 도구는 없음: 담당자는 대장 반입(`import_equipment`)의 `담당자` 열에 이메일로 입력.
    """
    body = {
        "model_id": model_id,
        "status": status,
        "status_reason": status_reason,
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
async def list_model_requests(
    ctx: Context, include_decided: bool = False, gaps: bool = False, case: str | None = None
) -> dict[str, Any]:
    """카탈로그에 없다고 올라온 기종 요청 목록. `gaps=True`면 미연결 장비 전체의 보강 목록.

    요청: 같은 표기끼리 묶음, 건수가 큰 순서. 묶음마다 `normalized`(결정 시 쓰는 키) ·
    `text` · `count` · `proposals`(장비별 기재 내용과 못 찾은 이유) 포함. 한 번만 나온 요청은
    자작 장비일 수 있음.

    `gaps=True`(시스템 관리자 전용): 요청이 없는 미연결 장비까지 제조사+모델명 표기로 묶어
    `case`별로 가름. `exact`(같은 기종 있음) · `similar`(비슷한 기종, 다른 기종일 수 있음) ·
    `series_only`(계열만 있음) · `not_in_catalog`(제조사·계열부터 없음, 사양서 조사 대상) ·
    `no_model`(모델명 없음, 대조 불가) · `excluded`(관리자가 대상 아님으로 정함). `case`로
    좁힘. 묶음마다 `key` · 후보 `models`/`series`(후보일 뿐, 같은 기종이라는 판정 아님) ·
    장비 앞 다섯 대. `by_category`의 `in_catalog=false`는 분류부터 카탈로그 정본에 없음.

    결정은 `decide_model_request`(보강 목록 묶음은 `gap=True`와 `key`).
    """
    if gaps:
        found = await _get(ctx, "/equipment-models/gaps", params={"case": case})
        if not isinstance(found, dict) or "groups" not in found:
            return _listed(found, "groups")
        # **응답 한도 안에 들게 줄인다** — 미연결 장비가 수백 대면 통째로는 잘린 채 도착한다.
        # 요약 · 분류별 표는 그대로 두고 묶음과 장비 목록만 자른다(전체는 화면의 CSV).
        groups = found["groups"]
        found["groups"] = [
            {**group, "units": group["units"][:5]} for group in groups[:GAP_GROUPS]
        ]
        found["groups_shown"] = len(found["groups"])
        return dict(found)
    return _listed(
        await _get(
            ctx,
            "/equipment-models/proposals",
            params={"include_decided": "true" if include_decided else "false"},
        ),
        "groups",
    )


#: 보강 목록 묶음을 한 번에 몇 개까지 돌려주나. 큰 묶음이 앞이라 앞 쉰 개면 일의 대부분이다.
GAP_GROUPS = 50


@writes
async def decide_model_request(
    ctx: Context,
    normalized: str,
    model_id: str | None = None,
    series_id: str | None = None,
    name: str | None = None,
    reject: bool = False,
    gap: bool = False,
) -> dict[str, Any]:
    """기종 요청 한 묶음 결정: 연결 · 신규 기종 등록 · 거절 중 하나만. 시스템 관리자 전용.

    `model_id`(기존 기종, `resolve(kind="model")`·`search_models`로 조회) ·
    `series_id`+`name`(그 계열에 기종 신규 등록. 이름에 계열 이름 혼합 금지: 섞으면 `6800
    68FM-300`과 `68FM-300`이 별개 기종이 됨) · `reject=True`(자작 장비처럼 카탈로그 대상이
    아님). 아무것도 없으면 400. 결정하면 요청한 장비들이 일괄로 그 기종에 연결됨. 한 대가
    막혀도 나머지는 연결되고, 막힌 줄은 `failed`로 반환. `gap=True`면 `normalized` 자리에
    보강 목록(`list_model_requests(gaps=True)`)의 `key`: 요청이 없으면 만든 뒤 같은 규칙으로
    결정.

    **결정 전 사람에게 보여 주고 확인 필수.** 기종을 고르면 그 계열의 시험 항목이 장비에
    복사되고 조건 판정이 그 기종 사양을 씀: 비슷한 기종으로 대체하면 그 장비의 하중·온도가 남의
    것이 되고 오답이 드러나지 않음. 확신이 없으면 결정하지 않고 둠(요청은 유지). `reject`는
    사람이 거절을 지시한 경우만. 시스템 관리자 토큰이 아니면 403(TSC-EQUIPMENT-0041).
    """
    decision = {"model_id": model_id, "series_id": series_id, "name": name, "reject": reject}
    if gap:
        # 보강 목록 묶음 — 요청이 없으면 서버가 만든 뒤 같은 규칙으로 정한다.
        return await _send(
            ctx, "POST", "/equipment-models/gaps/resolve", {"key": normalized, **decision}
        )
    return await _send(
        ctx,
        "POST",
        "/equipment-models/proposals/decide",
        {"normalized": normalized, **decision},
    )


@mcp.tool()
async def get_calibrations(ctx: Context, equipment_id: str) -> dict[str, Any]:
    """장비의 **교정 이력**: 일자, 기관, 결과, 차기일. 최신순.

    마지막 교정일, 현재 유효 여부에 대한 답. 이력이 비어 있는데 장비가 교정
    대상(`calibration_required`)이면 모름이 아니라 **채워야 할 항목**으로 전달.
    """
    return _listed(await _get(ctx, f"/equipment/{equipment_id}/calibrations"), "calibrations")


@mcp.tool()
async def list_calibrations_due(ctx: Context) -> dict[str, Any]:
    """곧 만료되거나 **이미 지난** 교정 목록. 전사 범위, 조회 권한 있는 장비만.

    지난 것도 포함(빼면 만료 장비가 계속 쓰이고 그 장비로 낸 값 전체를 신뢰할 수 없게 됨). 이달
    교정 대상 장비를 물으면 여기서 시작.
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
    """교정 이력 한 줄 추가. 날짜는 `YYYY-MM-DD`.

    **성적서에 차기일(`next_due_on`)이 있으면 반드시 입력.** 기관이 정한 날이 기준이며, 없으면
    시스템이 교정 주기로 계산해 표시(계산값 표시가 붙지만, 성적서가 있는데 안 넣으면 그 표시가
    틀린 정보가 됨).

    교정 기관은 축의 값(`resolve(axis="calibration_provider", …)`). 자유 문자열이면 같은 기관이
    한국계량측정협회와 (주)한국계량측정협회로 갈려 서로 다른 기관이 됨.

    이력을 넣어도 장비가 교정 대상으로 표시되지 않았으면 곧 만료 목록에 안 뜸:
    `update_equipment(calibration_required=True, calibration_interval_months=…)`를 함께 호출.
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
    """카탈로그가 **정본보다 뒤처졌는지** 확인. 카탈로그에 없다고 답하기 전 확인.

    반입은 사람이 실행하고 배포는 파일만 교체. `behind`가 참이면 이 설치의 카탈로그는
    정본(`objects` 객체)보다 오래된 것(`imported_objects` 객체, `imported_at`)이라 없다는 답이
    아직 반입 전일 수 있음. 그 사실을 전달하고 관리자에게 `scripts/import_catalog.py` 실행
    요청. `never`는 한 번도 반입하지 않은 설치.
    """
    return await _get(ctx, "/server/catalog")


@mcp.tool()
async def list_pending_work(ctx: Context) -> dict[str, Any]:
    """**남은 일 목록.** 채울 곳과 사람이 정할 것을 한 번에 집계(0건 항목은 생략).

    채울 곳: 시험 항목 미기재 장비 · 사양 미기재 보유 기종 · 시험 항목 미기재 보유 계열 · 원본
    확인이 필요한 기종 · 교정 기한이 지난 장비. 정할 것: 확인 대기 신뢰성 시험(후보, 확인
    권한자에게만) · 시스템 관리자에게는 검토함 미결 · 시험 항목 요청 · 기종 등록 요청(묶음 수).

    **이것이 답**: 항목마다 수와 화면 주소(`link`) 포함. 각 목록 도구를 따로 다시 부를 필요
    없음(사용자가 특정 항목을 물을 때만). 카탈로그 전체가 아니라 보유 자원 기준.
    """
    return _listed(await _get(ctx, "/server/maintenance"), "items")


# ── 시험 항목 카탈로그 — 사슬의 가운데 ──────────────────────────────────────────


@mcp.tool()
async def list_test_items(ctx: Context, gap: str | None = None) -> dict[str, Any]:
    """**시험 항목 96종, 줄마다 사슬 전체의 연결 수.** 0이 곧 공백.

        물성  ⇄  시험 항목  →  규격  →  계열/기종  →  보유 장비

    줄마다 `properties_total`(그중 `properties_confirmed`) · `methods_total`(그중
    `methods_with_requirements`) · `series_count` / `model_count` · `equipment_count`(조회 권한
    있는 보유 장비) · `condition_keys`(검색축 라벨) 포함.

    `gap`으로 공백만 필터: `properties`(물성 없음) · `methods`(규격 없음) · `series`(가능 계열
    없음) · `equipment`(보유 장비 없음) · `axes`(검색축 없음). 채우는 주체가 각각 다름: 물성은
    재료 쪽, 규격은 시험실, 검색축은 시스템 관리자.

    이 시험의 수행 가능 여부는 `equipment_count`, 구매로 가능한지는 `series_count`가 답함. 둘
    다 0이면 카탈로그에도 그 장비가 없음.
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
            return {"error": f"gap은 {' · '.join(gaps)} 중 하나여야 함"}
        rows = [r for r in rows if gaps[gap](r)]
    return _listed(rows, "test_items")


@mcp.tool()
async def get_test_item(ctx: Context, test_item_term_id: str) -> dict[str, Any]:
    """시험 항목 하나: **측정 물성 · 규격 · 가능 계열 · 보유 장비 · 검색축** 일괄 조회.

    `condition_keys`가 이 시험에 뜻이 있는 조건 축(인장 → 하중·속도·온도). 검색에 조건을 붙이기
    전 먼저 확인(축 밖 조건은 대개 `unknown`만 늘림). 비어 있으면 미정(`set_test_item_axes`로
    지정, 시스템 관리자).

    `properties[].status`가 `suggested`면 기계 제안. `methods`는 이 시험의 규격으로 정해진 것,
    `series[].method_codes`는 그 계열이 이 시험에 인용한 규격. `equipment`는 조회 권한 있는
    보유 장비만.
    """
    return await _get(ctx, f"/test-items/{test_item_term_id}")


@writes
async def set_test_item_axes(
    ctx: Context, test_item_term_id: str, condition_key_ids: list[str]
) -> dict[str, Any]:
    """시험 항목에 **뜻이 있는 조건 축** 지정(전체 교체). 시스템 관리자 전용.

    인장은 하중·속도·온도, 챔버는 온도·습도. 카탈로그에 없는 지식이라 사람이 정함: **AI
    짐작으로 지정 금지.** 사람이 축을 말했을 때만 그대로 기록(예: 인장은 하중·속도·온도). 조건
    키 id는 `list_conditions()`가 제공.
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
    """규격 목록. **수행 불가 시험과 연결 끊김을 구분.**

    줄마다 `test_item`(규격이 속한 시험) · `series_count`(연결된 계열) ·
    `pending_series_count`(인용했으나 시험 항목 미정으로 미연결된 계열) ·
    `equipment_count`(수행 가능 장비) · `requirements`(요구 조건) 포함.

    **`series_count`가 0이고 `pending_series_count`가 0이 아니면 수행 불가가 아니라 연결
    끊김**: `set_method_test_items`로 시험 항목을 정하면 연결됨.

    필터: `test_item`은 값 id 또는 `none`(미정만) · `requirement=none`(요구 조건 없는 것만) ·
    `cited=none`(어느 계열에도 미연결만) · `used=owned`(보유 장비가 실제로 가리키는 것만. 요구
    조건은 여기부터 채움).
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
    test_item_term_ids: list[str] | None = None,
    body_term_id: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    """규격 등록. **먼저 `resolve(kind="method", text=code)`로 조회 필수.**

    규격 번호는 표기가 갈림(JIS B 0601 / JIS B0601). 서버가 공백을 제거해 비교하므로 이미
    있으면 409. 409는 실패가 아니라 답(그 id 사용).

    `edition`은 판(예: 2019, Ed.3). 같은 규격의 다른 판은 별도 줄(요구 조건이 판마다 바뀜).

    `test_item_term_ids`는 이 규격이 속한 시험 항목 목록(`resolve(kind="term",
    axis="test_item")`). 규격 하나가 여러 시험 항목을 덮는 경우가 흔함: IEC 60529는 IP 코드의
    1자리(방진)와 2자리(방수)를 한 문서가 정의하고, MIL-STD-810은 방법 번호마다 다른 시험.
    **하나만 적으면 나머지 항목에서 이 규격이 보이지 않음.**

    `body_term_id`는 제정기관(`axis="standard_body"`). 모르면 비움(항목 미정 규격은 검토함이
    사람에게 질의). 전사 공용으로 생성됨.
    """
    return await _send(
        ctx,
        "POST",
        "/methods",
        {
            "code": code,
            "title": title,
            "edition": edition,
            "test_item_term_ids": test_item_term_ids or [],
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
    """규격의 **요구 조건 한 줄** 기록. 여러 줄을 표로 넣을 때는 `import_requirements`.

    규격서를 읽다 조건 하나를 발견했을 때 사용. `condition_key_id`는 `list_conditions`가 제공.
    **값은 그 축의 `unit`으로 기재**(`list_conditions`가 축마다 제공. 하중 축은 kN이라 20
    kN이면 20, 낙하 높이는 cm라 1.5 m면 150. 축 단위를 지어내지 말고 확인). 같은 조건이 이미
    있으면 덮어씀. 한쪽을 비울 수 있음: 20 kN 이상은 min만 있고 max는 None(0으로 채우면 상한
    0과 구별 불가).

    이 조건이 곧 검색 물음이 됨(`search_test_items(method_id=…)`). 규격서에 적힌 것만 기재하고,
    관례로 아는 값은 `note`에 그 사실을 명시.
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
async def set_method_test_items(
    ctx: Context, method_id: str, test_item_term_ids: list[str]
) -> dict[str, Any]:
    """규격의 **시험 항목 지정(여러 개 가능).** 인용 계열에 자동 연결.

    정하는 즉시 그 규격을 항목 미정으로 인용한 계열의 해당 시험 항목에 자동 연결(계열마다 다시
    잇지 않음).

    **보낸 목록으로 전체 교체.** 하나를 더하려면 현재 목록(`get_method`의 `test_items`)에 더해
    전부 전송(누락 시 연결이 조용히 끊김).

    규격 하나가 여러 시험 항목을 덮는 경우가 흔함: IEC 60529는 IP 코드의 1자리(방진)와
    2자리(방수)를 한 문서가 정의하고, MIL-STD-810은 방법 번호마다 다른 시험.

    추측으로 지정 금지. ASTM D638이 인장이라는 판단은 규격 번호를 아는 사람의 몫. 모르면
    `get_method`의 `cited_series`(인용 계열)를 보고 사람에게 확인.

    검토함에 질문이 열려 있는 규격은 여기서 지정 불가: 같은 결과를 내도 검토함 줄이 열린 채
    남음(서버가 409로 차단). 검토함 첫 줄 확정 같은 요청은 `decide_review_item`으로(시스템
    관리자).
    """
    return await _send(
        ctx, "PATCH", f"/methods/{method_id}", {"test_item_term_ids": test_item_term_ids}
    )


@mcp.tool()
async def get_method(ctx: Context, method_id: str) -> dict[str, Any]:
    """규격 하나: 시험 항목 · 요구 조건 · **인용 계열**(`cited_series`) · 수행 가능 장비 수.

    `cited_series`의 줄이 `pending`이면 어느 시험 항목의 인용인지 미정.

    **규격서 원문 첨부 여부는 `list_attachments(target="method", …)`로 확인.** 요구 조건이 빈
    규격이 대부분(601 중 598)이라, 원문이 있으면 사람에게 원문을 읽고 채워 달라고 요청 가능.

    `test_items`는 목록: 규격 하나가 여럿을 덮음(IEC 60529는 방진·방수 둘 다). 비어 있으면
    미정이며 그 규격은 계열의 시험 항목에 연결되지 않음.
    """
    return await _get(ctx, f"/methods/{method_id}")


@writes
async def import_requirements(ctx: Context, text: str, dry_run: bool = True) -> dict[str, Any]:
    """규격 **요구 조건 표** 일괄 반입(규격서를 보고 작성한 표).

    `text`는 머리글 줄을 포함한 표(탭 또는 쉼표). 열: 규격 · 판 · 조건 · 최소 · 최대 · 값 ·
    필수 · 비고. 값은 조건의 단위(kN · °C)로 기재, 단위를 함께 적어도 됨. 다른 단위면 거절(20
    N을 kN으로 받으면 천 배 오차).

    `dry_run=True`(기본)면 저장 없이 줄마다 판정만 반환. 사람이 확인한 뒤 같은 내용으로
    `dry_run=False`. 같은 규격·조건이 이미 있으면 `replaces`로 미리 알림.

    **값 지어내기 금지.** 사람이 규격서를 보고 작성한 표를 옮기는 용도. 틀린 조건은 빈 조건보다
    나쁨(검색이 확신을 갖고 틀린 답을 냄).
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
    """시험 항목 → 물성 연결 **제안**(확인 아님).

    규격·문헌을 읽고 알게 된 연결을 기록(예: 인장에서 항복강도가 나옴). 상태는 항상
    `suggested`, 출처는 `agent`. **AI의 자체 확인 금지.** 확인은 사람이 검토했다는 뜻이며
    카탈로그 정본에 실리므로 사람이 물성 화면이나 `confirm_property_links`로 수행.

    둘 다 id(`resolve(kind="term", axis="test_item"|"property")`). 이미 연결되어 있으면 409.
    `note`에는 부가 조건(예: 신율계 필요)이나 근거(규격 번호) 기재.
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
    """물성↔시험 항목 제안 **일괄 확인**(`confirmed`) 또는 되돌리기(`suggested`).

    사람이 인장이 내는 물성 다섯 개가 맞다고 했을 때 해당 줄의 `link_id`를 한 번에
    전송(`search_properties`의 `links[].id` 또는 `get_test_item`의 `properties[].link_id`).
    이미 그 상태인 것은 세지 않고 실제 바뀐 수를 `changed`로 반환.

    **AI의 자체 확인 금지.** 확인은 사람이 검토했다는 뜻이며 내보내기가 카탈로그 정본에 싣는
    값. 사람이 말한 것만 기록.
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
    """**기종 고유 사양** 한 줄: 정의 없이 이름·값·단위로 추가.

    `list_spec_definitions`에 맞는 칸이 없을 때 사용(카탈로그 키 950종 중 803종이 한 기종에만
    등장. 전부 정의로 세우면 사양 추가 목록이 쓸모없어짐). 값은 원문 그대로(예: LV 4종, 0 ~
    600). 같은 이름이 여러 기종에 쌓이면 `promote_free_spec`으로 정의 승격. 기존 줄은
    `get_model`의 `free_specs`.
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
    """기종 고유 사양을 **정의로 승격.** 시스템 관리자 전용.

    `key`(소문자·밑줄, 생성 후 변경 불가) · `label` · `group_id`(`/spec-groups`) ·
    `kind`(`range` · `number` · `text` · `boolean`) · `unit`은 사람이 결정: **이름을 기계가
    지어내면 그대로 정본이 됨.** 정의는 그 기종의 분류에 붙고, `apply_same_key`면 같은 원본
    키를 가진 다른 기종의 줄도 함께 이동. 수치로 못 읽는 줄(예: 약 300)은 그대로 남고 `left`로
    집계.

    승격 시점: `get_model`의 `free_specs[].same_key_models`가 0이 아닐 때.
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


# ── 온톨로지 — 축과 값 ────────────────────────────────────────────────────────


@mcp.tool()
async def list_reference(ctx: Context) -> dict[str, Any]:
    """**시스템 온톨로지 개요**: 객체 종류마다 한 줄.

    종류(시험 항목·물성·장비 계열·기종·보유 장비·신뢰성 시험 …)마다 저장 방식(축의 값인지, 자체
    표를 가진 객체인지) · 건수 · 고정 칸 · 관리자 정의 칸(검색 조건·사양·속성) 포함. **무엇을
    어디에 적을지 모를 때 여기부터 확인**: 축에 값을 더할지, 객체로 만들지에 대한 답이 있음.
    """
    return _listed(await _get(ctx, "/reference/overview"), "kinds")


@mcp.tool()
async def list_axes(ctx: Context) -> dict[str, Any]:
    """온톨로지 **축** 목록: slug · 이름 · 소속 · 값 수 · 등록 정책.

    `entry_policy`가 `open`이면 누구나 값 추가 가능(`create_term`). `closed`면 시스템 관리자
    전용(제정기관·조건처럼 뜻이 계약인 축). 값이 0인 축은 아직 아무도 채우지 않은 축이며, 값을
    넣으면 그 축을 쓰는 화면이 그때부터 답을 냄.
    """
    return _listed(await _get(ctx, "/vocabularies"), "axes")


@mcp.tool()
async def list_terms(
    ctx: Context, axis: str, q: str | None = None, include_deprecated: bool = False
) -> dict[str, Any]:
    """한 축의 값 목록: 이름 · 코드 · 별칭 · 상위 값 · 상태.

    `axis`는 `list_axes`의 slug(`test_item` · `property` · `site` · `equipment_category` ·
    `maker` · `standard_body` …). **값 생성 전 이 도구로 조회 필수**(같은 뜻의 값이 있는데 새로
    만들면 검색이 절반만 답함). 표기가 갈릴 것 같으면 `resolve(kind="term", axis=…)`가 별칭까지
    조회.
    """
    return _listed(
        await _get(
            ctx,
            f"/vocabularies/{axis}/terms",
            {"q": q, "include_deprecated": "true" if include_deprecated else None},
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
    """온톨로지 **축** 신규 생성. 시스템 관리자 전용. **가급적 생성 자제.**

    **먼저 `list_axes`로 확인.** 뜻이 닿는 축이 있으면 그 축에 값을 추가(`create_term`). 축이
    둘로 갈리면 값도 갈리고 합칠 방법이 없음(값 병합 `merge_terms`는 같은 축 안에서만 가능).
    예: 불량 모드와 불량 유형이 따로 서면 그대로 굳음.

    여기서 만든 축은 보관용일 뿐. 기존 축(`manufacturer` 등)은 화면과 코드가 slug를 참조해 값이
    쓰임. 새 축은 그런 참조가 없어 검색·판정·반입 어디에도 자동 반영되지 않고, 값을 담아 사람이
    보는 목록이 됨. 그래도 뜻이 다른 값을 남의 축에 넣는 것보다는 나음(제정기관 축에 회사
    이름이 들어간 실제 사례 있음).

    `domain`은 화면의 묶음 단위: `equipment` · `catalog` · `method` · `common`.
    `entry_policy`가 `closed`면 값도 시스템 관리자만 추가.

    `attribute_schema`는 이 축의 값이 갖는 칸(물성 값의 기호·단위 등): `[{"key": "symbol",
    "label": "기호", "kind": "text"}]`. `kind`는 `text`·`number`·`list`. 축에 한 번만
    정의(값마다 정의하면 같은 내용을 수백 번 저장). 수정은 `update_axis`.

    이 설치에만 존재. 설치 시드(`ensure_reference_data`)가 심는 축이 정본이라 여기서 만든 축은
    새 설치 서버에 생기지 않음. 계속 쓸 축이면 사람이 시드에 추가해야 한다고 안내.
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
    """축의 **이름·설명·정책·값의 칸** 수정. 시스템 관리자 전용. 보내지 않은 항목은 유지.

    `slug`와 소속은 변경 불가(코드가 그 이름을 참조).

    **`attribute_schema`는 전체 교체.** 칸 하나를 더하려면 `list_axes`로 현재 칸을 받아 전부
    전송: 빠진 칸은 정의에서 사라지고 화면이 그 칸을 그리지 않음(값에 적힌 내용은 남아 그 밖의
    속성으로 표시).

    `entry_policy`를 `open` -> `closed`로 잠그는 경우 있음(값이 흩어지기 시작한 축). 반대로
    여는 것도 가능하나, 검색의 첫 축이면 오타가 값이 됨.
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
    """**검색 조건 축** 신규 생성(온도·하중처럼 판정에 쓰는 칸). 시스템 관리자 전용.

    **먼저 `list_conditions`로 확인.** 같은 뜻의 축이 있으면 그것을 사용(시험 온도와 온도가
    따로 서면 장비마다 다른 축에 기록되고 검색이 절반만 답함).

    ## 단위 오류는 조용히 틀린 답을 냄

    값의 저장 단위는 `display_unit`(비면 `si_unit`)이며 응답의 `unit`이 그것. `display_unit`은
    실무 단위(kN · degC · cm), `si_unit`은 그 차원의 기준 단위(낙하 높이면 m). `dimension`이
    같아야 환산 성립(temperature · force · length · time · frequency). `list_conditions`로 인접
    축의 단위를 보고 맞춤.

    **생성 후 `display_unit`은 변경 불가로 간주.** 수정 API는 숫자가 이미 있으면 거절하고
    환산(convert) 또는 유지(keep)를 묻는데, 둘 다 사람이 정할 일.

    `kind`: `range`(구간, 대부분) · `choice`(선택값, `choices` 필요) · `boolean`.

    ## 생성 후 할 일

    축만 만들면 아무 효과 없음. 시험 항목에 연결해야(`set_test_item_axes`) 그 시험 질의 시
    조건으로 표시되고, 장비·기종에 값이 기재되어야 판정 가능.
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
    """온톨로지 값 하나 추가. **생성 전 조회 필수.**

    `resolve(kind="term", axis=…, text=…)`나 `list_terms`로 먼저 확인하고, 같은 뜻의 값이
    있으면 그 값 사용. 이미 있는 이름이면 409. 409는 실패가 아니라 답(별칭까지 보고 막으므로
    409면 그 값의 id 사용).

    **`resolve`가 `candidates`를 주면 생성도, 별칭 연결도 하지 말고 사람에게 확인.** 크리프가
    크리프 파단의 후보로 잡혔을 때 별칭으로 붙이면 다른 시험이 한 이름이 됨(실측에서 AI가
    실제로 그렇게 함). 같은 것인지는 사람만 판단 가능.

    `code`는 정본·반입이 참조하는 이름(시험 항목의 `tensile` 등). 모르면 비움(지어내면 다음
    반입이 다른 코드로 같은 값을 또 생성). `parent_term_id`는 계층이 있는 축(장비 분류의 군 →
    유형)에서만.

    `entry_policy`가 `closed`인 축(제정기관·조건 …)은 시스템 관리자만 추가 가능. 거절되면
    사람에게 인계.

    `attributes`는 그 축이 정한 칸을 채움(`list_axes`의 `attribute_schema`가 칸 정의): 물성이면
    `{"symbol": "σ", "unit": "MPa"}`. 스키마에 없는 키는 지워지지는 않지만 화면이 그 밖의
    속성으로 밀어 둠. 칸 이름 지어내기 금지, 스키마 먼저 확인. 모르는 칸은 비움.
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
    """온톨로지 값 수정. **보내지 않은 칸은 유지.**

    **이름 변경은 그 값을 쓰는 모든 화면의 글자를 바꾸는 일.** 오타 수정이면 가능. 뜻이 다른
    값이면 수정하지 말고 새로 생성(인장을 고온 인장으로 고치면 그 값을 쓰던 장비 전부가 조용히
    다른 시험 장비가 됨).

    `attributes`는 보낸 키만 변경(축의 `attribute_schema`가 칸 정의). `status`는 `active` ·
    `deprecated`. 폐기해도 삭제되지 않음: 쓰던 곳은 그대로 남고 새로 고를 때만 숨겨짐. 값
    병합은 `merge_terms`.
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
    """온톨로지 값에 **다른 이름(별칭)** 추가. 시스템 관리자 전용.

    별칭은 `resolve`가 이름보다 먼저 보는 항목이라, thermal shock으로 물어도 열충격을 찾게 됨.
    **사람이 이 표기가 그 값이라고 말했을 때만** 추가. `resolve`가 후보로 제시했다는 이유로
    추가 금지(후보는 비슷함이지 같음이 아님). 같은 축의 다른 값이 쓰는 표기는 추가 불가(409. 한
    이름이 두 값을 가리켜 검색이 갈림). 실제로 갈려 들어온 표기만 추가하고, 있을 법한 표기를
    지어 붙이지 않음.
    """
    return await _send(ctx, "POST", f"/vocabularies/terms/{term_id}/aliases", {"value": value})


@writes
async def merge_terms(ctx: Context, term_id: str, into_term_id: str) -> dict[str, Any]:
    """같은 뜻으로 갈린 두 값을 하나로 병합. 시스템 관리자 전용.

    `term_id`의 쓰임이 `into_term_id`로 이동하고 원래 이름은 별칭으로 남음(같은 오타의 재유입
    방지).

    **사람이 두 값이 같다고 말했을 때만** 호출. 비슷해 보인다는 이유로 합치면(인장과 고온 인장)
    다른 시험이 한 줄이 되고 갈랐던 흔적도 사라짐. 먼저 `get_term_references`로 이동 대상을
    보여 주고 확인받음.
    """
    return await _send(
        ctx, "POST", f"/vocabularies/terms/{term_id}/merge", {"target_term_id": into_term_id}
    )


# ── 온톨로지 — 쓰임과 연결 해제 ──────────────────────────────────────────────


@mcp.tool()
async def get_term_references(ctx: Context, term_id: str) -> dict[str, Any]:
    """온톨로지 값 하나의 **사용처**: 계열·기종·장비·규격·물성 연결 등 종류별 수와 줄.

    값 삭제·병합 전 확인. 사용 중인 값은 삭제 불가: 쓰임을 풀거나 다른 값으로 옮긴 뒤
    삭제(`detach_term_reference`).
    """
    return _listed(await _get(ctx, f"/vocabularies/terms/{term_id}/references"), "groups")


@writes
async def detach_term_reference(
    ctx: Context,
    term_id: str,
    kind: str,
    row_id: str,
    reassign_to_term_id: str | None = None,
) -> dict[str, Any]:
    """온톨로지 값의 쓰임 하나를 **해제하거나 다른 값으로 이동.** 시스템 관리자 전용.

    `kind`와 `row_id`는 `get_term_references`가 제공. `reassign_to_term_id`를 주면 그 값으로
    이동, 안 주면 해제(종류에 따라 비우거나 삭제. 응답의 `detach`에 명시). **사람이 그 변경을
    지시했을 때만** 사용(예: 이 장비의 분류를 저것으로 변경).
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


# ── 신뢰성 시험 — 사업부가 수행하는 절차 ──────────────────────────────────────


@mcp.tool()
async def list_divisions(ctx: Context) -> dict[str, Any]:
    """사업부 목록. 신뢰성 시험의 **소속 단위**.

    줄마다 `code`(`mx`·`vd`…. 코드가 키라 이름이 바뀌어도 유지) · `name` · `can_register`(토큰
    소유자의 등록 가능 여부) 포함.

    **등록 전 호출 필수.** `can_register`가 false인 사업부에 `create_reliability_test`를
    호출하면 403. 이 403은 범위 부족으로 오해되어 토큰을 재발급하게 되지만, 실제 원인은 그
    사람의 부서가 그 사업부 소속이 아닌 것.
    """
    return _listed(await _get(ctx, "/reliability-tests/divisions"), "divisions")


@mcp.tool()
async def list_reliability_tests(
    ctx: Context,
    division: str | None = None,
    attr: list[str] | None = None,
    status: str | None = None,
    revision: str | None = None,
    include_superseded: bool = False,
    name: str | None = None,
    purpose: str | None = None,
    test_item: str | None = None,
    equipment: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """**사업부**가 수행하는 신뢰성 시험 목록(고온고습 1000h · 열충격 500 cycle …).

    시험 항목(장비가 하는 측정: 인장·경도)과 다른 층: 신뢰성 시험 하나가 시험 항목 하나 이상을
    쓰고, 그 항목이 장비로 이어짐. `division`에 사업부 코드(`mx`·`vd`…, `list_divisions`)를
    주면 그 사업부만, 생략하면 전사.

    부서(팀)가 아니라 사업부 단위. 줄마다 적용 시험 항목과 그 항목이 가능한 그 사업부 장비 수
    포함. 0이면 시험은 정했으나 돌릴 장비가 그 사업부에 없음.

    `attr`은 속성 값 조건: 왼쪽은 `list_attribute_definitions`의 `key`(`["temp_x>=100"]`). 여러
    개면 모두 만족. `key*`는 기재되어 있기만 하면, `key!*`는 미기재. 조건 미기재 시험은 장비
    판정에서 빠지므로 채울 곳 찾기에 사용(`!=`는 *기재되어 있으나* 다른 값이라 다름).

    조건 묶음 지정은 `key@묶음`(`["temp_x@주>=80"]`). 생략하면 묶음 구분 없이 한 줄이라도
    닿으면 걸림: 주 조건 70 °C·불량 시 90 °C인 시험이 `temp_x>=80`에 걸림. 주 조건이 80
    이상인지 물을 때만 `@` 사용.

    속성 외 칸 필터: `name`·`purpose`(포함 글자), `test_item`(시험 항목 이름). 셋 중 둘은
    `"none"`으로 미기재를 조회: `purpose="none"`은 목적이 빈 줄, `test_item="none"`은 시험
    항목이 하나도 없는 줄. `equipment="none"`은 그 사업부에 돌릴 장비가 한 대도 없는 줄.
    미지정과 다름: 앞은 항목은 이었으나 가능한 장비가 없는 것, 뒤는 항목 미연결.

    기본은 최신판만. 판마다 줄이 서므로(개정 14의 열충격과 18의 열충격은 별도 줄) 구분하지
    않으면 목록이 판 수만큼 늘어남. 지난 판 포함은 `include_superseded=True`, 특정 판만은
    `revision`.

    페이지 단위 반환: `count`는 조건에 맞는 전체 수, `shown`은 이번에 받은 줄 수. 한 사업부에
    1784건이 있으므로 **전부 받아 세지 말고 `count` 사용.**

    조건을 걸었는데 0건이면 `diagnosis` 동봉: 조건별 값 기재 수 · 단위 변환 실패 수 · 그 조건
    하나로 걸리는 수와 요약 한 줄. 그런 시험 없음으로 뭉개지 말고 그 줄을 그대로 전달. 가장
    흔한 실제 원인은 아무도 기재하지 않음.

    줄마다 `status`: `candidate`(후보) · `confirmed`(확정). **후보는 AI가 올리고 사람이 아직
    확인하지 않은 것**: 이를 근거로 이 부서가 이 시험을 수행한다고 말하기 금지. `status` 생략
    시 전사는 확정만, 사업부 지정 시 후보 포함. 전사로 후보까지 보려면 `status="all"` 한 번
    (사업부마다 반복 호출 불필요).
    """
    got = await _get(
        ctx,
        "/reliability-tests",
        {
            "division": division,
            "attr": attr,
            "status": status,
            "revision": revision,
            "include_superseded": include_superseded or None,
            "name": name,
            "purpose": purpose,
            "test_item": test_item,
            "equipment": equipment,
            "limit": limit,
            "offset": offset,
        },
    )
    # 서버는 쪽으로 준다(`items`·`total`). **도구의 모양은 그대로 둔다** — 부르는 쪽이
    # 읽던 `tests`·`count` 가 바뀌면, 그 글을 읽고 짜인 대화가 전부 어긋난다.
    if isinstance(got, dict) and "items" in got:
        found = {
            "tests": got["items"],
            "count": got.get("total", len(got["items"])),
            "shown": len(got["items"]),
            "offset": got.get("offset", 0),
        }
    else:
        found = _listed(got, "tests")
    if division is None and status is None and found.get("count") == 0:
        # 전사는 확정만 준다. 확정이 0이면 AI 는 사업부마다 다시 불러 후보를 찾는다(측정
        # 2026-10-04: q13 18회 · q15 21회). 후보 수를 세어 한 번에 보는 길을 알려 준다.
        waiting = await _get(
            ctx,
            "/reliability-tests",
            {"status": "candidate", "attr": attr, "name": name, "limit": 1},
        )
        pending = waiting.get("total", 0) if isinstance(waiting, dict) else 0
        if pending:
            found["next"] = (
                f"전사 확정 0건. 확인 전 후보 {pending}건 있음: 같은 조건에 `status=\"all\"`로"
                " 한 번 조회(사업부별 반복 호출 불필요). 후보는 확정이 아님."
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
    """신뢰성 시험 하나: 목적 · 적용 시험 항목 · 속성 값 전체.

    속성의 `status`가 `draft`면 **초안**: 표시와 수집만 하고 검색·판정·색인 카드에는 미포함.
    초안 값을 근거로 이 조건으로 검색된다고 말하기 금지.
    """
    return await _get(ctx, f"/reliability-tests/{test_id}")


@writes
async def create_upload_ticket(ctx: Context, local_path: str | None = None) -> dict[str, Any]:
    """**PC 파일을 서버로 직접 업로드**하는 준비물: 5분 유효 티켓과 그대로 실행할 `curl`.

    **파일 바이트는 AI를 거치지 않음.** 50 MB 규격서를 base64로 나르면 대화가 그것으로 가득
    차므로 파일은 셸에서 직접 전송. 실제 토큰을 셸에 적지 않는 이유도 동일(오래 유효한 자격이며
    기록에 남음). 티켓은 5분 유효, 업로드 외 기능 없음.

    반환된 `curl`의 `<대상>` 자리를 채워 실행하면 `{id, …}` 출력. 그 id가 첨부 id이며,
    워드·파워포인트면 `extract_document_images`에 전달.

    `target`은 `spec_document` · `reliability_test` · `method` · `equipment`. 장비에는 그
    장비의 사양서·매뉴얼·성적서를 첨부: 첨부 후 읽은 내용을 요약해 `set_equipment_attributes`의
    장비 자료 발췌 칸에 적으면 의미 검색이 그 글까지 읽음.

    사람에게는 명령을 그대로 보여 주고 실행 요청. 셸을 가진 환경이면 직접 실행 가능.
    """
    got = await _send(ctx, "POST", "/attachments/upload-ticket", {})
    if isinstance(got, dict) and got.get("error"):
        return got
    ticket = got.get("ticket", "")
    url = f"{API_BASE}/attachments/upload-with-ticket"
    where = local_path or "<로컬 파일 경로>"
    # **자리를 비워 둔다.** `spec_document` 를 박아 두면 장비에 붙이려던 사람이 그대로
    # 실행하고, 그 파일은 엉뚱한 규격서에 붙는다 — 되돌리려면 지우고 다시 올려야 한다.
    query = (
        "?target=<spec_document|reliability_test|method|equipment>&object_id=<대상 id>"
        f"&filename={quote(Path(where).name, safe='')}"
    )
    return {
        "ticket": ticket,
        "expires_in_seconds": got.get("expires_in_seconds", 300),
        "curl": (
            f"curl -sS -X POST '{url}{query}' "
            f"-H 'X-Upload-Ticket: {ticket}' --data-binary @{shlex.quote(where)}"
        ),
        "next": (
            "셸에서 이 명령을 실행하면 첨부 id 출력. 워드·파워포인트면"
            " extract_document_images로 그림을 낱장 추출."
        ),
    }


@writes
async def extract_document_images(ctx: Context, attachment_id: str) -> dict[str, Any]:
    """업로드한 **워드·파워포인트에서 그림을 낱장으로** 추출(서버가 zip으로 해제).

    규격서 한 벌에 그림 서른 장이 흔함. 문서를 통째로 올린 뒤 호출하면 낱장 첨부가 되어 문서와
    같은 위치에 생성. 바이트는 서버 안에서만 이동.

    줄마다 `caption` 포함: 문서에서 그 그림 위치의 제목과 글(예: 3.2 열충격, 온습도 프로파일).
    **AI는 그림을 볼 수 없으므로 이 글자가 유일한 단서.** 이것으로 어느 시험의 그림인지 정하고
    `attach_references`로 한 번에 연결.

    같은 그림이 여러 쪽에 나오면(머리글 로고) 한 번만 추출. 추출 실패분은 `skipped_*`로 집계해
    전달(누락이 조용하면 사람이 알아채지 못함).
    """
    return await _send(ctx, "POST", f"/attachments/{attachment_id}/extract-images", {})


@writes
async def attach_references(
    ctx: Context, items: list[dict[str, Any]], dry_run: bool = True
) -> dict[str, Any]:
    """업로드된 그림 여러 장을 **한 번에 대상에 연결.** 바이트 이동 없음.

    규격서 한 벌에서 나온 그림 서른 장을 시험 서른 건에 나눠 연결하는 용도(한 장씩 호출하면
    서른 번이고 중간에 끊기면 진행 위치 파악이 어려움). 줄 하나가 한 장:

        {"attachment_id": "…", "target": "reliability_test", "object_id": "…",
         "definition_id": "…(어느 칸에. 없으면 카드 전체)", "caption": "…(없으면 원본 것)"}

    **기본은 미리보기**(`dry_run=true`): 판정만 하고 연결하지 않음. 사람에게 표를 보여 확인받은
    뒤 같은 내용을 `dry_run=false`로 재전송(서른 장을 잘못 건 뒤 되돌리는 것보다 비용이 적음).

    판정은 줄마다 별도: 한 줄이 막혀도 나머지는 연결되고, 실패한 줄은 이유와 함께 반환. 연결
    실행은 전부 성공 또는 전부 실패.

    어느 그림이 어느 시험의 것인지는 `extract_document_images`가 준 `caption`으로 판단(AI는
    그림을 볼 수 없음). 설명이 빈 그림은 짐작으로 연결하지 말고 사람에게 확인.
    """
    return await _send(
        ctx,
        "POST",
        "/attachments/attach-batch",
        {"items": items},
        {"dry_run": "true" if dry_run else "false"},
    )


@mcp.tool()
async def list_spec_documents(
    ctx: Context, workspace: str | None = None, q: str | None = None
) -> dict[str, Any]:
    """**사내 규격서** 목록: 부서가 만든 시험 문서(예: MX-REL-012 환경 시험 표준).

    공개 규격(`list_methods`, ASTM·ISO·KS 601건)과 별개의 표. 공개 규격은 외부에서 만들어
    전사가 인용하는 것, 사내 규격서는 부서가 만들고 고치며 외부에서는 존재를 모름(섞어 세면
    인용 중인 공개 규격 집계가 틀어짐).

    줄마다 `code`(문서 번호, 사람이 쓰는 이름) · `title` · `revision`(판) · `file_count`(첨부
    원본 수) · `linked_test_count`(이 문서를 가리키는 신뢰성 시험 수) 포함. `file_count`가
    0이면 번호만 있고 원본 없음.

    판은 줄을 나누지 않음. 개정 시 `revision`을 고치고 파일을 추가하므로, Rev.2 신규 생성이
    아니라 그 문서의 판 상향과 파일 추가가 맞는 답.

    **id는 `resolve(kind="spec_document", text="MX-REL-012", workspace=…)`로 확정**: 부서 간에
    번호가 겹칠 수 있어 첫 줄을 집으면 남의 부서 문서를 시험에 연결하게 됨. 그 id가 신뢰성
    시험의 규격서 칸(`document_id`)과 첨부 목록(`list_attachments(target="spec_document")`)에
    그대로 사용됨.

    **원문 읽기 불가**(첨부는 파일 이름과 설명까지만 제공). 한글·워드 파일이 많고 첨부 사실과
    이름까지만 알 수 있음: 안의 조건을 말하면 지어내는 것.
    """
    return _listed(
        await _get(ctx, "/spec-documents", {"workspace": workspace, "q": q}),
        "documents",
    )



@writes
async def create_spec_document(
    ctx: Context,
    workspace_slug: str,
    title: str,
    code: str | None = None,
    revision: str | None = None,
    pages: str | None = None,
    is_excerpt: bool = False,
    source_path: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """사내 규격서 하나 등록: **시험의 출처가 될 문서.**

    **먼저 `resolve(kind="spec_document", text=code, workspace=…)`로 존재 여부 확인.** 같은
    부서에 같은 번호는 하나뿐이며 이미 있으면 그것을 사용(번호만 달리 적어 둘을 만들면 어느
    쪽이 정본인지 알 수 없게 됨).

    이 줄에는 AI가 올렸다는 표시가 남음(`submitted_via`). 사람이 등록한 것과 구별되어야
    검토자가 더 볼 곳을 앎: **문서에 적힌 그대로** 입력. 번호·제목을 다듬거나 지어내면 표시가
    있어도 소용없음.

    생성 후 원본 파일 첨부: `create_upload_ticket` → 티켓으로 업로드 →
    `attach_references(target="spec_document", …)`. 파일 없는 규격서는 번호만 있는 껍데기라
    값이 틀렸을 때 추적 근거가 못 됨.

    이어서 그 문서를 시험의 규격서 칸(`document_id`)에 연결(시험에서 원본으로 바로 이동 가능).

    번호가 없으면 비움. 번호 없는 사내 문서가 실제로 있음(지어낸 번호는 문서관리 시스템 번호로
    오인되어 누군가 찾으러 감). 대신 `pages`(참조 쪽, 예: 12-18), `is_excerpt`(전문 미확인 시
    참), `source_path`(원본의 사내 경로·URL)를 채움. 이 셋을 비고 문장에 섞으면 검색도 추적도
    불가.
    """
    return _then(
        await _send(
            ctx,
            "POST",
            "/spec-documents",
            {
                "workspace_slug": workspace_slug,
                "code": code,
                "title": title,
                "revision": revision,
                "pages": pages,
                "is_excerpt": is_excerpt,
                "source_path": source_path,
                "note": note,
            },
        ),
        "규격서 등록 완료. 다음: 원본 파일 첨부, 시험의 규격서 칸(`document_id`)에 연결.",
    )

@mcp.tool()
async def list_attachments(ctx: Context, target: str, object_id: str) -> dict[str, Any]:
    """붙은 **그림과 첨부** 목록: 무엇이 어느 칸에 붙어 있는지.

    `target`은 `reliability_test` · `method` · `spec_document` · `equipment` 넷. 줄마다
    `caption` · `definition_label`(붙은 칸, 비면 카드 전체) · 형식 · 크기 포함.

    원문이 붙는 곳은 둘이며 서로 다른 표. `method`는 공개 규격(ASTM·ISO·KS)의 원문,
    `spec_document`는 사내 규격서(`list_spec_documents`). 신뢰성 시험의 문서를 찾으려면 그
    시험의 참조 규격 칸이 가리키는 `method_id`, 또는 규격서 칸이 가리키는 `document_id`로 호출.

    **AI는 그림을 볼 수 없음.** 읽을 수 있는 것은 `caption`뿐: 설명이 비어 있으면 없는 것과
    같으므로 그림 3장이 있고 설명은 없다고 그대로 전달하고 내용 짐작 금지. 시편 장착 방향이라고
    적힌 그림을 보고 방향을 말하는 것도 짐작(적힌 글자까지만 전달).

    **PDF 본문도 읽기 불가.** 규격서 첨부 사실과 파일 이름·설명까지만 알 수 있음: ASTM E8
    원문이 있다는 말은 가능하나 그 안의 요구 조건을 말하면 지어내는 것.

    업로드한 파일을 서버에서 되받아 읽는 방법은 없음. 장비 자료를 요약해
    `set_equipment_attributes`의 장비 자료 발췌 칸에 적으려면 업로드 전에 가진 파일을 읽어야
    함(업로드 후 서버에 물으면 파일 이름만 받음).

    사람에게 보이려면 화면에서 그 시험이나 규격을 열도록 안내. 파일 주소(`url`)는 자격이 있어야
    열리므로 그대로 건네도 브라우저에서 열리지 않음.
    """
    return _listed(
        await _get(ctx, "/attachments", {"target": target, "object_id": object_id}),
        "attachments",
    )


@writes
async def create_reliability_test(
    ctx: Context,
    division_code: str,
    name: str,
    purpose: str = "",
    document_revision_id: str | None = None,
    test_item_term_ids: list[str] | None = None,
    attributes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """신뢰성 시험 하나를 **후보로** 등록. 그 사업부 소속 부서 관리자(또는 시스템 관리자) 전용.

    사업부 코드는 `list_divisions`가 제공(`can_register`가 true인 것만 가능).

    **AI가 올린 시험은 바로 쓰이지 않음.** 값 하나가 틀리면 그 조건으로 장비를 고르고 보고서가
    나가므로, 사람이 화면에서 읽고 확인해야 확정. 그 전에는 전사 목록에도 미표시. 사용자에게
    등록 완료가 아니라 후보 등록, 확인 필요로 전달.

    **모르는 칸은 비우고 못 채운 칸을 알림.** 그럴듯하게 채우면 검토자가 가려내지 못함(빈 칸은
    눈에 띄지만 그럴듯한 오답은 안 띔).

    먼저 `resolve(kind="reliability_test", text=…, workspace=…)`로 같은 시험의 존재 여부 확인.
    부서마다 같은 이름이 있는 표라, 확인 없이 만들면 한 부서에 고온고습 1000h가 둘이 되고
    정본을 알 수 없게 됨.

    `test_item_term_ids`는 이 시험이 쓰는 시험 항목의 값 id(`resolve(kind="term",
    axis="test_item", text=…)`). 모르면 비움: 비슷한 항목을 넣으면 엉뚱한 장비로 이어지고
    검색이 그 장비로 가능이라 답함.

    같은 시험의 다른 판이면 호출 금지(여기서는 409). 판 적재는
    `create_reliability_tests`(묶음)가 처리.

    `attributes`는 칸 하나가 한 줄이며 칸 종류마다 채우는 자리가 다름: 형태와 id 조회 방법은
    `get_guide("신뢰성 시험")`의 표. 종류와 다른 값은 조용히 버려짐: 먼저
    `list_attribute_definitions`로 `kind` 확인.

    새 이름 생성 전 정의 목록 확인. `new_label`로 적으면 초안이 생기고, 초안은 온톨로지 밖이라
    검색·판정에 미사용.

    조건 속성(`kind="condition"`)은 그대로 장비 판정에 사용: -40~125 degC로 적으면
    `test_capability`가 그 온도를 내는 장비만 답함. 조건은 문장이 아니라 수치. 폭이 없는 한
    점은 `num_value`. 점 넷을 -40 ~ 85 구간으로 뭉치기 금지(사이 아무 온도나 된다는 뜻이 되며
    문서에 없는 말).

    조건이 한 벌이 아니면 묶음으로 구분(`set_label`·`step_order`). 동작 -15 ~ 45와 저장 -40 ~
    25를 뭉치면 -40 ~ 45라는 문서에 없는 조건이 생김. 주 조건과 예외, 프로파일 순서도 같은
    방식(형태는 가이드의 조건 묶음 대목).

    확실하지 않으면 비우고 `note` 기재. 메모 없이 비우면 없음으로, 메모와 함께 비우면 아직
    모름으로 읽힘.
    """
    return _then(
        await _send(
            ctx,
            "POST",
            "/reliability-tests",
            {
                "division_code": division_code,
                "name": name,
                "purpose": purpose,
                "document_revision_id": document_revision_id,
                "test_item_term_ids": test_item_term_ids or [],
                "attributes": attributes or [],
            },
        ),
        "후보로 등록됨. 사람이 부서 화면에서 확인해야 확정이며 그 전에는 전사 목록에 미표시."
        " 등록 완료가 아니라 후보 등록 후 확인 필요로 안내하고, 못 채운 칸이 있으면 함께"
        " 알림. 확인은 AI 불가(사람이 화면에서 수행).",
    )


@writes
async def create_reliability_tests(
    ctx: Context,
    division_code: str,
    tests: list[dict[str, Any]],
    document_id: str | None = None,
    document_revision_id: str | None = None,
) -> dict[str, Any]:
    """**문서 하나에서 추출한 신뢰성 시험 여러 건 일괄 등록.** 줄마다 결과 반환.

    규격서 한 권에서 스무 건을 뽑았으면 `create_reliability_test`를 스무 번 호출하지 말고 이
    도구를 한 번 호출. 스무 번 호출 중 열 번째에서 끊기면 앞의 아홉은 들어가고 뒤의 열은 없는
    상태가 되고, 재호출 시 아홉이 이름 중복으로 막혀 사람이 등록 실패로 오해함.

    `tests`의 한 줄: `{"name": …, "purpose": …, "test_item_term_ids": [...], "attributes":
    [...]}`. `create_reliability_test`와 같은 칸이며 `division_code`만 묶음 단위. 한 번에 최대
    500건.

    `document_id` 지정(`resolve(kind="spec_document", text="MX-REL-012", workspace=…)`). 줄마다
    규격서 칸에 연결되어 사람이 문서 단위로 검토 가능(한 문서에서 나온 줄은 같은 실수를
    공유하므로 함께 봐야 드러남). 줄의 `attributes`에 규격서가 이미 있으면 덮지 않음.

    **규격서를 주면 `document_revision_id`도 필수**(없으면 400). 판마다 줄이 생기므로 개정 14를
    올린 뒤 18을 올릴 때는 이 칸만 바꿔 같은 이름으로 재전송: 18은 14의 줄에 붙지 않고 새 줄로
    생성(14의 값은 그 줄에 유지). 목록은 최신판만 보여 줘 줄이 늘어나지 않음. 판 목록은
    `list_spec_documents`의 `revisions`.

    판 없이 올리면 같은 자리에 쌓여 뒤의 값이 앞의 값을 조용히 덮음(운영에서 36건 값 소실,
    2026-10-01).

    응답 세 가지: `created`(새 줄), `merged`(같은 판 재업로드), `failed`(막힌 줄과 이유). **셋
    모두 읽고 전달.** `merged` 줄의 `action`: `updated`면 `changed`에 덮어쓴 칸 이름(그 칸의 옛
    값은 이 판에서 소실), `skipped`면 변경 없음. 등록 완료만 말하지 말고 덮어쓴 칸을 그대로
    전달.
    """
    return _then(
        await _send(
            ctx,
            "POST",
            "/reliability-tests/batch",
            {
                "division_code": division_code,
                "document_id": document_id,
                "document_revision_id": document_revision_id,
                "tests": tests,
            },
        ),
        "줄별 결과 반환됨. **`created`·`merged`·`failed` 모두 전달 필수**(등록된 줄만"
        " 말하면 병합·실패 줄이 누락됨). `merged`는 같은 판 재업로드이며 줄의 `changed`에"
        " 덮어쓴 칸 기재: 그 칸의 옛 값은 소실되었으므로 그대로 전달. 새 줄은 후보이며"
        " 사람이 화면에서 문서 단위로 확인해야 확정.",
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
    """신뢰성 시험 수정. **보내지 않은 칸은 유지.**

    **확정된 시험은 수정 불가**(409 `TSC-RELIABILITY-0005`). 사람이 내용을 확인한 것이라
    수정하려면 확인부터 해제해야 함: 사용자에게 화면의 다시 후보로 버튼을 눌러 달라고 요청.
    AI가 해제하는 방법은 없음. 수정 가능한 것은 후보 상태 시험.

    `test_id`는 `resolve(kind="reliability_test", …)`로 확정(이름만 보고 고르면 같은 이름의
    다른 부서 시험을 수정하게 됨).

    `test_item_term_ids`와 `attributes`는 보내면 전체 교체: 하나를 더하려면 현재
    값(`get_reliability_test`)에 더해 전부 전송(누락분은 조용히 삭제).

    칸 몇 개만 고칠 때는 `set_reliability_attributes` 사용. 그 도구는 현재 값을 읽어 겹치는
    줄만 교체(스물두 칸을 다시 적다 하나를 빠뜨리는 사고가 실제로 발생).
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


@writes
async def set_reliability_attributes(
    ctx: Context, test_id: str, attributes: list[dict[str, Any]]
) -> dict[str, Any]:
    """신뢰성 시험의 **칸 몇 개만** 수정. 나머지는 유지.

    `update_reliability_test(attributes=…)`는 목록을 전체 교체. 카드에 칸이 스물 넘게 있어 온도
    하나를 고치려 스물둘을 다시 보내다 하나를 빠뜨리면 그 값은 조용히 사라짐(아무도 못 찾음).
    이 도구는 현재 값을 읽어 `definition_id`가 같은 줄만 교체하고 나머지는 그대로 전송.

    줄 형태는 `create_reliability_test`와
    동일(구간·수치·문장·불리언·날짜·term·method·document·pairs·matrix). 없던 칸이면 새로 추가,
    `new_label`로 주면 초안 생성.

    **묶음이 있으면 `set_label`·`step_order`까지 같아야 같은 줄.** 동작과 저장은 같은 시험 온도
    두 줄이라, 묶음 없이 보내면 그 둘이 아니라 세 번째 줄이 생김. 먼저 읽어 현재 묶음을
    확인하고 고칠 줄의 묶음을 그대로 포함.

    삭제는 명시적으로: `{"definition_id": "…", "remove": true}`. 빈 값 전송으로는 삭제되지
    않음(빈 문자열과 미기재는 다름). 묶음이 있는 줄은 묶음까지 같아야 삭제됨.

    확정된 시험은 수정 불가(409): 사람이 화면에서 다시 후보로 버튼을 눌러야 함. 여러 건은
    목록에서 체크해 한 번에 해제 가능(사유 기재). 막힌 줄이 여럿이면 하나씩이 아니라 건수를
    세어 일괄 해제 요청.
    """
    now = await _get(ctx, f"/reliability-tests/{test_id}")
    if isinstance(now, dict) and now.get("error"):
        # 못 읽었으면 **보내지 않는다** — 빈 목록으로 덮으면 스물둘이 한 번에 사라진다.
        return now

    return _then(
        await _send(
            ctx,
            "PATCH",
            f"/reliability-tests/{test_id}",
            {"attributes": merge(now.get("attributes", []), attributes)},
        ),
        "보낸 칸만 변경, 나머지는 유지. 고친 칸이 조건(`kind=\"condition\"`)이면"
        " 장비 판정도 바뀜: `test_capability`로 재확인 후 전달.",
    )


@writes
async def set_equipment_attributes(
    ctx: Context, equipment_id: str, attributes: list[dict[str, Any]]
) -> dict[str, Any]:
    """보유 장비의 **칸 몇 개만** 수정. 나머지는 유지.

    `update_equipment`에는 속성 칸이 없고, 장비 `attributes`를 통째로 보내면 보내지 않은 칸이
    조용히 사라짐. 이 도구는 현재 값을 읽어 `definition_id`가 같은 줄만 교체. 줄 형태는 신뢰성
    시험과 동일(`set_reliability_attributes`).

    ## 장비 자료 발췌(`equipment_document_digest`)

    **AI가 채우는 칸.** 장비에 첨부된 사양서·매뉴얼에서 읽은 내용을 요약해 적으면 의미 검색의
    장비 카드에 함께 임베딩됨: 얇은 판 잡아당기는 장비처럼 낱말이 겹치지 않는 질문으로도 그
    장비가 검색됨.

    원문 통째 입력 금지(카드가 길수록 조각이 늘고 조각마다 뜻이 흐려져 오히려 덜 검색됨). 측정
    대상·범위·딸린 부속을 몇 문장으로 기재. 지어내기 금지(자료에 없는 수치를 적으면 그 수치로
    검색이 답함).

    자료를 먼저 첨부하려면 `create_upload_ticket`으로 `target=equipment`에 업로드.

    삭제는 `{"definition_id": "…", "remove": true}`. 빈 값으로는 삭제되지 않음.
    """
    now = await _get(ctx, f"/equipment/{equipment_id}")
    if isinstance(now, dict) and now.get("error"):
        # 못 읽었으면 **보내지 않는다** — 빈 목록으로 덮으면 있던 칸이 한 번에 사라진다.
        return now

    return await _send(
        ctx,
        "PATCH",
        f"/equipment/{equipment_id}",
        {"attributes": merge(now.get("attributes", []), attributes)},
    )


@writes
async def propose_test_item(
    ctx: Context, test_id: str, text: str, note: str | None = None
) -> dict[str, Any]:
    """시험 항목 축에 **맞는 값이 없음**을 요청으로 기록.

    시험 항목 축은 닫혀 있어 AI가 값을 추가할 수 없음(검색의 첫 축이라 오타 하나가 값이 되면
    이후 아무도 못 찾음). 요청 없이 비우면 빈 칸이 해당 없음으로 읽힘.

    `text`는 **문서에 적힌 그대로**(예: 염수분무(5%)). 고쳐 쓰거나 비슷한 축 값으로 바꾸지
    않음(판단자가 원문을 봐야 결정 가능). `note`에는 못 찾은 이유 기재(예: 염수 분무는 있으나
    농도별 구분이 없음).

    같은 표기가 여러 시험에서 나오면 한 줄로 모임. 관리자가 한 번 정하면 그 표기를 낸 시험
    전부에 연결되므로, 스무 건이면 스무 번 호출이 맞음.

    **비슷한 값으로 대체 금지.** 인장이 없다고 굽힘을 넣으면 그 시험이 엉뚱한 장비로 이어지고
    검색이 그 장비로 가능이라 답함.
    """
    return _then(
        await _send(
            ctx,
            "POST",
            "/reliability-tests/item-proposals",
            {"reliability_test_id": test_id, "text": text, "note": note},
        ),
        "요청 등록됨. **시험 항목은 아직 미연결**(관리자 결정 후 연결). 사용자에게 시험"
        " 항목을 못 찾아 요청으로 남겼다고 그대로 전달.",
    )


@mcp.tool()
async def list_test_item_requests(
    ctx: Context, include_decided: bool = False
) -> dict[str, Any]:
    """시험 항목 축에 없다고 올라온 요청 목록. 같은 표기끼리 묶음, 건수가 큰 순서.

    묶음마다 `normalized`(정할 때 쓰는 열쇠) · `text` · `count` · `proposals`(요청한 시험과
    원문) 포함. 결정은 `decide_test_item_request`(시스템 관리자).
    """
    return _listed(
        await _get(
            ctx,
            "/reliability-tests/item-proposals",
            params={"include_decided": "true" if include_decided else "false"},
        ),
        "groups",
    )


@writes
async def decide_test_item_request(
    ctx: Context,
    normalized: str,
    term_id: str | None = None,
    new_value: str | None = None,
    reject: bool = False,
) -> dict[str, Any]:
    """시험 항목 요청 한 묶음의 결정. 연결 · 신규 등록 · 거절 중 하나만. 시스템 관리자 전용.

    `term_id`(기존 시험 항목에 연결, `resolve(kind="term", axis="test_item")`로 확인) ·
    `new_value`(시험 항목 축에 새 값 등록) · `reject=True`(시험 항목 아님). 셋 다 없으면 400.
    결정 결과는 그 표기를 요청한 신뢰성 시험 전부에 일괄 적용.

    **결정 전 사용자 확인 필수.** 시험 항목은 검색의 첫 축이라 값이 갈리면 이후 검색 누락.
    비슷한 값이 있으면 신규 등록 대신 연결. `reject`는 사용자가 거절을 지시한 경우만.
    """
    return await _send(
        ctx,
        "POST",
        "/reliability-tests/item-proposals/decide",
        {
            "normalized": normalized,
            "term_id": term_id,
            "new_value": new_value,
            "reject": reject,
        },
    )


@writes
async def propose_equipment_model(
    ctx: Context,
    equipment_id: str,
    model_text: str,
    maker_text: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """카탈로그에 **그 기종이 없음**을 요청으로 기록.

    카탈로그 기종은 시스템 관리자만 등록(기종을 고르면 그 계열의 시험 항목이 장비로 복사되고
    조건 판정이 그 기종 사양을 씀). AI가 만든 기종은 잘못된 답의 근거가 되고 그 오답은 드러나지
    않음. 요청 없이 비우면 빈 칸이 아직 안 채운 것으로 읽힘(할 일이 다름).

    `model_text`는 **라벨에 적힌 그대로**(`68FM-300`). 고쳐 쓰거나 비슷한 기종 이름으로 바꾸지
    않음(판단자가 그 글자를 봐야 계열 결정 가능). `maker_text`에 제조사, `note`에 못 찾은 이유
    기재(예: 6800 시리즈는 있으나 이 모델만 없음).

    `register_equipment`로 등록한 뒤 호출(요청은 그 장비에 연결).

    같은 기종을 여러 장비가 요청하면 한 줄로 모임. 관리자가 한 번 정하면 요청한 장비 전부가
    연결되므로 열 대면 열 번 호출이 맞음. 같은 장비의 같은 요청 중복도 허용.

    **비슷한 기종으로 대체 금지.** 카탈로그의 다른 기종을 고르면 그 장비의 하중·온도가 남의
    것이 되고 조건 검색 화면이 그 수치로 가능이라 답함.
    """
    return _then(
        await _send(
            ctx,
            "POST",
            f"/equipment/{equipment_id}/model-proposals",
            {"model_text": model_text, "maker_text": maker_text, "note": note},
        ),
        "요청 등록됨. **기종은 아직 미연결**(관리자가 카탈로그에 등록해야 연결). 사용자에게"
        " 카탈로그에서 기종을 못 찾아 등록 요청으로 남겼다고 그대로 전달.",
    )


@writes
async def add_spec_document_revision(
    ctx: Context,
    document_id: str,
    label: str,
    issued_on: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    """규격서에 **개정 한 줄** 추가.

    `revision` 글자 하나로는 개정 18에서 신설 같은 사실을 기록할 수 없음. 개정을 줄로 쌓아야
    시험이 들어온 판과 사람이 확인한 판을 가리킬 수 있음.

    `label`은 문서 표기 그대로(예: 18, Rev.3, 2024-05).

    **`summary` 비우기 금지.** 변경 내용이 재검토 범위를 결정: 오타 수정이면 딸린 시험 재검토
    불필요, 시험 온도 상향이면 전부 재검토. 판단은 사람이 하며, 줄에 설명이 없으면 판단 근거가
    없음.

    개정을 추가해도 딸린 시험은 확정 상태 유지(수십 건이 한꺼번에 후보로 내려가면 업무가 멈춤).
    대신 이 개정 미확인 표시가 붙음. **표시 해제는 사람 전용**(AI 불가).
    """
    return _then(
        await _send(
            ctx,
            "POST",
            f"/spec-documents/{document_id}/revisions",
            {"label": label, "issued_on": issued_on, "summary": summary},
        ),
        "개정 추가됨. 딸린 시험은 확정 상태 유지, 이 개정 미확인 표시가 붙음(해제는 사람이"
        " 화면에서 수행). 해당 시험 건수를 함께 전달.",
    )


@mcp.tool()
async def compare_revisions(ctx: Context, before: str, after: str) -> dict[str, Any]:
    """같은 규격서의 **두 판 비교**: 추가된 시험 · 없어진 시험 · 조건이 바뀐 시험.

    개정 시 딸린 수십 건 중 재검토 대상 선별 용도(전부 재검토는 업무를 멈추고, 아무것도 안 보면
    바뀐 조건을 놓침).

    `changed[].differences`가 변경 위치와 내용을 한 줄로 제공(85 degC 이상 -> 95 degC 이상).
    **그대로 전달**: N건 바뀜으로 요약하면 사람이 다시 열어 봐야 함.

    `unchanged_count`가 크면 개정 범위가 좁다는 뜻이며 그 사실도 함께 전달.

    시험은 한 줄이고 판은 값에 붙으므로 이 비교는 한 줄 안의 두 시점 비교: `changed`의
    `before_id`와 `after_id`는 같은 시험. 추가됨은 뒤 판에서 처음 값이 기재된 시험, 없어짐은 앞
    판에는 있었으나 뒤 판이 손대지 않은 시험(삭제 아님).

    판 id는 `list_spec_documents`의 `revisions`가 제공. 다른 문서의 판끼리는 비교 불가.
    """
    return await _get(
        ctx, "/reliability-tests/revision-compare", {"before": before, "after": after}
    )


@mcp.tool()
async def test_capability(ctx: Context, test_id: str) -> dict[str, Any]:
    """**이 시험을 수행할 수 있는 장비** 조회. 이 시스템이 답하는 물음의 마지막 단계.

    `test_id`는 `resolve(kind="reliability_test", …)`가 준 값 사용.

    이 시험의 조건 속성이 그대로 검색 조건이 되어(범위 하나는 상한·하한 두 물음) 시험 항목마다
    장비를 판정. 부서로 좁히지 않음(옆 부서 장비도 대여 가능).

    읽는 법:

    * `conditions_asked`: 실제로 물은 조건 수. 0이면 조건 속성이 없어 시험 항목만으로 판정한
      것. 이때의 가능은 온도·하중을 보지 않은 답이므로 그 사실을 전달.
    * `skipped`: 단위 변환 실패로 제외한 조건과 이유. 있으면 조건을 다 본 것이 아님.
    * `unmet_count`: 조건 미달로 빠진 장비 수. 0대의 원인이 항목 가능 장비 없음인지 조건
      미달인지 구분.
    * 줄의 `verdict`: `match` 전부 충족 · `accessory` 부속(챔버·노) 장착 시 가능 · `partial`
      일부 모름 · `unknown` 전부 모름. **`unknown`을 가능으로 옮기기 금지.**
    * 조건 줄의 `accessory` 칸: 장착할 부속(`model_name`), 가능 범위(`condition_range`), 보유
      여부(`owned_units`). 0이 아니면 구매 대상 아님.

    **0대면 그것이 답.** 그 시험 항목이 기재된 장비 없음(unmet_count 0) 또는 조건
    미달(unmet_count > 0)로 전달하고 종료. 챔버·항온항습 같은 다른 이름으로 장비 재검색
    금지(그런 장비는 시험 항목 미기재로 검색에 안 걸리며 기재는 사람의 몫). 구매 후보는
    `search_catalog` 한 번.
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
            "이것이 답(0대). unmet_count로 이유(항목 미기재 / 조건 미달)를 전달하고 종료."
            " 다른 이름으로 장비 재검색 금지, 구매 후보는 search_catalog 한 번."
            if total == 0
            else "이것이 답. 줄마다 부서·위치·담당자·판정 포함. 장비 재검색, 사양 재확인 금지."
        ),
    )


# ── 속성 — 열이 아니라 행으로 붙는 칸 ─────────────────────────────────────────


@mcp.tool()
async def list_attribute_definitions(
    ctx: Context, target: str, include_inactive: bool = False
) -> dict[str, Any]:
    """객체별 **기재 가능한 칸** 목록(속성 정의).

    `target`: `reliability_test` · `equipment` · `series` · `method`. 줄마다 `key`(필터 조건에
    쓰는 이름) · `label` · `kind` · `unit` · `status` · `value_count` 포함.

    `status`가 `standard`면 정식이며 검색·판정·색인 카드에 포함. `draft`는 초안: 값 입력자가 새
    이름을 써서 생긴 것으로 온톨로지 밖. **값을 적을 때는 정식부터 찾아 사용**하고 없을 때만 새
    이름 생성.

    `kind`가 `condition`이면 검색축에 이어진 조건: 그 칸에 수치를 적으면 `test_capability`가 그
    조건으로 장비를 판정.
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
    """새 속성 칸 정의. **시스템 관리자 전용, 사람이 지시했을 때만.**

    `kind`: number(수치) · range(구간) · text(문장) · boolean · date · choice(선택지) ·
    condition(검색축에 이어진 조건) · term(온톨로지 값) · method(공개 규격) · document(사내
    규격서) · pairs(이름별 수량) · matrix(사양 매트릭스). 조건은
    `condition_key_id`(`list_conditions`), 온톨로지는 `vocabulary_id`, 선택은 `choices` 필요.

    `key`는 필터 조건에 그대로 쓰이는 이름이라 영문·숫자·`_.-`만 허용. 비우면 서버가 임의
    생성(코드나 반입이 참조할 이름이면 직접 지정).

    **먼저 `list_attribute_definitions`로 확인.** 같은 뜻의 칸을 하나 더 만들면 값이 두 곳에
    쌓이고 어느 쪽이 맞는지 알 수 없게 됨. `status="standard"`로 바로 정식 생성은 사람이 그
    이름으로 확정했을 때만. 확신이 없으면 초안으로 두고 검토함의 초안 속성 정리 대기열이
    질의하게 함.
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


# ── 일반 — 전용 도구가 없는 고치기 · 지우기 · 만들기 ─────────────────────────────


async def _by_kind(
    ctx: Context,
    table: dict[str, tuple[str, str]],
    kind: str,
    ids: dict[str, str] | None,
    body: dict[str, Any] | None = None,
    *,
    preview: bool = False,
) -> dict[str, Any]:
    """`kind` 표에서 메서드·경로를 고르고 `ids` 로 경로를 채워 부른다.

    경로에 안 쓰인 `ids` 의 칸은 질의로 간다(표기 떼기의 `value`). **자격은 서버가 가른다**
    — 이 표는 길만 안다(얇은 프록시, AGENTS.md). 그래서 역할마다 다른 표를 두지 않는다:
    부서 멤버가 계열을 지우려 하면 서버의 403 이 그대로 간다.
    """
    if kind not in table:
        return {"error": f"알 수 없는 kind: {kind}", "kinds": sorted(table)}
    method, template = table[kind]
    given = {key: str(value) for key, value in (ids or {}).items() if value}
    names = re.findall(r"\{(\w+)\}", template)
    lacking = [name for name in names if name not in given]
    if lacking:
        return {"error": f"{kind}: ids 누락({', '.join(lacking)})", "needs": names}
    path = template.format(**{name: given[name] for name in names})
    params = {key: value for key, value in given.items() if key not in names} or None
    if preview:
        return {
            "preview": True,
            "will": f"{method} {path}",
            "kind": kind,
            "ids": given,
            "next": "대상을 사용자에게 제시하고 확인을 받은 뒤 confirm=True로 재호출.",
        }
    result = await _send(ctx, method, path, body, params=params)
    return result if isinstance(result, dict) else {"result": result}


@writes
async def delete_record(
    ctx: Context, kind: str, ids: dict[str, str], confirm: bool = False
) -> dict[str, Any]:
    """기록 하나의 삭제. confirm 없이 호출하면 삭제 없이 대상만 반환. 자격 판단은 서버.

    kind · ids · 자격:

        reliability_test     test_id  (확인 전 후보만. 확정 건은 기계 자격으로 삭제 불가)
        equipment            equipment_id  (그 부서 관리자)
        equipment_test_item  equipment_test_item_id  (그 부서 멤버)
        test_condition       equipment_test_item_id · limit_id  (그 부서 멤버)
        equipment_spec       equipment_id · definition_id  (장비 실측값, 그 부서 멤버)
        spec_document        document_id  (그 부서 관리자)
        attachment           attachment_id  (붙은 대상의 수정 자격)
        method · requirement method_id · requirement_id  (공개 규격은 시스템 관리자,
                             사내 시험법은 그 부서 관리자)
        이하 시스템 관리자:
        series · series_test_item · series_condition · series_relation
                             series_id · series_test_item_id · limit_id · relation_id
        model · model_spec · free_spec   model_id · definition_id · free_spec_id
        attribute_definition · spec_definition   definition_id
        spec_group           group_id
        property_link        link_id
        term_alias           term_id · value

    **삭제 전 사용자 확인 필수.** confirm 없이 호출해 대상을 받고, 사용자에게 제시해 확인을
    받은 뒤 confirm=True로 재호출. 사용 중인 정의·값은 서버가 409로 거절. 그때는 사용 중지
    (update_record) 또는 사용자에게 인계. 신뢰성 시험 확정·반려, 검토함 확정은 사람 전용.
    """
    table = {
        "reliability_test": ("DELETE", "/reliability-tests/{test_id}"),
        "equipment": ("DELETE", "/equipment/{equipment_id}"),
        "equipment_test_item": ("DELETE", "/equipment-test-items/{equipment_test_item_id}"),
        "test_condition": (
            "DELETE",
            "/equipment-test-items/{equipment_test_item_id}/limits/{limit_id}",
        ),
        "equipment_spec": ("DELETE", "/equipment/{equipment_id}/specs/{definition_id}"),
        "spec_document": ("DELETE", "/spec-documents/{document_id}"),
        "attachment": ("DELETE", "/attachments/{attachment_id}"),
        "method": ("DELETE", "/methods/{method_id}"),
        "requirement": ("DELETE", "/methods/{method_id}/requirements/{requirement_id}"),
        "series": ("DELETE", "/equipment-series/{series_id}"),
        "series_test_item": (
            "DELETE",
            "/equipment-series/{series_id}/test-items/{series_test_item_id}",
        ),
        "series_condition": (
            "DELETE",
            "/equipment-series/{series_id}/test-items/{series_test_item_id}/limits/{limit_id}",
        ),
        "series_relation": ("DELETE", "/equipment-series/{series_id}/relations/{relation_id}"),
        "model": ("DELETE", "/equipment-models/{model_id}"),
        "model_spec": ("DELETE", "/equipment-models/{model_id}/specs/{definition_id}"),
        "free_spec": ("DELETE", "/equipment-models/{model_id}/free-specs/{free_spec_id}"),
        "attribute_definition": ("DELETE", "/attribute-definitions/{definition_id}"),
        "spec_definition": ("DELETE", "/spec-definitions/{definition_id}"),
        "spec_group": ("DELETE", "/spec-groups/{group_id}"),
        "property_link": ("DELETE", "/test-item-properties/{link_id}"),
        "term_alias": ("DELETE", "/vocabularies/terms/{term_id}/aliases"),
    }
    return await _by_kind(ctx, table, kind, ids, preview=not confirm)


@writes
async def update_record(
    ctx: Context, kind: str, ids: dict[str, str], fields: dict[str, Any]
) -> dict[str, Any]:
    """기록 하나의 수정. 보낸 칸만 변경. 장비·신뢰성 시험·축·값은 전용 update_* 도구 사용.

    kind · ids · 자격:

        equipment_test_item   equipment_test_item_id  (그 부서 멤버)
        spec_document         document_id  (그 부서 관리자)
        attachment            attachment_id  (설명 등, 붙은 대상의 수정 자격)
        method                method_id  (공개 규격은 시스템 관리자,
                              사내 시험법은 그 부서 관리자)
        이하 시스템 관리자:
        series · model       series_id · model_id
        free_spec            model_id · free_spec_id
        condition_key        condition_key_id  (단위 변경 시 fields에 stored_values 필요)
        spec_definition      definition_id
        spec_group           group_id
        attribute_definition definition_id  (fields={"merge_into": "<id>"} 이면 그 정의로 병합)
        property_link        link_id

    칸 이름은 화면·API 스키마와 동일. 모르는 칸은 서버가 422로 반환하므로 추측으로 채우지
    말고 오류의 칸 목록 확인. 삭제는 delete_record, 전용 생성 도구가 없는 것은 create_record.
    """
    table = {
        "equipment_test_item": ("PATCH", "/equipment-test-items/{equipment_test_item_id}"),
        "spec_document": ("PATCH", "/spec-documents/{document_id}"),
        "attachment": ("PATCH", "/attachments/{attachment_id}"),
        "method": ("PATCH", "/methods/{method_id}"),
        "series": ("PATCH", "/equipment-series/{series_id}"),
        "model": ("PATCH", "/equipment-models/{model_id}"),
        "free_spec": ("PUT", "/equipment-models/{model_id}/free-specs/{free_spec_id}"),
        "condition_key": ("PATCH", "/condition-keys/{condition_key_id}"),
        "spec_definition": ("PATCH", "/spec-definitions/{definition_id}"),
        "spec_group": ("PATCH", "/spec-groups/{group_id}"),
        "attribute_definition": ("PATCH", "/attribute-definitions/{definition_id}"),
        "attribute_definition_merge": ("POST", "/attribute-definitions/{definition_id}/merge"),
        "property_link": ("PATCH", "/test-item-properties/{link_id}"),
    }
    if kind == "attribute_definition" and "merge_into" in fields:
        return await _by_kind(
            ctx, table, "attribute_definition_merge", ids, {"target_id": fields["merge_into"]}
        )
    return await _by_kind(ctx, table, kind, ids, fields)


@writes
async def create_record(
    ctx: Context, kind: str, fields: dict[str, Any], ids: dict[str, str] | None = None
) -> dict[str, Any]:
    """전용 생성 도구가 없는 것의 생성. 사양 정의 · 사양 그룹 · 계열 조건. 시스템 관리자 전용.

        spec_definition   fields: key · label · group_id · kind · dimension · si_unit ·
                          display_unit · condition_key_id · help
        spec_group        fields: slug · label · description
        series_condition  ids: series_id · series_test_item_id
                          fields: condition_key_id · min_value · max_value · text_value · note
                          (같은 조건이 있으면 덮어씀)

    **사양 정의 생성 전 list_spec_definitions로 중복 확인.** 같은 뜻의 칸이 둘이면 기종마다
    다른 칸에 기록되어 검색 결과가 절반만 나옴. 값의 단위는 축 단위(list_conditions의 unit).
    """
    table = {
        "spec_definition": ("POST", "/spec-definitions"),
        "spec_group": ("POST", "/spec-groups"),
        "series_condition": (
            "PUT",
            "/equipment-series/{series_id}/test-items/{series_test_item_id}/limits",
        ),
    }
    return await _by_kind(ctx, table, kind, ids, fields)


# ── 검토함 — 보고 정하기 (정하기는 시스템 관리자) ──────────────────────────────


@mcp.tool()
async def list_review_queues(ctx: Context) -> dict[str, Any]:
    """검토함의 물음별 남은 건수(어느 물음이 얼마나 밀렸는지).

    반입이 정하지 못한 항목(규격의 시험 항목 · 물을 조건 · 물성 산출 여부 · 초안 속성 병합)이
    쌓이는 곳. 줄 조회는 `list_review_items`, 결정은 `decide_review_item`(시스템 관리자 토큰만,
    사용자 지시 후).
    """
    return _listed(await _get(ctx, "/review"), "queues")


@mcp.tool()
async def list_review_items(
    ctx: Context, queue: str, status: str = "open", limit: int = 20, offset: int = 0
) -> dict[str, Any]:
    """한 물음의 줄 목록: 대상 · 물음 문장 · 근거 자료 · 후보 · 추천과 이유.

    `queue`는 `list_review_queues`의 `key`. `status`: open · voted · decided · skipped · gone ·
    all.

    줄의 `question`은 그 줄이 묻는 내용을 담은 완전한 문장, `facts`는 판단에 필요한 사실.
    **추천(`recommended`)은 정답이 아님**: 근거(`reason`)를 함께 읽고, 사람에게 전달할 때도
    둘을 함께 전달. 결정은 `decide_review_item`.
    """
    return await _get(
        ctx, f"/review/{queue}", {"status": status, "limit": limit, "offset": offset}
    )


@writes
async def decide_review_item(
    ctx: Context,
    queue: str,
    proposal_id: str,
    action: str = "decide",
    choice: list[str] | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """검토함 한 줄의 확정 · 의견 · 보류 · 다시 열기. 확정·보류·다시 열기는 시스템 관리자.

    action:

        decide   확정. choice 필수(후보의 code 목록, 빈 목록은 해당 없음). 카탈로그에 바로
                 적용됨(규격의 시험 항목이면 인용 계열에 붙음 등)
        vote     의견. 누구나 가능, 데이터 변경 없음
        skip     보류 전환(다시 호출하면 해제)
        reopen   결정 취소 후 다시 열기. 이미 적용된 변경은 되돌리지 않음

    **확정은 사용자가 대상과 선택을 지시한 경우에만.** 지시가 분명하면(예: 추천대로) 그대로
    확정. 모호하면 `list_review_items`의 question · facts · 후보 · 추천과 근거 · 다른
    의견(votes)을 제시하고 선택을 받음. 추천은 정답이 아님. 줄에는 `이름(MCP)` 형식으로,
    감사에는 토큰 이름이 기록됨. 여러 줄을 추천대로 확정하는 것은 `decide_review_recommended`.
    규격의 시험 항목을 `set_method_test_items`로 직접 고치는 우회는 409(검토함에서 정함).
    """
    if action == "decide":
        if choice is None:
            return {"error": "decide에는 choice 필요(빈 목록은 해당 없음)."}
        return await _send(
            ctx,
            "POST",
            f"/review/{queue}/{proposal_id}/decide",
            {"choice": choice, "note": note},
        )
    if action == "vote":
        return await _send(
            ctx,
            "POST",
            f"/review/{queue}/{proposal_id}/vote",
            {"choice": choice or [], "note": note},
        )
    if action == "skip":
        return await _send(ctx, "POST", f"/review/{queue}/{proposal_id}/skip")
    if action == "reopen":
        return await _send(ctx, "POST", f"/review/{queue}/{proposal_id}/reopen")
    return {
        "error": f"알 수 없는 action: {action}",
        "actions": ["decide", "vote", "skip", "reopen"],
    }


@writes
async def decide_review_recommended(
    ctx: Context, queue: str, ids: list[str], note: str | None = None
) -> dict[str, Any]:
    """검토함 여러 줄을 줄마다의 추천대로 일괄 확정. 시스템 관리자. 줄마다 결과 반환.

    추천이 없는 줄, 추천과 다른 의견이 있는 줄은 확정하지 않고 `failed`로 사유와 함께 반환
    (하나씩 `decide_review_item`으로). 한 번에 최대 500줄. `note`는 감사에 남음(비우면
    기본 문구 `추천대로 한꺼번에 확정`).

    **사용자가 일괄 확정을 지시한 경우에만.** 대상 줄 수와 대표 줄(대상 · 추천 · 근거)을 먼저
    제시하고 승인을 받은 뒤 호출. 확정하면 카탈로그에 바로 적용됨.
    """
    return await _send(
        ctx,
        "POST",
        f"/review/{queue}/decide-recommended",
        {"ids": ids, "note": note},
    )


# ── 지식 그래프 — 무엇이 무엇과 이어지나 (읽기) ──────────────────────────────


@mcp.tool()
async def graph_overview(ctx: Context) -> dict[str, Any]:
    """저장소 **구조**: 객체 종류와 관계 종류, 각각의 실제 건수.

    시스템에 들어 있는 대상과 연결 관계를 한 번에 조회. 건수 0인 관계는 정의만 있고 아직
    연결되지 않은 것(채울 곳 표시).
    """
    return await _get(ctx, "/graph/overview")


@mcp.tool()
async def graph_search(ctx: Context, q: str) -> dict[str, Any]:
    """그래프 시작점 검색(**종류 무관**): 이름·코드·별칭·자산번호.

    반환되는 `id`가 `graph_neighbors` · `graph_node`에 넣는 노드 id. 무엇을 물어야 할지 모를
    때, 사람이 말한 이름 하나로 어느 종류의 무엇인지부터 판별.
    """
    return _listed(await _get(ctx, "/graph/search", {"q": q}), "hits")


@mcp.tool()
async def graph_neighbors(
    ctx: Context, node_id: str, depth: int = 1, fanout: int = 30, limit: int = 100
) -> dict[str, Any]:
    """객체 하나의 **이웃**: 연결 대상과 관계.

    `node_id`는 `"<종류>:<uuid>"` 형식(`test_item:…` · `series:…` · `method:…` · `equipment:…`
    · `reliability_test:…`). uuid만으로는 표를 알 수 없으므로 `graph_search`가 준 id를 그대로
    사용.

    **서버가 상한을 강제.** 노드에 `truncated`가 붙어 있으면 그 노드의 이웃이 다 온 것이
    아님(`degree`가 실제 수). 전부라고 말하지 말고, 더 봐야 하면 그 노드를 중심으로 재호출.
    """
    return await _get(
        ctx,
        "/graph/neighborhood",
        {"focus": node_id, "depth": depth, "fanout": fanout, "limit": limit},
    )


@mcp.tool()
async def graph_node(ctx: Context, node_id: str) -> dict[str, Any]:
    """객체 하나의 요약과 **관계 목록**: 어떤 관계로 무엇과 이어졌는지 이름까지.

    `related_total`이 목록보다 크면 잘린 것. 상세 화면 주소(`detail_path`)가 함께 오므로
    사람에게 전달할 때 그 링크 제공(id만으로는 사람이 활용 불가).
    """
    return await _get(ctx, "/graph/node", {"id": node_id})


def main() -> None:
    """기동. **기본은 127.0.0.1 이고, 밖에 열 때는 허용 Host 를 반드시 받는다.**

    띄우는 길 셋(`run_mcp.ps1` · 배포판 `run_mcp.ps1` · 서비스 정의)이 전부 이 함수를
    지난다 — 전에는 셋이 각자 `-c "import server; server.mcp.run(...)"` 를 적어서, 한 곳만
    고치면 갈라졌다. 그러면 갈라진 쪽만 조용히 보호 없이 뜬다.

    허용 Host 판정은 `bind.py` 에 있다(시험이 `mcp` 패키지 없이도 돌게).
    """
    if os.environ.get("TESTSCOPE_MCP_TRANSPORT", "streamable-http") == "stdio":
        mcp.run(transport="stdio")
        return

    host = os.environ.get("TESTSCOPE_MCP_HOST", "127.0.0.1")
    try:
        allowed = bind.allowed_hosts(host, os.environ.get("TESTSCOPE_MCP_ALLOWED_HOSTS"))
    except ValueError as refusal:
        raise SystemExit(str(refusal)) from None

    mcp.run(
        transport="streamable-http",
        host=host,
        port=int(os.environ.get("TESTSCOPE_MCP_PORT", "8022")),
        # **넘기지 않으면 보호가 꺼진다.** SDK 는 localhost 로 들을 때만 저절로 켠다 —
        # 0.0.0.0 으로 바꾸는 순간 Host·Origin 검사가 사라진다(bind.py 머리의 실측).
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=allowed,
        ),
    )


if __name__ == "__main__":
    main()

"""MCP 도구가 저장소 규칙을 지키는가 — **정적으로 본다.**

진짜 MCP 클라이언트로 왕복해야만 드러나는 어긋남이 있다. HTTP 로 같은 엔드포인트를
부르면 멀쩡하므로 화면이나 curl 로는 영영 안 보인다(MatNexus 실측). 그런 것을
여기서 막는다.
"""

from __future__ import annotations

import ast
from pathlib import Path

SERVER = Path(__file__).resolve().parents[3] / "mcp_server" / "server.py"


#: 바꾸는 도구의 이름 앞머리. 읽기 전용 프로필에서 안 실려야 하는 것들이다.
WRITE_PREFIXES = (
    "create_",
    "set_",
    "add_",
    "import_",
    "update_",
    "register_",
    "merge_",
    "promote_",
    "detach_",
    "confirm_",
)


def _decorated(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """이 함수가 도구라면 어느 데코레이터로 달렸나 — `tool` 또는 `writes`."""
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call) and getattr(decorator.func, "attr", "") == "tool":
            return "tool"
        if isinstance(decorator, ast.Name) and decorator.id == "writes":
            return "writes"
    return None


def _tools() -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    tree = ast.parse(SERVER.read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and _decorated(node) is not None
    ]


def test_mcp_서버가_있다() -> None:
    assert SERVER.exists(), "mcp_server/server.py 가 없습니다"
    assert _tools(), "도구가 하나도 없습니다"


def test_도구는_dict_를_돌려준다() -> None:
    """**감싸지 않으면 그 도구는 통째로 죽는다.**

    mcp 2.x 는 도구가 돌려준 값을 반환 표기로 검증한다. 목록 엔드포인트는 배열을
    주므로 `-> dict[str, Any]` 로 적어 두고 `_listed()` 로 감싸야 한다 — 안 그러면
    클라이언트에는 `Error executing tool …` 만 가고 원인이 사라진다.
    """
    for tool in _tools():
        assert tool.returns is not None, f"{tool.name}: 반환 표기가 없습니다"
        text = ast.unparse(tool.returns)
        assert text in ("str", "dict[str, Any]"), (
            f"{tool.name}: 반환 표기가 {text} 입니다 — dict[str, Any] 나 str 이어야 "
            f"합니다(목록은 _listed() 로 감쌉니다)"
        )


def test_도구마다_설명이_있다() -> None:
    """**도구 설명이 곧 지침이다.** AI 가 도구를 볼 때 항상 함께 오는 유일한 글이다."""
    for tool in _tools():
        doc = ast.get_docstring(tool)
        assert doc, f"{tool.name}: 설명이 없습니다"
        assert len(doc) > 40, f"{tool.name}: 설명이 너무 짧습니다"


def test_만능_토큰을_두지_않는다() -> None:
    """서버가 자기 자격으로 부르면 **그 순간 모든 사용자가 같은 권한을 갖는다.**"""
    text = SERVER.read_text(encoding="utf-8")
    for banned in ("TESTSCOPE_TOKEN", "TESTSCOPE_PAT", "SERVICE_TOKEN"):
        assert banned not in text, f"{banned} — 서버가 자기 토큰을 들면 안 됩니다"


def test_도구가_부르는_경로가_실재한다() -> None:
    """**오타 하나면 그 도구가 통째로 죽는다.**

    MCP 는 얇은 프록시라 경로를 글자로 들고 있다. 서버에서 경로가 바뀌면(실제로
    `/capabilities` 가 `/equipment-test-items` 가 됐다) 이쪽은 아무 말 없이 404 를
    받고, 그 사실은 그 도구를 실제로 부른 사람에게만 드러난다.
    """
    import json
    import re

    spec = json.loads(
        (SERVER.parents[1] / "backend" / "openapi.json").read_text(encoding="utf-8")
    )

    #: `{model_id}` 같은 자리를 하나로 맞춰 비교한다 — 이름은 달라도 같은 자리다.
    def shape(path: str) -> str:
        return re.sub(r"\{[^}]+\}", "{}", path)

    known = {shape(one.removeprefix("/api")) for one in spec["paths"]}
    source = SERVER.read_text(encoding="utf-8")
    #: `_get(ctx, "/…")` · `_send(ctx, "POST", f"/…")` 가 부르는 자리들.
    called = {
        shape(one)
        for one in re.findall(r'f?"(/[a-z][^"]*)"', source)
        if not one.startswith("/api")
    }
    missing = sorted(one for one in called if one not in known)
    assert not missing, f"서버에 없는 경로를 부른다: {missing}"


def test_배포_스크립트가_개발용과_같은_전송으로_MCP_를_띄운다() -> None:
    """서버는 공식 mcp SDK 2.x 라 `run(transport='streamable-http', host=…, port=…)` 다.

    `'http'` 와 `FASTMCP_*` 환경변수는 다른 패키지(fastmcp)의 관례라 여기서는 안 통한다 —
    개발용 run_mcp.ps1 은 맞게 부르는데 배포용 템플릿과 서비스 정의가 옛 관례로 남아, 운영
    첫 설치에서 MCP 서비스만 곧장 죽었다. 셋이 같은 이름을 쓰는지 여기서 본다.
    """
    root = SERVER.parents[1]
    for rel in (
        "mcp_server/run_mcp.ps1",
        "scripts/ci/run_mcp_template.ps1",
        "scripts/deploy/service.ps1",
    ):
        text = (root / rel).read_text(encoding="utf-8-sig")
        assert "transport='streamable-http'" in text, (
            f"{rel} 이 streamable-http 로 안 띄웁니다"
        )
        assert "transport='http'" not in text, (
            f"{rel} 이 fastmcp 의 전송 이름 'http' 를 씁니다"
        )
        assert "$env:FASTMCP_" not in text and "FASTMCP_PORT =" not in text, (
            f"{rel} 이 FASTMCP_* 환경변수를 씁니다 — 공식 SDK 는 안 읽습니다"
        )


def test_바꾸는_도구는_writes_로_단다() -> None:
    """읽기 전용 프로필(`TESTSCOPE_MCP_TOOLS=read`)에서 **안 실려야 할 것**을 가른다.

    표시를 빠뜨리면 그 도구가 읽기 전용에서도 실리고, 부르면 403 이 온다 — 그 403 은
    「범위가 없다」 로 읽혀 사람이 토큰을 다시 만들게 만든다. 읽기 도구에 잘못 달면
    반대로 그 도구가 조용히 사라진다.
    """
    for tool in _tools():
        writes = tool.name.startswith(WRITE_PREFIXES) and tool.name != "import_columns"
        marked = _decorated(tool) == "writes"
        assert marked == writes, (
            f"{tool.name}: {'@writes 로 달아야' if writes else '@mcp.tool() 이어야'} 합니다"
        )


def test_도구_목록이_조용히_불어나지_않는다() -> None:
    """**도구 목록은 매 턴 통째로 실린다.** 예순 개가 넘으면 그것만으로 수만 자이고,
    그만큼 대화가 짧아진다 — 그리고 그 비용은 도구를 더한 사람 눈에 안 보인다.

    그래서 상한을 여기 적는다. 넘기려면 이 수를 고치면서 **왜 그만한 값어치가 있는지**
    한 번 생각하게 하는 것이 목적이다. 설명 하나가 너무 길어지는 것도 같이 본다 —
    긴 이야기는 `get_guide(주제)` 가 할 일이고, 도구 설명에는 규칙만 남긴다.
    """
    tools = _tools()
    assert len(tools) <= 70, f"도구가 {len(tools)}개입니다 — 묶거나 상한을 다시 정하세요"
    for tool in tools:
        doc = ast.get_docstring(tool) or ""
        assert len(doc) <= 1600, (
            f"{tool.name}: 설명이 {len(doc)}자입니다 — 긴 것은 GUIDE.md 의 대목으로 옮기고"
            f" 도구에는 규칙만 남기세요"
        )
        first = doc.strip().splitlines()[0]
        assert len(first) <= 100, (
            f"{tool.name}: 첫 줄이 {len(first)}자입니다 — 첫 줄만 읽고 고를 수 있어야 합니다"
        )


def test_길잡이가_도구_목록과_함께_실린다() -> None:
    """**도구 예순 개를 이름으로 훑어 고르는 것은 안 된다.** 비슷한 이름이 여럿이라
    (search_test_items · search_catalog · search_semantic) 고르는 데 실패하면 그다음
    행동이 통째로 틀린다. 그래서 「무엇을 물었나 -> 첫 도구」 표를 서버 안내문에 싣는다 —
    그 글은 도구 목록과 함께 항상 실리는 유일한 자리다.
    """
    text = SERVER.read_text(encoding="utf-8")
    assert "ROUTING" in text, "길잡이 표(ROUTING)가 없습니다"
    start = text.index("ROUTING = ")
    routing = text[start : text.index('"""', text.index('"""', start) + 3)]
    for tool in (
        "search_test_items",
        "import_equipment",
        "list_reference",
        "list_pending_work",
    ):
        assert tool in routing, f"길잡이에 {tool} 이 없습니다"
    assert "ROUTING" in text[text.index("instructions=") :], (
        "길잡이를 instructions 에 안 싣습니다 — 안 실리면 아무도 안 읽는다"
    )

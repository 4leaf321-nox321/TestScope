"""MCP 도구가 저장소 규칙을 지키는가 — **정적으로 본다.**

진짜 MCP 클라이언트로 왕복해야만 드러나는 어긋남이 있다. HTTP 로 같은 엔드포인트를
부르면 멀쩡하므로 화면이나 curl 로는 영영 안 보인다(MatNexus 실측). 그런 것을
여기서 막는다.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

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
    "suggest_",
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


def test_MCP_설정은_개발도_운영도_backend_env_에서_읽는다() -> None:
    """`MCP_PORT`·`MCP_HOST` 는 **띄우는 스크립트 셋이 같은 파일에서** 읽어야 한다.

    운영(service.ps1)만 이 두 키를 읽고 개발(run_mcp.ps1)은 무시하던 때가 있었다 —
    `.env` 에 적어 둔 포트가 개발에서만 안 듣는 것은, 도구가 실패하고 나서야 드러나고
    그때 원인이 「내가 적은 값이 안 읽힌다」 라 찾는 데 오래 걸린다. 셋이 같은 키를
    보는지, 그리고 `.env.example` 이 그 키를 알려 주는지 여기서 본다.
    """
    root = SERVER.parents[1]
    for rel in (
        "mcp_server/run_mcp.ps1",
        "scripts/ci/run_mcp_template.ps1",
        "scripts/deploy/service.ps1",
    ):
        text = (root / rel).read_text(encoding="utf-8-sig")
        for key in ("MCP_PORT", "MCP_HOST"):
            assert key in text, f"{rel} 이 {key} 를 안 읽습니다 — 개발·운영이 갈립니다"

    example = (root / "backend" / ".env.example").read_text(encoding="utf-8-sig")
    for key in ("MCP_PORT", "MCP_HOST"):
        assert f"{key}=" in example, (
            f".env.example 에 {key} 가 없습니다 — 이 파일만 보고 설정하는 사람은"
            f" 그 키의 존재를 모릅니다"
        )
    #: 서버 주소는 스크립트가 PORT 로 계산한다. 두 군데 적으면 언젠가 한쪽만 고친다.
    #: 주석으로 「여기 적지 않는다」 라고 말하는 것은 괜찮다 — 값을 주는 줄만 막는다.
    assigned = [
        one.split("=", 1)[0].strip()
        for one in example.splitlines()
        if "=" in one and not one.lstrip().startswith("#")
    ]
    assert "TESTSCOPE_API_BASE" not in assigned, (
        ".env.example 이 TESTSCOPE_API_BASE 에 값을 줍니다 — mcp_server/server.py 는"
        " .env 를 안 읽으므로 그 값은 효과가 없고, 주소가 두 군데로 갈립니다"
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

    69 -> 73 (2026-09-23): 기준정보를 AI 가 **끝까지** 채울 수 있게 넷을 더했다 —
    `create_axis` · `update_axis` · `create_condition_key` · `update_term`.

    축과 값만 만들 수 있고 **값이 갖는 칸**(물성의 기호·단위 같은 `attribute_schema`)은
    화면에서만 채울 수 있었다. 그러면 AI 가 온톨로지를 절반만 세우고 나머지를 사람에게
    넘기는데, 넘겨받은 사람은 **무엇이 비었는지 모른다** — 값은 서 있으니 다 된 것처럼
    보인다. 반쪽짜리 자동화가 아무것도 없는 것보다 나쁜 자리다.

    넷 다 쓰기 도구라 읽기 전용 프로필(`TESTSCOPE_MCP_TOOLS=read`)에는 안 실린다 —
    비용은 쓰기 연결에만 붙는다.

    73 -> 74 (2026-09-23): `list_attachments`. 그림은 **AI 가 못 보는 자료**지만, 있다는
    사실과 설명은 읽어야 한다 — 「절차 그림 3장이 붙어 있습니다」 를 말할 수 없으면 AI 가
    카드를 절반만 옮기고, 사람은 그 절반을 전부로 읽는다. **더 늘리기 전에는 묶을 자리부터
    찾아라.**
    """
    tools = _tools()
    assert len(tools) <= 74, f"도구가 {len(tools)}개입니다 — 묶거나 상한을 다시 정하세요"
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


def test_측정_물음이_부르는_도구가_실재한다() -> None:
    """도구 이름을 바꾸면 물음 파일의 기대 자취가 조용히 틀린다 — 그러면 채점이 늘 「필수
    미달」 로 나오는데, 그것은 AI 가 헤맨 것이 아니라 파일이 낡은 것이다."""
    import json

    doc = json.loads((SERVER.parent / "eval" / "questions.json").read_text(encoding="utf-8"))
    names = {tool.name for tool in _tools()}
    for question in doc["questions"]:
        for key in ("start_with", "must_call", "must_not_call"):
            for tool in question.get(key, []):
                assert tool in names, f"{question['id']}.{key}: {tool} 라는 도구가 없습니다"
        assert question["max_calls"] >= len(question.get("must_call", [])), (
            f"{question['id']}: 필수 도구가 상한보다 많습니다"
        )


def test_자취_채점은_표식으로_자르고_다섯_항목을_센다() -> None:
    """채점기는 LLM 없이도 돌아야 한다 — 자취만 있으면. 표식이 있으면 그것으로 자르고,
    없으면 시간 간격으로 자르되 그렇다고 말한다."""
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("score", SERVER.parent / "eval" / "score.py")
    assert spec is not None and spec.loader is not None
    score = importlib.util.module_from_spec(spec)
    # dataclass 가 `from __future__ import annotations` 를 풀 때 sys.modules 에서 제 모듈을
    # 찾는다 — 등록 안 하면 None.__dict__ 로 죽는다.
    sys.modules["score"] = score
    spec.loader.exec_module(score)

    questions = [
        {
            "id": "q01",
            "text": "인장 되는 장비",
            "start_with": ["resolve"],
            "must_call": ["search_test_items"],
            "must_not_call": ["create_series"],
            "max_calls": 3,
        },
        {
            "id": "q02",
            "text": "뭐가 있나",
            "start_with": ["list_reference"],
            "must_call": [],
            "must_not_call": [],
            "max_calls": 2,
        },
    ]

    def call(tool: str, ts: str, empty: bool = False) -> dict[str, Any]:
        return {"ts": ts, "session": "s", "tool": tool, "ok": True, "empty": empty}

    # 표식이 있는 자취 — q01 은 잘 갔고, q02 는 빈손으로 세 번 더듬었다.
    rows: list[dict[str, Any]] = [
        {"ts": "2026-09-20T01:00:00+00:00", "session": "s", "event": "question", "id": "q01"},
        call("resolve", "2026-09-20T01:00:01+00:00"),
        call("search_test_items", "2026-09-20T01:00:02+00:00"),
        {"ts": "2026-09-20T01:01:00+00:00", "session": "s", "event": "question", "id": "q02"},
        call("search_semantic", "2026-09-20T01:01:01+00:00", empty=True),
        call("search_series", "2026-09-20T01:01:02+00:00", empty=True),
        call("list_reference", "2026-09-20T01:01:03+00:00"),
    ]
    report = score.score(rows, questions, gap_seconds=90)
    assert report["marked"] is True and report["answered"] == 2
    first, second = report["results"]
    assert first["score"] == 5 and first["trace"] == ["resolve", "search_test_items"]
    assert second["checks"] == {
        "호출 수": False,
        "시작": False,
        "필수": True,
        "금지": True,
        "빈손": False,
    }
    assert report["score"] == 7 and report["possible"] == 10

    # 표식이 없으면 시간 간격으로 자르고, 덜 정확하다고 말한다.
    unmarked = [row for row in rows if "tool" in row]
    unmarked[2]["ts"] = "2026-09-20T01:05:00+00:00"  # 세 번째 호출부터 새 물음
    unmarked[3]["ts"] = "2026-09-20T01:05:01+00:00"
    unmarked[4]["ts"] = "2026-09-20T01:05:02+00:00"
    loose = score.score(unmarked, questions, gap_seconds=90)
    assert loose["marked"] is False and loose["answered"] == 2
    assert "덜 정확" in score.render(loose)


def test_server_가_import_하는_옆_모듈은_배포_패키지에도_담긴다() -> None:
    """**빠지면 운영에서만, 그것도 조용히 터진다.**

    `server.py` 가 `import calltrace` 를 하는데 `package_deploy.ps1` 이 그 파일을 안 담았다.
    개발에서는 폴더에 있으니 멀쩡하고, CI 의 왕복 시험도 저장소에서 도니까 멀쩡하다. 운영에만
    안 들어가서 서비스가 ImportError 로 즉시 죽고, WinSW 가 되살리다 무한 재시작에 빠졌다 —
    화면에 보이는 것은 「서비스 STOPPED」 뿐이라 로그를 열기 전에는 원인을 알 수 없었다
    (v0.15.0 부터 세 판이 그렇게 나갔다, 2026-09-23 실측).

    그래서 **여기서 잡는다** — server.py 가 제 옆의 .py 를 import 하면 패키징 스크립트가
    그것을 담는지 본다.
    """
    root = SERVER.parent
    packager = SERVER.resolve().parents[1] / "scripts" / "ci" / "package_deploy.ps1"
    script = packager.read_text(encoding="utf-8")

    imported: set[str] = set()
    for node in ast.walk(ast.parse(SERVER.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module.split(".")[0])

    # 옆에 같은 이름의 .py 가 있으면 그것은 이 저장소의 모듈이다(설치된 패키지가 아니라).
    local = sorted(name for name in imported if (root / f"{name}.py").exists())
    assert local, "server.py 가 옆 모듈을 하나도 안 쓴다면 이 시험의 전제가 바뀐 것이다"
    for name in local:
        assert f"mcp_server\{name}.py" in script, (
            f"server.py 가 {name} 을 import 하는데 package_deploy.ps1 이 안 담습니다 —"
            f" 담지 않으면 운영 MCP 서비스가 ImportError 로 죽습니다."
        )

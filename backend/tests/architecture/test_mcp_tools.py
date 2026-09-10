"""MCP 도구가 저장소 규칙을 지키는가 — **정적으로 본다.**

진짜 MCP 클라이언트로 왕복해야만 드러나는 어긋남이 있다. HTTP 로 같은 엔드포인트를
부르면 멀쩡하므로 화면이나 curl 로는 영영 안 보인다(MatNexus 실측). 그런 것을
여기서 막는다.
"""

from __future__ import annotations

import ast
from pathlib import Path

SERVER = Path(__file__).resolve().parents[3] / "mcp_server" / "server.py"


def _tools() -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    tree = ast.parse(SERVER.read_text(encoding="utf-8"))
    found: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and getattr(decorator.func, "attr", "") == "tool"
            ):
                found.append(node)
    return found


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

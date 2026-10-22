"""사람 확인 증표의 서명이 **백엔드와 MCP 서버에서 같은가.**

두 벌이다 — MCP 서버는 백엔드를 import 하지 않는다(얇은 프록시, 따로 배포). 한쪽만 고치면
사람이 확인 창에서 수락한 요청이 「증표가 맞지 않음」 으로 전부 막히고, 그것은 운영에서 사람이
수락을 누른 뒤에야 드러난다.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from app.shared import confirm

_MCP_CONFIRM = Path(__file__).resolve().parents[3] / "mcp_server" / "confirm.py"


def test_백엔드와_MCP_서버의_서명이_같다() -> None:
    spec = importlib.util.spec_from_file_location("mcp_confirm", _MCP_CONFIRM)
    assert spec is not None and spec.loader is not None
    mcp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mcp)

    assert mcp.HEADER == confirm.HEADER
    assert mcp.VERSION == confirm.VERSION
    assert mcp.derive_key("비밀") == confirm.derive_key("비밀")
    args: dict[str, Any] = {
        "ts": "1790000000",
        "nonce": "abc",
        "method": "post",
        "path": "/api/reliability-tests/bulk",
        "query": "revision_id=1",
        "token": "tsp_토큰",
        "body": '{"ids":["가"]}'.encode(),
    }
    key = confirm.derive_key("비밀")
    assert mcp.signature(key, **args) == confirm.signature(key, **args)
    # 본문 한 글자가 다르면 다른 서명이다.
    assert mcp.signature(key, **{**args, "body": b"{}"}) != confirm.signature(key, **args)


def test_개발_기본_비밀값이_백엔드와_같다() -> None:
    """개발 PC 의 `.env` 에는 대개 `JWT_SECRET` 이 없다 — 둘이 같은 기본값을 써야 맞는다."""
    from app.config import Settings

    spec = importlib.util.spec_from_file_location("mcp_confirm", _MCP_CONFIRM)
    assert spec is not None and spec.loader is not None
    mcp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mcp)
    assert Settings.model_fields["jwt_secret"].default == mcp.DEV_SECRET

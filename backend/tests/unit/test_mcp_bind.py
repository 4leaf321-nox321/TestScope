"""밖에 열 때의 허용 Host — **조용히 꺼지는 보호를 막는다.**

공식 SDK 는 듣는 자리가 localhost 일 때만 DNS rebinding 보호를 저절로 켜고, 그 밖이면
설정이 없는 채로 돈다(하위 호환). 즉 `MCP_HOST` 를 `0.0.0.0` 으로 바꾸는 것만으로 **지금
있던 Host·Origin 검사가 사라진다** — 실측(2026-09-28)으로 확인했다:

    MCP_HOST=127.0.0.1   Host: evil.example → 421
    MCP_HOST=0.0.0.0     Host: evil.example → 200

그래서 밖에 열려면 허용 Host 를 말로 적게 하고, 없으면 **기동을 거절한다.** 경고만 찍고
뜨면 아무도 안 읽고, 보호가 없는 줄 모른 채 몇 달이 간다.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[3] / "mcp_server" / "bind.py"
_SPEC = importlib.util.spec_from_file_location("mcp_bind", _PATH)
assert _SPEC and _SPEC.loader
bind = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bind)


class Test안에서_들을_때:
    def test_목록이_없어도_뜨고_localhost_셋을_허용한다(self) -> None:
        got = bind.allowed_hosts("127.0.0.1", None)
        assert got == ["127.0.0.1:*", "localhost:*", "[::1]:*"]

    def test_IPv6_localhost_가_빠지지_않는다(self) -> None:
        """SDK 가 저절로 넣던 셋과 같아야 한다 — `[::1]:*` 를 빼면 IPv6 로 붙던
        클라이언트가 그날부터 421 을 받고, 그 사람은 제 설정을 의심한다."""
        assert "[::1]:*" in bind.allowed_hosts("localhost", "")

    def test_적어_준_것이_있으면_그것을_쓴다(self) -> None:
        """안에서 들어도 사람이 적었으면 듣는다 — 적은 것이 안 듣는 편이 더 나쁘다."""
        assert bind.allowed_hosts("127.0.0.1", "10.240.25.85:8022") == ["10.240.25.85:8022"]


class Test밖으로_열_때:
    def test_목록이_없으면_거절한다(self) -> None:
        with pytest.raises(ValueError) as refused:
            bind.allowed_hosts("0.0.0.0", None)
        said = str(refused.value)
        # 사유만 말하고 끝내면 사람은 무엇을 적어야 할지 모른다 — 키 이름과 보기를 준다.
        assert "MCP_ALLOWED_HOSTS" in said
        assert "0.0.0.0" in said
        assert ":8022" in said

    def test_빈_칸만_있는_것도_없는_것이다(self) -> None:
        with pytest.raises(ValueError):
            bind.allowed_hosts("0.0.0.0", " , ,  ")

    def test_적어_주면_그대로_쓴다(self) -> None:
        got = bind.allowed_hosts("0.0.0.0", "10.240.25.85:8022, 127.0.0.1:8022")
        assert got == ["10.240.25.85:8022", "127.0.0.1:8022"]

    def test_localhost_기본값을_섞지_않는다(self) -> None:
        """밖에 열면서 127.0.0.1 을 덤으로 넣어 주면, 적은 것보다 넓게 열린다."""
        assert bind.allowed_hosts("0.0.0.0", "10.240.25.85:8022") == ["10.240.25.85:8022"]


def test_쉼표로_가르고_빈_칸을_버린다() -> None:
    assert bind.parse_allowed(" a:1 , , b:2 ") == ["a:1", "b:2"]
    assert bind.parse_allowed(None) == []

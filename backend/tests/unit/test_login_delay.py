"""로그인 지연 — **잠그지 않고 늦추기만 한다.**

관리자 복구가 서버 콘솔뿐인 시스템에서 잠금은 자해다. 늦추기만 해도 무차별 시도는
시간당 몇 번으로 줄고, 비밀번호를 아는 사람은 한 번 기다리면 된다.
"""

from __future__ import annotations

from app.config import get_settings
from app.modules.auth.services import login_delay_seconds


def test_문턱_전에는_안_늦춘다() -> None:
    settings = get_settings()
    for failures in range(1, settings.login_delay_after):
        assert login_delay_seconds(failures) == 0.0


def test_문턱부터_늘어난다() -> None:
    settings = get_settings()
    first = login_delay_seconds(settings.login_delay_after)
    second = login_delay_seconds(settings.login_delay_after + 1)
    assert 0 < first < second


def test_상한을_넘지_않는다() -> None:
    settings = get_settings()
    assert login_delay_seconds(10_000) == settings.login_delay_max_seconds

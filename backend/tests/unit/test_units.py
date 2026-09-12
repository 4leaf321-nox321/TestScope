"""단위 환산 — **사양의 단위와 검색축의 단위가 다르면 곱해서 옮기고, 못 곱하면 안 옮긴다.**

500 gf 를 그대로 kN 축에 옮기면 500 kN 이 된다 — 1억 배 틀린 자신 있는 오답.
"""

from __future__ import annotations

import pytest

from app.shared.units import compatible, convert, normalize_unit


def test_같은_차원은_곱해서_옮긴다() -> None:
    assert convert(500, "gf", "kN") == pytest.approx(0.004903325)
    assert convert(20, "kN", "N") == 20000
    assert convert(4000, "cP", "Pa·s") == pytest.approx(4)
    assert convert(60, "mm/s", "mm/min") == pytest.approx(3600)


def test_표기가_흔들려도_같은_단위다() -> None:
    assert normalize_unit("°C") == normalize_unit("degC")
    assert normalize_unit("µm") == normalize_unit("um")
    assert normalize_unit("N·m") == normalize_unit("Nm")
    assert convert(3, "N·m", "mNm") == 3000


def test_온도는_곱셈이_아니라_자리_옮김이다() -> None:
    # 배율표에 섞으면 0 °C 가 0 K 가 된다.
    assert convert(0, "degC", "K") == pytest.approx(273.15)
    assert convert(300, "K", "°C") == pytest.approx(26.85)


def test_못_바꾸면_None_이다() -> None:
    # 쇼어 경도 ↔ kN — 지어서 옮기면 틀린 값이 검색에 쓰인다.
    assert convert(70, "ShoreA", "kN") is None
    assert convert(20, "degC", "kN") is None
    assert compatible("gf", "kN") is True
    assert compatible("ShoreA", "kN") is False
    # 둘 다 비어 있으면 같은 것이다(단위 없는 축).
    assert compatible("", "") is True

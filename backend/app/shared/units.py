"""단위 환산 — **사양의 단위와 검색축의 단위가 다르면 곱해서 옮긴다.**

사양 정의(「시험력」 gf)를 검색축(「하중 용량」 kN)에 이으면 그 값이 검색 조건이 된다. 전에는
숫자를 **그대로** 옮겼다 — 500 gf 가 500 kN 이 되어 검색이 「500 kN 됨」 이라고 답한다.
1억 배 틀린 자신 있는 오답. 지금까지 안 터진 것은 이어진 정의가 우연히 축과 같은 단위였기
때문이다(kN↔kN · degC↔degC).

프론트의 `shared/units.ts` 와 같은 표다. 두 벌인 이유: 화면은 사람이 친 「4000 cP」 를 그
자리에서 바꿔 보여 줘야 하고, 서버는 저장된 사양을 조건으로 옮길 때 바꿔야 한다 — 서로
부를 길이 없다. 그래서 **같은 규칙, 같은 검증**을 둔다(`tests/unit/test_units.py`).

## 모르면 모른다고 한다

표에 없는 단위나 차원이 다른 짝(쇼어 경도 ↔ kN)은 `None` 을 돌려주고, 부르는 쪽은 옮기지
않는다. 지어서 옮기면 틀린 값이 검색에 쓰인다(ADR 0003).

## 온도는 곱셈이 아니다

K 와 °C 는 자리 옮김이다(K = °C + 273.15). 배율표에 섞으면 0 °C 가 0 K 가 된다.
"""

from __future__ import annotations

import re
from collections.abc import Callable

_UNITS: dict[str, tuple[str, float]] = {}


def normalize_unit(raw: str) -> str:
    """표기 흔들림을 하나로. `°C` · `degC`, `µm` · `um`, `N·m` · `Nm`."""
    text = raw.strip()
    text = re.sub(r"°C", "degc", text, flags=re.IGNORECASE)
    text = text.replace("℃", "degc").replace("µ", "u").replace("·", "")
    text = re.sub(r"\s+", "", text).replace("^", "")
    return text.lower()


def _define(dimension: str, table: dict[str, float]) -> None:
    for name, factor in table.items():
        _UNITS[normalize_unit(name)] = (dimension, factor)


_define(
    "force",
    {
        "N": 1,
        "kN": 1e3,
        "MN": 1e6,
        "mN": 1e-3,
        "uN": 1e-6,
        "nN": 1e-9,
        "kgf": 9.80665,
        "gf": 0.00980665,
    },
)
_define(
    "length", {"m": 1, "km": 1e3, "cm": 1e-2, "mm": 1e-3, "um": 1e-6, "nm": 1e-9, "pm": 1e-12}
)
_define("mass", {"kg": 1, "g": 1e-3, "mg": 1e-6, "t": 1e3})
_define(
    "pressure",
    {"Pa": 1, "kPa": 1e3, "MPa": 1e6, "GPa": 1e9, "bar": 1e5, "mbar": 1e2, "psi": 6894.757},
)
_define("time", {"s": 1, "ms": 1e-3, "us": 1e-6, "ns": 1e-9, "min": 60, "h": 3600})
_define("frequency", {"Hz": 1, "kHz": 1e3, "MHz": 1e6, "GHz": 1e9})
_define("voltage", {"V": 1, "mV": 1e-3, "kV": 1e3, "uV": 1e-6})
_define("current", {"A": 1, "mA": 1e-3, "uA": 1e-6, "kA": 1e3})
_define("power", {"W": 1, "mW": 1e-3, "kW": 1e3, "MW": 1e6})
_define("torque", {"N·m": 1, "Nm": 1, "mN·m": 1e-3, "mNm": 1e-3, "nN·m": 1e-9, "nNm": 1e-9})
_define("energy", {"J": 1, "kJ": 1e3, "mJ": 1e-3, "Wh": 3600, "kWh": 3.6e6})
_define("viscosity", {"Pa·s": 1, "Pas": 1, "mPa·s": 1e-3, "mPas": 1e-3, "cP": 1e-3, "P": 0.1})
_define("angle", {"deg": 1, "°": 1, "rad": 57.29577951308232})
_define("volume", {"L": 1, "mL": 1e-3, "m³": 1e3, "m3": 1e3, "cc": 1e-3})
_define("speed", {"mm/min": 1, "mm/s": 60, "m/min": 1e3, "m/s": 6e4, "um/min": 1e-3})
_define("ratio", {"%": 1, "pct": 1, "ppm": 1e-4})
_define("acceleration", {"g": 1, "m/s²": 1 / 9.80665, "m/s2": 1 / 9.80665})

_TEMPERATURE_TO_C: dict[str, Callable[[float], float]] = {
    "degc": lambda v: v,
    "c": lambda v: v,
    "k": lambda v: v - 273.15,
    "f": lambda v: (v - 32) * 5 / 9,
    "degf": lambda v: (v - 32) * 5 / 9,
}
_TEMPERATURE_FROM_C: dict[str, Callable[[float], float]] = {
    "degc": lambda v: v,
    "c": lambda v: v,
    "k": lambda v: v + 273.15,
    "f": lambda v: v * 9 / 5 + 32,
    "degf": lambda v: v * 9 / 5 + 32,
}


def convert(value: float, from_unit: str, to_unit: str) -> float | None:
    """`from_unit` 의 값을 `to_unit` 으로. **못 바꾸면 None** — 지어서 옮기지 않는다."""
    source = normalize_unit(from_unit or "")
    target = normalize_unit(to_unit or "")
    if source == target:
        return value
    if source in _TEMPERATURE_TO_C and target in _TEMPERATURE_FROM_C:
        return _TEMPERATURE_FROM_C[target](_TEMPERATURE_TO_C[source](value))
    left = _UNITS.get(source)
    right = _UNITS.get(target)
    if left is None or right is None or left[0] != right[0]:
        return None
    return value * left[1] / right[1]


def compatible(from_unit: str, to_unit: str) -> bool:
    """같은 단위이거나 환산할 수 있나. 둘 다 비어 있으면 같은 것으로 본다."""
    return convert(1.0, from_unit, to_unit) is not None

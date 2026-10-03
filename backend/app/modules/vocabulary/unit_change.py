"""단위를 고치면 **저장된 숫자의 뜻이 바뀐다** — 그래서 값이 있으면 묻는다.

조건 축(장비 조건 · 계열 조건 · 규격 요구)과 사양 정의(기종 사양 · 개체 실측)는 숫자만 담고
단위는 정의에서 읽는다. 정의의 단위를 cm 에서 m 로 고치는 순간 152 가 152 m 가 된다 — 전에는
감사 기록에 「cm → m」 한 줄이 남을 뿐 그대로 통과했다.

값이 있으면 **어떻게 할지를 말하게 한다**(`stored_values`):

    convert  숫자를 새 단위로 환산한다 — 152 cm 가 1.52 m 가 된다. 못 바꾸는 짝이면 거절.
    keep     숫자를 그대로 둔다 — 「단위 이름이 틀렸고, 숫자는 원래 새 단위였다」.

안 말하면 409 와 함께 몇 줄이 걸리는지 준다. 값이 없는 정의와 표기만 다른 같은 단위
(°C · degC)는 묻지 않는다 — 물을 것이 없는데 물으면 사람은 생각 없이 keep 을 누르게 된다.

속성 정의는 여기를 안 탄다. 값마다 단위 칸이 있어서, 고치기 전의 단위를 비어 있는 값에
적어 두면 뜻이 지켜진다(`attributes.services.keep_unit`).
"""

from __future__ import annotations

from typing import Literal

from app.shared.errors import Conflict
from app.shared.units import convert, same_unit

StoredValues = Literal["convert", "keep"]


def decide(
    *,
    what: str,
    before: str,
    after: str,
    counts: dict[str, int],
    stored_values: str | None,
    ask_code: str,
    cannot_code: str,
) -> StoredValues | None:
    """저장된 숫자를 어떻게 할지. None 이면 물을 것이 없다(값이 없거나 같은 단위).

    물어야 하는데 안 말했으면 409(`ask_code`) — 어느 표에 몇 줄인지 함께 준다. `convert` 인데
    못 바꾸는 짝이면 409(`cannot_code`). 두 단위는 정의의 `unit`(display_unit, 없으면
    si_unit)이다.
    """
    total = sum(counts.values())
    if total == 0 or same_unit(before, after):
        return None
    old, new = before or "단위 없음", after or "단위 없음"
    if stored_values is None:
        where = " · ".join(f"{name} {count}줄" for name, count in counts.items() if count)
        raise Conflict(
            ask_code,
            f"{what}의 단위를 {old}에서 {new}(으)로 바꾸면 저장된 값 {total}줄"
            f"({where})의 의미가 바뀜. 숫자를 새 단위로 환산하려면"
            ' stored_values="convert", 숫자가 원래 새 단위였다면 "keep"을 함께 전송 필요.',
            details={"before": before, "after": after, "stored": counts},
        )
    if stored_values == "keep":
        return "keep"
    if convert(1.0, before, after) is None:
        raise Conflict(
            cannot_code,
            f"{old}에서 {new}(으)로 환산 불가(표에 없는 단위이거나 차원이"
            ' 다름). 숫자가 원래 새 단위였다면 stored_values="keep"으로 전송 필요.',
            details={"before": before, "after": after},
        )
    return "convert"


def moved(value: float | None, before: str, after: str) -> float | None:
    """`decide` 가 `convert` 를 돌려줬을 때 숫자 하나를 옮긴다.

    열두 자리에서 자른다 — 152 cm 를 m 로 갔다 오면 151.99999999999997 이 되고, 화면은 그
    꼬리를 그대로 그린다.
    """
    if value is None:
        return None
    result = convert(value, before, after)
    assert result is not None  # decide 가 짝을 확인했다
    return float(f"{result:.12g}")

"""목록 응답 — **상한을 서버가 강제한다.**

클라이언트가 보낸 limit 을 그대로 믿으면 `?limit=1000000` 한 번에 서버가 죽는다.
악의가 없어도 그렇게 된다 — 화면이 "전부 보기" 를 구현하면서 큰 수를 넣는다.

total 을 함께 주는 이유: 없으면 화면이 "다음 쪽이 있는지" 를 알려고 한 건 더
요청하는 편법을 쓰게 되고, 그 편법은 화면마다 달라진다.
"""

from __future__ import annotations

from pydantic import BaseModel

DEFAULT_LIMIT = 50
MAX_LIMIT = 200

#: **카탈로그는 상한이 따로 높다.**
#:
#: 카탈로그(계열·기종)는 한 화면에 통째로 놓고 훑는 목록이다 — 기종 1608개를 50개씩
#: 서른세 쪽으로 끊으면 「이 제조사 것이 몇 종인가」 를 사람이 종이에 적으며 봐야 한다.
#: 그리고 그 줄들은 가볍고, 목록을 만드는 질의 수가 **줄 수와 무관하다**(계열·제조사·
#: 사양·보유 수를 한 번에 모아 온다 — `catalog_models.list_models`).
#:
#: **그래도 무한은 아니다.** `?limit=1000000` 한 번에 서버가 죽는 것은 그대로다. 그리고
#: 이 상한을 전역으로 올리지 않는 이유가 측정으로 남아 있다: 신뢰성 시험은 한 사업부에
#: 1784건이 들어왔고 그것을 통째로 그리면 **브라우저가 멎는다** — 줄마다 속성·시험 항목·
#: 장비 수가 딸려 온다(2026-09-30, `reliability/services.py`). 가벼운 목록의 편의를 위해
#: 무거운 목록의 상한을 함께 올리면, 그 사고가 다른 화면에서 되살아난다.
CATALOG_MAX_LIMIT = 5000


def clamp_limit(limit: int | None, *, cap: int = MAX_LIMIT) -> int:
    """상한을 **서버가** 정한다. `cap` 을 주면 그 목록만 더 받는다(카탈로그)."""
    if limit is None:
        return DEFAULT_LIMIT
    return max(1, min(limit, cap))


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int

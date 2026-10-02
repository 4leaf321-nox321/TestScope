"""카탈로그는 **한 화면에 다 놓고 훑는다** — 그래서 상한이 따로 높다.

기종 1608개를 50개씩 서른세 쪽으로 끊으면 「이 제조사 것이 몇 종인가」 를 사람이 종이에
적으며 봐야 한다. 그래서 카탈로그 목록의 상한만 올렸다(2026-10-03).

**전역으로 올리지 않은 이유가 측정으로 남아 있다.** 신뢰성 시험은 한 사업부에 1784건이
들어왔고, 그것을 통째로 그리면 브라우저가 멎는다 — 줄마다 속성·시험 항목·장비 수가 딸려
온다(2026-09-30). 가벼운 목록의 편의를 위해 무거운 목록의 상한을 함께 올리면 그 사고가
다른 화면에서 되살아난다.

카탈로그를 올려도 되는 근거는 옆 시험이 지킨다 — `test_catalog_list_cost.py` 가 **질의 수가
줄 수를 따라 늘지 않음**을 못박는다. 그게 깨지면 상한을 올린 것이 위험해지므로, 둘은 함께
읽어야 한다.

여기서 지키는 것:

1. 카탈로그(계열·기종)는 **200 을 넘는 limit 을 받는다** — 받은 수가 응답에 그대로 온다.
2. 무거운 목록(보유 장비·신뢰성 시험)은 **여전히 200 에서 막힌다.**
3. 카탈로그도 **무한은 아니다** — `?limit=1000000` 은 거절한다.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.shared.pagination import CATALOG_MAX_LIMIT, MAX_LIMIT
from tests.api.conftest import Signed

#: 카탈로그 목록 둘. 같은 상한을 쓰므로 함께 본다.
CATALOG = ("/api/equipment-series", "/api/equipment-models")

#: **무거운 목록** — 줄마다 속성·시험 항목이 딸려 온다. 여기는 200 그대로다.
HEAVY = ("/api/equipment", "/api/reliability-tests")


def test_카탈로그는_이백을_넘겨_받는다(client: TestClient, admin: Signed) -> None:
    asked = MAX_LIMIT * 2
    assert asked <= CATALOG_MAX_LIMIT
    for path in CATALOG:
        got = client.get(path, params={"limit": asked}, headers=admin.headers)
        assert got.status_code == 200, f"{path}: {got.text}"
        # **응답이 받은 수를 그대로 말해야 한다.** Query 는 통과했는데 서비스가 조용히
        # 200 으로 자르면, 화면은 「다 받았다」 고 믿고 나머지를 안 가져온다.
        assert got.json()["limit"] == asked, f"{path}: 서비스가 잘랐다"


def test_무거운_목록은_이백에서_막힌다(client: TestClient, admin: Signed) -> None:
    """가벼운 목록의 편의가 무거운 목록으로 번지지 않는다."""
    for path in HEAVY:
        got = client.get(path, params={"limit": MAX_LIMIT + 1}, headers=admin.headers)
        assert got.status_code == 422, f"{path}: {got.status_code} — 상한이 풀렸다"


def test_카탈로그도_무한은_아니다(client: TestClient, admin: Signed) -> None:
    """`?limit=1000000` 한 번에 서버가 죽는 것은 그대로 막는다."""
    for path in CATALOG:
        got = client.get(path, params={"limit": 1_000_000}, headers=admin.headers)
        assert got.status_code == 422, f"{path}: {got.status_code}"

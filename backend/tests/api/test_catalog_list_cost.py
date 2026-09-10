"""카탈로그 목록은 **줄 수와 무관하게 값싸야 한다.**

## 왜 이 시험이 있나

계열 목록 한 쪽(50줄)이 질의를 **1,058회** 했다. 실측이다. 그중 425회가 제조사·분류를
줄마다 다시 꺼낸 것이고, 379회가 시험 항목마다 인용 규격과 조건 수치를 만든 것이었다 —
그런데 목록 화면이 그 시험 항목으로 하는 일은 **개수를 세는 것**뿐이었다.

이런 것은 눈으로 안 보인다. 화면은 잘 그려지고, 개발 DB 는 질의당 0.5 ms 라 0.5 초면
끝난다. 배포 환경에서 DB 가 망 건너에 있어 왕복이 2 ms 가 되는 날 4,000번이 8 초가 되고,
그때는 이미 「원래 느린 화면」 이 되어 있다.

## 무엇을 못박나

**질의 수가 줄 수를 따라 늘지 않는다.** 이것 하나다. 상한을 숫자로 적어 두면 나중에
한 줄을 더 채우려고 `db.get` 하나를 넣는 순간 시험이 깨진다 — 그 한 줄이 목록에서는
200번이라는 사실을 그때 알려 주는 것이 이 시험의 일이다.

느슨하게 잡는다. 정확한 수를 못박으면 무해한 변경마다 숫자를 고치게 되고, 그러다
아무도 안 읽는 시험이 된다.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import event

from app.database import engine
from tests.api.conftest import Signed

#: 한 쪽에 허용하는 질의 수. **줄 수와 무관해야 한다.**
#:
#: 지금 실측은 계열 6회·기종 12회다. 스무 번이면 배치를 몇 개 더 붙일 여유가 있고,
#: 줄마다 묻는 코드가 돌아오면(줄당 한 번만 물어도 50회) 반드시 넘는다.
BUDGET = 20

#: 줄 수를 두 배로 늘려 본다. 질의가 함께 늘면 줄마다 묻고 있다는 뜻이다.
FEW = 3
MANY = 12


@contextmanager
def counted() -> Iterator[list[str]]:
    """그 사이에 나간 SQL 을 모은다. 세는 것만으로는 **어디가 범인인지** 모른다."""
    seen: list[str] = []

    def _watch(
        conn: Any, cursor: Any, statement: str, params: Any, context: Any, many: bool
    ) -> None:
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", _watch)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", _watch)


def _series(client: TestClient, admin: Signed, tag: str) -> str:
    response = client.post(
        "/api/equipment-series",
        json={"name": f"{tag}-{uuid.uuid4().hex[:8]}"},
        headers=admin.headers,
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _with_test_item(client: TestClient, admin: Signed, series_id: str) -> None:
    """시험 항목 하나를 단다. **이게 옛 코드에서 가장 비쌌다** — 항목마다 인용 규격과
    조건 수치를 만드느라 줄당 예닐곱 번을 물었다."""
    term = client.post(
        "/api/vocabularies/test_item/terms",
        json={"value": f"항목-{uuid.uuid4().hex[:8]}"},
        headers=admin.headers,
    )
    assert term.status_code == 201, term.text
    response = client.post(
        f"/api/equipment-series/{series_id}/test-items",
        json={"test_item_term_id": term.json()["id"]},
        headers=admin.headers,
    )
    assert response.status_code == 201, response.text


def _model(client: TestClient, admin: Signed, series_id: str) -> None:
    response = client.post(
        "/api/equipment-models",
        json={"series_id": series_id, "name": f"기종-{uuid.uuid4().hex[:8]}"},
        headers=admin.headers,
    )
    assert response.status_code == 201, response.text


def _fill(client: TestClient, admin: Signed, count: int) -> None:
    for _ in range(count):
        series_id = _series(client, admin, "비용")
        _with_test_item(client, admin, series_id)
        _model(client, admin, series_id)


def _cost(client: TestClient, admin: Signed, path: str) -> tuple[int, list[str]]:
    with counted() as seen:
        response = client.get(path, headers=admin.headers)
    assert response.status_code == 200, response.text
    assert response.json()["items"], "빈 목록으로는 아무것도 못 잰다"
    return len(seen), seen


def test_계열_목록의_질의가_줄_수를_따라_늘지_않는다(
    client: TestClient, admin: Signed
) -> None:
    _fill(client, admin, MANY)
    few, _ = _cost(client, admin, f"/api/equipment-series?limit={FEW}")
    many, statements = _cost(client, admin, f"/api/equipment-series?limit={MANY}")

    assert many <= BUDGET, f"{MANY}줄에 질의 {many}회 — 줄마다 묻고 있다.\n" + "\n".join(
        f"  {one[:110]}" for one in statements[:25]
    )
    # **네 배로 늘려도 그대로여야 한다.** 조금 늘어나는 것(총건수·권한 같은 고정비)은
    # 봐 주되, 줄 수에 비례하면 안 된다.
    assert many <= few + 2, f"{FEW}줄에 {few}회 · {MANY}줄에 {many}회 — 줄에 비례한다"


def test_기종_목록의_질의가_줄_수를_따라_늘지_않는다(
    client: TestClient, admin: Signed
) -> None:
    _fill(client, admin, MANY)
    few, _ = _cost(client, admin, f"/api/equipment-models?limit={FEW}")
    many, statements = _cost(client, admin, f"/api/equipment-models?limit={MANY}")

    assert many <= BUDGET, f"{MANY}줄에 질의 {many}회 — 줄마다 묻고 있다.\n" + "\n".join(
        f"  {one[:110]}" for one in statements[:25]
    )
    assert many <= few + 2, f"{FEW}줄에 {few}회 · {MANY}줄에 {many}회 — 줄에 비례한다"


def test_목록_줄은_상세를_안_싣는다(client: TestClient, admin: Signed) -> None:
    """목록이 상세를 실으면 위의 두 시험은 **다시 깨질 수밖에 없다.**

    질의 수는 결과지 원인이 아니다. 원인은 모양이라서, 모양도 함께 못박는다.
    """
    _fill(client, admin, FEW)

    series = client.get("/api/equipment-series?limit=3", headers=admin.headers)
    row = series.json()["items"][0]
    assert "test_item_count" in row, "계열 목록은 시험 항목을 **개수로** 준다"
    for heavy in ("test_items", "relations", "raw_limits"):
        assert heavy not in row, f"목록 줄에 {heavy} 가 실렸다 — 화면이 안 그리는 값이다"

    models = client.get("/api/equipment-models?limit=3", headers=admin.headers)
    model_row = models.json()["items"][0]
    assert all(isinstance(one, str) for one in model_row["test_items"]), (
        "기종 목록의 시험 항목은 **이름만**이다 — 조건 수치는 계열이 갖는 값이라 "
        "형제 기종끼리 전부 같고, 목록은 그것을 안 그린다"
    )
    assert "raw_specs" not in model_row, "사양 원문은 상세에서만 본다"

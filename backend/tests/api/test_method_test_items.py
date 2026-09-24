"""규격 ↔ 시험 항목은 **N:M** 이다 — 규격 하나가 여럿을 덮는다.

## 왜 이 시험이 있나

칸 하나(`test_methods.test_item_term_id`)로 두었을 때 IEC 60529 를 「분진 침투」 에 붙이면
「방수(IPX)」 는 **규격이 없는 항목**이 됐다. 그 항목으로 장비를 찾는 사람은 「그런 규격이
없다」 는 답을 받는다 — 문서는 그 시험도 정의하고 있는데.

실측(2026-09-24): 규격 0건인 시험 항목 19개 중 여럿이 이 부류였다. MIL-STD-810 은 방법
번호마다 다른 시험이고, IEC 60068-2 계열도 한 문서가 여러 조건을 담는다. 규격은 **문서**
이지 시험 항목이 아니다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.methods import services as methods
from tests.api.conftest import Signed


def _term(client: TestClient, admin: Signed, value: str) -> str:
    made = client.post(
        "/api/vocabularies/test_item/terms",
        json={"value": f"{value}-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def _method(client: TestClient, admin: Signed, items: list[str]) -> dict[str, Any]:
    made = client.post(
        "/api/methods",
        json={
            "code": f"IEC {uuid.uuid4().hex[:6]}",
            "title": "Degrees of protection provided by enclosures (IP Code)",
            "test_item_term_ids": items,
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    body: dict[str, Any] = made.json()
    return body


def test_규격_하나가_시험_항목_둘을_덮는다(client: TestClient, admin: Signed) -> None:
    """IEC 60529 는 IP 코드의 1자리(방진)와 2자리(방수)를 한 문서가 정의한다."""
    dust = _term(client, admin, "분진 침투")
    water = _term(client, admin, "방수")
    made = _method(client, admin, [dust, water])

    assert {one["term_id"] for one in made["test_items"]} == {dust, water}

    # **둘 다에서 걸린다.** 하나만 걸리면 나머지 항목은 「규격이 없는 항목」 이다.
    for term_id in (dust, water):
        found = client.get(f"/api/methods?test_item_term_id={term_id}", headers=admin.headers)
        assert found.status_code == 200, found.text
        assert made["id"] in {one["id"] for one in found.json()["items"]}, (
            f"{term_id} 로 물었는데 이 규격이 안 나온다"
        )


def test_보내면_통째로_바뀐다(client: TestClient, admin: Signed) -> None:
    """빠뜨리면 조용히 끊긴다 — 그래서 화면과 MCP 가 「지금 있는 것에 더해서」 보낸다."""
    first = _term(client, admin, "분진 침투")
    second = _term(client, admin, "방수")
    made = _method(client, admin, [first])

    changed = client.patch(
        f"/api/methods/{made['id']}",
        json={"test_item_term_ids": [first, second]},
        headers=admin.headers,
    )
    assert changed.status_code == 200, changed.text
    assert {one["term_id"] for one in changed.json()["test_items"]} == {first, second}

    # 비우면 「안 정함」 으로 돌아간다.
    emptied = client.patch(
        f"/api/methods/{made['id']}",
        json={"test_item_term_ids": []},
        headers=admin.headers,
    )
    assert emptied.json()["test_items"] == []


def test_같은_항목을_두_번_보내도_한_줄이다(client: TestClient, admin: Signed) -> None:
    """유일 제약이 막는다 — 막지 않으면 목록에 같은 이름이 두 번 선다."""
    item = _term(client, admin, "인장")
    made = _method(client, admin, [item, item])
    assert len(made["test_items"]) == 1


def test_항목이_하나도_없으면_미정으로_센다(client: TestClient, admin: Signed) -> None:
    """홈의 「남은 일」 이 이 조건으로 온다 — **세는 조건과 거르는 조건이 같아야 한다.**"""
    made = _method(client, admin, [])
    assert made["test_items"] == []

    undecided = client.get("/api/methods?test_item=none", headers=admin.headers)
    assert made["id"] in {one["id"] for one in undecided.json()["items"]}

    # 정하면 그 목록에서 빠진다.
    item = _term(client, admin, "인장")
    client.patch(
        f"/api/methods/{made['id']}",
        json={"test_item_term_ids": [item]},
        headers=admin.headers,
    )
    again = client.get("/api/methods?test_item=none", headers=admin.headers)
    assert made["id"] not in {one["id"] for one in again.json()["items"]}


def test_합치면_두_규격의_항목이_모두_남는다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """**합치기는 정보를 잃지 않는 일이어야 한다.** 한쪽만 남기면 연결이 준다.

    합치기는 REST 가 아니라 검토함(`method_cleanup`)을 통해서만 열려 있어서 서비스를
    직접 부른다 — 확인하려는 것은 화면이 아니라 합집합 규칙이다.
    """
    dust = _term(client, admin, "분진 침투")
    water = _term(client, admin, "방수")
    target = _method(client, admin, [dust])
    source = _method(client, admin, [water])

    methods.merge_into(db, None, uuid.UUID(source["id"]), uuid.UUID(target["id"]))
    db.commit()

    after = client.get(f"/api/methods/{target['id']}", headers=admin.headers).json()
    assert {one["term_id"] for one in after["test_items"]} == {dust, water}

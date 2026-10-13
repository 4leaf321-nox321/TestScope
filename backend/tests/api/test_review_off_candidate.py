"""규격의 시험 항목을 **후보 밖**으로 정할 때 — 안 이어지는 계열을 말하고, 이을 길을 준다.

후보는 이 규격을 인용한 계열이 이미 하는 시험이다. 후보 밖 항목으로 확정하면 그 시험 항목이
없는 인용 계열은 미정(PENDING)으로 남는데, 경고도 안내도 없어 처리가 끝난 것으로 보였고
실제로는 검색에 안 나왔다(2026-10-13 사용자 보고).

여기서 지키는 것:

1. 확정 전 미리보기가 이어질 계열과 **안 이어질 계열**, 후보 밖 항목을 말한다.
2. 그냥 확정하면 안 이어진 계열이 결정 줄(`payload.unlinked_series`)에 남는다.
3. 「인용 계열에도 추가」 로 확정하면 그 계열에 시험 항목이 더해져 이어진다.
4. 끊긴 규격이 홈 「남은 일」 과 목록(`?cited=unlinked`)에 서고, 규격 화면에서 이을 수 있다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.shared.text import method_key
from tests.api.conftest import Signed


def _item(db: Session, label: str) -> Any:
    """검토함은 시험 항목을 **코드**로 고른다 — 코드가 있는 값을 만든다."""
    from app.modules.vocabulary.models import Vocabulary, VocabularyTerm

    axis = db.scalar(select(Vocabulary).where(Vocabulary.slug == "test_item"))
    assert axis is not None
    tag = uuid.uuid4().hex[:6]
    term = VocabularyTerm(
        vocabulary_id=axis.id,
        value=f"{label}-{tag}",
        normalized=f"{label}-{tag}",
        code=f"item_{tag}",
    )
    db.add(term)
    db.commit()
    return term


def _series(client: TestClient, admin: Signed, *items: Any) -> dict[str, Any]:
    made = client.post(
        "/api/equipment-series",
        json={"name": f"계열-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    for term in items:
        added = client.post(
            f"/api/equipment-series/{made.json()['id']}/test-items",
            json={"test_item_term_id": str(term.id)},
            headers=admin.headers,
        )
        assert added.status_code == 201, added.text
    body: dict[str, Any] = made.json()
    return body


def _setup(client: TestClient, admin: Signed, db: Session) -> dict[str, Any]:
    """계열 둘이 규격 하나를 항목 미정으로 인용 — 하나는 시험 A 를 하고, 하나는 아무것도
    안 한다."""
    from app.modules.review.models import ReviewProposal
    from app.modules.test_items.models import SeriesPendingMethod

    doing = _item(db, "굽힘")
    off = _item(db, "피로")
    code = f"ISO {uuid.uuid4().hex[:5]}"
    method = client.post(
        "/api/methods", json={"code": code, "title": code}, headers=admin.headers
    ).json()
    with_item = _series(client, admin, doing)
    bare = _series(client, admin)
    for series in (with_item, bare):
        db.add(
            SeriesPendingMethod(
                series_id=uuid.UUID(series["id"]), method_id=uuid.UUID(method["id"])
            )
        )
    proposal = ReviewProposal(
        queue="method_test_items",
        subject_key=method_key(code),
        subject_id=uuid.UUID(method["id"]),
        subject_label=code,
        candidates=[{"code": doing.code, "label": doing.value}],
        status="open",
    )
    db.add(proposal)
    db.commit()
    return {
        "doing": doing,
        "off": off,
        "method": method,
        "with_item": with_item,
        "bare": bare,
        "proposal": str(proposal.id),
    }


def test_확정_전에_안_이어질_계열을_미리_말한다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    case = _setup(client, admin, db)
    url = f"/api/review/method_test_items/{case['proposal']}/preview"

    off = client.get(url, params={"choice": [case["off"].code]}, headers=admin.headers)
    assert off.status_code == 200, off.text
    assert off.json()["linked"] == []
    assert sorted(off.json()["unlinked"]) == sorted(
        [case["with_item"]["name"], case["bare"]["name"]]
    )
    assert off.json()["off_candidates"] == [case["off"].value]

    inside = client.get(url, params={"choice": [case["doing"].code]}, headers=admin.headers)
    assert inside.json()["linked"] == [case["with_item"]["name"]]
    assert inside.json()["unlinked"] == [case["bare"]["name"]]
    assert inside.json()["off_candidates"] == []


def test_그냥_확정하면_안_이어진_계열이_남고_남은_일에_선다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    case = _setup(client, admin, db)
    decided = client.post(
        f"/api/review/method_test_items/{case['proposal']}/decide",
        json={"choice": [case["off"].code]},
        headers=admin.headers,
    )
    assert decided.status_code == 200, decided.text
    payload = decided.json()["payload"]
    assert sorted(payload["unlinked_series"]) == sorted(
        [case["with_item"]["name"], case["bare"]["name"]]
    )
    assert payload["added_to_series"] == []

    method = client.get(f"/api/methods/{case['method']['id']}", headers=admin.headers).json()
    assert method["pending_series_count"] == 2

    listed = client.get(
        "/api/methods", params={"cited": "unlinked", "limit": 200}, headers=admin.headers
    ).json()
    assert case["method"]["id"] in [one["id"] for one in listed["items"]]
    rows = {
        one["key"]: one
        for one in client.get("/api/server/maintenance", headers=admin.headers).json()
    }
    assert rows["method_citation_unlinked"]["link"] == "/methods?cited=unlinked"

    # 규격 화면에서 잇는다 — 안 이어진 계열에 그 시험 항목을 더한다.
    linked = client.post(
        f"/api/methods/{case['method']['id']}/link-citations", headers=admin.headers
    )
    assert linked.status_code == 200, linked.text
    assert sorted(linked.json()["added_to"]) == sorted(
        [case["with_item"]["name"], case["bare"]["name"]]
    )
    assert linked.json()["still_unlinked"] == 0
    after = client.get(f"/api/methods/{case['method']['id']}", headers=admin.headers).json()
    assert after["pending_series_count"] == 0 and after["series_count"] == 2


def test_인용_계열에도_추가하고_확정하면_이어진다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    case = _setup(client, admin, db)
    decided = client.post(
        f"/api/review/method_test_items/{case['proposal']}/decide",
        json={"choice": [case["off"].code], "add_to_citing": True},
        headers=admin.headers,
    )
    assert decided.status_code == 200, decided.text
    payload = decided.json()["payload"]
    assert payload["unlinked_series"] == []
    assert sorted(payload["added_to_series"]) == sorted(
        [case["with_item"]["name"], case["bare"]["name"]]
    )

    method = client.get(f"/api/methods/{case['method']['id']}", headers=admin.headers).json()
    assert method["pending_series_count"] == 0 and method["series_count"] == 2
    series = client.get(
        f"/api/equipment-series/{case['bare']['id']}", headers=admin.headers
    ).json()
    assert case["off"].value in [row["test_item"] for row in series["test_items"]]


def test_다른_물음에는_인용_계열_추가를_못_쓴다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    from app.modules.review.models import ReviewProposal

    row = ReviewProposal(
        queue="test_item_axes",
        subject_key=f"axes-{uuid.uuid4().hex[:6]}",
        subject_label="x",
        candidates=[],
        status="open",
    )
    db.add(row)
    db.commit()
    refused = client.post(
        f"/api/review/test_item_axes/{row.id}/decide",
        json={"choice": [], "add_to_citing": True},
        headers=admin.headers,
    )
    assert refused.status_code == 400, refused.text
    assert refused.json()["error"]["code"] == "TSC-REVIEW-0017"

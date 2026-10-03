"""조건 축이 **얼마나, 어디까지** 쓰이나 — 온톨로지와 검색 사이의 다리.

온톨로지에서 축을 열면 「이 조건을 거는 시험」 까지는 보이는데 **값이 안 보였다.** 그래서
읽는 사람은 「-40 °C 이하인 시험」 을 물으려다 막히고, 이 플랫폼이 그걸 못 한다고 읽었다 —
실제로는 검색(`attr`)이 답하는 물음인데 그 경계가 화면에 없었다(2026-09-30).

**구간은 미리 안 나눈다.** 임의로 나눈 구간은 없는 것보다 나쁘다 — 읽는 사람이 그 경계에
뜻이 있다고 믿는다. 몇 건이고 어디까지인지, 그리고 **실제로 적힌 값**을 답하고(경계는 쓰임이
드러낸다), 좁히는 것은 검색으로 넘긴다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.workspaces.models import Workspace
from tests.api.conftest import Signed, division_term_id
from tests.api.test_reliability_tests import _signed_in


def _lab(db: Session, client: TestClient, tag: str) -> Signed:
    lab = Workspace(
        slug=f"lab-{tag}", name="신뢰성팀", division_term_id=division_term_id(db, "vd")
    )
    db.add(lab)
    db.commit()
    return _signed_in(client, db, lab, "manager")


def _condition_key(client: TestClient, admin: Signed, tag: str) -> dict[str, Any]:
    """이 시험만 쓰는 새 조건 축 — 다른 시험의 값이 섞이면 범위를 못 잰다."""
    made = client.post(
        "/api/condition-keys",
        json={
            "key": f"reach_{tag}",
            "label": f"도달 확인 온도-{tag}",
            "kind": "range",
            "dimension": "temperature",
            "si_unit": "degC",
            "display_unit": "degC",
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return dict(made.json())


def _definition(client: TestClient, admin: Signed, tag: str, key_id: str) -> dict[str, Any]:
    made = client.post(
        "/api/attribute-definitions",
        json={
            "target": "reliability_test",
            "label": f"도달 온도-{tag}",
            "kind": "condition",
            "unit": "degC",
            "condition_key_id": key_id,
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return dict(made.json())


def test_쓰임과_범위를_주고_구간은_안_나눈다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    tag = "a" + uuid.uuid4().hex[:5]
    manager = _lab(db, client, tag)
    key = _condition_key(client, admin, tag)
    definition = _definition(client, admin, tag, key["id"])

    for name, attrs in (
        (f"넓은 것-{tag}", {"num_min": -55, "num_max": 150}),
        (f"좁은 것-{tag}", {"num_min": -20, "num_max": 85}),
        # **값을 안 적은 줄** — 칸은 꺼냈는데 비고만 있다. 세기는 하되 범위에는 안 든다.
        (f"안 적은 것-{tag}", {"note": "규격에 따름"}),
    ):
        got = client.post(
            "/api/reliability-tests",
            json={
                "division_code": "vd",
                "name": name,
                "attributes": [{"definition_id": definition["id"], "unit": "degC", **attrs}],
            },
            headers=manager.headers,
        )
        assert got.status_code == 201, got.text

    reach = client.get(f"/api/condition-keys/{key['id']}/reach", headers=manager.headers)
    assert reach.status_code == 200, reach.text
    body = reach.json()

    assert body["test_count"] == 3, "칸을 꺼낸 것은 값이 없어도 센다"
    assert body["valued_count"] == 2, "값이 적힌 것만 범위에 든다"
    assert (body["low"], body["high"]) == (-55.0, 150.0)
    assert body["display_unit"] == "degC"
    # **좁히는 열쇠를 함께 준다** — `attr` 이 받는 것은 축 id 가 아니라 정의의 key 다.
    assert [one["key"] for one in body["definitions"]] == [definition["key"]]
    # **구간은 없다.** 있으면 읽는 사람이 그 경계에 뜻이 있다고 믿는다.
    assert "buckets" not in body and "ranges" not in body


def test_자주_적힌_값을_세고_그_값이_드는_시험으로_넘긴다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """「85 °C 2건 · -40 °C 2건」 — 시험이 실제로 쓰는 점이 곧 자연스러운 경계다."""
    tag = "a" + uuid.uuid4().hex[:5]
    manager = _lab(db, client, tag)
    key = _condition_key(client, admin, tag)
    definition = _definition(client, admin, tag, key["id"])

    for name, attrs in (
        (f"고온-{tag}", {"num_value": 85}),
        (f"열충격-{tag}", {"num_min": -40, "num_max": 85}),
        (f"넓은 열충격-{tag}", {"num_min": -40, "num_max": 125}),
        (f"상온-{tag}", {"num_value": 25}),
    ):
        got = client.post(
            "/api/reliability-tests",
            json={
                "division_code": "vd",
                "name": name,
                "attributes": [{"definition_id": definition["id"], "unit": "degC", **attrs}],
            },
            headers=manager.headers,
        )
        assert got.status_code == 201, got.text

    body = client.get(f"/api/condition-keys/{key['id']}/reach", headers=manager.headers).json()
    # 많이 적힌 것부터, 같으면 작은 값부터 — 늘 같은 순서다.
    assert [(one["value"], one["count"]) for one in body["common_values"]] == [
        (-40.0, 2),
        (85.0, 2),
        (25.0, 1),
        (125.0, 1),
    ]
    eighty_five = body["common_values"][1]
    assert eighty_five["attr"] == f"{definition['key']}=85"

    # 넘기면 그 값이 **드는** 시험이 온다 — 그대로 적은 둘보다 많을 수 있다(범위로 적은 것).
    listed = client.get(
        "/api/reliability-tests",
        params={"attr": eighty_five["attr"], "division": "vd", "q": tag},
        headers=manager.headers,
    )
    assert listed.status_code == 200, listed.text
    assert {one["name"] for one in listed.json()["items"]} == {
        f"고온-{tag}",
        f"열충격-{tag}",
        f"넓은 열충격-{tag}",
    }


def test_단위를_못_바꾼_값은_범위에서_빠지고_그_수를_말한다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """**조용히 빼면 「그만큼만 쓰인다」 로 읽힌다.**"""
    tag = "a" + uuid.uuid4().hex[:5]
    manager = _lab(db, client, tag)
    key = _condition_key(client, admin, tag)
    definition = _definition(client, admin, tag, key["id"])

    for name, unit, low in ((f"섭씨-{tag}", "degC", 40), (f"엉뚱한 단위-{tag}", "kN", 5)):
        got = client.post(
            "/api/reliability-tests",
            json={
                "division_code": "vd",
                "name": name,
                "attributes": [
                    {"definition_id": definition["id"], "num_min": low, "unit": unit}
                ],
            },
            headers=manager.headers,
        )
        assert got.status_code == 201, got.text

    body = client.get(f"/api/condition-keys/{key['id']}/reach", headers=manager.headers).json()
    assert body["test_count"] == 2
    assert body["valued_count"] == 1
    assert body["unconvertible_count"] == 1, "못 바꾼 줄을 세지 않으면 범위가 전부처럼 읽힌다"
    assert (body["low"], body["high"]) == (40.0, 40.0)


def test_아무도_안_쓰는_축은_빈_답을_준다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """0 은 「없다」 가 아니라 **「아직 아무도 안 걸었다」** 다 — 화면이 그렇게 말해야 한다."""
    tag = "a" + uuid.uuid4().hex[:5]
    manager = _lab(db, client, tag)
    key = _condition_key(client, admin, tag)
    body = client.get(f"/api/condition-keys/{key['id']}/reach", headers=manager.headers).json()
    assert body["test_count"] == 0
    assert body["definitions"] == []
    assert body["low"] is None and body["high"] is None

"""조건 묶음 — **한 시험에 조건이 한 벌뿐이 아니다.**

값이 칸마다 하나뿐이면(유일 인덱스가 시험+정의) 문서의 조건을 못 담는다. 사내 규격서를
옮겨 적다 드러난 네 모양(2026-09-30)을 여기서 지킨다:

    동작 -15 ~ 45 °C · 저장 -40 ~ 25 °C                      두 벌이 한 벌처럼 쓰인다
    -40 · -20 · 25 · 85 °C                                  이산 점 넷
    80 °C 80% 120h · 불량 시 70 °C 90% 360h                  주 조건과 예외
    70 °C 1h -> 25 °C 1h -> 30 °C 1h -> 25 °C 1h, 24 cycle   프로파일

**뭉개지면 없는 시험을 적은 것이 된다** — 동작과 저장을 한 벌로 합치면 -40 ~ 45 라는, 문서에
없는 조건이 생기고 그 조건으로 장비를 고른다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.workspaces.models import Workspace
from tests.api.conftest import Signed, division_term_id
from tests.api.test_reliability_tests import _signed_in


def _definition(client: TestClient, admin: Signed, label: str, key_id: str, unit: str) -> str:
    made = client.post(
        "/api/attribute-definitions",
        json={
            "target": "reliability_test",
            "label": label,
            "kind": "condition",
            "unit": unit,
            "condition_key_id": key_id,
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def _rows(body: dict[str, Any], definition_id: str) -> list[tuple[Any, ...]]:
    """그 칸의 줄들을 (묶음, 차례, 값) 로 — 서버가 준 순서 그대로."""
    return [
        (one["set_label"], one["step_order"], one["num_min"], one["num_max"], one["num_value"])
        for one in body["attributes"]
        if one["definition_id"] == definition_id
    ]


def test_같은_칸이_묶음마다_한_줄씩_선다(
    client: TestClient, db: Session, admin: Signed, condition_ids: dict[str, str]
) -> None:
    """동작 -15 ~ 45 와 저장 -40 ~ 25 는 **같은 칸 두 줄**이다."""
    tag = "a" + uuid.uuid4().hex[:5]
    lab = Workspace(
        slug=f"lab-{tag}", name="신뢰성팀", division_term_id=division_term_id(db, "vd")
    )
    db.add(lab)
    db.commit()
    manager = _signed_in(client, db, lab, "manager")
    temperature = _definition(
        client, admin, f"시험 온도-{tag}", condition_ids["temperature"], "degC"
    )

    made = client.post(
        "/api/reliability-tests",
        json={
            "division_code": "vd",
            "name": f"동작저장-{tag}",
            "attributes": [
                {
                    "definition_id": temperature,
                    "set_label": "동작",
                    "num_min": -15,
                    "num_max": 45,
                    "unit": "degC",
                },
                {
                    "definition_id": temperature,
                    "set_label": "저장",
                    "num_min": -40,
                    "num_max": 25,
                    "unit": "degC",
                },
            ],
        },
        headers=manager.headers,
    )
    assert made.status_code == 201, made.text
    assert _rows(made.json(), temperature) == [
        ("동작", None, -15.0, 45.0, None),
        ("저장", None, -40.0, 25.0, None),
    ]
    # **사람이 읽는 글자도 따로 선다** — 한 줄로 뭉치면 -40 ~ 45 로 읽힌다.
    shown = {one["set_label"]: one["display"] for one in made.json()["attributes"]}
    assert shown["동작"] == "-15 ~ 45 degC"
    assert shown["저장"] == "-40 ~ 25 degC"


def test_묶음이_없으면_예전처럼_칸마다_하나다(
    client: TestClient, db: Session, admin: Signed, condition_ids: dict[str, str]
) -> None:
    """묶음을 안 적은 같은 칸 두 줄은 **하나로 눌린다.**

    안 그러면 「칸마다 하나」 라는, 묶음 이전부터 있던 규칙이 조용히 깨진다 — 같은 칸이
    이름 없이 두 줄로 들어와 어느 쪽이 참인지 아무도 모르게 된다.
    """
    tag = "a" + uuid.uuid4().hex[:5]
    lab = Workspace(
        slug=f"lab-{tag}", name="신뢰성팀", division_term_id=division_term_id(db, "vd")
    )
    db.add(lab)
    db.commit()
    manager = _signed_in(client, db, lab, "manager")
    temperature = _definition(
        client, admin, f"시험 온도-{tag}", condition_ids["temperature"], "degC"
    )

    made = client.post(
        "/api/reliability-tests",
        json={
            "division_code": "vd",
            "name": f"한벌-{tag}",
            "attributes": [
                {"definition_id": temperature, "num_min": 10, "unit": "degC"},
                {"definition_id": temperature, "num_min": 20, "unit": "degC"},
            ],
        },
        headers=manager.headers,
    )
    assert made.status_code == 201, made.text
    assert _rows(made.json(), temperature) == [(None, None, 20.0, None, None)]


def test_이산_점_넷은_구간이_아니다(
    client: TestClient, db: Session, admin: Signed, condition_ids: dict[str, str]
) -> None:
    """-40 · -20 · 25 · 85 °C 를 -40 ~ 85 로 뭉치면 **그 사이 아무 온도나** 된다는 뜻이 된다.

    문서는 그런 말을 한 적이 없고, 그 구간으로 장비를 고른다.
    """
    tag = "a" + uuid.uuid4().hex[:5]
    lab = Workspace(
        slug=f"lab-{tag}", name="신뢰성팀", division_term_id=division_term_id(db, "vd")
    )
    db.add(lab)
    db.commit()
    manager = _signed_in(client, db, lab, "manager")
    temperature = _definition(
        client, admin, f"시험 온도-{tag}", condition_ids["temperature"], "degC"
    )

    made = client.post(
        "/api/reliability-tests",
        json={
            "division_code": "vd",
            "name": f"이산점-{tag}",
            "attributes": [
                {
                    "definition_id": temperature,
                    "set_label": "시험 점",
                    "step_order": step,
                    "num_value": value,
                    "unit": "degC",
                }
                for step, value in enumerate([-40, -20, 25, 85], 1)
            ],
        },
        headers=manager.headers,
    )
    assert made.status_code == 201, made.text
    assert _rows(made.json(), temperature) == [
        ("시험 점", 1, None, None, -40.0),
        ("시험 점", 2, None, None, -20.0),
        ("시험 점", 3, None, None, 25.0),
        ("시험 점", 4, None, None, 85.0),
    ]
    # **점은 폭이 없다** — 「-40 이상」 으로 읽히면 없는 여유를 만들어 준 셈이 된다.
    points = [
        one["display"]
        for one in made.json()["attributes"]
        if one["definition_id"] == temperature
    ]
    assert points == ["-40 degC", "-20 degC", "25 degC", "85 degC"]


def test_주_조건과_예외가_함께_선다(
    client: TestClient, db: Session, admin: Signed, condition_ids: dict[str, str]
) -> None:
    """80 °C 80% 120h · 불량 시 70 °C 90% 360h — 묶음 이름으로 가른다."""
    tag = "a" + uuid.uuid4().hex[:5]
    lab = Workspace(
        slug=f"lab-{tag}", name="신뢰성팀", division_term_id=division_term_id(db, "vd")
    )
    db.add(lab)
    db.commit()
    manager = _signed_in(client, db, lab, "manager")
    temperature = _definition(
        client, admin, f"시험 온도-{tag}", condition_ids["temperature"], "degC"
    )
    hours = _definition(client, admin, f"유지 시간-{tag}", condition_ids["duration"], "h")

    made = client.post(
        "/api/reliability-tests",
        json={
            "division_code": "vd",
            "name": f"주예외-{tag}",
            "attributes": [
                {
                    "definition_id": temperature,
                    "set_label": "주",
                    "num_min": 80,
                    "unit": "degC",
                },
                {"definition_id": hours, "set_label": "주", "num_min": 120, "unit": "h"},
                {
                    "definition_id": temperature,
                    "set_label": "불량 시",
                    "num_min": 70,
                    "unit": "degC",
                },
                {"definition_id": hours, "set_label": "불량 시", "num_min": 360, "unit": "h"},
            ],
        },
        headers=manager.headers,
    )
    assert made.status_code == 201, made.text
    got = [
        (one["set_label"], one["label"].split("-")[0], one["num_min"])
        for one in made.json()["attributes"]
        if one["definition_id"] in (temperature, hours)
    ]
    # **묶음끼리 뭉쳐 선다** — 칸 순서로만 늘어놓으면 주의 온도와 예외의 온도가 나란히 서고,
    # 읽는 사람은 그 둘이 한 벌인 줄 안다.
    assert got == [
        ("불량 시", "시험 온도", 70.0),
        ("불량 시", "유지 시간", 360.0),
        ("주", "시험 온도", 80.0),
        ("주", "유지 시간", 120.0),
    ]


def test_프로파일은_차례로_서고_사이클은_묶음_전체에_걸린다(
    client: TestClient, db: Session, admin: Signed, condition_ids: dict[str, str]
) -> None:
    """70 °C 1h -> 25 °C 1h -> 30 °C 1h -> 25 °C 1h, 24 cycle.

    몇 번 도는지는 **차례 없는 「사이클 수」** 다 — 묶음에 「몇 번 도나」 칸을 따로 안 만든
    것은, 그것이 이미 조건 축이기 때문이다.
    """
    tag = "a" + uuid.uuid4().hex[:5]
    lab = Workspace(
        slug=f"lab-{tag}", name="신뢰성팀", division_term_id=division_term_id(db, "vd")
    )
    db.add(lab)
    db.commit()
    manager = _signed_in(client, db, lab, "manager")
    temperature = _definition(
        client, admin, f"시험 온도-{tag}", condition_ids["temperature"], "degC"
    )
    hours = _definition(client, admin, f"유지 시간-{tag}", condition_ids["duration"], "h")
    cycles = _definition(client, admin, f"사이클 수-{tag}", condition_ids["cycles"], "회")

    steps: list[dict[str, Any]] = [
        {"definition_id": cycles, "set_label": "온도 사이클", "num_value": 24},
    ]
    for step, (degrees, hold) in enumerate([(70, 1), (25, 1), (30, 1), (25, 1)], 1):
        steps.append(
            {
                "definition_id": temperature,
                "set_label": "온도 사이클",
                "step_order": step,
                "num_value": degrees,
                "unit": "degC",
            }
        )
        steps.append(
            {
                "definition_id": hours,
                "set_label": "온도 사이클",
                "step_order": step,
                "step_label": "유지",
                "num_value": hold,
                "unit": "h",
            }
        )

    made = client.post(
        "/api/reliability-tests",
        json={"division_code": "vd", "name": f"프로파일-{tag}", "attributes": steps},
        headers=manager.headers,
    )
    assert made.status_code == 201, made.text
    rows = [
        (one["step_order"], one["label"].split("-")[0], one["num_value"])
        for one in made.json()["attributes"]
        if one["set_label"] == "온도 사이클"
    ]
    assert rows == [
        (None, "사이클 수", 24.0),
        (1, "시험 온도", 70.0),
        (1, "유지 시간", 1.0),
        (2, "시험 온도", 25.0),
        (2, "유지 시간", 1.0),
        (3, "시험 온도", 30.0),
        (3, "유지 시간", 1.0),
        (4, "시험 온도", 25.0),
        (4, "유지 시간", 1.0),
    ]
    first = [one for one in made.json()["attributes"] if one["step_order"] == 1]
    assert [one["step_label"] for one in first] == [None, "유지"]


def test_고치면_그_묶음만_바뀐다(
    client: TestClient, db: Session, admin: Signed, condition_ids: dict[str, str]
) -> None:
    """수정은 통째 교체다 — **묶음까지 함께 보내야 그 줄이 제자리로 간다.**"""
    tag = "a" + uuid.uuid4().hex[:5]
    lab = Workspace(
        slug=f"lab-{tag}", name="신뢰성팀", division_term_id=division_term_id(db, "vd")
    )
    db.add(lab)
    db.commit()
    manager = _signed_in(client, db, lab, "manager")
    temperature = _definition(
        client, admin, f"시험 온도-{tag}", condition_ids["temperature"], "degC"
    )
    made = client.post(
        "/api/reliability-tests",
        json={
            "division_code": "vd",
            "name": f"고치기-{tag}",
            "attributes": [
                {
                    "definition_id": temperature,
                    "set_label": "동작",
                    "num_min": -15,
                    "num_max": 45,
                    "unit": "degC",
                },
                {
                    "definition_id": temperature,
                    "set_label": "저장",
                    "num_min": -40,
                    "num_max": 25,
                    "unit": "degC",
                },
            ],
        },
        headers=manager.headers,
    )
    assert made.status_code == 201, made.text
    test_id = made.json()["id"]

    fixed = client.patch(
        f"/api/reliability-tests/{test_id}",
        json={
            "attributes": [
                {
                    "definition_id": temperature,
                    "set_label": "동작",
                    "num_min": -15,
                    "num_max": 45,
                    "unit": "degC",
                },
                {
                    "definition_id": temperature,
                    "set_label": "저장",
                    "num_min": -50,
                    "num_max": 25,
                    "unit": "degC",
                },
            ]
        },
        headers=manager.headers,
    )
    assert fixed.status_code == 200, fixed.text
    assert _rows(fixed.json(), temperature) == [
        ("동작", None, -15.0, 45.0, None),
        ("저장", None, -50.0, 25.0, None),
    ]

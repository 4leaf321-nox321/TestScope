"""이름 유일성의 자리 · 묶음을 아는 거르기 · 장비 속성 거르기.

셋 다 **실제 자료와 부딪혀 드러난 것**이다(2026-09-30).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.workspaces.models import Workspace
from tests.api.conftest import Signed, division_term_id
from tests.api.test_reliability_tests import _signed_in


def _lab(db: Session, client: TestClient, tag: str) -> tuple[Signed, str]:
    lab = Workspace(
        slug=f"lab-{tag}", name="신뢰성팀", division_term_id=division_term_id(db, "vd")
    )
    db.add(lab)
    db.commit()
    return _signed_in(client, db, lab, "manager"), f"lab-{tag}"


def _definitions(client: TestClient, who: Signed) -> dict[str, dict[str, Any]]:
    got = client.get(
        "/api/attribute-definitions",
        params={"target": "reliability_test"},
        headers=who.headers,
    )
    assert got.status_code == 200, got.text
    return {one["key"]: one for one in got.json()}


def _group_term(client: TestClient, admin: Signed, value: str) -> str:
    made = client.post(
        "/api/vocabularies/product_group/terms", json={"value": value}, headers=admin.headers
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


# ── 이름 유일성의 자리 ────────────────────────────────────────────────────────


def test_적용군이_다르면_같은_이름이_들어간다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """**이름만으로 유일하게 두었더니 실제 문서와 부딪혔다.**

    같은 이름이지만 적용군이 다른 별개의 시험이 있고, 제품군마다 제 규격서가 제 판을
    갖는다. 634장 중 202장이 그렇게 막혔고, 이름을 선점당한 17건은 아예 못 들어왔다 —
    막은 것이 중복이 아니라 **서로 다른 시험**이었다.
    """
    tag = "a" + uuid.uuid4().hex[:5]
    manager, _ = _lab(db, client, tag)
    spec = _definitions(client, manager)["reliability_product_group"]
    first = _group_term(client, admin, f"휴대폰-{tag}")
    second = _group_term(client, admin, f"TV-{tag}")

    made = [
        client.post(
            "/api/reliability-tests",
            json={
                "division_code": "vd",
                "name": f"고온고습 1000h {tag}",
                "attributes": [{"definition_id": spec["id"], "term_id": group}],
            },
            headers=manager.headers,
        )
        for group in (first, second)
    ]
    assert [one.status_code for one in made] == [201, 201], [one.text for one in made]

    # **같은 적용군이면 여전히 막는다** — 그 둘은 같은 시험이다.
    again = client.post(
        "/api/reliability-tests",
        json={
            "division_code": "vd",
            "name": f"고온고습 1000h {tag}",
            "attributes": [{"definition_id": spec["id"], "term_id": first}],
        },
        headers=manager.headers,
    )
    assert again.status_code == 409, again.text
    assert again.json()["error"]["details"]["product_group_term_id"] == first


def test_규격서가_다르면_같은_이름이_들어간다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """제품군마다 **제 규격서가 제 판을 갖는다.**"""
    tag = "a" + uuid.uuid4().hex[:5]
    manager, slug = _lab(db, client, tag)
    spec = _definitions(client, manager)["reliability_spec_document"]
    documents = [
        client.post(
            "/api/spec-documents",
            json={"workspace_slug": slug, "code": f"MX-{tag}-{n}", "title": f"규격 {n}"},
            headers=manager.headers,
        ).json()["id"]
        for n in (1, 2)
    ]

    made = [
        client.post(
            "/api/reliability-tests",
            json={
                "division_code": "vd",
                "name": f"열충격 {tag}",
                "attributes": [{"definition_id": spec["id"], "document_id": document}],
            },
            headers=manager.headers,
        )
        for document in documents
    ]
    assert [one.status_code for one in made] == [201, 201], [one.text for one in made]


def test_가를_근거가_없으면_예전처럼_막는다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """**적용군도 규격서도 없으면 이름 하나다.**

    수백 건을 적재하는 동안 동명이 쌓이는 것을 막는 장치가 거기 남아 있어야 한다 —
    가르고 싶으면 가르는 근거를 적으라는 뜻이기도 하다.
    """
    tag = "a" + uuid.uuid4().hex[:5]
    manager, _ = _lab(db, client, tag)
    first = client.post(
        "/api/reliability-tests",
        json={"division_code": "vd", "name": f"염수분무 {tag}"},
        headers=manager.headers,
    )
    assert first.status_code == 201, first.text
    again = client.post(
        "/api/reliability-tests",
        json={"division_code": "vd", "name": f"염수분무{tag}"},
        headers=manager.headers,
    )
    assert again.status_code == 409, again.text
    # **무엇을 하면 되는지 말한다** — 「같은 이름이 있습니다」 만으로는 막다른 길이다.
    assert "적용군" in again.json()["error"]["message"]


def test_한쪽만_적힌_것과_안_적힌_것은_다른_자리다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """안 적은 것을 「아무거나」 로 받아 주면, 적어 둔 사람의 줄이 안 적은 사람의 줄에
    밀린다."""
    tag = "a" + uuid.uuid4().hex[:5]
    manager, _ = _lab(db, client, tag)
    spec = _definitions(client, manager)["reliability_product_group"]
    group = _group_term(client, admin, f"웨어러블-{tag}")

    bare = client.post(
        "/api/reliability-tests",
        json={"division_code": "vd", "name": f"낙하 {tag}"},
        headers=manager.headers,
    )
    assert bare.status_code == 201, bare.text
    tagged = client.post(
        "/api/reliability-tests",
        json={
            "division_code": "vd",
            "name": f"낙하 {tag}",
            "attributes": [{"definition_id": spec["id"], "term_id": group}],
        },
        headers=manager.headers,
    )
    assert tagged.status_code == 201, tagged.text


# ── 묶음을 아는 거르기 ────────────────────────────────────────────────────────


def test_묶음을_지정해_거를_수_있다(
    client: TestClient, db: Session, admin: Signed, condition_ids: dict[str, str]
) -> None:
    """**주 조건 70 °C · 불량 시 90 °C 인 시험이 `temp>=80` 에 걸렸다** — 어느 쪽도
    80을 주 조건으로 요구하지 않는데."""
    tag = "a" + uuid.uuid4().hex[:5]
    manager, _ = _lab(db, client, tag)
    made = client.post(
        "/api/attribute-definitions",
        json={
            "target": "reliability_test",
            "label": f"시험 온도-{tag}",
            "kind": "condition",
            "unit": "degC",
            "condition_key_id": condition_ids["temperature"],
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    definition = made.json()
    key = definition["key"]

    test = client.post(
        "/api/reliability-tests",
        json={
            "division_code": "vd",
            "name": f"주예외 {tag}",
            "attributes": [
                # **점으로 적는다.** 「70 이상」(num_min만)은 80 에 닿는 것이 맞다 —
                # 빈 끝은 제한 없음이다(ADR 0003). 주 조건 70 °C 는 점이다.
                {
                    "definition_id": definition["id"],
                    "set_label": "주",
                    "num_value": 70,
                    "unit": "degC",
                },
                {
                    "definition_id": definition["id"],
                    "set_label": "불량 시",
                    "num_value": 90,
                    "unit": "degC",
                },
            ],
        },
        headers=manager.headers,
    )
    assert test.status_code == 201, test.text
    name = test.json()["name"]

    def found(attr: str) -> list[str]:
        got = client.get(
            "/api/reliability-tests",
            params={"division": "vd", "status": "all", "attr": attr},
            headers=manager.headers,
        )
        assert got.status_code == 200, got.text
        return [one["name"] for one in got.json()["items"]]

    # 묶음을 안 가리면 예전 그대로 — 한 줄이라도 닿으면 걸린다.
    assert name in found(f"{key}>=80")
    # **주 묶음으로 물으면 안 걸린다** — 주 조건은 70 이다.
    assert name not in found(f"{key}@주>=80")
    # 불량 시 묶음으로 물으면 걸린다.
    assert name in found(f"{key}@불량 시>=80")
    # 없는 묶음으로 물으면 아무것도 안 걸린다.
    assert name not in found(f"{key}@없는묶음>=0")


# ── 장비 속성 거르기 ─────────────────────────────────────────────────────────


def test_장비도_속성_값으로_거른다(client: TestClient, db: Session, admin: Signed) -> None:
    """백엔드는 진작 받고 있었는데 **MCP 가 그 칸을 안 넘겼다** — AI 는 「투자 연도
    2020 이후 장비」 를 못 물었다."""
    tag = "a" + uuid.uuid4().hex[:5]
    made = client.post(
        "/api/attribute-definitions",
        json={"target": "equipment", "label": f"투자 연도-{tag}", "kind": "number"},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    got = client.get(
        "/api/equipment",
        params={"attr": f"{made.json()['key']}>=2020"},
        headers=admin.headers,
    )
    assert got.status_code == 200, got.text

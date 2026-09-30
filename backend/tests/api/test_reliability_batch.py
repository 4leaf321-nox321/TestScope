"""묶음 등록과 문서 단위 검토 — **한 문서에서 나온 줄은 함께 올라오고 함께 읽힌다.**

AI 가 규격서 한 권에서 시험 스무 건을 뽑는다. 한 건씩 스무 번 부르면 열 번째에서 끊겼을 때
앞의 아홉은 들어가 있고 뒤의 열은 없는데, 부른 쪽은 그 경계를 모른다. 그리고 스무 건이
한 문서에서 나왔다는 사실이 어디에도 안 남아, 검토하는 사람은 그것을 스무 개의 따로 난
일로 본다 — 같은 문서에서 나온 줄은 같은 실수를 함께 하는데 그 결이 안 보인다.
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


def _document(client: TestClient, who: Signed, slug: str, code: str) -> str:
    made = client.post(
        "/api/spec-documents",
        json={"workspace_slug": slug, "code": code, "title": "고온고습 시험 기준"},
        headers=who.headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def test_묶음으로_올리면_줄마다_결과가_온다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """**전부 되거나 전부 안 되거나로 두지 않는다.**

    스무 줄 중 하나가 이름이 겹친다고 열아홉이 함께 막히면, 부른 쪽은 그 하나를 고치려고
    스무 줄을 다시 보내다 하나를 빠뜨린다.
    """
    tag = "a" + uuid.uuid4().hex[:5]
    manager = _lab(db, client, tag)

    first = client.post(
        "/api/reliability-tests",
        json={"division_code": "vd", "name": f"이미 있는 시험-{tag}"},
        headers=manager.headers,
    )
    assert first.status_code == 201, first.text

    got = client.post(
        "/api/reliability-tests/batch",
        json={
            "division_code": "vd",
            "tests": [
                {"name": f"고온고습-{tag}", "purpose": "1000h"},
                {"name": f"이미 있는 시험-{tag}"},
                {"name": f"열충격-{tag}"},
            ],
        },
        headers=manager.headers,
    )
    assert got.status_code == 207, got.text
    body = got.json()
    assert body["requested"] == 3
    assert [one["name"] for one in body["created"]] == [f"고온고습-{tag}", f"열충격-{tag}"]
    # **이미 있는 시험은 막지 않고 그 값에 판을 붙인다**(0046) — 시험의 정체는 규격서 +
    # 이름 + 적용군이라, 다시 올리는 것은 같은 시험의 새 시점이다. 막으면 개정본을 올릴
    # 때 이백 줄이 전부 실패로 오고, 부른 쪽은 그것을 「이미 다 있다」 로 읽는다.
    assert [one["name"] for one in body["merged"]] == [f"이미 있는 시험-{tag}"]
    assert body["failed"] == []


def test_문서를_주면_줄마다_규격서가_걸리고_문서로_모아_볼_수_있다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """검토는 **문서 단위**다 — 스무 줄을 한 자리에 모으지 못하면 한 건씩 보다 같은
    오답을 스무 번 통과시킨다."""
    tag = "a" + uuid.uuid4().hex[:5]
    manager = _lab(db, client, tag)
    document = _document(client, manager, f"lab-{tag}", f"MX-REL-{tag}")

    got = client.post(
        "/api/reliability-tests/batch",
        json={
            "division_code": "vd",
            "document_id": document,
            "tests": [{"name": f"고온고습-{tag}"}, {"name": f"열충격-{tag}"}],
        },
        headers=manager.headers,
    )
    assert got.status_code == 207, got.text
    created = got.json()["created"]
    assert len(created) == 2
    for row in created:
        codes = [one["document_code"] for one in row["attributes"] if one["document_code"]]
        assert codes == [f"MX-REL-{tag}"], f"규격서가 안 걸렸습니다: {row['attributes']}"

    # 문서로 모아 본다.
    listed = client.get(
        "/api/reliability-tests",
        params={"division": "vd", "document": document},
        headers=manager.headers,
    )
    assert listed.status_code == 200, listed.text
    assert sorted(one["name"] for one in listed.json()["items"]) == [
        f"고온고습-{tag}",
        f"열충격-{tag}",
    ]

    # 문서를 안 주면 그 사업부의 다른 줄도 함께 온다 — 거르기가 실제로 좁힌 것이다.
    other = client.post(
        "/api/reliability-tests",
        json={"division_code": "vd", "name": f"문서 없는 시험-{tag}"},
        headers=manager.headers,
    )
    assert other.status_code == 201, other.text
    both = client.get(
        "/api/reliability-tests", params={"division": "vd"}, headers=manager.headers
    )
    names = {one["name"] for one in both.json()["items"]}
    assert f"문서 없는 시험-{tag}" in names
    still = client.get(
        "/api/reliability-tests",
        params={"division": "vd", "document": document},
        headers=manager.headers,
    )
    assert f"문서 없는 시험-{tag}" not in {one["name"] for one in still.json()["items"]}


def test_줄이_제_규격서를_적었으면_묶음이_안_덮는다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """한 문서가 다른 문서를 인용한다. 묶음이 준 문서로 덮으면 **더 정확한 값이 덜 정확한
    값에 밀린다.**"""
    tag = "a" + uuid.uuid4().hex[:5]
    manager = _lab(db, client, tag)
    outer = _document(client, manager, f"lab-{tag}", f"MX-REL-{tag}")
    inner = _document(client, manager, f"lab-{tag}", f"MX-SUB-{tag}")

    definitions = client.get(
        "/api/attribute-definitions",
        params={"target": "reliability_test"},
        headers=manager.headers,
    ).json()
    spec = next(one for one in definitions if one["key"] == "reliability_spec_document")

    got = client.post(
        "/api/reliability-tests/batch",
        json={
            "division_code": "vd",
            "document_id": outer,
            "tests": [
                {"name": f"바깥-{tag}"},
                {
                    "name": f"안쪽-{tag}",
                    "attributes": [{"definition_id": spec["id"], "document_id": inner}],
                },
            ],
        },
        headers=manager.headers,
    )
    assert got.status_code == 207, got.text
    by_name: dict[str, Any] = {one["name"]: one for one in got.json()["created"]}

    def codes(name: str) -> list[str]:
        return [
            one["document_code"] for one in by_name[name]["attributes"] if one["document_code"]
        ]

    assert codes(f"바깥-{tag}") == [f"MX-REL-{tag}"]
    assert codes(f"안쪽-{tag}") == [f"MX-SUB-{tag}"], "줄이 적은 규격서를 묶음이 덮었습니다"


def test_못_올리는_사업부면_한_줄도_안_들어간다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """**권한은 줄마다가 아니라 먼저 본다** — 못 올릴 사업부에 오백 번 시도할 이유가 없고,
    절반만 들어간 상태를 만들 이유는 더 없다."""
    tag = "a" + uuid.uuid4().hex[:5]
    manager = _lab(db, client, tag)  # vd 사업부의 관리자
    got = client.post(
        "/api/reliability-tests/batch",
        json={"division_code": "mx", "tests": [{"name": f"남의 사업부-{tag}"}]},
        headers=manager.headers,
    )
    assert got.status_code == 403, got.text
    listed = client.get(
        "/api/reliability-tests",
        params={"division": "mx", "status": "all"},
        headers=manager.headers,
    )
    assert f"남의 사업부-{tag}" not in {one["name"] for one in listed.json()["items"]}


def test_없는_문서를_주면_한_줄도_안_들어간다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """줄마다 같은 오류가 오백 번 나는 것을 막는다 — 그때 `failed` 오백 줄을 읽는 사람은
    무엇이 잘못됐는지 못 찾는다."""
    tag = "a" + uuid.uuid4().hex[:5]
    manager = _lab(db, client, tag)
    got = client.post(
        "/api/reliability-tests/batch",
        json={
            "division_code": "vd",
            "document_id": str(uuid.uuid4()),
            "tests": [{"name": f"없는 문서-{tag}"}],
        },
        headers=manager.headers,
    )
    assert got.status_code == 404, got.text
    listed = client.get(
        "/api/reliability-tests",
        params={"division": "vd", "status": "all"},
        headers=manager.headers,
    )
    assert f"없는 문서-{tag}" not in {one["name"] for one in listed.json()["items"]}

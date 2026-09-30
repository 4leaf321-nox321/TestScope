"""판마다 한 벌 — **규격서 하나에 시험이 한 벌만 붙던 것을 푼다.**

같은 규격서의 개정 14와 18에 이름이 같은 시험이 70개, 그중 36개는 조건이 다른데 먼저
올라간 판이 이기고 나머지는 409 로 막혔다(2026-09-30). 유일성 자리에 판이 없었다.

**판마다 복제한다.** 신뢰성 시험은 수백 건이고 개정이 잦지 않아 그 값이 싸다 — 대신
「이 판의 목록」 이 계산 없이 바로 나온다.
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


def _paper(client: TestClient, who: Signed, slug: str, tag: str) -> str:
    made = client.post(
        "/api/spec-documents",
        json={"workspace_slug": slug, "code": f"DGHT-{tag}", "title": "환경 시험 기준"},
        headers=who.headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def _revision(client: TestClient, who: Signed, document: str, label: str) -> str:
    made = client.post(
        f"/api/spec-documents/{document}/revisions",
        json={"label": label, "summary": f"개정 {label}"},
        headers=who.headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def _temperature(client: TestClient, admin: Signed, tag: str, key_id: str) -> dict[str, Any]:
    made = client.post(
        "/api/attribute-definitions",
        json={
            "target": "reliability_test",
            "label": f"시험 온도-{tag}",
            "kind": "condition",
            "unit": "degC",
            "condition_key_id": key_id,
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return dict(made.json())


def test_같은_이름이_판마다_따로_선다(client: TestClient, db: Session, admin: Signed) -> None:
    """**먼저 올라간 판이 이기던 것**을 푼다."""
    tag = "a" + uuid.uuid4().hex[:5]
    manager, slug = _lab(db, client, tag)
    paper = _paper(client, manager, slug, tag)
    old, new = _revision(client, manager, paper, "14"), _revision(client, manager, paper, "18")

    made = [
        client.post(
            "/api/reliability-tests",
            json={
                "division_code": "vd",
                "name": f"고온고습 1000h {tag}",
                "document_revision_id": revision,
            },
            headers=manager.headers,
        )
        for revision in (old, new)
    ]
    assert [one.status_code for one in made] == [201, 201], [one.text for one in made]
    assert [one.json()["document_revision_label"] for one in made] == ["14", "18"]

    # **같은 판에 같은 이름은 여전히 막는다** — 그 둘은 같은 시험이다.
    again = client.post(
        "/api/reliability-tests",
        json={
            "division_code": "vd",
            "name": f"고온고습 1000h {tag}",
            "document_revision_id": old,
        },
        headers=manager.headers,
    )
    assert again.status_code == 409, again.text
    assert again.json()["error"]["details"]["document_revision_id"] == old


def test_판으로_목록을_좁힌다(client: TestClient, db: Session, admin: Signed) -> None:
    """**계산이 없다** — 판마다 한 벌이라 이것이 곧 「이 판의 목록」 이다."""
    tag = "a" + uuid.uuid4().hex[:5]
    manager, slug = _lab(db, client, tag)
    paper = _paper(client, manager, slug, tag)
    old, new = _revision(client, manager, paper, "14"), _revision(client, manager, paper, "18")

    batch = client.post(
        "/api/reliability-tests/batch",
        json={
            "division_code": "vd",
            "document_id": paper,
            "document_revision_id": old,
            "tests": [{"name": f"고온고습 {tag}"}, {"name": f"열충격 {tag}"}],
        },
        headers=manager.headers,
    )
    assert batch.status_code == 207, batch.text
    assert len(batch.json()["created"]) == 2

    # 뒤 판은 같은 이름을 **다시** 올린다 — 판만 바꾼다.
    later = client.post(
        "/api/reliability-tests/batch",
        json={
            "division_code": "vd",
            "document_id": paper,
            "document_revision_id": new,
            "tests": [{"name": f"고온고습 {tag}"}, {"name": f"낙하 {tag}"}],
        },
        headers=manager.headers,
    )
    assert later.status_code == 207, later.text
    assert len(later.json()["created"]) == 2, later.text

    def names(revision: str) -> list[str]:
        got = client.get(
            "/api/reliability-tests",
            params={"division": "vd", "status": "all", "revision": revision},
            headers=manager.headers,
        )
        assert got.status_code == 200, got.text
        return sorted(one["name"] for one in got.json())

    assert names(old) == sorted([f"고온고습 {tag}", f"열충격 {tag}"])
    assert names(new) == sorted([f"고온고습 {tag}", f"낙하 {tag}"])


def test_줄이_제_판을_적으면_묶음이_안_덮는다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """한 묶음에 두 판이 섞인다 — 개정 18에서 **안 바뀐** 시험은 14의 판으로 남긴다."""
    tag = "a" + uuid.uuid4().hex[:5]
    manager, slug = _lab(db, client, tag)
    paper = _paper(client, manager, slug, tag)
    old, new = _revision(client, manager, paper, "14"), _revision(client, manager, paper, "18")
    got = client.post(
        "/api/reliability-tests/batch",
        json={
            "division_code": "vd",
            "document_id": paper,
            "document_revision_id": new,
            "tests": [
                {"name": f"바뀐 것 {tag}"},
                {"name": f"안 바뀐 것 {tag}", "document_revision_id": old},
            ],
        },
        headers=manager.headers,
    )
    assert got.status_code == 207, got.text
    by_name = {one["name"]: one for one in got.json()["created"]}
    assert by_name[f"바뀐 것 {tag}"]["document_revision_label"] == "18"
    assert by_name[f"안 바뀐 것 {tag}"]["document_revision_label"] == "14"


def test_없는_판을_주면_한_줄도_안_들어간다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """**없는 판을 그대로 받으면** 그 줄은 어느 판에도 안 속한 채로 남고, 「이 판의 목록」
    에서 영영 빠진다 — 올린 사람은 올렸다고 안다."""
    tag = "a" + uuid.uuid4().hex[:5]
    manager, _ = _lab(db, client, tag)
    got = client.post(
        "/api/reliability-tests/batch",
        json={
            "division_code": "vd",
            "document_revision_id": str(uuid.uuid4()),
            "tests": [{"name": f"없는 판 {tag}"}],
        },
        headers=manager.headers,
    )
    assert got.status_code == 404, got.text


def test_두_판을_견준다(
    client: TestClient, db: Session, admin: Signed, condition_ids: dict[str, str]
) -> None:
    """개정이 오면 딸린 수십 건 중 **무엇을 다시 봐야 하는지**가 문제다."""
    tag = "a" + uuid.uuid4().hex[:5]
    manager, slug = _lab(db, client, tag)
    paper = _paper(client, manager, slug, tag)
    old, new = _revision(client, manager, paper, "14"), _revision(client, manager, paper, "18")
    temperature = _temperature(client, admin, tag, condition_ids["temperature"])

    def put(revision: str, name: str, degrees: int | None) -> None:
        attrs = (
            [{"definition_id": temperature["id"], "num_min": degrees, "unit": "degC"}]
            if degrees is not None
            else []
        )
        got = client.post(
            "/api/reliability-tests",
            json={
                "division_code": "vd",
                "name": name,
                "document_revision_id": revision,
                "attributes": attrs,
            },
            headers=manager.headers,
        )
        assert got.status_code == 201, got.text

    put(old, f"그대로 {tag}", 85)
    put(old, f"조건 바뀜 {tag}", 85)
    put(old, f"없어짐 {tag}", 60)
    put(new, f"그대로 {tag}", 85)
    put(new, f"조건 바뀜 {tag}", 95)
    put(new, f"더해짐 {tag}", 40)

    got = client.get(
        "/api/reliability-tests/revision-compare",
        params={"before": old, "after": new},
        headers=manager.headers,
    )
    assert got.status_code == 200, got.text
    body = got.json()
    assert [one["name"] for one in body["added"]] == [f"더해짐 {tag}"]
    assert [one["name"] for one in body["removed"]] == [f"없어짐 {tag}"]
    assert [one["name"] for one in body["changed"]] == [f"조건 바뀜 {tag}"]
    assert body["unchanged_count"] == 1, "안 바뀐 것을 세야 개정의 범위가 보인다"
    # **무엇이 어떻게 바뀌었는지** 한 줄로 — 「바뀜」 만으로는 다시 열어 봐야 한다.
    difference = body["changed"][0]["differences"][0]
    assert difference["before"] == "85 degC 이상"
    assert difference["after"] == "95 degC 이상"


def test_다른_문서의_판끼리는_못_견준다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """견준 결과가 「전부 더해짐·전부 없어짐」 으로 나오면 읽는 사람이 그것을 개정으로
    읽는다."""
    tag = "a" + uuid.uuid4().hex[:5]
    manager, slug = _lab(db, client, tag)
    first = _paper(client, manager, slug, tag)
    second = client.post(
        "/api/spec-documents",
        json={"workspace_slug": slug, "code": f"OTHER-{tag}", "title": "다른 문서"},
        headers=manager.headers,
    ).json()["id"]
    got = client.get(
        "/api/reliability-tests/revision-compare",
        params={
            "before": _revision(client, manager, first, "1"),
            "after": _revision(client, manager, second, "1"),
        },
        headers=manager.headers,
    )
    assert got.status_code == 400, got.text
    assert got.json()["error"]["code"] == "TSC-RELIABILITY-0017"

"""한 시험은 한 줄, 과거 판은 **값에.**

같은 규격서의 개정 14와 18에 이름이 같은 시험이 70개, 그중 36개는 조건이 다른데 먼저
올라간 판이 이기고 나머지는 409 로 막혔다(2026-09-30).

판마다 시험을 복제해 봤더니(0045) 같은 시험이 판 수만큼 줄로 늘어났다 — 고칠 때 어느
줄을 고칠지 사람이 정해야 하고, 장비 판정·검색·색인이 같은 시험을 여러 건으로 셌다.
그래서 **시험은 한 줄**로 두고 판을 값에 붙인다(0046).

    시험의 정체 = 규격서 + 이름 + 적용군    (판은 자리가 아니다)
    값마다 `document_revision_id` 와 `is_current`
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


def test_같은_이름의_다른_판은_같은_시험이다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """**판은 자리가 아니다.** 개정 14와 18은 같은 시험의 두 시점이다."""
    tag = "a" + uuid.uuid4().hex[:5]
    manager, slug = _lab(db, client, tag)
    paper = _paper(client, manager, slug, tag)
    old = _revision(client, manager, paper, "14")
    new = _revision(client, manager, paper, "18")

    first = client.post(
        "/api/reliability-tests",
        json={
            "division_code": "vd",
            "name": f"고온고습 1000h {tag}",
            "document_revision_id": old,
        },
        headers=manager.headers,
    )
    assert first.status_code == 201, first.text

    # 한 건 등록은 **거절한다** — 사람이 이름을 다시 친 것이라면 그렇게 말해야 한다.
    again = client.post(
        "/api/reliability-tests",
        json={
            "division_code": "vd",
            "name": f"고온고습 1000h {tag}",
            "document_revision_id": new,
        },
        headers=manager.headers,
    )
    assert again.status_code == 409, again.text
    # **무엇을 하면 되는지 말한다** — 판이 다르면 그 시험을 고치면 된다.
    assert "다른 판이면" in again.json()["error"]["message"]

    # 묶음 적재는 **그 시험의 값에 판을 붙인다** — 개정 18을 올리는 것은 새 시험이 아니다.
    batch = client.post(
        "/api/reliability-tests/batch",
        json={
            "division_code": "vd",
            "document_revision_id": new,
            "tests": [{"name": f"고온고습 1000h {tag}"}],
        },
        headers=manager.headers,
    )
    assert batch.status_code == 207, batch.text
    assert batch.json()["created"] == []
    assert [one["id"] for one in batch.json()["merged"]] == [first.json()["id"]]
    assert batch.json()["merged"][0]["document_revision_label"] == "18"


def test_판으로_목록을_좁힌다(client: TestClient, db: Session, admin: Signed) -> None:
    """「이 판의 목록」 = **그 판에서 값이 적힌 시험.**

    개정 18이 손대지 않은 시험은 18의 목록에 안 뜬다 — 그것이 맞다.
    """
    tag = "a" + uuid.uuid4().hex[:5]
    manager, slug = _lab(db, client, tag)
    paper = _paper(client, manager, slug, tag)
    old = _revision(client, manager, paper, "14")
    new = _revision(client, manager, paper, "18")

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
    # 고온고습은 **있던 시험의 새 판**, 낙하는 새 시험.
    assert [one["name"] for one in later.json()["merged"]] == [f"고온고습 {tag}"]
    assert [one["name"] for one in later.json()["created"]] == [f"낙하 {tag}"]

    def names(revision: str) -> list[str]:
        got = client.get(
            "/api/reliability-tests",
            params={"division": "vd", "status": "all", "revision": revision},
            headers=manager.headers,
        )
        assert got.status_code == 200, got.text
        return sorted(one["name"] for one in got.json()["items"])

    assert names(old) == sorted([f"고온고습 {tag}", f"열충격 {tag}"])
    # 열충격은 18이 손대지 않았으므로 18의 목록에 없다.
    assert names(new) == sorted([f"고온고습 {tag}", f"낙하 {tag}"])

    # **줄은 셋뿐이다** — 판마다 복제하던 때는 넷이었다.
    everything = client.get(
        "/api/reliability-tests",
        params={"division": "vd", "status": "all"},
        headers=manager.headers,
    )
    assert len([one for one in everything.json()["items"] if tag in one["name"]]) == 3


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
        """묶음으로 올린다 — **있던 시험이면 그 값에 판이 붙는다.** 한 건 등록은 같은
        이름을 거절하므로(같은 시험이니까) 적재 경로가 이쪽이다."""
        attrs = (
            [{"definition_id": temperature["id"], "num_min": degrees, "unit": "degC"}]
            if degrees is not None
            else []
        )
        got = client.post(
            "/api/reliability-tests/batch",
            json={
                "division_code": "vd",
                "document_revision_id": revision,
                "tests": [{"name": name, "attributes": attrs}],
            },
            headers=manager.headers,
        )
        assert got.status_code == 207, got.text
        assert not got.json()["failed"], got.text

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
    # 한 줄 안의 두 시점이라 **앞뒤가 같은 시험**이다 — 줄을 잇는 수고가 없다.
    assert body["changed"][0]["before_id"] == body["changed"][0]["after_id"]
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


def test_과거_판의_값은_지금_값을_안_흉내낸다(
    client: TestClient, db: Session, admin: Signed, condition_ids: dict[str, str]
) -> None:
    """**이것이 이 설계의 가장 위험한 자리다.**

    값이 판마다 쌓이므로, 읽는 쪽이 `is_current` 를 안 걸면 과거 판의 조건으로 검색에
    답한다 — 그 답은 조용히 틀린다. 거르기·장비 판정·카드·이력을 한 번에 본다.
    """
    tag = "a" + uuid.uuid4().hex[:5]
    manager, slug = _lab(db, client, tag)
    paper = _paper(client, manager, slug, tag)
    old = _revision(client, manager, paper, "14")
    new = _revision(client, manager, paper, "18")
    temperature = _temperature(client, admin, tag, condition_ids["temperature"])
    key = temperature["key"]

    def load(revision: str, degrees: int) -> None:
        got = client.post(
            "/api/reliability-tests/batch",
            json={
                "division_code": "vd",
                "document_revision_id": revision,
                "tests": [
                    {
                        "name": f"온도 오름 {tag}",
                        "attributes": [
                            {
                                "definition_id": temperature["id"],
                                "num_value": degrees,
                                "unit": "degC",
                            }
                        ],
                    }
                ],
            },
            headers=manager.headers,
        )
        assert got.status_code == 207, got.text
        assert not got.json()["failed"], got.text

    load(old, 85)
    load(new, 95)

    rows = client.get(
        "/api/reliability-tests",
        # **태그로 좁힌다** — 쪽이 생긴 뒤로는 첫 쉰 줄에 내 줄이 없을 수 있다.
        params={"division": "vd", "status": "all", "q": tag},
        headers=manager.headers,
    ).json()["items"]
    mine = next(one for one in rows if one["name"] == f"온도 오름 {tag}")

    # ① 카드에는 **지금 값만** — 85 와 95 가 나란히 서면 어느 것이 조건인지 안 보인다.
    shown = [
        one["display"] for one in mine["attributes"] if one["label"] == temperature["label"]
    ]
    assert shown == ["95 degC"], shown

    # ② 거르기가 과거 값으로 안 걸린다.
    def found(attr: str) -> list[str]:
        got = client.get(
            "/api/reliability-tests",
            params={"division": "vd", "status": "all", "attr": attr},
            headers=manager.headers,
        )
        assert got.status_code == 200, got.text
        return [one["name"] for one in got.json()["items"]]

    assert f"온도 오름 {tag}" in found(f"{key}=95")
    assert f"온도 오름 {tag}" not in found(f"{key}=85"), "개정 14의 값으로 걸렸습니다"

    # ③ 이력에는 **둘 다** 있고, 어느 판의 것인지가 줄에 적혀 있다.
    history = client.get(
        f"/api/reliability-tests/{mine['id']}/value-history", headers=manager.headers
    )
    assert history.status_code == 200, history.text
    marks = sorted(
        (one["document_revision_label"], one["display"], one["is_current"])
        for one in history.json()
        if one["label"] == temperature["label"]
    )
    assert marks == [("14", "85 degC", False), ("18", "95 degC", True)]


def test_목록은_쪽으로_끊어_온다(client: TestClient, db: Session, admin: Signed) -> None:
    """운영에서 한 사업부에 **1784건**이 들어왔다. 통째로 그리면 브라우저가 멎는다 —
    줄마다 속성·시험 항목·장비 수가 딸려 오므로 응답부터 무겁다(2026-09-30)."""
    tag = "a" + uuid.uuid4().hex[:5]
    manager, _ = _lab(db, client, tag)
    got = client.post(
        "/api/reliability-tests/batch",
        json={
            "division_code": "vd",
            "tests": [{"name": f"쪽 {at:02d}-{tag}"} for at in range(7)],
        },
        headers=manager.headers,
    )
    assert got.status_code == 207, got.text

    def page(limit: int, offset: int) -> dict[str, Any]:
        found = client.get(
            "/api/reliability-tests",
            params={
                "division": "vd",
                "status": "all",
                "attr": [],
                "limit": limit,
                "offset": offset,
            },
            headers=manager.headers,
        )
        assert found.status_code == 200, found.text
        body: dict[str, Any] = found.json()
        return body

    first = page(3, 0)
    # **전체 수는 쪽과 따로 온다** — 이것이 없으면 화면이 「몇 쪽인가」 를 못 그린다.
    assert first["total"] >= 7
    assert len(first["items"]) == 3
    assert first["limit"] == 3 and first["offset"] == 0

    second = page(3, 3)
    assert len(second["items"]) == 3
    # 쪽이 겹치지 않는다 — 겹치면 같은 줄을 두 번 확인하게 된다.
    assert not ({one["id"] for one in first["items"]} & {one["id"] for one in second["items"]})

    # 상한을 넘겨 부르면 422 — 「전부 주세요」 로 우회할 수 없어야 쪽이 뜻을 갖는다.
    over = client.get(
        "/api/reliability-tests",
        params={"division": "vd", "limit": 5000},
        headers=manager.headers,
    )
    assert over.status_code == 422, over.text

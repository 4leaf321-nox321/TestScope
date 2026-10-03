"""판마다 줄, 목록은 **최신판만.**

0046 은 「한 시험은 한 줄, 과거 판은 값에」 로 갔다. 그 약속이 운영에서 깨졌다
(2026-10-01): 개정 14(117건)와 18(160건)을 올리니 겹치는 87건이 18 하나로 흡수되고,
**내용이 실제로 다른 36건은 개정 14 값이 저장되지 않았다.** 그러면서 묶음 적재는
`merged` 로 세어 성공처럼 보였다.

그래서 **판을 다시 줄의 자리로 올린다**(0049). 0045 로 되돌아가는 것처럼 보이지만,
그때 못 풀었던 「같은 시험이 판 수만큼 줄로 늘어나 목록이 부푼다」 를 여기서 함께 푼다:

    시험의 정체 = 규격서 + 이름 + 적용군 + **판**
    superseded_by_id            이 줄을 밀어낸 뒤 판의 줄. 비면 그것이 최신판
    목록의 기본                  최신판만. 지난 판은 `include_superseded` 나 `revision=`
    묶음 적재                    규격서를 주면 **판도 필수**
    병합                        같은 판의 재적재만. **무엇을 덮었는지 돌려준다**
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


def test_같은_이름의_다른_판은_다른_줄이고_목록은_최신판만(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """**판은 자리다**(0049). 개정 14와 18은 다른 줄이고, 목록은 18만 보여 준다.

    0046 은 반대로 갔었다 — 한 줄에 두 판의 값을 담으려 했는데, 운영에서 개정 18이 14를
    흡수하면서 **내용이 다른 36건의 14 값이 사라졌다.**
    """
    tag = "a" + uuid.uuid4().hex[:5]
    manager, slug = _lab(db, client, tag)
    paper = _paper(client, manager, slug, tag)
    old = _revision(client, manager, paper, "14")
    new = _revision(client, manager, paper, "18")
    name = f"고온고습 1000h {tag}"

    first = client.post(
        "/api/reliability-tests",
        json={"division_code": "vd", "name": name, "document_revision_id": old},
        headers=manager.headers,
    )
    assert first.status_code == 201, first.text

    # **같은 판에 같은 이름은 여전히 막는다** — 사람이 이름을 다시 친 것이다.
    twice = client.post(
        "/api/reliability-tests",
        json={"division_code": "vd", "name": name, "document_revision_id": old},
        headers=manager.headers,
    )
    assert twice.status_code == 409, twice.text

    # **다른 판은 들어간다.** 예전에는 여기서 409 가 났고, 그 409 가 「이미 다 있다」 로
    # 읽혀 개정 18의 160건이 통째로 막혔다.
    later = client.post(
        "/api/reliability-tests",
        json={"division_code": "vd", "name": name, "document_revision_id": new},
        headers=manager.headers,
    )
    assert later.status_code == 201, later.text
    assert later.json()["id"] != first.json()["id"]

    def listed(**params: object) -> list[str]:
        got = client.get(
            "/api/reliability-tests",
            params={"division": "vd", "status": "all", "q": tag, **params},
            headers=manager.headers,
        )
        assert got.status_code == 200, got.text
        return [one["document_revision_label"] for one in got.json()["items"]]

    # **기본은 최신판만** — 안 가리면 목록이 판 수만큼 부푼다.
    assert listed() == ["18"]
    # 지난 판은 일부러 펼쳐야 보인다.
    assert sorted(listed(include_superseded="true")) == ["14", "18"]
    # 판을 집어 물으면 그 판이 온다 — 가리면 이 물음이 늘 0건이 된다.
    assert listed(revision=old) == ["14"]


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
    # **판마다 줄이 선다**(0049) — 고온고습의 개정 18은 14의 줄에 안 붙는다. 붙였더니
    # 14의 값이 사라졌다. 병합은 같은 판을 다시 올릴 때만이다.
    assert later.json()["merged"] == []
    assert sorted(one["name"] for one in later.json()["created"]) == sorted(
        [f"고온고습 {tag}", f"낙하 {tag}"]
    )

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

    def everything(**params: object) -> list[str]:
        got = client.get(
            "/api/reliability-tests",
            params={"division": "vd", "status": "all", "q": tag, **params},
            headers=manager.headers,
        )
        assert got.status_code == 200, got.text
        return sorted(one["name"] for one in got.json()["items"])

    # **줄은 넷이지만 목록은 셋이다** — 고온고습의 개정 14가 18에 밀렸다. 판마다 줄을
    # 두되 목록이 부풀지 않게 하는 것이 0049 의 요점이다.
    assert everything() == sorted([f"고온고습 {tag}", f"열충격 {tag}", f"낙하 {tag}"])
    assert len(everything(include_superseded="true")) == 4


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
    # **앞뒤가 다른 줄이다**(0049). 그래서 짝은 줄 id 가 아니라 정체(규격서+이름+적용군)로
    # 맞춘다 — id 로 맞추면 갈린 줄이 전부 「더해짐 + 없어짐」 이 되고, 그 답은 개정
    # 하나에 백 건이 새로 생겼다고 말한다.
    assert body["changed"][0]["before_id"] != body["changed"][0]["after_id"]
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
    #
    # 판마다 줄이 서므로(0049) 두 값은 **다른 줄**에 있다 — 이력은 그 줄들을 가로질러
    # 모은다. 그러지 않으면 「개정 14에서는 얼마였나」 가 영영 답이 없다.
    history = client.get(
        f"/api/reliability-tests/{mine['id']}/value-history", headers=manager.headers
    )
    assert history.status_code == 200, history.text
    marks = [
        (one["document_revision_label"], one["display"], one["is_current"])
        for one in history.json()
        if one["label"] == temperature["label"]
    ]
    # **판 순서로 온다** — 뒤가 최신이다. `is_current` 는 「그 줄 안의 지금 값」 이라
    # 둘 다 참이다: 어느 판이 지금 쓰는 판인지는 `superseded_by_id` 가, 목록이 말한다.
    assert marks == [("14", "85 degC", True), ("18", "95 degC", True)]


def test_뒤_판이_앞_판을_안_삼킨다(
    client: TestClient, db: Session, admin: Signed, condition_ids: dict[str, str]
) -> None:
    """**운영에서 값이 사라진 그 자리**(2026-10-01).

    개정 14(117건)와 18(160건)을 올리니 겹치는 87건이 18 하나로 흡수되고, 내용이 실제로
    다른 36건은 **개정 14 값이 저장되지 않았다.** 그러면서 묶음 적재는 `merged` 로 세어
    성공처럼 보였다 — 버린 것이 어디에도 안 드러났다.
    """
    tag = "a" + uuid.uuid4().hex[:5]
    manager, slug = _lab(db, client, tag)
    paper = _paper(client, manager, slug, tag)
    old = _revision(client, manager, paper, "14")
    new = _revision(client, manager, paper, "18")
    temperature = _temperature(client, admin, tag, condition_ids["temperature"])
    name = f"열충격 {tag}"

    def put(revision: str, degrees: int) -> dict[str, Any]:
        got = client.post(
            "/api/reliability-tests/batch",
            json={
                "division_code": "vd",
                "document_id": paper,
                "document_revision_id": revision,
                "tests": [
                    {
                        "name": name,
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
        return dict(got.json())

    put(old, 85)
    later = put(new, 95)
    # **흡수가 아니라 새 줄이다.** 예전에는 여기가 `merged` 였고 85가 사라졌다.
    assert later["merged"] == []
    assert len(later["created"]) == 1

    # 두 판의 값이 **둘 다** 남는다 — 이것이 지켜지지 않아 36건이 사라졌다.
    rows = client.get(
        "/api/reliability-tests",
        params={"division": "vd", "status": "all", "q": tag, "include_superseded": "true"},
        headers=manager.headers,
    ).json()["items"]
    by_revision = {
        one["document_revision_label"]: [
            each["display"]
            for each in one["attributes"]
            if each["label"] == temperature["label"]
        ]
        for one in rows
    }
    assert by_revision == {"14": ["85 degC"], "18": ["95 degC"]}


def test_같은_판을_다시_올리면_무엇을_덮었는지_말한다(
    client: TestClient, db: Session, admin: Signed, condition_ids: dict[str, str]
) -> None:
    """**세는 것과 한 일을 말하는 것은 다르다.** 예전에는 `merged` 로 세기만 해서, 보낸
    값이 반영이 안 돼도 성공처럼 보였다."""
    tag = "a" + uuid.uuid4().hex[:5]
    manager, slug = _lab(db, client, tag)
    paper = _paper(client, manager, slug, tag)
    one = _revision(client, manager, paper, "14")
    temperature = _temperature(client, admin, tag, condition_ids["temperature"])

    def put(degrees: int) -> dict[str, Any]:
        got = client.post(
            "/api/reliability-tests/batch",
            json={
                "division_code": "vd",
                "document_id": paper,
                "document_revision_id": one,
                "tests": [
                    {
                        "name": f"고온고습 {tag}",
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
        return dict(got.json())

    put(85)
    # 같은 판을 다시 — 갈아 끼우는 것은 맞지만 **무엇을 덮었는지 말해야** 한다.
    changed = put(95)["merged"]
    assert len(changed) == 1
    assert changed[0]["action"] == "updated"
    assert changed[0]["changed"] == [temperature["label"]]

    # 덮은 것은 **감사에도** 남는다 — 응답은 부른 쪽만 보고, 반년 뒤에 「이 값 언제 누가
    # 바꿨나」 를 묻는 사람은 감사를 본다. 경로(묶음 적재)는 사유가 말한다.
    def audited() -> list[dict[str, Any]]:
        got = client.get(
            "/api/audit/entries?action=reliability_test.updated&limit=200",
            headers=admin.headers,
        )
        assert got.status_code == 200, got.text
        return [
            one for one in got.json()["items"] if one["target_id"] == changed[0]["test"]["id"]
        ]

    [entry] = audited()
    assert entry["reason"] == "같은 판을 다시 적재"
    shown = next(
        value for key, value in entry["changes"].items() if temperature["label"] in key
    )
    assert shown == {"before": "85 degC", "after": "95 degC"}

    # 같은 값을 또 보내면 바뀐 것이 없다 — 그것도 그대로 말한다. 감사도 늘지 않는다.
    same = put(95)["merged"]
    assert same[0]["action"] == "skipped"
    assert same[0]["changed"] == []
    assert "같음" in same[0]["reason"]
    assert len(audited()) == 1


def test_규격서를_주면_판도_있어야_한다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """**1509건이 판 없이 들어갔고, 그 길로 값이 사라졌다**(2026-10-01)."""
    tag = "a" + uuid.uuid4().hex[:5]
    manager, slug = _lab(db, client, tag)
    paper = _paper(client, manager, slug, tag)

    refused = client.post(
        "/api/reliability-tests/batch",
        json={
            "division_code": "vd",
            "document_id": paper,
            "tests": [{"name": f"고온고습 {tag}"}],
        },
        headers=manager.headers,
    )
    assert refused.status_code == 400, refused.text
    # **무엇을 하면 되는지 말한다** — 「판이 필요합니다」 만으로는 어디서 찾는지 모른다.
    assert "spec-documents" in refused.json()["error"]["message"]

    # 규격서가 없는 묶음은 개정을 말할 것이 없으므로 그대로 받는다.
    plain = client.post(
        "/api/reliability-tests/batch",
        json={"division_code": "vd", "tests": [{"name": f"규격서 없음 {tag}"}]},
        headers=manager.headers,
    )
    assert plain.status_code == 207, plain.text


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

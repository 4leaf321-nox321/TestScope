"""신뢰성 시험 — 부서가 등록하는, 제품 개발·검증을 위한 시험 절차.

「시험 항목」(장비가 할 수 있는 측정, 전사 공용)과 다른 층이다. 여기서 지키는 것 — 읽기는
누구나·쓰기는 그 부서의 관리자 · 같은 부서에 같은 이름은 하나 · 시험 항목 축의 값만 잇는다 ·
지우면 사라지되 감사에 남는다.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.audit.models import AuditEntry
from app.modules.auth import security
from app.modules.workspaces.models import Workspace, WorkspaceMember
from tests.api.conftest import Signed, category_id, site_id


def _term(client: TestClient, admin: Signed, axis: str, value: str) -> str:
    made = client.post(
        f"/api/vocabularies/{axis}/terms", json={"value": value}, headers=admin.headers
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


def _signed_in(client: TestClient, db: Session, workspace: Workspace, role: str) -> Signed:
    email = f"{role}-{uuid.uuid4().hex[:8]}@testscope.local"
    user = User(
        email=email,
        password_hash=security.hash_password("pw-" + role),
        display_name=role,
        status="active",
        home_workspace_id=workspace.id,
    )
    db.add(user)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=role))
    db.commit()
    token = client.post("/api/auth/login", json={"email": email, "password": "pw-" + role})
    return Signed(email=email, token=token.json()["access_token"], workspace=workspace.slug)


def test_그_부서의_관리자만_등록하고_누구나_본다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    tag = uuid.uuid4().hex[:6]
    lab = Workspace(slug=f"lab-{tag}", name="신뢰성팀")
    db.add(lab)
    db.commit()
    manager = _signed_in(client, db, lab, "manager")
    member = _signed_in(client, db, lab, "member")

    body = {"workspace_slug": lab.slug, "name": f"고온고습-{tag}", "purpose": "85/85 1000h"}
    assert (
        client.post("/api/reliability-tests", json=body, headers=member.headers).status_code
        == 403
    )
    made = client.post("/api/reliability-tests", json=body, headers=manager.headers)
    assert made.status_code == 201, made.text
    assert made.json()["can_edit"] is True

    # **다른 부서 사람도 본다** — 이 시스템의 물음은 부서를 가로지른다. 고치지는 못한다.
    seen = client.get(
        "/api/reliability-tests", params={"workspace": lab.slug}, headers=admin.headers
    )
    assert [one["name"] for one in seen.json()] == [f"고온고습-{tag}"]
    as_member = client.get(
        f"/api/reliability-tests/{made.json()['id']}", headers=member.headers
    )
    assert as_member.status_code == 200 and as_member.json()["can_edit"] is False

    # 같은 부서에 같은 이름은 하나 — 대소문자만 달라도.
    clash = client.post(
        "/api/reliability-tests",
        json={**body, "name": f"고온고습-{tag.upper()}"},
        headers=manager.headers,
    )
    assert clash.status_code == 409


def test_시험_항목을_잇고_그_부서의_장비_수를_센다(client: TestClient, admin: Signed) -> None:
    tag = uuid.uuid4().hex[:6]
    shock = _term(client, admin, "test_item", f"열충격-{tag}")
    site = site_id(client, admin)

    # 시험 항목 축이 아닌 값은 거절 — 「인장」 자리에 「3동」 이 그려지지 않게.
    wrong = client.post(
        "/api/reliability-tests",
        json={
            "workspace_slug": admin.workspace,
            "name": f"TS-{tag}",
            "test_item_term_ids": [site],
        },
        headers=admin.headers,
    )
    assert wrong.status_code == 400, wrong.text

    made = client.post(
        "/api/reliability-tests",
        json={
            "workspace_slug": admin.workspace,
            "name": f"TS-{tag}",
            "test_item_term_ids": [shock],
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    assert made.json()["test_items"][0]["equipment_count"] == 0

    equipment = client.post(
        "/api/equipment",
        json={
            "asset_no": f"CH-{tag}",
            "name": "열충격 챔버",
            "workspace_slug": admin.workspace,
            "site_term_id": site,
            "location": "2동",
            "category_term_id": category_id(client, admin),
        },
        headers=admin.headers,
    ).json()
    client.post(
        "/api/equipment-test-items",
        json={"equipment_id": equipment["id"], "test_item_term_id": shock},
        headers=admin.headers,
    )
    again = client.get(f"/api/reliability-tests/{made.json()['id']}", headers=admin.headers)
    assert again.json()["test_items"][0]["equipment_count"] == 1

    # 통째로 바꾼다 — 비우면 빈다. 이름만 고칠 때는 안 건드린다.
    client.patch(
        f"/api/reliability-tests/{made.json()['id']}",
        json={"name": f"TS2-{tag}"},
        headers=admin.headers,
    )
    kept = client.get(f"/api/reliability-tests/{made.json()['id']}", headers=admin.headers)
    assert len(kept.json()["test_items"]) == 1
    client.patch(
        f"/api/reliability-tests/{made.json()['id']}",
        json={"test_item_term_ids": []},
        headers=admin.headers,
    )
    emptied = client.get(f"/api/reliability-tests/{made.json()['id']}", headers=admin.headers)
    assert emptied.json()["test_items"] == []


def test_지우면_목록에서_빠지고_감사에_남는다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    tag = uuid.uuid4().hex[:6]
    made = client.post(
        "/api/reliability-tests",
        json={"workspace_slug": admin.workspace, "name": f"낙하-{tag}"},
        headers=admin.headers,
    ).json()
    gone = client.delete(f"/api/reliability-tests/{made['id']}", headers=admin.headers)
    assert gone.status_code == 204
    assert (
        client.get(f"/api/reliability-tests/{made['id']}", headers=admin.headers).status_code
        == 404
    )
    entry = db.scalar(
        select(AuditEntry).where(
            AuditEntry.action == "reliability_test.deleted",
            AuditEntry.target_id == uuid.UUID(made["id"]),
        )
    )
    assert entry is not None and f"낙하-{tag}" in entry.target_label
    # 지운 이름은 다시 쓸 수 있다 — 부분 유일 인덱스.
    again = client.post(
        "/api/reliability-tests",
        json={"workspace_slug": admin.workspace, "name": f"낙하-{tag}"},
        headers=admin.headers,
    )
    assert again.status_code == 201


def test_부서를_안_주면_전사_전부가_부서_순으로_온다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """전체 표 — 「누가 무슨 시험을 하나」 를 부서를 가로질러 본다. 읽기는 누구나."""
    tag = uuid.uuid4().hex[:6]
    lab = Workspace(slug=f"lab-{tag}", name="신뢰성팀", sort_order=999)
    db.add(lab)
    db.commit()
    manager = _signed_in(client, db, lab, "manager")
    for name in (f"열충격-{tag}", f"고온고습-{tag}"):
        made = client.post(
            "/api/reliability-tests",
            json={"workspace_slug": lab.slug, "name": name},
            headers=manager.headers,
        )
        assert made.status_code == 201, made.text
    listed = client.get("/api/reliability-tests", headers=admin.headers)
    assert listed.status_code == 200, listed.text
    mine = [one for one in listed.json() if one["workspace_slug"] == lab.slug]
    assert [one["name"] for one in mine] == [f"고온고습-{tag}", f"열충격-{tag}"]
    # 다른 부서 것도 같이 온다 — 이 부서 것만이 아니다.
    assert (
        any(one["workspace_slug"] != lab.slug for one in listed.json())
        or len(listed.json()) == 2
    )


def test_사내_시험_카드의_칸이_설치에_들어있다(client: TestClient, admin: Signed) -> None:
    """**카드 한 장이 곧 이 속성들이다.** 없으면 사람은 목적 칸에 조건을 몰아 적고,
    그렇게 적힌 조건은 `test_capability` 가 못 읽는다.

    조건 칸(`kind="condition"`)은 **축에 이어져 있어야** 한다 — 이어져 있지 않으면
    값은 저장되지만 장비 판정에 안 실린다.
    """
    rows = client.get(
        "/api/attribute-definitions",
        params={"target": "reliability_test"},
        headers=admin.headers,
    )
    assert rows.status_code == 200, rows.text
    by_label = {one["label"]: one for one in rows.json()}

    for label in (
        "유형",
        "적용군",
        # **규격서 칸은 없다.** 사내 규격서는 「참조 규격」 이 가리키는 규격에 **파일로**
        # 붙는다(2026-09-24) — 번호만 있고 원문이 없으면 읽을 수가 없고, 여러 시험이
        # 한 문서를 인용하므로 시험마다 값을 고르게 두면 같은 설명을 다시 적게 된다.
        "참조 규격",
        "시험 대상",
        "시험기·비품",
        "시료 수",
        "기타 조건",
        "시험 절차",
        "시험 방법",
        "판정 기준",
        "주의사항",
    ):
        assert label in by_label, f"「{label}」 칸이 없습니다"

    # 조건은 축에 이어져 있어야 판정이 된다.
    for label in ("시험 온도", "상대 습도", "가진 주파수", "가속도"):
        one = by_label[label]
        assert one["kind"] == "condition", label
        assert one["condition_key_id"], f"「{label}」 이 조건 축에 안 이어져 있습니다"

    # 고르는 칸은 온톨로지 축에 이어져 있어야 고를 것이 있다.
    for label in ("유형", "적용군"):
        assert by_label[label]["kind"] == "term", label
        assert by_label[label]["vocabulary_id"], f"「{label}」 이 축에 안 이어져 있습니다"

    assert by_label["참조 규격"]["kind"] == "method"
    assert by_label["시료 수"]["kind"] == "number"


def test_등급별_수량은_짝으로_담기고_이름_없는_숫자는_거절한다(
    client: TestClient, admin: Signed
) -> None:
    """「A등급 4 · B등급 4」 는 **값 하나가 아니다.** 글자로 뭉개 넣으면 사람은 읽어도
    기계는 못 읽고, 그러면 그 칸을 만든 뜻이 없다.

    **이름 없는 숫자는 안 받는다.** 「4」 만 남으면 그것이 A등급인지 1단계인지 적어 둔
    사람 말고는 아무도 모른다.
    """
    tag = uuid.uuid4().hex[:6]
    definitions = {
        one["label"]: one["id"]
        for one in client.get(
            "/api/attribute-definitions",
            params={"target": "reliability_test"},
            headers=admin.headers,
        ).json()
    }
    assert "등급별 수량" in definitions and "적용 사양 매트릭스" in definitions

    made = client.post(
        "/api/reliability-tests",
        json={
            "workspace_slug": admin.workspace,
            "name": f"짝 시험-{tag}",
            "attributes": [
                {
                    "definition_id": definitions["등급별 수량"],
                    "json_value": [
                        {"label": "A등급", "value": 4},
                        {"label": "B등급", "value": 4},
                    ],
                },
                {
                    "definition_id": definitions["적용 사양 매트릭스"],
                    "json_value": [
                        {
                            "label": "사양 A",
                            "entries": [
                                {"label": "A등급", "value": 4},
                                {"label": "B등급", "value": 2},
                            ],
                        }
                    ],
                },
            ],
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    values = {one["label"]: one for one in made.json()["attributes"]}

    # 값은 그대로 돌아오고, **읽는 글자는 서버가 만든다** — 화면·MCP·찾기가 같은 말을 쓴다.
    assert values["등급별 수량"]["json_value"] == [
        {"label": "A등급", "value": 4},
        {"label": "B등급", "value": 4},
    ]
    assert values["등급별 수량"]["display"] == "A등급 4 개 · B등급 4 개"
    assert values["적용 사양 매트릭스"]["display"] == "사양 A: A등급 4 개 · B등급 2 개"

    # 이름이 빈 줄은 거절한다.
    bad = client.post(
        "/api/reliability-tests",
        json={
            "workspace_slug": admin.workspace,
            "name": f"이름 없는 숫자-{tag}",
            "attributes": [
                {"definition_id": definitions["등급별 수량"], "json_value": [{"value": 4}]}
            ],
        },
        headers=admin.headers,
    )
    assert bad.status_code == 400, bad.text
    assert bad.json()["error"]["code"] == "TSC-ATTR-0011"


def test_조건은_한쪽만_적어도_되고_숫자로_못_적으면_비고에_적는다(
    client: TestClient, admin: Signed
) -> None:
    """**조건이 늘 두 값 사이인 것은 아니다.**

    「85 이상」 은 최대를 비운 것이고, 「상온」 은 숫자로 못 적는 것이다. 숫자가 없는 줄은
    사람이 읽고 장비 판정에는 안 실린다(`capability` 가 값 없는 조건을 「제한 없음」 으로
    넘긴다) — 그렇게라도 남겨야 카드가 시험을 다 말한다.

    그리고 조건 축은 **열하나 전부** 칸으로 서 있다. 넷만 있던 때는 「전압으로 도는 시험」 을
    적을 자리가 없었다.
    """
    tag = uuid.uuid4().hex[:6]
    rows = client.get(
        "/api/attribute-definitions",
        params={"target": "reliability_test"},
        headers=admin.headers,
    ).json()
    conditions = {one["label"]: one for one in rows if one["kind"] == "condition"}
    # 손으로 적던 넷 말고도 축이 있으면 칸이 있다.
    for label in ("시험 온도", "상대 습도", "전압", "토크", "충격 에너지"):
        assert label in conditions, f"「{label}」 조건 칸이 없습니다"

    made = client.post(
        "/api/reliability-tests",
        json={
            "workspace_slug": admin.workspace,
            "name": f"한쪽 조건-{tag}",
            "attributes": [
                # 85 이상 — 최대를 비운다.
                {"definition_id": conditions["시험 온도"]["id"], "num_min": 85},
                # 숫자로 못 적는 것.
                {"definition_id": conditions["전압"]["id"], "note": "규격에 따름"},
            ],
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    values = {one["label"]: one for one in made.json()["attributes"]}
    assert values["시험 온도"]["display"] == "85 degC 이상"
    assert values["전압"]["num_min"] is None and values["전압"]["note"] == "규격에 따름"

    # 숫자도 비고도 없으면 아무 말도 안 하는 줄이라 거절한다.
    empty = client.post(
        "/api/reliability-tests",
        json={
            "workspace_slug": admin.workspace,
            "name": f"빈 조건-{tag}",
            "attributes": [{"definition_id": conditions["토크"]["id"]}],
        },
        headers=admin.headers,
    )
    assert empty.status_code == 400, empty.text
    assert empty.json()["error"]["code"] == "TSC-ATTR-0011"

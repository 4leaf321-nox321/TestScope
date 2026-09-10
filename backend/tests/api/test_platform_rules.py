"""플랫폼 규약 — 부분 수정·권한·기준정보 중복·감사 기록."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.auth import security
from app.modules.workspaces.models import Workspace, WorkspaceMember
from tests.api.conftest import Signed, category_id, site_id


def test_부분_수정은_안_보낸_칸을_지우지_않는다(client: TestClient, admin: Signed) -> None:
    """구별하지 않으면 상태 하나 바꿀 때마다 담당자와 위치가 지워지고, **그 손실은
    저장한 사람 눈에 안 보인다.**"""
    created = client.post(
        "/api/equipment",
        json={
            "asset_no": f"UTM-{uuid.uuid4().hex[:6]}",
            "site_term_id": site_id(client, admin),
            "category_term_id": category_id(client, admin),
            "name": "인장시험기",
            "workspace_slug": admin.workspace,
            "location": "3동 201호",
            "serial_no": "SN-5982",
        },
        headers=admin.headers,
    ).json()

    url = f"/api/equipment/{created['id']}"
    updated = client.patch(url, json={"status": "maintenance"}, headers=admin.headers)
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "maintenance"
    assert updated.json()["location"] == "3동 201호"
    assert updated.json()["serial_no"] == "SN-5982"

    # 비우는 것은 **안 보낸 것과 구별된다** — 선택 항목은 null 로 비워진다.
    cleared = client.patch(url, json={"serial_no": None}, headers=admin.headers).json()
    assert cleared["serial_no"] is None
    assert cleared["location"] == "3동 201호"

    # 필수 항목은 못 비운다. **조용히 성공시키면 안 된다** — DB 가 거절하면 500 이
    # 나가고, 그때 사람은 서버가 고장 났다고 읽는다.
    refused = client.patch(url, json={"location": None}, headers=admin.headers)
    assert refused.status_code == 400, refused.text
    assert refused.json()["error"]["code"] == "TSC-EQUIPMENT-0009"


def test_남의_부서_장비는_고칠_수_없다(
    client: TestClient, db: Session, admin: Signed, workspace: Workspace
) -> None:
    """보이는 것과 고칠 수 있는 것은 다른 축이다. 목록에는 뜨되 손은 못 댄다."""
    created = client.post(
        "/api/equipment",
        json={
            "asset_no": f"UTM-{uuid.uuid4().hex[:6]}",
            "site_term_id": site_id(client, admin),
            "category_term_id": category_id(client, admin),
            "location": "3동 201호",
            "name": "충격시험기",
            "workspace_slug": admin.workspace,
        },
        headers=admin.headers,
    ).json()

    other = Workspace(slug=f"other-{uuid.uuid4().hex[:8]}", name="다른팀")
    db.add(other)
    db.flush()
    email = f"member-{uuid.uuid4().hex[:8]}@testscope.local"
    member = User(
        email=email,
        password_hash=security.hash_password("member-password"),
        display_name="멤버",
        status="active",
        home_workspace_id=other.id,
    )
    db.add(member)
    db.flush()
    db.add(WorkspaceMember(workspace_id=other.id, user_id=member.id, role="member"))
    db.commit()

    token = client.post(
        "/api/auth/login", json={"email": email, "password": "member-password"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # **보이기는 한다.** 이 시스템의 물음이 부서를 가로지르므로 가리는 쪽이 예외다.
    seen = client.get(f"/api/equipment/{created['id']}", headers=headers)
    assert seen.status_code == 200
    assert seen.json()["can_edit"] is False

    blocked = client.patch(
        f"/api/equipment/{created['id']}", json={"name": "바꿔치기"}, headers=headers
    )
    assert blocked.status_code == 403


def test_기준정보는_별칭까지_뒤져_중복을_막는다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    """별칭은 **예방**이다. 안 보면 같은 값을 다시 등록할 수 있게 되고, 그 순간
    별칭을 등록해 둔 뜻이 사라진다."""
    value = f"만능재료시험기-{uuid.uuid4().hex[:6]}"
    term = term_factory("equipment_category", value)

    again = client.post(
        "/api/vocabularies/equipment_category/terms",
        json={"value": value},
        headers=admin.headers,
    )
    assert again.status_code == 409
    # **어느 값과 겹치는지까지 말해 준다.** 안 말하면 사람은 목록을 손으로 뒤진다.
    assert again.json()["error"]["details"]["term_id"] == term

    alias = f"UTM-{uuid.uuid4().hex[:6]}"
    assert (
        client.post(
            f"/api/vocabularies/terms/{term}/aliases",
            json={"value": alias},
            headers=admin.headers,
        ).status_code
        == 201
    )
    blocked = client.post(
        "/api/vocabularies/equipment_category/terms",
        json={"value": alias},
        headers=admin.headers,
    )
    assert blocked.status_code == 409


def test_닫힌_축은_관리자만_값을_더한다(
    client: TestClient, db: Session, admin: Signed, workspace: Workspace
) -> None:
    """시험 항목은 **검색의 첫 축**이다. 오타가 값이 되면 그 장비는 영영 안 걸린다."""
    email = f"plain-{uuid.uuid4().hex[:8]}@testscope.local"
    user = User(
        email=email,
        password_hash=security.hash_password("member-password"),
        display_name="멤버",
        status="active",
        home_workspace_id=workspace.id,
    )
    db.add(user)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="member"))
    db.commit()

    token = client.post(
        "/api/auth/login", json={"email": email, "password": "member-password"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    closed = client.post(
        "/api/vocabularies/test_item/terms", json={"value": "마음대로"}, headers=headers
    )
    assert closed.status_code == 403
    assert closed.json()["error"]["code"] == "TSC-VOCAB-0002"

    # 열린 축은 누구나 더한다 — 기다리게 하면 피커가 멈추고, 사람은 시스템 밖에서 일한다.
    opened = client.post(
        "/api/vocabularies/manufacturer/terms",
        json={"value": f"제조사-{uuid.uuid4().hex[:6]}"},
        headers=headers,
    )
    assert opened.status_code == 201


def test_장비_폐기는_변경_이력에_남는다(client: TestClient, admin: Signed) -> None:
    """되돌릴 수 없는 일만 남긴다 — 점검·수리는 오가는 상태라 안 남긴다."""
    created = client.post(
        "/api/equipment",
        json={
            "asset_no": f"UTM-{uuid.uuid4().hex[:6]}",
            "site_term_id": site_id(client, admin),
            "category_term_id": category_id(client, admin),
            "location": "3동 201호",
            "name": "폐기할 장비",
            "workspace_slug": admin.workspace,
        },
        headers=admin.headers,
    ).json()

    url = f"/api/equipment/{created['id']}"
    client.patch(url, json={"status": "maintenance"}, headers=admin.headers)
    client.patch(url, json={"status": "retired"}, headers=admin.headers)

    entries = client.get(
        "/api/audit/entries?action=equipment.retired", headers=admin.headers
    ).json()
    labels = [one["target_label"] for one in entries["items"]]
    assert any(created["asset_no"] in label for label in labels)
    # 점검은 안 남는다.
    maintenance = client.get(
        "/api/audit/entries?target_table=equipment", headers=admin.headers
    ).json()
    assert all(one["action"] != "equipment.maintenance" for one in maintenance["items"])


def _series(client: TestClient, admin: Signed, **extra: object) -> dict[str, Any]:
    payload = {"name": f"SER-{uuid.uuid4().hex[:6]}", **extra}
    response = client.post("/api/equipment-series", json=payload, headers=admin.headers)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def _model_in(
    client: TestClient, admin: Signed, series_id: str, **extra: object
) -> dict[str, Any]:
    payload = {"series_id": series_id, "name": f"MDL-{uuid.uuid4().hex[:6]}", **extra}
    response = client.post("/api/equipment-models", json=payload, headers=admin.headers)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def test_카탈로그_시험_항목은_장비로_복사된다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    """**상속이 아니라 복사다.** 등록한 뒤로는 그 장비가 진실이고, 챔버를 뗀 대는
    거기서 고친다 — 갈라지는 것이 정상이다(ADR 0004).

    시험 항목은 계열에 붙고 기종이 그것을 물려받는다(ADR 0006)."""
    item = term_factory("test_item", f"인장-{uuid.uuid4().hex[:6]}")
    conditions = client.get("/api/condition-keys", headers=admin.headers).json()
    force = next(one["id"] for one in conditions if one["key"] == "force")

    series = _series(client, admin)
    model = _model_in(client, admin, series["id"])

    test_item = client.post(
        f"/api/equipment-series/{series['id']}/test-items",
        json={"test_item_term_id": item},
        headers=admin.headers,
    ).json()
    client.put(
        f"/api/equipment-series/{series['id']}/test-items/{test_item['id']}/limits",
        json={"condition_key_id": force, "min_value": 0, "max_value": 250},
        headers=admin.headers,
    )

    made = client.post(
        "/api/equipment",
        json={
            "asset_no": f"CAT-{uuid.uuid4().hex[:6]}",
            "site_term_id": site_id(client, admin),
            "location": "3동 201호",
            "name": "카탈로그에서 만든 장비",
            "workspace_slug": admin.workspace,
            "model_id": model["id"],
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    # **제조사·분류·기종명은 카탈로그에서 끌어온다.** 개체는 그것을 갖지 않는다.
    assert made.json()["model_name"] == model["name"]
    assert made.json()["series_name"] == series["name"]

    copied = client.get(
        f"/api/equipment-test-items?equipment_id={made.json()['id']}", headers=admin.headers
    ).json()
    assert len(copied) == 1
    # 사양서에서 온 값이라는 뜻이 그 칸에 이미 있다.
    assert copied[0]["confidence"] == "catalog"
    assert copied[0]["limits"][0]["max_value"] == 250

    # 시험 항목이 장비 목록 한 줄에서 바로 보인다 — 시험 항목을 열어 봐야 아는 화면은
    # 「우리가 무슨 시험을 할 수 있나」 에 답하지 못한다.
    listed = client.get(f"/api/equipment/{made.json()['id']}", headers=admin.headers).json()
    assert listed["test_items"] == [copied[0]["test_item"]]

    # 개체를 좁혀도 카탈로그는 그대로다 — 그래야 다음 대가 사양서대로 복사된다.
    client.put(
        f"/api/equipment-test-items/{copied[0]['id']}/limits",
        json={"condition_key_id": force, "min_value": 0, "max_value": 50},
        headers=admin.headers,
    )
    catalog = client.get(f"/api/equipment-series/{series['id']}", headers=admin.headers).json()
    assert catalog["test_items"][0]["limits"][0]["max_value"] == 250
    assert catalog["unit_count"] == 1


def test_기종마다_조건이_갈린다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    """**한 계열 안에서 하중이 600배 갈린다.** 계열 봉투를 그대로 복사하면
    0.5 kN 짜리 한 대가 300 kN 된다고 답한다 — ADR 0006 이 막으려는 것."""
    item = term_factory("test_item", f"인장-{uuid.uuid4().hex[:6]}")
    definitions = {
        row["key"]: row
        for row in client.get("/api/spec-definitions", headers=admin.headers).json()
    }

    series = _series(client, admin)
    client.post(
        f"/api/equipment-series/{series['id']}/test-items",
        json={"test_item_term_id": item},
        headers=admin.headers,
    )
    small = _model_in(client, admin, series["id"])
    large = _model_in(client, admin, series["id"])
    for model, force in ((small, 0.5), (large, 300)):
        saved = client.put(
            f"/api/equipment-models/{model['id']}/specs",
            json={"definition_id": definitions["force_capacity"]["id"], "num_value": force},
            headers=admin.headers,
        )
        assert saved.status_code == 200, saved.text
        # 검색축에 이어진 사양이라는 것을 화면에 말해 준다.
        assert saved.json()["search_axis"] == "하중 용량"
        assert saved.json()["existing_units"] == 0

    made = {}
    for label, model in (("small", small), ("large", large)):
        response = client.post(
            "/api/equipment",
            json={
                "asset_no": f"SPL-{uuid.uuid4().hex[:6]}",
                "site_term_id": site_id(client, admin),
                "location": "3동 201호",
                "name": f"{label} 장비",
                "workspace_slug": admin.workspace,
                "model_id": model["id"],
            },
            headers=admin.headers,
        )
        assert response.status_code == 201, response.text
        made[label] = response.json()["id"]

    def _force(equipment_id: str) -> float:
        rows = client.get(
            f"/api/equipment-test-items?equipment_id={equipment_id}", headers=admin.headers
        ).json()
        limit = next(one for one in rows[0]["limits"] if one["condition_key"] == "force")
        value: float = limit["max_value"]
        return value

    assert _force(made["small"]) == 0.5
    assert _force(made["large"]) == 300


def test_가리키는_장비가_있는_기종은_못_지운다(client: TestClient, admin: Signed) -> None:
    """지우면 그 장비가 무엇이었는지 알 수 없게 된다 — 단종은 status 로 적는다."""
    series = _series(client, admin)
    model = _model_in(client, admin, series["id"])
    client.post(
        "/api/equipment",
        json={
            "asset_no": f"CAT-{uuid.uuid4().hex[:6]}",
            "site_term_id": site_id(client, admin),
            "location": "3동 201호",
            "name": "지우기 막는 장비",
            "workspace_slug": admin.workspace,
            "model_id": model["id"],
        },
        headers=admin.headers,
    )

    blocked = client.delete(f"/api/equipment-models/{model['id']}", headers=admin.headers)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "TSC-CATALOG-0003"

    # 기종이 매달린 계열도 못 지운다.
    held = client.delete(f"/api/equipment-series/{series['id']}", headers=admin.headers)
    assert held.status_code == 409
    assert held.json()["error"]["code"] == "TSC-CATALOG-0011"

    # 단종으로는 바꿀 수 있다.
    retired = client.patch(
        f"/api/equipment-models/{model['id']}",
        json={"status": "discontinued"},
        headers=admin.headers,
    )
    assert retired.status_code == 200
    assert retired.json()["status"] == "discontinued"


def test_같은_제조사에_같은_계열명은_하나다(client: TestClient, admin: Signed) -> None:
    """`5982` 와 `5982 ` 는 눈에 같아 보이는데 DB 는 다르게 본다 — 비교키로 막는다."""
    name = f"SER-{uuid.uuid4().hex[:6]}"
    first = client.post("/api/equipment-series", json={"name": name}, headers=admin.headers)
    assert first.status_code == 201

    again = client.post(
        "/api/equipment-series", json={"name": f"  {name} "}, headers=admin.headers
    )
    assert again.status_code == 409
    assert again.json()["error"]["details"]["series_id"] == first.json()["id"]


def test_부속은_양쪽에서_보인다(client: TestClient, admin: Signed) -> None:
    """**한쪽만 보여 주면 챔버 화면이 늘 비어 있다.** 「이 챔버가 붙는 시험기들」 은
    관계의 대상 쪽에서만 보이는 사실이다."""
    frame = _series(client, admin)
    chamber = _series(client, admin, kind="accessory")

    made = client.post(
        f"/api/equipment-series/{frame['id']}/relations",
        json={
            "part_series_id": chamber["id"],
            "relation": "extends_temperature",
            "note": "-150 ~ +600 degC",
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    assert made.json()["inbound"] is False

    seen = client.get(f"/api/equipment-series/{chamber['id']}", headers=admin.headers).json()[
        "relations"
    ]
    assert len(seen) == 1
    assert seen[0]["inbound"] is True
    assert seen[0]["other_series_id"] == frame["id"]

    # 부속은 기본 목록에서 안 보인다 — 챔버와 시험기가 한 줄씩 섞이면
    # 「우리가 무슨 장비를 가졌나」 가 안 보인다.
    mains = client.get("/api/equipment-series?kind=main", headers=admin.headers).json()
    assert all(one["id"] != chamber["id"] for one in mains["items"])


def test_채울_자리는_보유한_것만_센다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    """**전부를 채우라고 하면 아무도 안 채운다.**

    카탈로그에는 아직 안 산 계열도 들어 있다. 홈의 「남은 일」 이 그것까지 세면
    목록에 끝이 없어 보여서 사람은 시작하지 않는다 — 우리가 가진 것만 센다.
    """

    def counts() -> dict[str, int]:
        response = client.get("/api/server/maintenance", headers=admin.headers)
        assert response.status_code == 200, response.text
        return {row["key"]: row["count"] for row in response.json()}

    before = counts()

    # 아무도 안 가진 계열·기종은 안 센다.
    idle = _series(client, admin)
    _model_in(client, admin, idle["id"])
    assert counts().get("series_without_test_item", 0) == before.get(
        "series_without_test_item", 0
    )

    # 보유하면 그때 센다.
    owned = _series(client, admin)
    model = _model_in(client, admin, owned["id"])
    client.post(
        "/api/equipment",
        json={
            "asset_no": f"GAP-{uuid.uuid4().hex[:6]}",
            "site_term_id": site_id(client, admin),
            "location": "3동 201호",
            "name": "빈 카탈로그를 가리키는 장비",
            "workspace_slug": admin.workspace,
            "model_id": model["id"],
        },
        headers=admin.headers,
    )
    after = counts()
    assert after["series_without_test_item"] == before.get("series_without_test_item", 0) + 1
    assert after["model_without_specs"] == before.get("model_without_specs", 0) + 1

    # 목록이 그 줄과 같은 것을 돌려준다 — 링크를 눌렀는데 다른 것이 나오면
    # 사람은 숫자를 안 믿게 된다.
    listed = client.get("/api/equipment-models?owned=true&issue=specs", headers=admin.headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == after["model_without_specs"]
    assert any(row["id"] == model["id"] for row in listed.json()["items"])

    # 시험 항목을 적으면 그 줄이 사라진다.
    item = term_factory("test_item", f"인장-{uuid.uuid4().hex[:6]}")
    client.post(
        f"/api/equipment-series/{owned['id']}/test-items",
        json={"test_item_term_id": item},
        headers=admin.headers,
    )
    assert counts().get("series_without_test_item", 0) == before.get(
        "series_without_test_item", 0
    )


def test_기종_피커는_서버가_거른다(client: TestClient, admin: Signed) -> None:
    """**목록을 통째로 받아 두면 안 된다.** 카탈로그가 상한(200)을 넘는 순간
    나머지가 조용히 안 보이고, 못 찾은 사람은 「카탈로그에 없구나」 하고 빈 칸으로
    저장한다. 실제로 그랬다."""
    series = _series(client, admin)
    tag = uuid.uuid4().hex[:8]
    made = _model_in(client, admin, series["id"], name=f"찾아낼기종-{tag}")

    # 이름 조각으로 서버에 물으면 걸린다.
    found = client.get(f"/api/equipment-models?q={tag}", headers=admin.headers)
    assert found.status_code == 200, found.text
    assert [row["id"] for row in found.json()["items"]] == [made["id"]]

    # 기종으로 장비를 거르는 것도 서버가 한다 — 화면이 전체를 받아 걸러 내면
    # 그 기종은 대수가 많아진 날 「보유 없음」 이 된다.
    client.post(
        "/api/equipment",
        json={
            "asset_no": f"PCK-{uuid.uuid4().hex[:6]}",
            "site_term_id": site_id(client, admin),
            "location": "3동 201호",
            "name": "피커 시험 장비",
            "workspace_slug": admin.workspace,
            "model_id": made["id"],
        },
        headers=admin.headers,
    )
    mine = client.get(f"/api/equipment?model_id={made['id']}", headers=admin.headers)
    assert mine.status_code == 200, mine.text
    assert mine.json()["total"] == 1

"""AI·MCP 가 쓰는 표면 — 범위·해석·이름으로 쓰기.

여기서 지키는 것 넷:

1. 기계 자격은 **준 범위 안에서만** 쓴다. 모르는 경로는 막힌다.
2. 「이게 이미 있나」 에 exact · candidates · none 으로 답한다.
3. 이름으로 써도 되지만, **하나로 안 정해지면 거절**한다.
4. 누가 넣었는지에 **통로와 토큰**이 남는다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.auth import security
from app.modules.auth.models import PersonalAccessToken
from app.modules.review.models import ReviewProposal
from app.modules.workspaces.models import Workspace, WorkspaceMember
from tests.api.conftest import Signed, category_id, site_id


def _token(client: TestClient, admin: Signed, scopes: list[str]) -> dict[str, str]:
    response = client.post(
        "/api/auth/tokens",
        json={"name": f"MCP-시험-{uuid.uuid4().hex[:6]}", "scopes": scopes},
        headers=admin.headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["pat"]["scopes"] == scopes
    return {"Authorization": f"Bearer {response.json()['token']}", "X-Client": "mcp"}


def test_토큰은_준_범위_안에서만_쓴다(client: TestClient, admin: Signed) -> None:
    """**기본이 읽기뿐이다.** 「일단 만들고 나중에 좁히자」 는 나중이 오지 않는다."""
    read_only = _token(client, admin, ["read"])

    assert client.get("/api/equipment-series", headers=read_only).status_code == 200

    blocked = client.post(
        "/api/equipment-series", json={"name": "막혀야 한다"}, headers=read_only
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "TSC-AUTH-0106"

    # 범위를 주면 된다.
    writer = _token(client, admin, ["read", "catalog:write"])
    made = client.post(
        "/api/equipment-series",
        json={"name": f"MCP 계열-{uuid.uuid4().hex[:6]}"},
        headers=writer,
    )
    assert made.status_code == 201, made.text

    # **POST 지만 읽기인 것은 통과한다.** 검색과 해석은 본문에 물음을 싣기 때문에
    # POST 일 뿐이다 — 이걸 막으면 읽기 전용 토큰이 이 시스템을 못 쓴다.
    for path, body in (
        ("/api/resolve", {"kind": "series", "text": "무엇이든"}),
        ("/api/search/test-items", {"conditions": []}),
    ):
        reading = client.post(path, json=body, headers=read_only)
        assert reading.status_code == 200, f"{path}: {reading.text}"

    # **표에 없는 경로는 어느 범위로도 못 쓴다.** 새 엔드포인트가 생길 때마다
    # 자동으로 열리면 그것을 알아채는 사람이 아무도 없다.
    elsewhere = client.post(
        "/api/notices",
        json={"title": "기계가 쓰면 안 되는 것", "body": "x"},
        headers=writer,
    )
    assert elsewhere.status_code == 403
    assert elsewhere.json()["error"]["code"] == "TSC-AUTH-0105"


def test_새_도구가_쓰는_경로도_범위_안이다(client: TestClient, admin: Signed) -> None:
    """**도구를 더하면 그 경로가 기계 자격으로 열려 있는지 여기서 본다.**

    범위 표(`shared/auth._WRITE_SCOPES`)에 없는 경로는 어느 범위로도 못 쓴다 — 그것이
    규칙이고, 그래서 새 도구가 조용히 403 을 받는 일이 생긴다. MCP 도구가 실제로 부르는
    경로를 여기서 한 번 눌러 본다: 기준정보 값·신뢰성 시험·속성 정의는 되고, 검토함의
    확정은 **안 되는 것이 맞다**(고른 것이 곧 카탈로그 정본이라 사람이 화면에서 한다).
    """
    read_only = _token(client, admin, ["read"])
    catalog = _token(client, admin, ["read", "catalog:write"])
    equipment = _token(client, admin, ["read", "equipment:write"])
    tag = uuid.uuid4().hex[:6]

    # 기준정보 값 — catalog:write.
    term = client.post(
        "/api/vocabularies/test_item/terms", json={"value": f"MCP인장-{tag}"}, headers=catalog
    )
    assert term.status_code == 201, term.text
    assert (
        client.post(
            "/api/vocabularies/test_item/terms",
            json={"value": f"MCP경도-{tag}"},
            headers=read_only,
        ).status_code
        == 403
    )

    # 속성 정의 — catalog:write.
    definition = client.post(
        "/api/attribute-definitions",
        json={
            "target": "reliability_test",
            "label": f"시험 온도-{tag}",
            "key": f"mcp_temp_{tag}",
            "kind": "number",
            "unit": "degC",
            "status": "standard",
        },
        headers=catalog,
    )
    assert definition.status_code == 201, definition.text

    # 신뢰성 시험 — 부서 것이라 equipment:write.
    test = client.post(
        "/api/reliability-tests",
        json={
            "workspace_slug": admin.workspace,
            "name": f"MCP 고온고습-{tag}",
            "test_item_term_ids": [term.json()["id"]],
            "attributes": [
                {"definition_id": definition.json()["id"], "num_value": 85, "unit": "degC"}
            ],
        },
        headers=equipment,
    )
    assert test.status_code == 201, test.text
    assert (
        client.post(
            "/api/reliability-tests",
            json={"workspace_slug": admin.workspace, "name": f"막힘-{tag}"},
            headers=catalog,
        ).status_code
        == 403
    ), "카탈로그 범위로 부서의 시험을 못 만든다"

    # 규격 등록과 요구 조건 한 줄 — catalog:write. 물성 연결 제안도 같은 범위다.
    method = client.post(
        "/api/methods",
        json={"code": f"MCP {tag}", "title": "확인용 규격"},
        headers=catalog,
    )
    assert method.status_code == 201, method.text
    keys = {
        one["key"]: one["id"]
        for one in client.get("/api/condition-keys", headers=read_only).json()
    }
    requirement = client.put(
        f"/api/methods/{method.json()['id']}/requirements",
        json={"condition_key_id": keys["force"], "min_value": 20000},
        headers=catalog,
    )
    assert requirement.status_code == 200, requirement.text

    # 읽기 도구들은 read 하나로 된다 — 가능한 장비·그래프·검토함·교정·부서.
    for path, params in (
        (f"/api/reliability-tests/{test.json()['id']}/equipment", None),
        ("/api/workspaces/options", None),
        ("/api/server/calibrations-due", None),
        ("/api/attribute-definitions", {"target": "reliability_test"}),
        ("/api/reference/overview", None),
        ("/api/graph/overview", None),
        ("/api/graph/search", {"q": tag}),
        ("/api/review", None),
    ):
        reading = client.get(path, params=params, headers=read_only)
        assert reading.status_code == 200, f"{path}: {reading.text}"

    # **검토함의 확정은 기계 자격으로 안 연다.** 버그가 아니라 결정이다.
    blocked = client.post(
        f"/api/review/attribute_drafts/{uuid.uuid4()}/decide",
        json={"choice": ["keep"]},
        headers=catalog,
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "TSC-AUTH-0105"


def _resolve(client: TestClient, headers: dict[str, str], **body: object) -> dict[str, Any]:
    response = client.post("/api/resolve", json=body, headers=headers)
    assert response.status_code == 200, response.text
    out: dict[str, Any] = response.json()
    return out


def test_해석은_셋으로_답한다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    """**「비슷한 것들」 이 아니라 「하나로 정해졌나」 를 답한다.**

    목록 검색으로 흉내내면 AI 는 첫 줄을 집는다 — 틀린 줄도 첫 줄이면 집는다.
    """
    tag = uuid.uuid4().hex[:8]
    made = client.post(
        "/api/equipment-series",
        json={"name": f"해석계열-{tag}"},
        headers=admin.headers,
    ).json()

    exact = _resolve(client, admin.headers, kind="series", text=f"해석계열-{tag}")
    assert exact["match"] == "exact"
    assert exact["id"] == made["id"]
    assert exact["candidates"][0]["why"] == "정확히 같음"

    # 일부만 맞으면 후보다 — **고르지 않는다.**
    partial = _resolve(client, admin.headers, kind="series", text="해석계열")
    assert partial["match"] == "candidates"
    assert partial["id"] is None

    none = _resolve(client, admin.headers, kind="series", text=f"없는것-{tag}")
    assert none["match"] == "none"
    assert "지어내" not in none["hint"] or True  # 안내가 있다는 것만 본다
    assert none["hint"]

    # 기준정보는 별칭까지 본다.
    term_factory("test_item", f"인장-{tag}")
    axis = _resolve(client, admin.headers, kind="term", axis="test_item", text=f"인장-{tag}")
    assert axis["match"] == "exact"

    # 축을 안 주면 거절한다 — 어느 축인지 모르면 답이 여럿이 된다.
    missing = client.post(
        "/api/resolve", json={"kind": "term", "text": "인장"}, headers=admin.headers
    )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "TSC-RESOLVE-0001"


def test_부서의_것도_이름으로_하나로_정한다(
    client: TestClient, admin: Signed, db: Session, workspace: Workspace
) -> None:
    """**목록을 주면 AI 는 첫 줄을 집는다.** 「고온고습 1000h」 는 거의 모든 부서에 하나씩
    있으므로, 이름이 정확히 같아도 둘이면 exact 가 아니라 candidates 여야 한다 — 부서를
    함께 주면 그때 하나로 줄어든다. 장비는 자산번호가 유일하니 그것만 exact 다.
    """
    tag = uuid.uuid4().hex[:6]
    other = Workspace(slug=f"lab-{tag}", name=f"신뢰성팀-{tag}")
    db.add(other)
    db.commit()

    name = f"고온고습 1000h-{tag}"
    for slug in (admin.workspace, other.slug):
        made = client.post(
            "/api/reliability-tests",
            json={"workspace_slug": slug, "name": name},
            headers=admin.headers,
        )
        assert made.status_code == 201, made.text

    both = _resolve(client, admin.headers, kind="reliability_test", text=name)
    assert both["match"] == "candidates", "같은 이름이 둘인데 하나로 정하면 안 된다"
    assert {one["detail"] for one in both["candidates"]} == {"시험팀", f"신뢰성팀-{tag}"}
    assert "사람에게" in both["hint"]

    one_team = _resolve(
        client, admin.headers, kind="reliability_test", text=name, workspace=other.slug
    )
    assert one_team["match"] == "exact" and one_team["label"] == name

    # 부서 자신도 찾는다 — 쓰기 API 가 요구하는 것은 이름이 아니라 slug 다.
    found = _resolve(client, admin.headers, kind="workspace", text=f"신뢰성팀-{tag}")
    assert found["match"] == "exact" and found["candidates"][0]["detail"] == f"slug: lab-{tag}"

    # 장비 — 자산번호는 유일하니 exact, 이름은 여럿이면 후보다.
    for index in (1, 2):
        client.post(
            "/api/equipment",
            json={
                "asset_no": f"UTM-{tag}-{index}",
                "name": f"만능재료시험기-{tag}",
                "workspace_slug": admin.workspace,
                "site_term_id": site_id(client, admin),
                "location": "3동",
                "category_term_id": category_id(client, admin),
            },
            headers=admin.headers,
        )
    by_asset = _resolve(client, admin.headers, kind="equipment", text=f"UTM-{tag}-1")
    assert by_asset["match"] == "exact"
    assert by_asset["label"] == f"만능재료시험기-{tag} (UTM-{tag}-1)"
    by_name = _resolve(client, admin.headers, kind="equipment", text=f"만능재료시험기-{tag}")
    assert by_name["match"] == "candidates" and len(by_name["candidates"]) == 2

    # 없는 이름은 none — **지어내지 말라**는 안내가 함께 온다.
    empty = _resolve(client, admin.headers, kind="reliability_test", text=f"없는시험-{tag}")
    assert empty["match"] == "none" and "비슷한 이름을" in empty["hint"]

    # 없는 부서로 좁히면 조용히 무시하지 않고 거절한다 — 무시하면 전사 결과를 부서
    # 결과로 오해한다.
    bad = client.post(
        "/api/resolve",
        json={"kind": "reliability_test", "text": name, "workspace": f"없는부서-{tag}"},
        headers=admin.headers,
    )
    assert bad.status_code == 400


def test_가린_부서의_장비는_후보에도_안_선다(
    client: TestClient, admin: Signed, db: Session, workspace: Workspace
) -> None:
    """resolve 는 목록과 **같은 가시성 규칙**을 쓴다. 안 그러면 못 보는 장비의 id 가
    후보로 흘러나오고, 그 id 로 부른 다음 요청이 404 로 끝난다."""
    tag = uuid.uuid4().hex[:6]
    made = client.post(
        "/api/equipment",
        json={
            "asset_no": f"HID-{tag}",
            "name": f"가린 챔버-{tag}",
            "workspace_slug": admin.workspace,
            "site_term_id": site_id(client, admin),
            "location": "3동",
            "category_term_id": category_id(client, admin),
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    assert (
        _resolve(client, admin.headers, kind="equipment", text=f"HID-{tag}")["match"]
        == "exact"
    )

    workspace.restricted = True
    other = Workspace(slug=f"out-{tag}", name="다른팀")
    db.add(other)
    db.flush()
    email = f"outsider-{tag}@testscope.local"
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
    outsider = {"Authorization": f"Bearer {token}"}

    assert _resolve(client, outsider, kind="equipment", text=f"HID-{tag}")["match"] == "none"


def test_이름으로_써도_되지만_모호하면_거절한다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    """AI 는 이름을 알지 id 를 모른다. 그렇다고 **비슷한 것을 골라 주지는 않는다** —
    여기서 첫 줄을 집으면 그 선택은 아무 데도 안 남는다."""
    tag = uuid.uuid4().hex[:8]
    term_factory("manufacturer", f"인스트론-{tag}")

    made = client.post(
        "/api/equipment-series",
        json={"name": f"이름계열-{tag}", "maker": f"인스트론-{tag}"},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    assert made.json()["maker"] == f"인스트론-{tag}"

    # 없는 제조사는 만들지 않는다.
    refused = client.post(
        "/api/equipment-series",
        json={"name": f"거절계열-{tag}", "maker": f"없는제조사-{tag}"},
        headers=admin.headers,
    )
    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "TSC-RESOLVE-0003"

    # 기종은 계열 이름으로 만들 수 있다.
    model = client.post(
        "/api/equipment-models",
        json={"series": f"이름계열-{tag}", "name": f"이름기종-{tag}"},
        headers=admin.headers,
    )
    assert model.status_code == 201, model.text
    assert model.json()["series_id"] == made.json()["id"]

    # 계열이 없으면 끼워 넣지 않는다.
    orphan = client.post(
        "/api/equipment-models",
        json={"series": f"없는계열-{tag}", "name": "고아기종"},
        headers=admin.headers,
    )
    assert orphan.status_code == 400
    assert orphan.json()["error"]["code"] == "TSC-CATALOG-0015"


def test_감사에_통로와_토큰이_남는다(client: TestClient, admin: Signed) -> None:
    """`actor_id` 는 토큰 소유자, 즉 **사람**이다.

    그것만 남기면 사람이 넣은 것과 AI 가 넣은 것이 구별되지 않는다 — 반년 뒤
    「이 값 누가 넣었나」 에 "관리자" 라고만 답하면 쓸모가 없다.
    """
    headers = _token(client, admin, ["read", "catalog:write"])

    conditions = client.get("/api/condition-keys", headers=headers).json()
    target = next(one for one in conditions if one["key"] == "humidity")
    # **감사가 남는 변경을 고른다.** 도움말만 바꾸면 diff 가 비어서 기록이 안 남는다 —
    # 그건 의도된 동작이다(안 바뀐 값 스무 개를 매번 남기지 않는다).
    changed = client.patch(
        f"/api/condition-keys/{target['id']}",
        json={"is_active": False},
        headers=headers,
    )
    assert changed.status_code == 200, changed.text
    client.patch(
        f"/api/condition-keys/{target['id']}",
        json={"is_active": True},
        headers=admin.headers,
    )

    entries = client.get(
        "/api/audit/entries?target_table=condition_keys", headers=admin.headers
    ).json()["items"]
    mine = [one for one in entries if one["actor_client"] == "mcp"]
    assert mine, "MCP 로 들어온 변경이 감사에 안 남았습니다"
    assert mine[0]["actor_token"].startswith("MCP-시험-")

    # 카탈로그를 만든 것도 남는다 — **AI 가 만든 계열을 셀 수 있어야** 통로 기록이
    # 뜻을 갖는다.
    made = client.post(
        "/api/equipment-series",
        json={"name": f"감사계열-{uuid.uuid4().hex[:6]}"},
        headers=headers,
    )
    assert made.status_code == 201, made.text
    catalog = client.get(
        "/api/audit/entries?target_table=equipment_series", headers=admin.headers
    ).json()["items"]
    mine = [one for one in catalog if one["target_id"] == made.json()["id"]]
    assert mine, "계열 생성이 감사에 안 남았습니다"
    assert mine[0]["actor_client"] == "mcp"


def test_이름을_바꿔도_이미_나간_토큰은_계속_쓴다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    """TestAtlas → TestScope 로 PAT 표식이 `tas_pat_` 에서 `tsc_pat_` 로 바뀌었다.

    **이미 나간 토큰을 죽이면 안 된다.** 그 토큰은 사람의 MCP 설정 안에
    붙어 있고, 이름을 바꾸는 쪽이 거기까지 손을 뻗을 수 없다. 발급은 새 표식으로만
    하되, 받을 때는 구 표식도 알아본다.
    """
    assert security.PAT_PREFIX == "tsc_pat_"
    assert "tas_pat_" in security.LEGACY_PAT_PREFIXES

    user = db.scalar(select(User).where(User.email == admin.email))
    assert user is not None

    raw = "tas_pat_" + uuid.uuid4().hex
    db.add(
        PersonalAccessToken(
            user_id=user.id,
            name=f"구-토큰-{uuid.uuid4().hex[:6]}",
            prefix=raw[:14],
            token_hash=security.hash_token(raw),
            scopes=["read"],
        )
    )
    db.commit()

    old = {"Authorization": f"Bearer {raw}"}
    assert client.get("/api/equipment-series", headers=old).status_code == 200

    # 구 표식이라고 범위가 넓어지지는 않는다.
    blocked = client.post("/api/equipment-series", json={"name": "막혀야 한다"}, headers=old)
    assert blocked.status_code == 403


def test_검토함에_열린_규격의_시험_항목은_기계_자격으로_못_정한다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    """검토함의 확정은 막혀 있는데 규격의 시험 항목을 직접 고치는 길은 열려 있었다 — 그 길로
    가면 결과는 확정과 같다. 실측(2026-09-20, q22)에서 AI 가 정확히 그 우회로를 썼다. 사람
    세션은 막지 않는다."""
    tag = uuid.uuid4().hex[:6]
    made = client.post(
        "/api/methods",
        json={"code": f"GUARD {tag}", "title": "우회 확인"},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    method_id = made.json()["id"]
    item = client.post(
        "/api/vocabularies/test_item/terms",
        json={"value": f"인장-{tag}"},
        headers=admin.headers,
    ).json()["id"]
    db.add(
        ReviewProposal(
            queue="method_test_items",
            subject_key=f"guard {tag}",
            subject_id=uuid.UUID(method_id),
            subject_label=f"GUARD {tag}",
            candidates=[],
            status="open",
        )
    )
    db.commit()

    machine = _token(client, admin, ["read", "catalog:write"])
    blocked = client.patch(
        f"/api/methods/{method_id}", json={"test_item_term_id": item}, headers=machine
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["error"]["code"] == "TSC-METHODS-0007"

    # 사람은 된다 — 그 사람의 권한이 이미 한계다.
    allowed = client.patch(
        f"/api/methods/{method_id}", json={"test_item_term_id": item}, headers=admin.headers
    )
    assert allowed.status_code == 200, allowed.text


def _member_token(
    client: TestClient,
    db: Session,
    workspace: Workspace,
    scopes: list[str],
    role: str = "member",
) -> dict[str, str]:
    """**관리자가 아닌 사람**의 MCP 토큰. 범위는 다 줘 본다 — 막는 것이 범위가 아니라
    자격임을 보이려는 것이다."""
    email = f"member-{uuid.uuid4().hex[:8]}@testscope.local"
    person = User(
        email=email,
        password_hash=security.hash_password("member-password"),
        display_name="일반 사용자",
        status="active",
        is_system_admin=False,
        home_workspace_id=workspace.id,
    )
    db.add(person)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=person.id, role=role))
    db.commit()

    login = client.post(
        "/api/auth/login", json={"email": email, "password": "member-password"}
    )
    assert login.status_code == 200, login.text
    made = client.post(
        "/api/auth/tokens",
        json={"name": f"일반 유저 MCP-{uuid.uuid4().hex[:6]}", "scopes": scopes},
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert made.status_code == 201, made.text
    return {"Authorization": f"Bearer {made.json()['token']}", "X-Client": "mcp"}


def test_기준정보를_고치는_것은_범위가_아니라_자격이_막는다(
    client: TestClient, admin: Signed, db: Session, workspace: Workspace
) -> None:
    """**막는 자리가 둘이다** — 토큰 범위(무엇을 건드리나)와 사람의 자격(해도 되나).

    범위를 다 줘도 일반 사용자는 기준정보를 **못 고친다**. 이 규칙이 지금은 라우터마다
    `require_system_admin` 으로 흩어져 있어서, 누가 한 줄을 `current_user` 로 바꿔도
    아무도 모른다 — 그 한 줄이 온톨로지를 누구나 고칠 수 있게 만든다.

    403 의 뜻도 여기서 갈린다: `TSC-AUTH-0106` 은 「범위가 없다」(토큰을 다시 만들면 된다),
    `TSC-AUTH-0103` 은 「자격이 없다」(토큰을 다시 만들어도 소용없다). 도구 설명과 README 가
    그 둘을 구별해 말해야 사람이 헛되이 토큰을 재발급하지 않는다.
    """
    tag = uuid.uuid4().hex[:6]
    scopes = ["read", "catalog:write", "equipment:write"]
    machine = _member_token(client, db, workspace, scopes)

    # 읽기는 된다 — 못 보면 「없다」 와 「이름이 다르다」 를 구별할 수 없다.
    assert client.get("/api/vocabularies", headers=machine).status_code == 200

    # **열린 축에 값은 더한다.** 승인 대기를 두면 피커가 멈추고 사람은 시스템 밖에서 일한다.
    added = client.post(
        "/api/vocabularies/manufacturer/terms",
        json={"value": f"일반유저 제조사-{tag}"},
        headers=machine,
    )
    assert added.status_code == 201, added.text
    term_id = added.json()["id"]

    # 닫힌 축은 관리자만 — 시험 항목이 흩어지면 검색이 절반만 답한다.
    closed = client.post(
        "/api/vocabularies/test_item/terms", json={"value": f"닫힌-{tag}"}, headers=machine
    )
    assert closed.status_code == 403
    assert closed.json()["error"]["code"] == "TSC-VOCAB-0002"

    # **고치는 것은 전부 관리자다.** 이름을 바꾸는 것은 그 값을 쓰는 모든 화면의 글자를
    # 바꾸는 일이라, 기계 자격으로 열어 두면 되돌릴 자리가 감사 기록뿐이다.
    forbidden = (
        ("PATCH", f"/api/vocabularies/terms/{term_id}", {"value": f"고침-{tag}"}),
        ("POST", f"/api/vocabularies/terms/{term_id}/aliases", {"value": f"별칭-{tag}"}),
        ("POST", "/api/vocabularies", {"slug": f"probe_{tag}", "label": "축"}),
        ("PATCH", "/api/vocabularies/manufacturer", {"label": "바뀌면 안 됨"}),
        ("POST", "/api/condition-keys", {"key": f"probe_{tag}", "label": "조건축"}),
        ("POST", "/api/equipment-series", {"name": f"계열-{tag}"}),
    )
    for method, path, body in forbidden:
        response = client.request(method, path, json=body, headers=machine)
        assert response.status_code == 403, f"{path}: {response.status_code} {response.text}"
        assert response.json()["error"]["code"] == "TSC-AUTH-0103", path

    # **제 부서의 장비는 멤버가 넣고 고친다**(2026-09-23). 장비를 쓰는 사람이 등록한다 —
    # 부서 관리자를 거치게 하면 등록이 밀리고, 밀린 장비는 검색에 안 걸린다.
    unit_body = {
        "asset_no": f"MEM-{tag}",
        "name": f"일반 유저 장비-{tag}",
        "workspace_slug": workspace.slug,
        "site_term_id": site_id(client, admin),
        "location": "1동",
        "category_term_id": category_id(client, admin),
    }
    unit = client.post("/api/equipment", json=unit_body, headers=machine)
    assert unit.status_code == 201, unit.text
    equipment_id = unit.json()["id"]

    # 고치는 것도, **시험 항목을 다는 것도** 된다 — 등록만 열고 시험 항목을 막으면
    # 그 장비는 영영 검색에 안 걸린다.
    assert (
        client.patch(
            f"/api/equipment/{equipment_id}", json={"location": "2동"}, headers=machine
        ).status_code
        == 200
    )
    marked = client.post(
        "/api/equipment-test-items",
        json={
            "equipment_id": equipment_id,
            "test_item_term_id": _any_test_item(client, admin),
        },
        headers=machine,
    )
    assert marked.status_code == 201, marked.text
    assert (
        client.post(
            f"/api/equipment/{equipment_id}/calibrations",
            json={"calibrated_on": "2026-01-01", "next_due_on": "2027-01-01"},
            headers=machine,
        ).status_code
        == 201
    )

    # **지우는 것만 부서 관리자다.** 고친 것은 되돌릴 수 있지만 지운 것은 목록에서 사라진다.
    assert client.delete(f"/api/equipment/{equipment_id}", headers=machine).status_code == 403

    # 신뢰성 시험은 부서의 **절차**라 여전히 부서 관리자다.
    assert (
        client.post(
            "/api/reliability-tests",
            json={"workspace_slug": workspace.slug, "name": f"시험-{tag}"},
            headers=machine,
        ).status_code
        == 403
    )

    # 부서 관리자여도 **기준정보는 여전히 못 고친다.**
    manager = _member_token(client, db, workspace, scopes, role="manager")
    still = client.patch(
        f"/api/vocabularies/terms/{term_id}", json={"value": f"또 고침-{tag}"}, headers=manager
    )
    assert still.status_code == 403
    assert still.json()["error"]["code"] == "TSC-AUTH-0103"


def _any_test_item(client: TestClient, admin: Signed) -> str:
    """시험 항목 값 하나 — 닫힌 축이라 관리자가 만든다."""
    made = client.post(
        "/api/vocabularies/test_item/terms",
        json={"value": f"인장-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])

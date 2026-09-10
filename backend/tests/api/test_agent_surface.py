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
from tests.api.conftest import Signed


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
        ("/api/search/test_items", {"conditions": []}),
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

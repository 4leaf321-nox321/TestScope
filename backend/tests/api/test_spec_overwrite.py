"""사양 값 — **기계 자격은 있는 값을 조용히 못 덮는다.**

## 왜 이 시험이 있나

카탈로그 반입은 처음부터 이 규칙을 지켰다 — 「이미 있으면 안 덮는다. 손으로 고쳐 둔 것이
사양서보다 정확하다」(`catalog_import/values.py`). 그런데 **API 경로에는 그 규칙이 없었다.**
그래서 AI 가 「카탈로그 사양 채워줘」 를 하다가 사람이 운영에서 고쳐 둔 값을 사양서 값으로
되돌릴 수 있었다.

빈말이 아니다: 두 기종(인스트론 9450RHK · 9420 High Energy)의 단위환산을 사람이 운영
서버에서 직접 했다(2026-10-03). 그리고 그 직후에 MCP 백필 도구를 늘렸다.

## 누가 넣었는지로 가르지 않는다

`model_spec_values` 에는 그 칸이 없고, 넣더라도 **이미 들어가 있는 값들**은 반입이 넣은
것과 사람이 고친 것이 구별되지 않는다. 그 구별을 지금 만들 수는 없으므로 「있는 값」 전부를
한 번 물어보게 한다. 거절은 `replace=True` 로 넘긴다 — 지우는 것이 아니라 **의도를 적게**
하는 것이 목적이다.

여기서 지키는 것:

1. 기계 자격은 **빈 자리를 채운다** — 백필이 하는 일이 그것이고, 막으면 쓸모가 없다.
2. 기계 자격은 **있는 값을 못 덮는다** — 409 로 거절하고 **지금 값을 함께** 준다.
3. `replace=True` 면 덮는다 — 길을 막는 것이 아니라 의도를 적게 하는 것이다.
4. **사람 세션은 안 막는다** — 화면에서 고치는 사람은 지금 값을 보고 있다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import Signed


def _machine(client: TestClient, admin: Signed) -> dict[str, str]:
    """개인 토큰 = 기계 자격. 범위는 카탈로그 쓰기."""
    made = client.post(
        "/api/auth/tokens",
        json={
            "name": f"사양-백필-{uuid.uuid4().hex[:6]}",
            "scopes": ["read", "catalog:write"],
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return {"Authorization": f"Bearer {made.json()['token']}", "X-Client": "mcp"}


def _model(client: TestClient, admin: Signed) -> str:
    series = client.post(
        "/api/equipment-series",
        json={"name": f"계열-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert series.status_code == 201, series.text
    made = client.post(
        "/api/equipment-models",
        json={"series_id": series.json()["id"], "name": f"기종-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    model_id: str = made.json()["id"]
    return model_id


def _weight(client: TestClient, admin: Signed) -> str:
    """수치 사양 하나 — 설치가 심어 두는 것 중 분류를 안 붙인 것."""
    got = client.get("/api/spec-definitions", headers=admin.headers)
    assert got.status_code == 200, got.text
    found = next(row for row in got.json() if row["key"] == "weight")
    key: str = found["definition_id"] if "definition_id" in found else found["id"]
    return key


def _put(client: TestClient, model_id: str, headers: dict[str, str], **payload: Any) -> Any:
    return client.put(f"/api/equipment-models/{model_id}/specs", json=payload, headers=headers)


def test_기계는_빈_자리를_채운다(client: TestClient, admin: Signed) -> None:
    """막으면 백필이 쓸모가 없다."""
    model_id = _model(client, admin)
    definition_id = _weight(client, admin)
    got = _put(
        client, model_id, _machine(client, admin), definition_id=definition_id, num_value=1200
    )
    assert got.status_code == 200, got.text
    assert got.json()["value"]["num_value"] == 1200


def test_기계는_있는_값을_못_덮고_지금_값을_받는다(client: TestClient, admin: Signed) -> None:
    model_id = _model(client, admin)
    definition_id = _weight(client, admin)
    # 사람이 운영에서 고쳐 둔 값이라고 치자.
    assert (
        _put(
            client, model_id, admin.headers, definition_id=definition_id, num_value=30
        ).status_code
        == 200
    )

    refused = _put(
        client, model_id, _machine(client, admin), definition_id=definition_id, num_value=300
    )
    assert refused.status_code == 409, refused.text
    body = refused.json()["error"]
    assert body["code"] == "TSC-SPEC-0014"
    # **지금 값을 함께 준다** — 무엇을 덮으려 했는지 안 보여 주면 부르는 쪽은
    # `replace` 를 눌러 보는 것밖에 할 게 없다.
    assert "30" in body["message"]
    assert body["details"]["held"] == "30.0"

    # 그리고 값은 **안 바뀌었다.**
    sheet = client.get(f"/api/equipment-models/{model_id}/specs", headers=admin.headers)
    held = [
        value
        for group in sheet.json()["groups"]
        for value in group["items"]
        if value["definition_id"] == definition_id
    ]
    assert held and held[0]["num_value"] == 30


def test_replace_면_덮는다(client: TestClient, admin: Signed) -> None:
    """길을 막는 것이 아니라 **의도를 적게** 하는 것이다."""
    model_id = _model(client, admin)
    definition_id = _weight(client, admin)
    assert (
        _put(
            client, model_id, admin.headers, definition_id=definition_id, num_value=30
        ).status_code
        == 200
    )
    done = _put(
        client,
        model_id,
        _machine(client, admin),
        definition_id=definition_id,
        num_value=300,
        replace=True,
    )
    assert done.status_code == 200, done.text
    assert done.json()["value"]["num_value"] == 300


def test_사람_세션은_안_막는다(client: TestClient, admin: Signed) -> None:
    """화면에서 고치는 사람은 지금 값을 보고 있다."""
    model_id = _model(client, admin)
    definition_id = _weight(client, admin)
    assert (
        _put(
            client, model_id, admin.headers, definition_id=definition_id, num_value=30
        ).status_code
        == 200
    )
    again = _put(client, model_id, admin.headers, definition_id=definition_id, num_value=300)
    assert again.status_code == 200, again.text
    assert again.json()["value"]["num_value"] == 300

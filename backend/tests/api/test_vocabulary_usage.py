"""기준정보 값의 **쓰임 수** — 「이 값 지워도 되나」 에 답하는 자리.

전에는 `vocabulary_terms.usage_count` 칸에 적어 두게 되어 있었는데 **아무도 안
갱신했다.** 장비 700대와 계열 200개를 들이고도 모든 값이 0 이었다 — 0 인 화면은
거짓말을 하고, 그 거짓말로는 값을 지울지 말지 정할 수 없다.

여기서 지키는 것:

1. **시드가 심는 축**은 전부 셀 줄 안다. 축을 새로 만들면서 참조 표에 한 줄 더하는 것을
   잊으면, 그 축의 값은 영원히 0 으로 보인다.
2. 실제로 쓰이는 값은 0 이 아니다.

**DB 에 있는 축 전부가 아니라 시드 목록(`AXES`)과 견준다**(2026-09-23). 축을 API 로도
만들 수 있게 되면서 「DB 에 있는 축」 이 더는 코드가 정하는 집합이 아니다. 런타임에 만든
축은 **아무 코드도 그 slug 를 안 걸고 있으므로 쓰임 0 이 참이다** — 나중에 거는 코드를
쓰는 사람이 그때 `_REFERENCES` 에 한 줄 더한다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.modules.vocabulary.reference import AXES
from app.modules.vocabulary.references import _REFERENCES
from tests.api.conftest import Signed, site_id


def _axes(client: TestClient, admin: Signed) -> list[dict[str, Any]]:
    response = client.get("/api/vocabularies", headers=admin.headers)
    assert response.status_code == 200, response.text
    rows: list[dict[str, Any]] = response.json()
    return rows


def test_시드가_심는_축은_모두_쓰임을_셀_줄_안다() -> None:
    """표에 없는 축의 값은 **영원히 0** 으로 보인다.

    그 0 은 「안 쓰인다」 와 구별되지 않는다.
    """
    missing = [row[0] for row in AXES if row[0] not in _REFERENCES]
    assert not missing, f"쓰임을 셀 줄 모르는 축: {missing}"


def test_쓰는_데가_있으면_0_이_아니다(client: TestClient, admin: Signed) -> None:
    site = site_id(client, admin)
    made = client.post(
        "/api/equipment",
        json={
            "asset_no": f"USE-{uuid.uuid4().hex[:6]}",
            "name": "거점을 쓰는 장비",
            "workspace_slug": admin.workspace,
            "site_term_id": site,
            "location": "3동 201호",
            "category_term_id": client.post(
                "/api/vocabularies/equipment_category/terms",
                json={"value": f"분류-{uuid.uuid4().hex[:6]}"},
                headers=admin.headers,
            ).json()["id"],
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text

    terms = client.get("/api/vocabularies/site/terms", headers=admin.headers)
    assert terms.status_code == 200, terms.text
    used = {row["id"]: row["usage_count"] for row in terms.json()}
    assert used.get(site, 0) >= 1, used


def test_지운_장비는_값을_붙잡지_않는다(client: TestClient, admin: Signed) -> None:
    """지운 장비가 값을 붙잡고 있으면 「쓰는 데가 있다」 가 거짓이 된다 — 그러면 그
    값은 영영 정리되지 않는다."""
    axis = "site"
    fresh = client.post(
        f"/api/vocabularies/{axis}/terms",
        json={"value": f"거점-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert fresh.status_code == 201, fresh.text
    term_id = fresh.json()["id"]

    made = client.post(
        "/api/equipment",
        json={
            "asset_no": f"DEL-{uuid.uuid4().hex[:6]}",
            "name": "곧 지울 장비",
            "workspace_slug": admin.workspace,
            "site_term_id": term_id,
            "location": "3동 201호",
            "category_term_id": client.post(
                "/api/vocabularies/equipment_category/terms",
                json={"value": f"분류-{uuid.uuid4().hex[:6]}"},
                headers=admin.headers,
            ).json()["id"],
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text

    def count() -> int:
        rows = client.get(f"/api/vocabularies/{axis}/terms", headers=admin.headers).json()
        found: int = next(row["usage_count"] for row in rows if row["id"] == term_id)
        return found

    assert count() == 1
    dropped = client.delete(f"/api/equipment/{made.json()['id']}", headers=admin.headers)
    assert dropped.status_code == 204, dropped.text
    assert count() == 0

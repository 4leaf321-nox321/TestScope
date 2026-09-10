"""기준정보 축의 **소속** — 어디의 축인가.

축이 일곱이 되면 한 목록으로는 「이게 어디 쓰이는 값이지」 를 알 수 없다. 제조사와
규격 제정기관이 나란히 서 있으면, 장비를 등록하러 온 사람이 제정기관 축에 회사 이름을
넣는다 — 그리고 그 값은 아무도 안 지운다.

여기서 지키는 것:

1. 모든 축이 소속을 갖는다. 아는 값 넷 중 하나다.
2. 세 층(보유 장비·카탈로그·시험법)에 **각각 축이 있다.**
3. 소속 이름은 **서버가 준다** — 화면마다 사전을 두면 한 곳만 안 고쳐진다.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import Signed

DOMAINS = {"equipment", "catalog", "method", "common"}


def _axes(client: TestClient, admin: Signed) -> list[dict[str, Any]]:
    response = client.get("/api/vocabularies", headers=admin.headers)
    assert response.status_code == 200, response.text
    rows: list[dict[str, Any]] = response.json()
    return rows


def test_모든_축이_소속을_갖는다(client: TestClient, admin: Signed) -> None:
    rows = _axes(client, admin)
    assert rows, "축이 하나도 없습니다"
    for row in rows:
        assert row["domain"] in DOMAINS, row
        # 이름까지 서버가 준다 — 화면이 슬러그를 한글로 옮기지 않게 한다.
        assert row["domain_label"], row


def test_세_층에_각각_축이_있다(client: TestClient, admin: Signed) -> None:
    by_domain: dict[str, list[str]] = {}
    for row in _axes(client, admin):
        by_domain.setdefault(row["domain"], []).append(row["slug"])

    assert "site" in by_domain.get("equipment", [])
    assert "calibration_provider" in by_domain.get("equipment", [])
    assert "manufacturer" in by_domain.get("catalog", [])
    assert "equipment_category" in by_domain.get("catalog", [])
    assert "form_factor" in by_domain.get("catalog", [])
    assert "drive" in by_domain.get("catalog", [])
    assert "standard_body" in by_domain.get("method", [])
    # 시험 항목은 **정말 여러 층이 쓴다** —
    # 장비의 시험 항목·계열의 시험 항목·시험법이 모두 그 축을 가리킨다.
    assert "test_item" in by_domain.get("common", [])

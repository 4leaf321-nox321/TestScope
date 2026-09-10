"""보유 장비의 속성 — **현장이 요구하는 모양.**

여기서 지키는 것들:

1. 무슨 종류의 장비인지는 반드시 답한다 — 기종을 고르거나, 장비유형을 고르거나.
2. 카탈로그에 연결하면 개체가 적어 둔 제조사·모델명·분류는 **서버가 비운다.**
3. 공용여부는 보유 부서와 **다른 칸**이다 — 공용 장비에도 관리 부서는 하나 있다.
4. 폐기일은 폐기일 때만 있다. 되돌리면 사라진다.
5. 교정 대상이면 주기를 적는다. 대상인데 이력이 없으면 목록이 그것을 말한다.
6. 유휴는 **쓸 수 있는 상태**다 — 안 쓰고 있다는 것은 못 쓴다는 뜻이 아니다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import Signed, category_id, site_id


def _make(client: TestClient, admin: Signed, **extra: Any) -> Any:
    payload: dict[str, Any] = {
        "asset_no": f"EQ-{uuid.uuid4().hex[:6]}",
        "name": "인장시험기",
        "workspace_slug": admin.workspace,
        "site_term_id": site_id(client, admin),
        "location": "3동 201호",
        **extra,
    }
    if "model_id" not in payload:
        payload.setdefault("category_term_id", category_id(client, admin))
    return client.post("/api/equipment", json=payload, headers=admin.headers)


def _model(client: TestClient, admin: Signed) -> dict[str, Any]:
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
    body: dict[str, Any] = made.json()
    return body


def test_무슨_종류인지_모르는_장비는_안_받는다(client: TestClient, admin: Signed) -> None:
    """분류가 없으면 분류로 좁히는 모든 화면에서 통째로 빠지고, 빠진 줄은 아무도 못 찾는다."""
    refused = client.post(
        "/api/equipment",
        json={
            "asset_no": f"EQ-{uuid.uuid4().hex[:6]}",
            "name": "정체불명",
            "workspace_slug": admin.workspace,
            "site_term_id": site_id(client, admin),
            "location": "3동 201호",
        },
        headers=admin.headers,
    )
    assert refused.status_code == 400, refused.text
    assert refused.json()["error"]["code"] == "TSC-EQUIPMENT-0007"


def test_거점과_상세위치는_비울_수_없다(client: TestClient, admin: Signed) -> None:
    refused = client.post(
        "/api/equipment",
        json={
            "asset_no": f"EQ-{uuid.uuid4().hex[:6]}",
            "name": "어디 있는지 모르는 장비",
            "workspace_slug": admin.workspace,
            "category_term_id": category_id(client, admin),
        },
        headers=admin.headers,
    )
    # 스키마가 먼저 막는다 — 없는 칸이라 422 다.
    assert refused.status_code == 422, refused.text


def test_카탈로그에_연결하면_개체가_적은_글자를_비운다(
    client: TestClient, admin: Signed
) -> None:
    """같은 사실이 두 곳에 남으면, 갈린 뒤에 어느 쪽이 맞는지 알 방법이 없다."""
    made = _make(
        client,
        admin,
        maker_text="사내 제작",
        model_text="자작-1호",
    )
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["catalog_linked"] is False
    assert body["manufacturer"] == "사내 제작"
    assert body["model_name"] == "자작-1호"
    assert body["category"] == "만능재료시험기"

    model = _model(client, admin)
    linked = client.patch(
        f"/api/equipment/{body['id']}",
        json={"model_id": model["id"]},
        headers=admin.headers,
    )
    assert linked.status_code == 200, linked.text
    after = linked.json()
    assert after["catalog_linked"] is True
    assert after["model_name"] == model["name"]
    # 개체가 적어 둔 글자는 사라졌다 — 이제 카탈로그가 말한다.
    assert after["manufacturer"] != "사내 제작"


def test_공용여부는_보유_부서와_다른_칸이다(client: TestClient, admin: Signed) -> None:
    """전에는 부서를 비우는 것이 「공용」 이었다 — 그러면 공용으로 표시하는 순간
    관리 부서를 잃는다."""
    made = _make(client, admin, shared_use=True)
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["shared_use"] is True
    assert body["workspace_slug"] == admin.workspace


def test_폐기일은_폐기일_때만_있고_되돌리면_사라진다(
    client: TestClient, admin: Signed
) -> None:
    made = _make(client, admin)
    assert made.status_code == 201, made.text
    url = f"/api/equipment/{made.json()['id']}"

    refused = client.patch(url, json={"retired_on": "2026-01-01"}, headers=admin.headers)
    assert refused.status_code == 400, refused.text
    assert refused.json()["error"]["code"] == "TSC-EQUIPMENT-0006"

    retired = client.patch(
        url, json={"status": "retired", "retired_on": "2026-01-01"}, headers=admin.headers
    )
    assert retired.status_code == 200, retired.text
    assert retired.json()["retired_on"] == "2026-01-01"

    # 되돌리면 폐기일도 지운다 — 가동 중인 장비에 폐기일이 붙어 있으면 목록이 거짓말한다.
    back = client.patch(url, json={"status": "operational"}, headers=admin.headers)
    assert back.status_code == 200, back.text
    assert back.json()["retired_on"] is None


def test_교정_대상이면_주기를_적고_이력이_없으면_말해_준다(
    client: TestClient, admin: Signed
) -> None:
    refused = _make(client, admin, calibration_required=True)
    assert refused.status_code == 400, refused.text
    assert refused.json()["error"]["code"] == "TSC-EQUIPMENT-0005"

    made = _make(client, admin, calibration_required=True, calibration_interval_months=12)
    assert made.status_code == 201, made.text
    body = made.json()
    # **대상인데 한 번도 안 받았다.** 이력이 없다는 사실만으로는 못 가른다.
    assert body["calibration_missing"] is True
    assert body["calibration_due_on"] is None

    url = f"/api/equipment/{body['id']}"
    client.post(
        f"{url}/calibrations",
        json={"calibrated_on": "2026-01-31"},
        headers=admin.headers,
    )
    after = client.get(url, headers=admin.headers).json()
    assert after["calibration_missing"] is False
    # 성적서에 차기일이 없으니 주기로 계산한다 — **계산값임을 함께 말한다.**
    assert after["calibration_due_on"] == "2027-01-31"
    assert after["calibration_due_estimated"] is True


def test_성적서에_적힌_차기일이_계산을_이긴다(client: TestClient, admin: Signed) -> None:
    """기관이 정한 날이 진실이고, 주기는 우리가 적어 둔 짐작이다."""
    made = _make(client, admin, calibration_required=True, calibration_interval_months=12)
    url = f"/api/equipment/{made.json()['id']}"
    client.post(
        f"{url}/calibrations",
        json={"calibrated_on": "2026-01-31", "next_due_on": "2026-08-01"},
        headers=admin.headers,
    )
    after = client.get(url, headers=admin.headers).json()
    assert after["calibration_due_on"] == "2026-08-01"
    assert after["calibration_due_estimated"] is False


def test_유휴는_쓸_수_있는_상태다(client: TestClient, admin: Signed) -> None:
    """「안 쓰고 있다」 와 「못 쓴다」 는 빌리려는 사람에게 정반대다."""
    made = _make(client, admin, status="idle")
    assert made.status_code == 201, made.text

    listed = client.get("/api/equipment?status=idle", headers=admin.headers)
    assert listed.status_code == 200, listed.text
    assert any(row["id"] == made.json()["id"] for row in listed.json()["items"])


def test_장비군은_저장하지_않고_유형에서_따라온다(client: TestClient, admin: Signed) -> None:
    """저장하면 유형만 고친 날 군이 어긋나고, 그 어긋남은 아무 화면에도 안 보인다."""
    parent = client.post(
        "/api/vocabularies/equipment_category/terms",
        json={"value": f"정적 기계 시험기-{uuid.uuid4().hex[:4]}"},
        headers=admin.headers,
    )
    assert parent.status_code == 201, parent.text
    child = client.post(
        "/api/vocabularies/equipment_category/terms",
        json={
            "value": f"크리프 시험기-{uuid.uuid4().hex[:4]}",
            "parent_term_id": parent.json()["id"],
        },
        headers=admin.headers,
    )
    assert child.status_code == 201, child.text

    made = _make(client, admin, category_term_id=child.json()["id"])
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["category"] == child.json()["value"]
    assert body["category_group"] == parent.json()["value"]

"""보유 장비 목록의 **열마다 거르기** — 거르는 것은 서버다.

화면이 한 쪽을 받아 놓고 거르면, 상한을 넘는 순간 나머지가 조용히 빠진다. 그리고
그때 목록은 「그 조건에 맞는 장비가 이것뿐」 이라고 거짓말한다.

여기서 지키는 것:

1. 분류는 **두 곳**에서 온다 — 기종이 있으면 그 계열, 없으면 개체가 직접 가리킨 것.
   한쪽만 보면 카탈로그 미연결 장비가 통째로 빠진다.
2. 교정의 「대상 아님」 과 「이력 없음」 은 **다른 물음**이다.
3. 거른 뒤에도 `total` 은 거른 결과의 수다 — 쪽 넘김이 그 수를 믿는다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import Signed, site_id


def _category(client: TestClient, admin: Signed, name: str) -> str:
    response = client.post(
        "/api/vocabularies/equipment_category/terms",
        json={"value": f"{name}-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _equipment(client: TestClient, admin: Signed, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "asset_no": f"FIL-{uuid.uuid4().hex[:6]}",
        "name": "거르기 시험 장비",
        "workspace_slug": admin.workspace,
        "site_term_id": site_id(client, admin),
        "location": "3동 201호",
        **extra,
    }
    if "model_id" not in payload:
        payload.setdefault("category_term_id", _category(client, admin, "분류"))
    response = client.post("/api/equipment", json=payload, headers=admin.headers)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def _listed(client: TestClient, admin: Signed, query: str) -> list[str]:
    response = client.get(f"/api/equipment?{query}&limit=200", headers=admin.headers)
    assert response.status_code == 200, response.text
    return [row["id"] for row in response.json()["items"]]


def test_분류로_거를_때_카탈로그_미연결_장비도_걸린다(
    client: TestClient, admin: Signed
) -> None:
    """기종이 있으면 계열이 분류를 갖고, 없으면 개체가 직접 가리킨다(ADR 0006).
    한쪽만 보면 자작 장비가 통째로 빠진다."""
    category = _category(client, admin, "만능재료시험기")

    series = client.post(
        "/api/equipment-series",
        json={"name": f"계열-{uuid.uuid4().hex[:6]}", "category_term_id": category},
        headers=admin.headers,
    )
    assert series.status_code == 201, series.text
    model = client.post(
        "/api/equipment-models",
        json={"series_id": series.json()["id"], "name": f"기종-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert model.status_code == 201, model.text

    linked = _equipment(client, admin, model_id=model.json()["id"])
    direct = _equipment(client, admin, category_term_id=category)
    other = _equipment(client, admin)

    found = _listed(client, admin, f"category_term_id={category}")
    assert linked["id"] in found
    assert direct["id"] in found
    assert other["id"] not in found


def test_교정은_대상_아님과_이력_없음을_가른다(client: TestClient, admin: Signed) -> None:
    """뭉쳐 두면 빠뜨린 장비가 대상 아닌 장비 뒤에 숨는다."""
    exempt = _equipment(client, admin)
    missing = _equipment(
        client, admin, calibration_required=True, calibration_interval_months=12
    )
    done = _equipment(client, admin, calibration_required=True, calibration_interval_months=12)
    added = client.post(
        f"/api/equipment/{done['id']}/calibrations",
        json={"calibrated_on": "2026-01-31", "next_due_on": "2027-01-31"},
        headers=admin.headers,
    )
    assert added.status_code == 201, added.text

    required = _listed(client, admin, "calibration=required")
    assert missing["id"] in required and done["id"] in required
    assert exempt["id"] not in required

    without = _listed(client, admin, "calibration=missing")
    assert missing["id"] in without
    assert done["id"] not in without and exempt["id"] not in without

    assert exempt["id"] in _listed(client, admin, "calibration=exempt")


def test_기한이_지난_것만_따로_거른다(client: TestClient, admin: Signed) -> None:
    overdue = _equipment(
        client, admin, calibration_required=True, calibration_interval_months=12
    )
    client.post(
        f"/api/equipment/{overdue['id']}/calibrations",
        json={"calibrated_on": "2020-01-01", "next_due_on": "2021-01-01"},
        headers=admin.headers,
    )
    assert overdue["id"] in _listed(client, admin, "calibration=overdue")


def test_시험_항목과_거점으로_거른다(client: TestClient, admin: Signed) -> None:
    item = client.post(
        "/api/vocabularies/test_item/terms",
        json={"value": f"인장-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert item.status_code == 201, item.text
    with_item = _equipment(client, admin)
    without = _equipment(client, admin)
    made = client.post(
        "/api/equipment-test-items",
        json={"equipment_id": with_item["id"], "test_item_term_id": item.json()["id"]},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text

    found = _listed(client, admin, f"test_item_term_id={item.json()['id']}")
    assert with_item["id"] in found and without["id"] not in found

    # 거점은 둘 다 같은 값이라 둘 다 걸린다 — 거르기가 도는지만 본다.
    site = site_id(client, admin)
    at_site = _listed(client, admin, f"site_term_id={site}")
    assert with_item["id"] in at_site


def test_거른_결과의_수가_total_이다(client: TestClient, admin: Signed) -> None:
    """쪽 넘김이 이 수를 믿는다. 거르기 전 수를 주면 「다음 쪽」 이 빈 쪽으로 간다."""
    category = _category(client, admin, "특정분류")
    _equipment(client, admin, category_term_id=category)
    _equipment(client, admin)

    response = client.get(f"/api/equipment?category_term_id={category}", headers=admin.headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == len(body["items"]) == 1


def test_고를_수_있는_값은_목록에_있는_것뿐이다(client: TestClient, admin: Signed) -> None:
    """기준정보 전체를 내려보내면 골라도 0 건인 선택지가 섞이고, 한 번 겪으면 사람은
    거르기를 안 믿는다.

    부서를 여기서 주는 이유가 하나 더 있다: `/api/workspaces` 는 **내 소속만** 준다 —
    그것으로 거르게 두면 목록에는 보이는데 못 거르는 부서가 생긴다.
    """
    category = _category(client, admin, "고를수있는분류")
    _category(client, admin, "아무도안쓰는분류")
    mine = _equipment(client, admin, category_term_id=category)

    response = client.get("/api/equipment/filter-options", headers=admin.headers)
    assert response.status_code == 200, response.text
    body = response.json()

    labels = {row["label"] for row in body["categories"]}
    assert any(one.startswith("고를수있는분류") for one in labels)
    assert not any(one.startswith("아무도안쓰는분류") for one in labels)

    # 수를 함께 준다 — 고르기 전에 몇 대인지 알아야 한다.
    picked = next(row for row in body["categories"] if row["label"] in labels and row["count"])
    assert picked["count"] >= 1
    assert admin.workspace in {row["value"] for row in body["workspaces"]}
    assert mine["id"] in _listed(client, admin, f"category_term_id={category}")


def test_자산번호와_이름을_따로_거른다(client: TestClient, admin: Signed) -> None:
    """한 칸으로 합치면 번호를 치는 사람이 이름에 걸린 줄을 함께 보게 되고, 그 줄들이
    찾는 것을 가린다."""
    marker = uuid.uuid4().hex[:6]
    by_no = _equipment(client, admin, asset_no=f"UTM-{marker}", name="이름은 평범")
    by_name = _equipment(
        client, admin, asset_no=f"ETC-{uuid.uuid4().hex[:6]}", name=f"인장기-{marker}"
    )

    only_no = _listed(client, admin, f"asset_no={marker}")
    assert by_no["id"] in only_no
    assert by_name["id"] not in only_no

    only_name = _listed(client, admin, f"name={marker}")
    assert by_name["id"] in only_name
    assert by_no["id"] not in only_name

    # `q` 는 둘 다 본다 — 현장에서 라벨의 번호를 치고, 회의에서는 이름을 친다.
    both = _listed(client, admin, f"q={marker}")
    assert by_no["id"] in both and by_name["id"] in both


def test_모르는_교정_거르기는_거절한다(client: TestClient, admin: Signed) -> None:
    """**조용히 무시하지 않는다.** 무시하면 거른 줄 아는 사람이 전체 목록을 본다."""
    response = client.get("/api/equipment?calibration=weird", headers=admin.headers)
    assert response.status_code == 422, response.text

"""기준정보 편집 — **화면에서 고친 것이 사실이 되려면** 축·값·표기·병합이 전부 고쳐져야 한다.

전에는 관리 화면이 이름 바꾸기·표기 추가·폐기 셋뿐이었다. 그리고 병합은 쓰이는 값에서
RESTRICT 에 막혔다 — 쓰이는 값일수록 합칠 일이 많은데 바로 그 값이 안 합쳐졌다.

여기서 지키는 것:

1. 병합은 **원본을 가리키던 도메인 행을 대상으로 돌린다.** 같은 짝이 이미 있으면
   그 행은 하나로.
2. 표기를 뗄 수 있다.
3. 축의 이름·설명·정책·속성 칸을 고칠 수 있다. slug 는 못 바꾼다.
4. 속성 칸이 있는 축의 값은 그 칸으로 속성을 고친다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import Signed, category_id


def _series(client: TestClient, admin: Signed, name: str) -> str:
    response = client.post("/api/equipment-series", json={"name": name}, headers=admin.headers)
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _series_item(client: TestClient, admin: Signed, series_id: str, item: str) -> None:
    response = client.post(
        f"/api/equipment-series/{series_id}/test-items",
        json={"test_item_term_id": item},
        headers=admin.headers,
    )
    assert response.status_code == 201, response.text


def _term(client: TestClient, admin: Signed, term_id: str, axis: str) -> dict[str, Any]:
    rows = client.get(f"/api/vocabularies/{axis}/terms", headers=admin.headers).json()
    found: dict[str, Any] = next(one for one in rows if one["id"] == term_id)
    return found


def test_병합은_쓰이는_값도_합치고_참조를_대상으로_돌린다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    tag = uuid.uuid4().hex[:6]
    typo = term_factory("test_item", f"인장시험-{tag}")
    proper = term_factory("test_item", f"인장-{tag}")
    only_typo = _series(client, admin, f"A-{tag}")
    both = _series(client, admin, f"B-{tag}")
    _series_item(client, admin, only_typo, typo)
    _series_item(client, admin, both, typo)
    _series_item(client, admin, both, proper)

    merged = client.post(
        f"/api/vocabularies/terms/{typo}/merge",
        json={"target_term_id": proper},
        headers=admin.headers,
    )
    assert merged.status_code == 200, merged.text
    # 원본 이름은 대상의 표기로 남는다 — 같은 오타가 또 들어오지 않게.
    assert f"인장시험-{tag}" in merged.json()["aliases"]

    # A 는 이제 「인장」 을 가리키고, B 는 같은 짝이 둘이 되지 않는다.
    a = client.get(f"/api/equipment-series/{only_typo}", headers=admin.headers).json()
    assert [one["test_item_term_id"] for one in a["test_items"]] == [proper]
    b = client.get(f"/api/equipment-series/{both}", headers=admin.headers).json()
    assert [one["test_item_term_id"] for one in b["test_items"]] == [proper]

    # 쓰임 수도 대상으로 옮겨 갔다 — 두 계열.
    assert _term(client, admin, proper, "test_item")["usage_count"] == 2


def test_표기를_뗄_수_있다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    tag = uuid.uuid4().hex[:6]
    term = term_factory("manufacturer", f"제조사-{tag}")
    client.post(
        f"/api/vocabularies/terms/{term}/aliases",
        json={"value": f"Maker-{tag}"},
        headers=admin.headers,
    )
    assert f"Maker-{tag}" in _term(client, admin, term, "manufacturer")["aliases"]

    gone = client.delete(
        f"/api/vocabularies/terms/{term}/aliases",
        params={"value": f"maker-{tag}"},  # 비교키로 찾는다 — 대소문자가 달라도 같은 표기
        headers=admin.headers,
    )
    assert gone.status_code == 200, gone.text
    assert gone.json()["aliases"] == []

    missing = client.delete(
        f"/api/vocabularies/terms/{term}/aliases",
        params={"value": "없는표기"},
        headers=admin.headers,
    )
    assert missing.status_code == 404


def test_축의_이름_설명_정책_속성_칸을_고친다(client: TestClient, admin: Signed) -> None:
    before = next(
        one
        for one in client.get("/api/vocabularies", headers=admin.headers).json()
        if one["slug"] == "calibration_provider"
    )
    changed = client.patch(
        "/api/vocabularies/calibration_provider",
        json={
            "description": "교정 성적서를 낸 기관.",
            "attribute_schema": [
                {"key": "accreditation", "label": "인정 번호", "kind": "text"},
                {"key": "scopes", "label": "인정 범위", "kind": "list"},
            ],
        },
        headers=admin.headers,
    )
    assert changed.status_code == 200, changed.text
    body = changed.json()
    assert body["slug"] == "calibration_provider"
    assert body["label"] == before["label"]  # 안 보낸 것은 안 바뀐다
    assert body["description"] == "교정 성적서를 낸 기관."
    assert [one["key"] for one in body["attribute_schema"]] == ["accreditation", "scopes"]

    # 겹치는 키는 거절 — 화면이 어느 칸에 쓸지 알 수 없다.
    clash = client.patch(
        "/api/vocabularies/calibration_provider",
        json={"attribute_schema": [{"key": "a", "label": "A"}, {"key": "a", "label": "B"}]},
        headers=admin.headers,
    )
    assert clash.status_code == 400
    assert clash.json()["error"]["code"] == "TSC-VOCAB-0010"

    # 되돌린다 — 다른 시험이 이 축을 본다.
    client.patch(
        "/api/vocabularies/calibration_provider",
        json={"description": before["description"], "attribute_schema": []},
        headers=admin.headers,
    )


def test_물성_축은_속성_칸을_갖고_값의_속성을_고칠_수_있다(
    client: TestClient, admin: Signed
) -> None:
    axis = next(
        one
        for one in client.get("/api/vocabularies", headers=admin.headers).json()
        if one["slug"] == "property"
    )
    assert {one["key"] for one in axis["attribute_schema"]} >= {"symbol", "si_unit", "domain"}

    tag = uuid.uuid4().hex[:6]
    made = client.post(
        "/api/vocabularies/property/terms",
        json={
            "value": f"항복강도-{tag}",
            "code": f"mechanical.yield_strength_{tag}",
            "attributes": {"symbol": "Rp0.2", "si_unit": "Pa"},
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    fixed = client.patch(
        f"/api/vocabularies/terms/{made.json()['id']}",
        json={"attributes": {"symbol": "Rp0.2", "si_unit": "Pa", "domain": "mechanical"}},
        headers=admin.headers,
    )
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["attributes"]["domain"] == "mechanical"


def test_쓰임의_내역을_보고_한_줄씩_떼거나_옮긴다(
    client: TestClient, admin: Signed, term_factory: Callable[[str, str], str]
) -> None:
    """쓰임 수 「2」 는 지워도 되나에는 답하지만 그 둘이 무엇인가에는 답하지 않는다.
    보고, 그 자리에서 떼고 옮길 수 있어야 계열 화면까지 안 가고 고친다."""
    tag = uuid.uuid4().hex[:6]
    item = term_factory("test_item", f"굽힘-{tag}")
    other = term_factory("test_item", f"3점 굽힘-{tag}")
    series_a = _series(client, admin, f"A-{tag}")
    series_b = _series(client, admin, f"B-{tag}")
    _series_item(client, admin, series_a, item)
    _series_item(client, admin, series_b, item)
    method = client.post(
        "/api/methods",
        json={"code": f"ISO 178-{tag}", "title": "굽힘", "test_item_term_id": item},
        headers=admin.headers,
    ).json()

    groups = client.get(f"/api/vocabularies/terms/{item}/references", headers=admin.headers)
    assert groups.status_code == 200, groups.text
    by_key = {one["key"]: one for one in groups.json()}
    assert {row["label"] for row in by_key["series_test_item"]["rows"]} == {
        f"A-{tag}",
        f"B-{tag}",
    }
    assert by_key["series_test_item"]["detach"] == "delete"
    assert by_key["method_test_item"]["rows"][0]["href"] == f"/methods/{method['id']}"
    assert by_key["method_test_item"]["detach"] == "null"
    # 내역의 합이 쓰임 수다 — 세는 표와 보여 주는 표가 같다.
    total = sum(len(one["rows"]) for one in groups.json())
    assert _term(client, admin, item, "test_item")["usage_count"] == total == 3

    # 계열 A 의 줄을 뗀다 → 연결 줄이 지워진다.
    a_row = next(r for r in by_key["series_test_item"]["rows"] if r["label"] == f"A-{tag}")
    gone = client.delete(
        f"/api/vocabularies/terms/{item}/references/series_test_item/{a_row['id']}",
        headers=admin.headers,
    )
    assert gone.status_code == 204, gone.text
    a = client.get(f"/api/equipment-series/{series_a}", headers=admin.headers).json()
    assert a["test_items"] == []

    # 시험법의 시험 항목을 뗀다 → 칸이 비워진다(규격은 남는다).
    m_row = by_key["method_test_item"]["rows"][0]
    client.delete(
        f"/api/vocabularies/terms/{item}/references/method_test_item/{m_row['id']}",
        headers=admin.headers,
    )
    assert (
        client.get(f"/api/methods/{method['id']}", headers=admin.headers).json()["test_item"]
        is None
    )

    # 계열 B 의 줄을 다른 값으로 옮긴다.
    b_row = next(r for r in by_key["series_test_item"]["rows"] if r["label"] == f"B-{tag}")
    moved = client.post(
        f"/api/vocabularies/terms/{item}/references/series_test_item/{b_row['id']}/reassign",
        json={"target_term_id": other},
        headers=admin.headers,
    )
    assert moved.status_code == 204, moved.text
    b = client.get(f"/api/equipment-series/{series_b}", headers=admin.headers).json()
    assert [one["test_item_term_id"] for one in b["test_items"]] == [other]
    assert _term(client, admin, item, "test_item")["usage_count"] == 0

    # 비울 수 없는 칸(장비의 거점)은 떼지 못하고 옮기기만 된다.
    site = term_factory("site", f"거점-{tag}")
    equipment = client.post(
        "/api/equipment",
        json={
            "asset_no": f"E-{tag}",
            "name": "장비",
            "workspace_slug": admin.workspace,
            "site_term_id": site,
            "location": "1동",
            "category_term_id": category_id(client, admin),
        },
        headers=admin.headers,
    ).json()
    refs = client.get(
        f"/api/vocabularies/terms/{site}/references", headers=admin.headers
    ).json()
    assert refs[0]["detach"] == "none"
    refused = client.delete(
        f"/api/vocabularies/terms/{site}/references/equipment_site/{equipment['id']}",
        headers=admin.headers,
    )
    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "TSC-VOCAB-0014"

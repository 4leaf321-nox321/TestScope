"""기종 목록의 **대표 사양** — 이름만으로는 못 고른다.

한 계열에 기종이 열일곱까지 있고, 제조사·계열·시험 항목은 그 열일곱이 전부 같다
(계열이 갖는 값이다 — ADR 0006). 그러니 목록 한 줄이 무엇을 보여 줘야 고를 수
있느냐는 **수치**이고, 어느 수치냐는 분류가 정한다.

여기서 지키는 것 셋:

1. 분류가 정한 대표(`headline_specs`)가 **검색축보다 먼저**다.
2. 대표를 안 정한 분류는 **검색축에 이은 사양으로 대신한다** — 통째로 비면 그
   화면은 「사양이 없다」 로 읽히는데, 실제로는 적을 자리를 안 정한 것이다.
3. 값이 없는 대표는 **안 싣는다** — 라벨만 그려진 빈 칸은 0 으로도 모름으로도 읽힌다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import Signed


def _definitions(client: TestClient, admin: Signed) -> dict[str, dict[str, Any]]:
    response = client.get("/api/spec-definitions", headers=admin.headers)
    assert response.status_code == 200, response.text
    return {row["key"]: row for row in response.json()}


def _category(client: TestClient, admin: Signed, headline: list[str] | None) -> str:
    """대표 사양을 적어 둔 장비 분류 하나. **정본은 온톨로지**이고, 반입이 그것을
    이 칸(`attributes.headline_specs`)으로 옮긴다."""
    payload: dict[str, Any] = {"value": f"분류-{uuid.uuid4().hex[:6]}"}
    if headline is not None:
        payload["attributes"] = {"headline_specs": headline}
    response = client.post(
        "/api/vocabularies/equipment_category/terms", json=payload, headers=admin.headers
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _model(client: TestClient, admin: Signed, *, category_term_id: str | None) -> str:
    series = client.post(
        "/api/equipment-series",
        json={
            "name": f"계열-{uuid.uuid4().hex[:6]}",
            **({"category_term_id": category_term_id} if category_term_id else {}),
        },
        headers=admin.headers,
    )
    assert series.status_code == 201, series.text
    response = client.post(
        "/api/equipment-models",
        json={"series_id": series.json()["id"], "name": f"기종-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _put(client: TestClient, admin: Signed, model_id: str, **payload: object) -> None:
    response = client.put(
        f"/api/equipment-models/{model_id}/specs", json=payload, headers=admin.headers
    )
    assert response.status_code == 200, response.text


def _listed(client: TestClient, admin: Signed, model_id: str) -> dict[str, Any]:
    """목록에서 그 기종 한 줄. **목록이 주는 것을 본다** — 상세만 확인하면 목록이
    비어 있어도 시험은 통과한다."""
    response = client.get("/api/equipment-models?limit=200", headers=admin.headers)
    assert response.status_code == 200, response.text
    rows = [row for row in response.json()["items"] if row["id"] == model_id]
    assert rows, "목록에 그 기종이 없다"
    row: dict[str, Any] = rows[0]
    return row


def test_분류가_정한_대표_사양이_검색축보다_먼저다(client: TestClient, admin: Signed) -> None:
    definitions = _definitions(client, admin)
    # 무게는 검색축에 안 이어진 사양이고, 하중 용량은 이어진 사양이다.
    category = _category(client, admin, ["weight"])
    model = _model(client, admin, category_term_id=category)
    _put(client, admin, model, definition_id=definitions["weight"]["id"], num_value=850)
    _put(
        client,
        admin,
        model,
        definition_id=definitions["force_capacity"]["id"],
        num_value=300,
    )

    row = _listed(client, admin, model)
    keys = [spec["key"] for spec in row["headline_specs"]]
    assert keys == ["weight"], keys
    assert row["headline_specs"][0]["num_value"] == 850
    assert row["headline_specs"][0]["display_unit"] == "kg"
    assert row["spec_count"] == 2


def test_대표를_안_정한_분류는_검색축에_이은_사양으로_대신한다(
    client: TestClient, admin: Signed
) -> None:
    definitions = _definitions(client, admin)
    model = _model(client, admin, category_term_id=_category(client, admin, None))
    _put(client, admin, model, definition_id=definitions["weight"]["id"], num_value=850)
    _put(
        client,
        admin,
        model,
        definition_id=definitions["force_capacity"]["id"],
        num_value=300,
    )

    keys = [spec["key"] for spec in _listed(client, admin, model)["headline_specs"]]
    # 무게는 검색이 묻는 축이 아니다 — 대신 세우는 자리에는 안 온다.
    assert keys == ["force_capacity"], keys


def test_값이_없는_대표는_안_싣고_사양_칸_수로_말한다(
    client: TestClient, admin: Signed
) -> None:
    definitions = _definitions(client, admin)
    category = _category(client, admin, ["force_capacity"])
    model = _model(client, admin, category_term_id=category)

    empty = _listed(client, admin, model)
    assert empty["headline_specs"] == []
    assert empty["spec_count"] == 0

    # 대표로 정한 칸이 아닌 값만 있으면, 대표는 여전히 비고 칸 수만 는다.
    _put(client, admin, model, definition_id=definitions["weight"]["id"], num_value=850)
    filled = _listed(client, admin, model)
    assert filled["headline_specs"] == []
    assert filled["spec_count"] == 1


def test_상세도_목록과_같은_대표_사양을_준다(client: TestClient, admin: Signed) -> None:
    """**한 곳에서만 정한다.** 상세가 따로 계산하면 두 화면이 다른 수치를 대표로
    내세우는 날이 오고, 그때 어느 쪽이 맞는지는 아무도 모른다."""
    definitions = _definitions(client, admin)
    category = _category(client, admin, ["force_capacity"])
    model = _model(client, admin, category_term_id=category)
    _put(
        client,
        admin,
        model,
        definition_id=definitions["force_capacity"]["id"],
        num_value=300,
    )

    detail = client.get(f"/api/equipment-models/{model}", headers=admin.headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["headline_specs"] == _listed(client, admin, model)["headline_specs"]

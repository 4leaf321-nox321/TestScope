"""카탈로그가 **한 칸에 여러 벌을 적어 오는** 자리들.

원본은 사양을 늘 한 값으로 적지 않는다. 그냥 담으면 각각 다른 방식으로 틀린 값이 된다:

    [15, 25]                 고를 수 있는 구성 -> 최대만 담으면 15 짜리가 25 라고 답한다
    [[0.6, 260], [6, 2600]]  저·고 두 레인지  -> 합치면 레인지별 분해능이 사라진다
    400 (상한만)             구간에 그냥 넣으면 400~400 이 되어 100 도에 안 걸린다

여기서 지키는 것:

1. 세 규칙표가 가리키는 정의가 **실재한다.** 오타 하나면 그 값이 조용히 안 들어온다.
2. 같은 축에 확정값과 구성 구간이 함께 오면 **확정값이 이긴다.**
3. 위쪽 시험공간 하중은 하중 용량과 **다른 칸**이고, 검색축에 안 잇는다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.modules.vocabulary.catalog_specs import (
    CATALOG_SPEC_DEFINITIONS,
    MAX_ONLY_SOURCES,
    OPTION_RANGE_SOURCES,
    RANGE_PAIR_SOURCES,
    SOURCE_SPEC_MAP,
)
from app.modules.vocabulary.reference import SPEC_DEFINITIONS
from tests.api.conftest import Signed, category_id, site_id

#: 반입이 심는 것과 설치가 심는 것을 합친 전부.
_ALL = {row[0]: row for row in [*SPEC_DEFINITIONS, *CATALOG_SPEC_DEFINITIONS]}


def test_반입_규칙이_가리키는_정의가_실재한다() -> None:
    """오타 하나면 그 값이 **조용히 안 들어온다.** 반입은 아무 말도 안 하고 넘어간다."""
    wanted: set[str] = set(OPTION_RANGE_SOURCES.values()) | set(MAX_ONLY_SOURCES.values())
    for low, high in RANGE_PAIR_SOURCES.values():
        wanted |= {low, high}
    wanted |= {target for target, _ in SOURCE_SPEC_MAP.values()}
    missing = sorted(key for key in wanted if key not in _ALL)
    assert not missing, f"정의가 없는 이름을 가리킨다: {missing}"


def test_구성_배열은_구간_정의로_간다() -> None:
    """`[15, 25]` 는 「15 나 25 로 나온다」 이지 「25 다」 가 아니다 — 수치 하나로
    담으면 15 짜리를 가진 부서가 25 된다고 답한다."""
    for target in set(OPTION_RANGE_SOURCES.values()):
        assert _ALL[target][3] == "range", target


def test_상한만_적힌_값은_구간_정의로_간다() -> None:
    """400 을 수치 정의에 넣으면 「400 도에서만」 이 된다."""
    for target in set(MAX_ONLY_SOURCES.values()):
        assert _ALL[target][3] == "range", target


def test_이중_레인지는_정의_둘로_나뉜다() -> None:
    for low, high in RANGE_PAIR_SOURCES.values():
        assert low != high
        # 같은 단위여야 한다 — 저·고가 다른 단위면 나눈 뜻이 없다.
        assert _ALL[low][5] == _ALL[high][5], (low, high)


def test_위쪽_시험공간_하중은_검색축에_안_이어진다() -> None:
    """3 kN 인데 그 장비 아래쪽은 300 kN 일 수 있다. 이 값으로 「300 kN 되나」 에
    답하면 검색이 거짓말을 한다."""
    upper = _ALL["upper_test_space_force"]
    assert upper[6] is None, upper
    assert SOURCE_SPEC_MAP["upper_test_room_load_kN"][0] == "upper_test_space_force"
    # 반대로 구성별 하중은 **하중 축에 이어야** 검색이 범위로 답한다.
    assert _ALL["force_capacity_range"][6] == "force"


def _group_id(client: TestClient, admin: Signed) -> str:
    response = client.get("/api/spec-groups", headers=admin.headers)
    assert response.status_code == 200, response.text
    return str(response.json()[0]["id"])


def _definitions(client: TestClient, admin: Signed) -> dict[str, dict[str, Any]]:
    response = client.get("/api/spec-definitions", headers=admin.headers)
    assert response.status_code == 200, response.text
    return {row["key"]: row for row in response.json()}


def test_확정값이_구성_구간을_이긴다(client: TestClient, admin: Signed) -> None:
    """한 기종이 둘 다 갖는 일이 있다 — 실측 15기종 중 8기종이 그렇다.

    구성별 값은 「이 기종은 이 범위로 나온다」 이지 「이 대가 그렇다」 가 아니다.
    순서에 맡기면 같은 기종이 반입할 때마다 다른 조건을 갖고, 그 차이는 검색 결과가
    갈린 날에야 드러난다.
    """
    definitions = _definitions(client, admin)
    force = definitions["force_capacity"]

    made = client.post(
        "/api/spec-definitions",
        json={
            "key": f"force_options_{uuid.uuid4().hex[:6]}",
            "label": "하중 용량(구성별)",
            "group_id": _group_id(client, admin),
            "kind": "range",
            "dimension": "force",
            "si_unit": "kN",
            "display_unit": "kN",
            # **같은 검색축에 이어 둔다.** 충돌이 생기는 자리가 바로 여기다.
            "condition_key_id": force["condition_key_id"],
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    options = made.json()

    series = client.post(
        "/api/equipment-series",
        json={"name": f"계열-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    model = client.post(
        "/api/equipment-models",
        json={"series_id": series.json()["id"], "name": f"기종-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert model.status_code == 201, model.text
    model_id = model.json()["id"]

    for payload in (
        {"definition_id": options["id"], "num_min": 15, "num_max": 25},
        {"definition_id": force["id"], "num_value": 300},
    ):
        saved = client.put(
            f"/api/equipment-models/{model_id}/specs", json=payload, headers=admin.headers
        )
        assert saved.status_code == 200, saved.text

    # 장비를 등록하면 그때 사양이 시험 조건으로 합쳐진다(ADR 0006).
    item = client.post(
        "/api/vocabularies/test_item/terms",
        json={"value": f"인장-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    added = client.post(
        f"/api/equipment-series/{series.json()['id']}/test_items",
        json={"test_item_term_id": item.json()["id"]},
        headers=admin.headers,
    )
    assert added.status_code == 201, added.text

    equipment = client.post(
        "/api/equipment",
        json={
            "asset_no": f"SHP-{uuid.uuid4().hex[:6]}",
            "name": "구성이 여럿인 기종의 장비",
            "workspace_slug": admin.workspace,
            "site_term_id": site_id(client, admin),
            "location": "3동 201호",
            "category_term_id": category_id(client, admin),
            "model_id": model_id,
        },
        headers=admin.headers,
    )
    assert equipment.status_code == 201, equipment.text

    test_items = client.get(
        f"/api/equipment-test-items?equipment_id={equipment.json()['id']}",
        headers=admin.headers,
    )
    assert test_items.status_code == 200, test_items.text
    limits = [
        limit
        for test_item in test_items.json()
        for limit in test_item["limits"]
        if limit["condition_key"] == "force"
    ]
    assert limits, test_items.text
    # 구성별 15~25 가 아니라 확정 300 이다.
    assert limits[0]["max_value"] == 300, limits

"""카탈로그 목록의 **열별 거르기** — 거르는 것은 서버다.

## 왜 서버여야 하나

화면이 한 쪽을 받아 놓고 스스로 거르면, 상한을 넘는 순간 나머지가 조용히 빠진다.
그때 목록은 「그 조건에 맞는 것이 이것뿐」 이라고 **거짓말**한다 — 그리고 그 거짓말은
화면 어디에도 안 남아서, 못 찾은 사람은 없다고 결론 내리고 계열을 새로 만든다.

## 여기서 지키는 것

1. 열마다 거르면 **그 열만** 좁힌다 — 이름 칸에 친 글자가 제조사에 걸린 줄을
   데려오면, 그 줄들이 찾는 것을 가린다.
2. 제조사·분류는 **계열이 갖는 값**이라(ADR 0006) 기종을 거르려면 계열을 거친다.
3. 고를 수 있는 값은 **카탈로그에 실제로 있는 것뿐**이다.
4. 홈의 「남은 일」 이 세는 조건과 목록이 거르는 조건이 **같은 말**이어야 한다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from tests.api.conftest import Signed


def _term(client: TestClient, admin: Signed, axis: str, value: str) -> str:
    response = client.post(
        f"/api/vocabularies/{axis}/terms", json={"value": value}, headers=admin.headers
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _series(client: TestClient, admin: Signed, **payload: Any) -> dict[str, Any]:
    body = {"name": f"계열-{uuid.uuid4().hex[:8]}", **payload}
    response = client.post("/api/equipment-series", json=body, headers=admin.headers)
    assert response.status_code == 201, response.text
    row: dict[str, Any] = response.json()
    return row


def _model(
    client: TestClient, admin: Signed, series_id: str, **payload: Any
) -> dict[str, Any]:
    body = {"series_id": series_id, "name": f"기종-{uuid.uuid4().hex[:8]}", **payload}
    response = client.post("/api/equipment-models", json=body, headers=admin.headers)
    assert response.status_code == 201, response.text
    row: dict[str, Any] = response.json()
    return row


def _ids(client: TestClient, admin: Signed, path: str) -> set[str]:
    response = client.get(path, headers=admin.headers)
    assert response.status_code == 200, response.text
    return {row["id"] for row in response.json()["items"]}


def test_계열을_제조사로_거른다(client: TestClient, admin: Signed) -> None:
    maker = _term(client, admin, "manufacturer", f"제조사-{uuid.uuid4().hex[:8]}")
    mine = _series(client, admin, maker_term_id=maker)
    other = _series(client, admin)

    found = _ids(client, admin, f"/api/equipment-series?maker_term_id={maker}&limit=200")
    assert mine["id"] in found
    assert other["id"] not in found


def test_계열_이름_칸은_그_열만_본다(client: TestClient, admin: Signed) -> None:
    """`q` 는 제조사까지 보고 `name` 은 이름만 본다.

    한 칸으로 합치면 이름을 치는 사람이 **제조사에 걸린 줄을 함께** 보게 되고, 그
    줄들이 찾는 것을 가린다.
    """
    tag = uuid.uuid4().hex[:8]
    maker = _term(client, admin, "manufacturer", f"제조사{tag}")
    by_name = _series(client, admin, name=f"이름{tag}")
    by_maker = _series(client, admin, maker_term_id=maker)

    loose = _ids(client, admin, f"/api/equipment-series?q={tag}&limit=200")
    assert {by_name["id"], by_maker["id"]} <= loose

    tight = _ids(client, admin, f"/api/equipment-series?name={tag}&limit=200")
    assert by_name["id"] in tight
    assert by_maker["id"] not in tight


def test_기종을_계열의_제조사와_분류로_거른다(client: TestClient, admin: Signed) -> None:
    """제조사·분류는 **기종이 갖지 않는다**(ADR 0006) — 한 계열 열 기종에 열 번
    적히면 그 열 번이 언젠가 서로 달라진다. 그래서 계열을 거쳐 거른다."""
    maker = _term(client, admin, "manufacturer", f"제조사-{uuid.uuid4().hex[:8]}")
    category = _term(client, admin, "equipment_category", f"분류-{uuid.uuid4().hex[:8]}")
    series = _series(client, admin, maker_term_id=maker, category_term_id=category)
    mine = _model(client, admin, series["id"])
    other = _model(client, admin, _series(client, admin)["id"])

    by_maker = _ids(client, admin, f"/api/equipment-models?maker_term_id={maker}&limit=200")
    assert mine["id"] in by_maker
    assert other["id"] not in by_maker

    by_category = _ids(
        client, admin, f"/api/equipment-models?category_term_id={category}&limit=200"
    )
    assert mine["id"] in by_category
    assert other["id"] not in by_category


def test_기종이_없는_계열만_거른다(client: TestClient, admin: Signed) -> None:
    """**0 이면 아무도 이 계열을 가리킬 수 없다** — 보유 장비가 가리키는 것은
    계열이 아니라 기종이다."""
    empty = _series(client, admin)
    filled = _series(client, admin)
    _model(client, admin, filled["id"])

    found = _ids(client, admin, "/api/equipment-series?models=none&limit=200")
    assert empty["id"] in found
    assert filled["id"] not in found


def test_시험_항목이_없는_계열만_거른다(client: TestClient, admin: Signed) -> None:
    """홈의 「남은 일」 이 이 조건으로 링크한다. 세는 조건과 거르는 조건이 다르면
    그 줄을 눌러 온 사람이 다른 목록을 보고, 그때 둘 다 안 믿는다."""
    bare = _series(client, admin)
    filled = _series(client, admin)
    item = _term(client, admin, "test_item", f"항목-{uuid.uuid4().hex[:8]}")
    added = client.post(
        f"/api/equipment-series/{filled['id']}/test-items",
        json={"test_item_term_id": item},
        headers=admin.headers,
    )
    assert added.status_code == 201, added.text

    found = _ids(client, admin, "/api/equipment-series?test_item=none&limit=200")
    assert bare["id"] in found
    assert filled["id"] not in found

    # 기종 쪽도 같은 말을 쓴다 — 계열에 시험 항목이 없으면 그 기종으로 등록한
    # 장비는 검색에 안 걸린다.
    orphan = _model(client, admin, bare["id"])
    covered = _model(client, admin, filled["id"])
    models = _ids(client, admin, "/api/equipment-models?test_item=none&limit=200")
    assert orphan["id"] in models
    assert covered["id"] not in models


def test_고를_수_있는_값은_카탈로그에_있는_것뿐이다(client: TestClient, admin: Signed) -> None:
    """기준정보 전체를 펼치면 골라도 0 건인 선택지가 섞이고, 한 번 겪으면 사람은
    거르기를 안 믿는다."""
    used = _term(client, admin, "manufacturer", f"쓰는제조사-{uuid.uuid4().hex[:8]}")
    unused = _term(client, admin, "manufacturer", f"안쓰는제조사-{uuid.uuid4().hex[:8]}")
    _series(client, admin, maker_term_id=used)

    response = client.get("/api/equipment-series/filter-options", headers=admin.headers)
    assert response.status_code == 200, response.text
    makers = {row["value"] for row in response.json()["makers"]}
    assert used in makers
    assert unused not in makers, "카탈로그가 안 쓰는 제조사가 선택지에 있다"


def test_기종_선택지의_수는_기종_수다(client: TestClient, admin: Signed) -> None:
    """계열 수를 적으면 **고른 뒤 나오는 줄 수와 안 맞는다** — 그 어긋남 하나가
    거르기를 안 믿게 만든다."""
    maker = _term(client, admin, "manufacturer", f"제조사-{uuid.uuid4().hex[:8]}")
    series = _series(client, admin, maker_term_id=maker)
    for _ in range(3):
        _model(client, admin, series["id"])

    response = client.get("/api/equipment-models/filter-options", headers=admin.headers)
    assert response.status_code == 200, response.text
    row = next(one for one in response.json()["makers"] if one["value"] == maker)
    assert row["count"] == 3, "제조사 옆의 수가 기종 수가 아니다"

    listed = client.get(
        f"/api/equipment-models?maker_term_id={maker}&limit=200", headers=admin.headers
    )
    assert listed.json()["total"] == row["count"], "선택지의 수와 걸러진 줄 수가 다르다"


def test_계열_목록_링크가_홈이_세는_것과_같다(client: TestClient, admin: Signed) -> None:
    """홈의 「남은 일」 이 계열 목록으로 거는 링크. **그 주소를 그대로 부른다** —
    링크 문자열과 거르기가 어긋나면 눌러 온 사람이 전체 목록을 본다.

    실제로 그런 일이 있었다: 링크는 `issue=test_items` 를 달고 갔는데 서버가 받는
    이름은 다른 것이었고, 모르는 조건은 조용히 무시되어 **전체 목록**이 떴다.
    """
    # 「남은 일」 은 **우리가 가진 것만** 센다 — 카탈로그 전부를 채우라고 하면
    # 아무도 안 채운다. 그래서 세어지려면 보유 장비가 하나 있어야 한다.
    bare = _series(client, admin)
    model = _model(client, admin, bare["id"])
    made = client.post(
        "/api/equipment",
        json={
            "asset_no": f"LINK-{uuid.uuid4().hex[:6]}",
            "name": "링크 확인용",
            "site_term_id": _term(client, admin, "site", f"거점-{uuid.uuid4().hex[:6]}"),
            "location": "3동 201호",
            "workspace_slug": admin.workspace,
            "model_id": model["id"],
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text

    response = client.get("/api/server/maintenance", headers=admin.headers)
    assert response.status_code == 200, response.text
    rows = {row["key"]: row for row in response.json()}
    assert rows["series_without_test_item"]["count"] >= 1
    assert (
        rows["series_without_test_item"]["link"]
        == "/catalog/equipment-series?owned=1&test_item=none"
    )

    # **링크가 가리키는 그 주소를 그대로 부른다.**
    listed = client.get(
        "/api/equipment-series?owned=true&test_item=none&limit=200", headers=admin.headers
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == rows["series_without_test_item"]["count"]
    assert bare["id"] in {row["id"] for row in listed.json()["items"]}

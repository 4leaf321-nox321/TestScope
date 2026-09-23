"""항목 정의·값 — 칸을 미리 뚫지 않고 이름을 행으로 둔다.

여기서 지키는 것 — 새 이름은 초안이 되고 같은 이름은 다시 안 생긴다 · 종류가 요구하는 칸이
비면 거절 · 정식은 시스템 관리자만 · 초안은 의미 색인 카드에 안 들어가고 정식은 들어간다 ·
합치면 값이 옮겨 가고 원래 항목은 꺼진다 · 값이 있는 항목의 종류는 못 바꾼다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.workspaces.models import Workspace
from app.shared import semantic
from tests.api.conftest import Signed
from tests.api.test_reliability_tests import _signed_in


def _definitions(client: TestClient, who: Signed, **params: str) -> list[dict[str, Any]]:
    got = client.get(
        "/api/attribute-definitions",
        params={"target": "reliability_test", **params},
        headers=who.headers,
    )
    assert got.status_code == 200, got.text
    rows: list[dict[str, Any]] = got.json()
    return rows


def test_새_이름은_초안이_되고_정식_항목과_함께_값이_붙는다(
    client: TestClient, db: Session, admin: Signed, condition_ids: dict[str, str]
) -> None:
    tag = uuid.uuid4().hex[:6]
    lab = Workspace(slug=f"lab-{tag}", name="신뢰성팀")
    db.add(lab)
    db.commit()
    manager = _signed_in(client, db, lab, "manager")

    # 관리자가 정식 항목 하나를 미리 — 조건 종류는 검색 조건 축이 필요하다.
    no_axis = client.post(
        "/api/attribute-definitions",
        json={"target": "reliability_test", "label": f"시험 온도-{tag}", "kind": "condition"},
        headers=admin.headers,
    )
    assert no_axis.status_code == 400, no_axis.text
    standard = client.post(
        "/api/attribute-definitions",
        json={
            "target": "reliability_test",
            "label": f"시험 온도-{tag}",
            "kind": "condition",
            "unit": "degC",
            "condition_key_id": condition_ids["temperature"],
            "is_required": True,
        },
        headers=admin.headers,
    )
    assert standard.status_code == 201, standard.text
    temperature_id = standard.json()["id"]
    # 부서 관리자는 정식 항목을 못 만든다.
    assert (
        client.post(
            "/api/attribute-definitions",
            json={"target": "reliability_test", "label": f"x-{tag}"},
            headers=manager.headers,
        ).status_code
        == 403
    )

    # 부서 관리자가 시험을 적으며 정식 항목 값 + 새 이름 둘(수치·문장).
    made = client.post(
        "/api/reliability-tests",
        json={
            "workspace_slug": lab.slug,
            "name": f"고온고습-{tag}",
            "attributes": [
                {
                    "definition_id": temperature_id,
                    "num_min": 85,
                    "num_max": 85,
                    "unit": "degC",
                },
                {"new_label": f"시료 수-{tag}", "new_kind": "number", "num_value": 5},
                {
                    "new_label": f"판정 기준-{tag}",
                    "new_kind": "text",
                    "text_value": "외관 이상 없음",
                },
            ],
        },
        headers=manager.headers,
    )
    assert made.status_code == 201, made.text
    shown = {one["label"]: one for one in made.json()["attributes"]}
    assert shown[f"시험 온도-{tag}"]["status"] == "standard"
    assert shown[f"시험 온도-{tag}"]["display"] == "85 ~ 85 degC"
    assert shown[f"시료 수-{tag}"]["status"] == "draft"
    assert shown[f"시료 수-{tag}"]["display"] == "5"
    # 정식이 먼저 온다.
    assert made.json()["attributes"][0]["status"] == "standard"

    # 초안이 목록에 서고, 건수가 붙는다. 대소문자만 다른 같은 이름은 다시 안 생긴다.
    listed = {one["label"]: one for one in _definitions(client, manager)}
    assert listed[f"시료 수-{tag}"]["status"] == "draft"
    assert listed[f"시료 수-{tag}"]["value_count"] == 1
    again = client.post(
        "/api/reliability-tests",
        json={
            "workspace_slug": lab.slug,
            "name": f"열충격-{tag}",
            "attributes": [
                {"new_label": f"시료 수-{tag.upper()}", "new_kind": "text", "num_value": 10}
            ],
        },
        headers=manager.headers,
    )
    assert again.status_code == 201, again.text
    listed = {one["label"]: one for one in _definitions(client, manager)}
    assert listed[f"시료 수-{tag}"]["value_count"] == 2
    assert f"시료 수-{tag.upper()}" not in listed

    # 종류가 요구하는 칸이 비면 거절 — 수치 항목에 글만 보내면.
    wrong = client.post(
        "/api/reliability-tests",
        json={
            "workspace_slug": lab.slug,
            "name": f"틀림-{tag}",
            "attributes": [
                {"definition_id": listed[f"시료 수-{tag}"]["id"], "text_value": "다섯"}
            ],
        },
        headers=manager.headers,
    )
    assert wrong.status_code == 400, wrong.text

    # 수정은 통째로 바뀐다 — 하나만 보내면 나머지는 사라진다.
    patched = client.patch(
        f"/api/reliability-tests/{made.json()['id']}",
        json={
            "attributes": [{"definition_id": temperature_id, "num_min": -40, "num_max": 125}]
        },
        headers=manager.headers,
    )
    assert patched.status_code == 200, patched.text
    # **단위를 빼지 않는다**(2026-09-23). 값에 단위를 안 보내도 칸의 단위로 읽어 준다 —
    # 「-40 ~ 125」 만 남으면 degC 인지 K 인지 알 수 없고, 그 답은 아무도 못 쓴다.
    assert [one["display"] for one in patched.json()["attributes"]] == ["-40 ~ 125 degC"]


def test_초안은_색인_카드에_안_들어가고_정식은_들어간다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    tag = uuid.uuid4().hex[:6]
    standard = client.post(
        "/api/attribute-definitions",
        json={"target": "reliability_test", "label": f"근거-{tag}", "kind": "text"},
        headers=admin.headers,
    ).json()
    made = client.post(
        "/api/reliability-tests",
        json={
            "workspace_slug": admin.workspace,
            "name": f"HAST-{tag}",
            "attributes": [
                {"definition_id": standard["id"], "text_value": f"사내 규정 {tag}"},
                {"new_label": f"메모-{tag}", "new_kind": "text", "text_value": f"비밀 {tag}"},
            ],
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    card = next(c for c in semantic.collect(db) if c.entity_id == made.json()["id"])
    assert f"근거-{tag}: 사내 규정 {tag}" in card.body
    assert f"비밀 {tag}" not in card.body


def test_합치면_값이_옮겨_가고_정식으로_올릴_수_있다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    tag = uuid.uuid4().hex[:6]

    def write(name: str, label: str, kind: str, **value: object) -> dict[str, Any]:
        made = client.post(
            "/api/reliability-tests",
            json={
                "workspace_slug": admin.workspace,
                "name": name,
                "attributes": [{"new_label": label, "new_kind": kind, **value}],
            },
            headers=admin.headers,
        )
        assert made.status_code == 201, made.text
        body: dict[str, Any] = made.json()
        return body

    first = write(f"A-{tag}", f"온도-{tag}", "range", num_min=-40, num_max=125, unit="degC")
    second = write(f"B-{tag}", f"시험온도-{tag}", "range", num_min=85, num_max=85, unit="degC")
    third = write(f"C-{tag}", f"Temp-{tag}", "text", text_value="상온")
    listed = {one["label"]: one for one in _definitions(client, admin)}
    onto = listed[f"온도-{tag}"]["id"]
    other = listed[f"시험온도-{tag}"]["id"]
    texty = listed[f"Temp-{tag}"]["id"]

    # 종류가 다르면 못 합친다 — 문장 값이 구간 항목에서 읽히지 않는다.
    assert (
        client.post(
            f"/api/attribute-definitions/{texty}/merge",
            json={"target_id": onto},
            headers=admin.headers,
        ).status_code
        == 409
    )
    merged = client.post(
        f"/api/attribute-definitions/{other}/merge",
        json={"target_id": onto},
        headers=admin.headers,
    )
    assert merged.status_code == 200, merged.text
    assert merged.json()["value_count"] == 2
    # 원래 항목은 꺼졌고 어디로 갔는지 남는다.
    gone = {one["id"]: one for one in _definitions(client, admin, include_inactive="true")}[
        other
    ]
    assert gone["is_active"] is False and gone["merged_into_id"] == onto
    assert f"시험온도-{tag}" not in {one["label"] for one in _definitions(client, admin)}
    # B 시험의 값은 이제 「온도」 로 읽힌다.
    b = client.get(f"/api/reliability-tests/{second['id']}", headers=admin.headers).json()
    assert [(one["label"], one["display"]) for one in b["attributes"]] == [
        (f"온도-{tag}", "85 ~ 85 degC")
    ]
    assert first["id"] and third["id"]

    # 정식으로 올리기 — status 하나. 값이 있는 항목의 종류는 못 바꾼다.
    promoted = client.patch(
        f"/api/attribute-definitions/{onto}",
        json={"status": "standard", "unit": "degC", "key": f"test_temperature_{tag}"},
        headers=admin.headers,
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["status"] == "standard"
    assert (
        client.patch(
            f"/api/attribute-definitions/{onto}", json={"kind": "text"}, headers=admin.headers
        ).status_code
        == 409
    )
    # 목록은 정식이 먼저다.
    statuses = [one["status"] for one in _definitions(client, admin)]
    assert statuses.index("standard") < statuses.index("draft")

    # 완전 삭제는 **값이 0건일 때만** — 값이 있으면 409, 오타 초안은 204.
    assert (
        client.delete(f"/api/attribute-definitions/{onto}", headers=admin.headers).status_code
        == 409
    )
    typo = client.post(
        "/api/attribute-definitions",
        json={"target": "reliability_test", "label": f"온됴-{tag}", "status": "draft"},
        headers=admin.headers,
    ).json()
    assert (
        client.delete(
            f"/api/attribute-definitions/{typo['id']}", headers=admin.headers
        ).status_code
        == 204
    )
    assert f"온됴-{tag}" not in {
        one["label"] for one in _definitions(client, admin, include_inactive="true")
    }


def test_보유_장비에도_같은_규칙으로_속성이_붙는다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    tag = uuid.uuid4().hex[:6]
    from tests.api.conftest import category_id, site_id

    standard = client.post(
        "/api/attribute-definitions",
        json={"target": "equipment", "label": f"담당 구역-{tag}", "kind": "text"},
        headers=admin.headers,
    ).json()
    made = client.post(
        "/api/equipment",
        json={
            "asset_no": f"EQ-{tag}",
            "name": "챔버",
            "workspace_slug": admin.workspace,
            "site_term_id": site_id(client, admin),
            "location": "3동",
            "category_term_id": category_id(client, admin),
            "attributes": [
                {"definition_id": standard["id"], "text_value": f"A라인 {tag}"},
                {"new_label": f"구매 연도-{tag}", "new_kind": "number", "num_value": 2021},
            ],
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    shown = {one["label"]: one for one in made.json()["attributes"]}
    assert shown[f"담당 구역-{tag}"]["status"] == "standard"
    assert shown[f"구매 연도-{tag}"] == {
        **shown[f"구매 연도-{tag}"],
        "status": "draft",
        "display": "2021",
    }
    # 신뢰성 시험 대상의 속성은 장비에 못 붙인다 — 목록이 섞이지 않게 대상을 가른다.
    other = client.post(
        "/api/attribute-definitions",
        json={"target": "reliability_test", "label": f"판정-{tag}", "kind": "text"},
        headers=admin.headers,
    ).json()
    wrong = client.patch(
        f"/api/equipment/{made.json()['id']}",
        json={"attributes": [{"definition_id": other["id"], "text_value": "x"}]},
        headers=admin.headers,
    )
    assert wrong.status_code == 400, wrong.text
    # 장비 카드에도 정식만.
    card = next(c for c in semantic.collect(db) if c.entity_id == made.json()["id"])
    assert f"담당 구역-{tag}: A라인 {tag}" in card.body
    assert "2021" not in card.body


def test_장비_계열과_시험법에도_속성이_붙고_허브가_종류마다_칸을_센다(
    client: TestClient, admin: Signed
) -> None:
    """모든 객체 종류에 관리자가 칸을 더할 수 있다 — 계열·규격도. 허브(/reference/overview)는
    종류마다 저장 방식·건수·고정 칸·정의한 칸을 한 줄로 준다."""
    tag = uuid.uuid4().hex[:6]
    series = client.post(
        "/api/equipment-series", json={"name": f"계열-{tag}"}, headers=admin.headers
    ).json()
    method = client.post(
        "/api/methods",
        json={"code": f"KS {tag}", "title": "규격"},
        headers=admin.headers,
    ).json()
    made = client.post(
        "/api/attribute-definitions",
        json={"target": "series", "label": f"국내 대리점-{tag}", "kind": "text"},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text

    patched = client.patch(
        f"/api/equipment-series/{series['id']}",
        json={
            "attributes": [
                {"definition_id": made.json()["id"], "text_value": "한국인스트론"},
                {
                    "new_label": f"보증 기간-{tag}",
                    "new_kind": "number",
                    "num_value": 2,
                    "unit": "년",
                },
            ]
        },
        headers=admin.headers,
    )
    assert patched.status_code == 200, patched.text
    shown = {one["label"]: one for one in patched.json()["attributes"]}
    assert shown[f"국내 대리점-{tag}"]["status"] == "standard"
    assert shown[f"보증 기간-{tag}"]["display"] == "2 년"

    # 규격 속성 — 값이 규격을 가리키는 종류(method)와 대상 열이 부딪히지 않는다.
    ref = client.post(
        "/api/attribute-definitions",
        json={"target": "method", "label": f"대체 규격-{tag}", "kind": "method"},
        headers=admin.headers,
    ).json()
    other = client.post(
        "/api/methods",
        json={"code": f"KS {tag}-2", "title": "다른 규격"},
        headers=admin.headers,
    ).json()
    patched = client.patch(
        f"/api/methods/{method['id']}",
        json={"attributes": [{"definition_id": ref["id"], "method_id": other["id"]}]},
        headers=admin.headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["attributes"][0]["display"] == f"KS {tag}-2"
    # 계열 속성 정의를 규격에 붙이면 거절.
    wrong = client.patch(
        f"/api/methods/{method['id']}",
        json={"attributes": [{"definition_id": made.json()["id"], "text_value": "x"}]},
        headers=admin.headers,
    )
    assert wrong.status_code == 400

    hub = client.get("/api/reference/overview", headers=admin.headers)
    assert hub.status_code == 200, hub.text
    kinds = {one["key"]: one for one in hub.json()}
    assert kinds["series"]["storage"] == "table" and kinds["series"]["defined_kind"] == "속성"
    assert kinds["series"]["defined_count"] >= 1 and kinds["series"]["draft_count"] >= 1
    assert kinds["model"]["defined_kind"] == "사양"
    assert kinds["axis:test_item"]["storage"] == "vocabulary"
    assert kinds["axis:test_item"]["defined_kind"] == "검색 조건"
    assert kinds["workspace"]["defined_kind"] is None


def test_보유_장비의_정식_속성은_설치가_심고_다시_심어도_안_겹친다(db: Session) -> None:
    """장비 용도 · 투자 연도 · 장비 예약 URL — 현장 장비 목록의 열 중 고정 칸에 없는 셋."""
    from sqlalchemy import select

    from app.modules.attributes.models import AttributeDefinition
    from app.modules.vocabulary.reference import ensure_equipment_attributes

    ensure_equipment_attributes(db)
    db.flush()
    again = ensure_equipment_attributes(db)
    assert again == 0
    keys = {
        d.key: d
        for d in db.scalars(
            select(AttributeDefinition).where(AttributeDefinition.target == "equipment")
        )
    }
    assert {"equipment_purpose", "investment_year", "reservation_url"} <= set(keys)
    assert keys["reservation_url"].status == "standard"
    assert keys["investment_year"].kind == "number"

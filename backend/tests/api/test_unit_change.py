"""단위를 고치면 저장된 숫자의 뜻이 바뀐다 — **값이 있으면 묻고, 고른 대로 한다.**

조건 축과 사양 정의는 숫자만 담고 단위는 정의에서 읽는다. 전에는 cm 를 m 로 고치면 감사에
한 줄 남고 그대로 통과해 152 가 152 m 가 됐다(v0.51.2 의 낙하 높이 버그와 같은 부류).

여기서 지키는 것 — 숫자가 있으면 409(어느 표에 몇 줄인지)이고 축은 그대로 · convert 는
세 표(장비 조건 · 계열 조건 · 규격 요구) / 두 표(기종 사양 · 개체 실측)를 같이 옮긴다 · keep 은
숫자를 안 건드린다 · 못 바꾸는 짝의 convert 는 409 · 숫자가 없으면 안 묻는다 · 속성 정의는
단위 없이 적힌 값에 옛 단위를 적어 뜻을 지킨다(고칠 때도, 합칠 때도) · 실측만 있는 사양
정의도 못 지운다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.test_items.models import SeriesTestCondition
from tests.api.conftest import Signed, category_id, site_id


def _ok(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


def _equipment(client: TestClient, admin: Signed, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = _ok(
        client.post(
            "/api/equipment",
            json={
                "asset_no": f"UC-{uuid.uuid4().hex[:6]}",
                "name": "단위 확인 장비",
                "workspace_slug": admin.workspace,
                "site_term_id": site_id(client, admin),
                "location": "3동 201호",
                "category_term_id": category_id(client, admin),
                **extra,
            },
            headers=admin.headers,
        ),
        201,
    )
    return body


def _axis(client: TestClient, admin: Signed) -> dict[str, Any]:
    """이 시험만 쓰는 길이 축 — 낙하 높이처럼 SI 는 m, 담는 단위는 cm. 심어 둔 축을 고치면
    다른 시험이 그 단위를 믿고 있다가 떨어진다."""
    tag = uuid.uuid4().hex[:6]
    body: dict[str, Any] = _ok(
        client.post(
            "/api/condition-keys",
            json={
                "key": f"t_len_{tag}",
                "label": f"확인 길이-{tag}",
                "kind": "range",
                "dimension": "length",
                "si_unit": "m",
                "display_unit": "cm",
            },
            headers=admin.headers,
        ),
        201,
    )
    return body


def _patch_axis(client: TestClient, admin: Signed, axis_id: str, **body: Any) -> Any:
    return client.patch(f"/api/condition-keys/{axis_id}", json=body, headers=admin.headers)


def test_숫자가_담긴_축의_단위는_말없이_못_바꾸고_고른_대로_옮긴다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    axis = _axis(client, admin)
    # 숫자가 하나도 없으면 묻지 않는다 — 물을 것이 없는데 물으면 사람은 생각 없이 누른다.
    _ok(_patch_axis(client, admin, axis["id"], display_unit="mm"))
    _ok(_patch_axis(client, admin, axis["id"], display_unit="cm"))

    item = _ok(
        client.post(
            "/api/vocabularies/test_item/terms",
            json={"value": f"낙하-{uuid.uuid4().hex[:6]}"},
            headers=admin.headers,
        ),
        201,
    )["id"]
    # 세 표에 한 줄씩 — 장비 조건 0~200, 계열 조건 10~150, 규격 요구 50 이상.
    equipment = _equipment(client, admin)
    test_item = _ok(
        client.post(
            "/api/equipment-test-items",
            json={"equipment_id": equipment["id"], "test_item_term_id": item},
            headers=admin.headers,
        ),
        201,
    )
    _ok(
        client.put(
            f"/api/equipment-test-items/{test_item['id']}/limits",
            json={"condition_key_id": axis["id"], "min_value": 0, "max_value": 200},
            headers=admin.headers,
        )
    )
    series = _ok(
        client.post(
            "/api/equipment-series",
            json={"name": f"계열-{uuid.uuid4().hex[:6]}"},
            headers=admin.headers,
        ),
        201,
    )
    series_item = _ok(
        client.post(
            f"/api/equipment-series/{series['id']}/test-items",
            json={"test_item_term_id": item},
            headers=admin.headers,
        ),
        201,
    )
    _ok(
        client.put(
            f"/api/equipment-series/{series['id']}/test-items/{series_item['id']}/limits",
            json={"condition_key_id": axis["id"], "min_value": 10, "max_value": 150},
            headers=admin.headers,
        )
    )
    method = _ok(
        client.post(
            "/api/methods",
            json={"code": f"UC {uuid.uuid4().hex[:6]}", "title": "단위 확인 규격"},
            headers=admin.headers,
        ),
        201,
    )
    _ok(
        client.put(
            f"/api/methods/{method['id']}/requirements",
            json={"condition_key_id": axis["id"], "min_value": 50},
            headers=admin.headers,
        )
    )

    def numbers() -> tuple[Any, ...]:
        limits = _ok(
            client.get(
                f"/api/equipment-test-items?equipment_id={equipment['id']}",
                headers=admin.headers,
            )
        )
        limit = next(
            one for one in limits[0]["limits"] if one["condition_key_id"] == axis["id"]
        )
        db.expire_all()
        series_limit = db.scalar(
            select(SeriesTestCondition).where(
                SeriesTestCondition.condition_key_id == uuid.UUID(axis["id"])
            )
        )
        assert series_limit is not None
        requirement = _ok(client.get(f"/api/methods/{method['id']}", headers=admin.headers))[
            "requirements"
        ][0]
        return (
            limit["min_value"],
            limit["max_value"],
            series_limit.min_value,
            series_limit.max_value,
            requirement["min_value"],
        )

    assert numbers() == (0, 200, 10, 150, 50)
    listed = _ok(client.get("/api/condition-keys", headers=admin.headers))
    # 계열 조건도 쓰임에 센다 — 빠져 있으면 「사용 2」 인 축이 실은 셋을 담고 있다.
    assert next(one for one in listed if one["id"] == axis["id"])["usage_count"] == 3

    # 말없이 바꾸면 409 — 어느 표에 몇 줄인지와 함께. 축은 그대로다.
    asked = _patch_axis(client, admin, axis["id"], display_unit="m")
    assert asked.status_code == 409, asked.text
    error = asked.json()["error"]
    assert error["code"] == "TSC-VOCAB-0017"
    assert error["details"]["stored"] == {"장비 조건": 1, "계열 조건": 1, "규격 요구": 1}
    listed = _ok(client.get("/api/condition-keys", headers=admin.headers))
    assert next(one for one in listed if one["id"] == axis["id"])["unit"] == "cm"

    # convert — 세 표가 같이 옮겨 간다(152 cm 가 1.52 m 이듯이).
    changed = _ok(
        _patch_axis(client, admin, axis["id"], display_unit="m", stored_values="convert")
    )
    assert changed["unit"] == "m"
    assert numbers() == (0, 2, 0.1, 1.5, 0.5)

    # 못 바꾸는 짝을 convert 로 보내면 409 — 지어서 옮기지 않는다.
    refused = _patch_axis(
        client, admin, axis["id"], display_unit="kg", stored_values="convert"
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "TSC-VOCAB-0018"

    # keep — 「단위 이름이 틀렸고 숫자는 원래 새 단위였다」. 숫자는 그대로다.
    _ok(_patch_axis(client, admin, axis["id"], display_unit="mm", stored_values="keep"))
    assert numbers() == (0, 2, 0.1, 1.5, 0.5)

    # 표기만 다른 같은 단위는 안 묻는다.
    _ok(_patch_axis(client, admin, axis["id"], display_unit="MM"))


def test_사양_정의도_숫자가_있으면_묻고_실측까지_같이_옮긴다(
    client: TestClient, admin: Signed
) -> None:
    tag = uuid.uuid4().hex[:6]
    group = _ok(client.get("/api/spec-groups", headers=admin.headers))[0]["id"]

    def definition(label: str) -> dict[str, Any]:
        body: dict[str, Any] = _ok(
            client.post(
                "/api/spec-definitions",
                json={
                    "key": f"uc_{label}_{tag}",
                    "label": f"{label}-{tag}",
                    "group_id": group,
                    "kind": "range",
                    "dimension": "force",
                    "si_unit": "gf",
                    "display_unit": "gf",
                },
                headers=admin.headers,
            ),
            201,
        )
        return body

    load = definition("load")
    measured_only = definition("measured")

    series = _ok(
        client.post(
            "/api/equipment-series",
            json={"name": f"계열-{tag}"},
            headers=admin.headers,
        ),
        201,
    )
    model = _ok(
        client.post(
            "/api/equipment-models",
            json={"series_id": series["id"], "name": f"기종-{tag}"},
            headers=admin.headers,
        ),
        201,
    )
    _ok(
        client.put(
            f"/api/equipment-models/{model['id']}/specs",
            json={"definition_id": load["id"], "num_min": 10, "num_max": 500},
            headers=admin.headers,
        )
    )
    equipment = _equipment(client, admin, model_id=model["id"])
    for one in (load, measured_only):
        _ok(
            client.put(
                f"/api/equipment/{equipment['id']}/specs",
                json={"definition_id": one["id"], "num_min": 100, "num_max": 400},
                headers=admin.headers,
            )
        )

    listed = {
        one["id"]: one
        for one in _ok(client.get("/api/spec-definitions", headers=admin.headers))
    }
    # 실측도 쓰임이다 — 빠져 있으면 실측만 있는 정의가 「사용 0」 으로 보인다.
    assert listed[load["id"]]["usage_count"] == 2
    assert listed[measured_only["id"]]["usage_count"] == 1
    # 그래서 실측만 있는 정의도 409 로 거절한다(전에는 FK 오류 500 이었다).
    removed = client.delete(
        f"/api/spec-definitions/{measured_only['id']}", headers=admin.headers
    )
    assert removed.status_code == 409, removed.text
    assert removed.json()["error"]["code"] == "TSC-SPEC-0007"

    asked = client.patch(
        f"/api/spec-definitions/{load['id']}",
        json={"display_unit": "kgf"},
        headers=admin.headers,
    )
    assert asked.status_code == 409, asked.text
    assert asked.json()["error"]["code"] == "TSC-SPEC-0024"
    assert asked.json()["error"]["details"]["stored"] == {"기종 사양": 1, "개체 실측": 1}

    _ok(
        client.patch(
            f"/api/spec-definitions/{load['id']}",
            json={"display_unit": "kgf", "stored_values": "convert"},
            headers=admin.headers,
        )
    )
    sheet = _ok(
        client.get(f"/api/equipment-models/{model['id']}/specs", headers=admin.headers)
    )
    stated = next(
        item
        for group_row in sheet["groups"]
        for item in group_row["items"]
        if item["definition_id"] == load["id"]
    )
    assert (stated["num_min"], stated["num_max"]) == (0.01, 0.5)
    measured = _ok(
        client.get(f"/api/equipment/{equipment['id']}/specs", headers=admin.headers)
    )
    mine = next(
        item
        for group_row in measured["groups"]
        for item in group_row["items"]
        if item["key"] == load["key"]
    )
    assert (mine["measured"]["num_min"], mine["measured"]["num_max"]) == (0.1, 0.4)

    refused = client.patch(
        f"/api/spec-definitions/{load['id']}",
        json={"display_unit": "mm", "stored_values": "convert"},
        headers=admin.headers,
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "TSC-SPEC-0025"


def test_속성_정의는_단위_없이_적힌_값에_옛_단위를_적어_뜻을_지킨다(
    client: TestClient, admin: Signed
) -> None:
    tag = uuid.uuid4().hex[:6]

    def definition(label: str, unit: str) -> dict[str, Any]:
        body: dict[str, Any] = _ok(
            client.post(
                "/api/attribute-definitions",
                json={
                    "target": "equipment",
                    "label": f"{label}-{tag}",
                    "key": f"uc_{label}_{tag}",
                    "kind": "number",
                    "unit": unit,
                    "status": "standard",
                },
                headers=admin.headers,
            ),
            201,
        )
        return body

    def value(equipment_id: str, definition_id: str) -> dict[str, Any]:
        body = _ok(client.get(f"/api/equipment/{equipment_id}", headers=admin.headers))
        found: dict[str, Any] = next(
            one for one in body["attributes"] if one["definition_id"] == definition_id
        )
        return found

    # 정의를 고친다 — 단위 없이 적힌 152 는 고치기 전의 cm 를 달고 남는다.
    height = definition("height", "cm")
    first = _equipment(
        client, admin, attributes=[{"definition_id": height["id"], "num_value": 152}]
    )
    assert value(first["id"], height["id"])["unit"] == ""
    _ok(
        client.patch(
            f"/api/attribute-definitions/{height['id']}",
            json={"unit": "m"},
            headers=admin.headers,
        )
    )
    kept = value(first["id"], height["id"])
    assert (kept["num_value"], kept["unit"]) == (152, "cm")

    # 합친다 — cm 속성의 30 이 m 속성으로 가도 30 cm 다.
    meters = definition("meters", "m")
    centimeters = definition("centi", "cm")
    second = _equipment(
        client, admin, attributes=[{"definition_id": centimeters["id"], "num_value": 30}]
    )
    _ok(
        client.post(
            f"/api/attribute-definitions/{centimeters['id']}/merge",
            json={"target_id": meters["id"]},
            headers=admin.headers,
        )
    )
    moved = value(second["id"], meters["id"])
    assert (moved["num_value"], moved["unit"]) == (30, "cm")

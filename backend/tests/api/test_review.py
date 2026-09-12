"""검토함 — 후보와 근거를 먼저 보여 주고, 도메인 전문가가 고른다.

여기서 지키는 것 셋:

1. 후보는 **파생**된다 — 규격을 인용한 계열이 하는 시험이 곧 후보다. 정본 없이도 선다.
2. 고르면 **기존 규칙**이 돈다 — 규격의 시험 항목을 정하면 인용한 계열에 붙는다.
3. 정본의 추천·근거·결정이 따라온다 — 결정된 줄은 다시 묻지 않고 적용된다.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEntry
from app.modules.methods.models import TestMethod
from app.modules.review import services
from app.shared import audit
from tests.api.conftest import Signed
from tests.api.test_pending_methods import _method, _pend, _series


def _item(client: TestClient, admin: Signed, prefix: str) -> tuple[str, str]:
    """코드 있는 시험 항목. 검토함은 **코드**로 정본과 잇는다."""
    code = f"{prefix}_{uuid.uuid4().hex[:6]}"
    made = client.post(
        "/api/vocabularies/test_item/terms",
        json={"value": f"{prefix}-{code[-6:]}", "code": code},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"]), code


def _cited_method(client: TestClient, admin: Signed, item_ids: list[str]) -> dict[str, Any]:
    """시험이 둘인 계열이 인용한, 항목 미정 규격."""
    method = _method(client, admin, None)
    series_id = _series(client, admin)
    for item_id in item_ids:
        added = client.post(
            f"/api/equipment-series/{series_id}/test-items",
            json={"test_item_term_id": item_id},
            headers=admin.headers,
        )
        assert added.status_code == 201, added.text
    _pend(series_id, method["id"])
    return method


def _rows(
    client: TestClient, admin: Signed, queue: str, **params: Any
) -> list[dict[str, Any]]:
    response = client.get(f"/api/review/{queue}", params=params, headers=admin.headers)
    assert response.status_code == 200, response.text
    rows: list[dict[str, Any]] = response.json()["items"]
    return rows


def test_인용한_계열의_시험이_후보로_서고_고르면_계열에_붙는다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    vib_id, vib = _item(client, admin, "진동")
    shock_id, shock = _item(client, admin, "충격")
    method = _cited_method(client, admin, [vib_id, shock_id])

    refreshed = client.post("/api/review/refresh", headers=admin.headers)
    assert refreshed.status_code == 200, refreshed.text
    row = next(
        one
        for one in _rows(client, admin, "method_test_items")
        if one["subject_id"] == method["id"]
    )
    assert {one["code"] for one in row["candidates"]} == {vib, shock}
    assert not any(one["recommended"] for one in row["candidates"]), "정본 없이는 추천이 없다"
    assert row["link"] == f"/methods/{method['id']}"
    assert row["context"] and row["context"].startswith("인용: ")

    decided = client.post(
        f"/api/review/method_test_items/{row['id']}/decide",
        json={"choice": [vib], "note": "규격 제목이 진동"},
        headers=admin.headers,
    )
    assert decided.status_code == 200, decided.text
    body = decided.json()
    assert body["status"] == "decided"
    assert body["choice"] == [vib]
    assert body["followed"] is None, "추천이 없었으니 따랐는지도 없다"
    assert body["decided_by"] == "관리자"

    # **기존 규칙이 돌았다** — 규격에 항목이 정해지고 인용한 계열에 붙었다.
    shown = client.get(f"/api/methods/{method['id']}", headers=admin.headers).json()
    assert shown["test_item_term_id"] == vib_id
    assert shown["pending_series_count"] == 0
    assert shown["series_count"] == 1

    entry = db.scalar(
        select(AuditEntry).where(
            AuditEntry.action == audit.REVIEW_DECIDED,
            AuditEntry.target_id == uuid.UUID(row["id"]),
        )
    )
    assert entry is not None and entry.changes["choice"] == [vib]

    again = client.post(
        f"/api/review/method_test_items/{row['id']}/decide",
        json={"choice": [shock]},
        headers=admin.headers,
    )
    assert again.status_code == 409, "이미 정한 것을 다시 정하면 거절한다"


def test_직접_고르기는_후보_밖의_시험_항목도_받는다(client: TestClient, admin: Signed) -> None:
    a_id, _ = _item(client, admin, "인장")
    b_id, _ = _item(client, admin, "압축")
    other_id, other = _item(client, admin, "굽힘")
    method = _cited_method(client, admin, [a_id, b_id])
    client.post("/api/review/refresh", headers=admin.headers)
    row = next(
        one
        for one in _rows(client, admin, "method_test_items")
        if one["subject_id"] == method["id"]
    )

    decided = client.post(
        f"/api/review/method_test_items/{row['id']}/decide",
        json={"choice": [other]},
        headers=admin.headers,
    )
    assert decided.status_code == 200, decided.text
    shown = client.get(f"/api/methods/{method['id']}", headers=admin.headers).json()
    assert shown["test_item_term_id"] == other_id

    unknown = _cited_method(client, admin, [a_id, b_id])
    client.post("/api/review/refresh", headers=admin.headers)
    row = next(
        one
        for one in _rows(client, admin, "method_test_items")
        if one["subject_id"] == unknown["id"]
    )
    bad = client.post(
        f"/api/review/method_test_items/{row['id']}/decide",
        json={"choice": ["no_such_code"]},
        headers=admin.headers,
    )
    assert bad.status_code == 404, "모르는 코드는 거절한다 — 오타가 시험 항목이 되면 안 된다"


def test_정본의_추천과_결정이_따라온다(
    client: TestClient, admin: Signed, db: Session, tmp_path: Path
) -> None:
    a_id, a = _item(client, admin, "인장")
    b_id, b = _item(client, admin, "압축")
    recommended = _cited_method(client, admin, [a_id, b_id])
    settled = _cited_method(client, admin, [a_id, b_id])
    (tmp_path / "method_test_items.json").write_text(
        json.dumps(
            {
                "queue": "method_test_items",
                "rows": [
                    {
                        "subject": recommended["code"],
                        "recommended": a,
                        "reason": "규격 제목이 Tensile",
                    },
                    {
                        "subject": settled["code"],
                        "recommended": b,
                        "reason": "규격 제목이 Compression",
                        "decided": {"choice": [b], "by": "김전문", "on": "2026-09-20"},
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    services.refresh(db, tmp_path)
    db.commit()

    rows = {
        one["subject_id"]: one
        for one in _rows(client, admin, "method_test_items", status="all")
    }
    hinted = rows[recommended["id"]]
    assert hinted["status"] == "open"
    picked = next(one for one in hinted["candidates"] if one["recommended"])
    assert (picked["code"], picked["reason"]) == (a, "규격 제목이 Tensile")

    # 정본이 이미 결정한 줄은 **적용되고 닫힌다** — 운영에서 다시 묻지 않는다.
    done = rows[settled["id"]]
    assert done["status"] == "decided"
    assert done["decided_by"] == "김전문"
    assert done["followed"] is True
    method = db.get(TestMethod, uuid.UUID(settled["id"]))
    assert method is not None and str(method.test_item_term_id) == b_id

    # 추천을 거스르면 followed 가 거짓으로 남는다 — 어느 추천이 틀리는지 셀 수 있게.
    against = client.post(
        f"/api/review/method_test_items/{hinted['id']}/decide",
        json={"choice": [b]},
        headers=admin.headers,
    )
    assert against.status_code == 200, against.text
    assert against.json()["followed"] is False


def test_화면에서_정한_것은_다시_세울_때_결정으로_닫힌다(
    client: TestClient, admin: Signed
) -> None:
    a_id, a = _item(client, admin, "인장")
    b_id, _ = _item(client, admin, "압축")
    method = _cited_method(client, admin, [a_id, b_id])
    client.post("/api/review/refresh", headers=admin.headers)
    row = next(
        one
        for one in _rows(client, admin, "method_test_items")
        if one["subject_id"] == method["id"]
    )

    fixed = client.patch(
        f"/api/methods/{method['id']}", json={"test_item_term_id": a_id}, headers=admin.headers
    )
    assert fixed.status_code == 200, fixed.text
    client.post("/api/review/refresh", headers=admin.headers)
    after = next(
        one
        for one in _rows(client, admin, "method_test_items", status="all")
        if one["id"] == row["id"]
    )
    assert (after["status"], after["choice"], after["decided_by"]) == (
        "decided",
        [a],
        "화면에서 정함",
    )


def test_건너뛰기는_되돌릴_수_있고_큐_수에_잡힌다(client: TestClient, admin: Signed) -> None:
    a_id, _ = _item(client, admin, "인장")
    b_id, _ = _item(client, admin, "압축")
    method = _cited_method(client, admin, [a_id, b_id])
    client.post("/api/review/refresh", headers=admin.headers)
    row = next(
        one
        for one in _rows(client, admin, "method_test_items")
        if one["subject_id"] == method["id"]
    )

    skipped = client.post(
        f"/api/review/method_test_items/{row['id']}/skip", headers=admin.headers
    )
    assert skipped.json()["status"] == "skipped"
    queues = {
        one["key"]: one for one in client.get("/api/review", headers=admin.headers).json()
    }
    assert queues["method_test_items"]["skipped"] >= 1
    assert set(queues) == {
        "method_test_items",
        "test_item_axes",
        "property_links",
        "free_spec_definitions",
    }

    back = client.post(
        f"/api/review/method_test_items/{row['id']}/skip", headers=admin.headers
    )
    assert back.json()["status"] == "open"

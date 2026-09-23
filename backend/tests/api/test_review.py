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
from app.modules.review.models import ReviewProposal
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
    assert set(queues) == set(services.QUEUES)

    back = client.post(
        f"/api/review/method_test_items/{row['id']}/skip", headers=admin.headers
    )
    assert back.json()["status"] == "open"


def test_결정은_정본으로_되돌려_쓰이고_다시_들이면_적용된다(
    client: TestClient, admin: Signed, db: Session, tmp_path: Path
) -> None:
    """개발에서 정한 것이 운영에 다시 묻지 않는 길 — 결정 → 정본 → 반입."""
    a_id, a = _item(client, admin, "인장")
    b_id, _ = _item(client, admin, "압축")
    method = _cited_method(client, admin, [a_id, b_id])
    client.post("/api/review/refresh", headers=admin.headers)
    row = next(
        one
        for one in _rows(client, admin, "method_test_items")
        if one["subject_id"] == method["id"]
    )
    decided = client.post(
        f"/api/review/method_test_items/{row['id']}/decide",
        json={"choice": [a], "note": "규격서 4절"},
        headers=admin.headers,
    )
    assert decided.status_code == 200, decided.text

    counts = services.export_decisions(db, tmp_path)
    assert counts["method_test_items"][1] >= 1
    doc = json.loads((tmp_path / "method_test_items.json").read_text(encoding="utf-8"))
    mine = next(one for one in doc["rows"] if one["subject"] == method["code"])
    assert mine["decided"]["choice"] == [a]
    assert mine["decided"]["by"] == "관리자"
    assert mine["decided"]["note"] == "규격서 4절"

    # 다른 설치를 흉내 낸다: 규격의 항목을 비우고 검토 줄을 지운 뒤, 정본으로 다시 세운다.
    target = db.get(TestMethod, uuid.UUID(method["id"]))
    assert target is not None
    target.test_item_term_id = None
    db.execute(
        select(ReviewProposal).where(ReviewProposal.id == uuid.UUID(row["id"]))
    )  # 존재 확인
    db.delete(db.get(ReviewProposal, uuid.UUID(row["id"])))
    db.commit()
    services.refresh(db, tmp_path)
    db.commit()
    db.refresh(target)
    assert str(target.test_item_term_id) == a_id, "정본의 결정이 적용됐다"
    again = next(
        one
        for one in _rows(client, admin, "method_test_items", status="all")
        if one["subject_id"] == method["id"]
    )
    assert (again["status"], again["decided_by"]) == ("decided", "관리자")


def test_검색축은_여러_개를_고르고_빈_결정은_축_없음이다(
    client: TestClient, admin: Signed, db: Session, tmp_path: Path
) -> None:
    item_id, code = _item(client, admin, "누프")
    other_id, other_code = _item(client, admin, "접촉각")
    (tmp_path / "test_item_axes.json").write_text(
        json.dumps(
            {
                "rows": [
                    {"subject": code, "recommended": ["force"], "reason": "시험력을 고른다"},
                    {"subject": other_code, "hint": "맞는 축이 없다"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    services.refresh(db, tmp_path)
    db.commit()
    rows = {one["subject_id"]: one for one in _rows(client, admin, "test_item_axes")}
    knoop = rows[item_id]
    assert [one["code"] for one in knoop["candidates"] if one["recommended"]] == ["force"]
    assert rows[other_id]["context"] == "맞는 축이 없다"

    decided = client.post(
        f"/api/review/test_item_axes/{knoop['id']}/decide",
        json={"choice": ["force", "temperature"]},
        headers=admin.headers,
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["followed"] is False, "추천(하중)에 온도를 더했으니 그대로는 아니다"
    shown = client.get(f"/api/test-items/{item_id}", headers=admin.headers).json()
    assert {one["key"] for one in shown["condition_keys"]} == {"force", "temperature"}

    none = client.post(
        f"/api/review/test_item_axes/{rows[other_id]['id']}/decide",
        json={"choice": []},
        headers=admin.headers,
    )
    assert none.status_code == 200, none.text
    assert none.json()["choice"] == []


def test_물성_연결은_확인하거나_끊고_사양은_정의로_올린다(
    client: TestClient, admin: Signed, db: Session, tmp_path: Path
) -> None:
    from tests.api.test_free_specs import _model, _seed_same_key
    from tests.api.test_properties import _link, _property

    item_id, item_code = _item(client, admin, "전단")
    prop_code = f"mechanical.mw_{uuid.uuid4().hex[:6]}"
    prop_id = _property(client, admin, f"분자량-{prop_code[-6:]}", prop_code)
    # 사람이 만든 연결은 확인 상태로 생기므로, 반입이 넣은 「제안」 으로 되돌린다.
    link = _link(client, admin, item_id, prop_id)
    keep_code = f"mechanical.ss_{uuid.uuid4().hex[:6]}"
    keep_id = _property(client, admin, f"전단강도-{keep_code[-6:]}", keep_code)
    kept = _link(client, admin, item_id, keep_id)
    back = client.patch(
        "/api/test-item-properties/bulk",
        json={"link_ids": [link["id"], kept["id"]], "status": "suggested"},
        headers=admin.headers,
    )
    assert back.status_code == 200, back.text

    model_a = _model(client, admin)
    model_b = _model(client, admin)
    key = f"column_gap_{uuid.uuid4().hex[:6]}"
    _seed_same_key(model_a["id"], key, "485")
    _seed_same_key(model_b["id"], key, "610")

    (tmp_path / "property_links.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "subject": f"{item_code}:{prop_code}",
                        "recommended": "reject",
                        "reason": "GPC 의 값",
                    },
                    {
                        "subject": f"{item_code}:{keep_code}",
                        "recommended": "confirm",
                        "reason": "맞다",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "free_spec_definitions.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "subject": f"{key}|mm",
                        "recommended": "promote",
                        "reason": "프레임 둘",
                        "definition": {
                            "key": key,
                            "label": "컬럼 간격",
                            "group": "space",
                            "kind": "number",
                            "unit": "mm",
                        },
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    services.refresh(db, tmp_path)
    db.commit()

    links = {one["subject_id"]: one for one in _rows(client, admin, "property_links")}
    rejected = client.post(
        f"/api/review/property_links/{links[link['id']]['id']}/decide",
        json={"choice": ["reject"]},
        headers=admin.headers,
    )
    assert rejected.status_code == 200, rejected.text
    confirmed = client.post(
        f"/api/review/property_links/{links[kept['id']]['id']}/decide",
        json={"choice": ["confirm"]},
        headers=admin.headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    listed = client.get(
        "/api/test-item-properties", params={"test_item": item_id}, headers=admin.headers
    ).json()
    assert {one["property_term_id"]: one["status"] for one in listed} == {keep_id: "confirmed"}

    free = _rows(client, admin, "free_spec_definitions")
    mine = next(one for one in free if one["subject_key"] == f"{key}|mm")
    assert mine["payload"]["models"] == 2
    promoted = client.post(
        f"/api/review/free_spec_definitions/{mine['id']}/decide",
        json={"choice": ["promote"]},
        headers=admin.headers,
    )
    assert promoted.status_code == 200, promoted.text
    definitions = {
        one["key"]: one
        for one in client.get("/api/spec-definitions", headers=admin.headers).json()
    }
    assert definitions[key]["label"] == "컬럼 간격"
    # **같은 키의 다른 기종도 함께 올라갔다** — 기존 규칙(promote, apply_same_key).
    for model in (model_a, model_b):
        sheet = client.get(
            f"/api/equipment-models/{model['id']}/specs", headers=admin.headers
        ).json()
        keys = {one["key"] for group in sheet["groups"] for one in group["items"]}
        assert key in keys


def test_대상이_지워지면_정한_것이_아니라_대상_없어짐으로_닫힌다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    a_id, _ = _item(client, admin, "인장")
    b_id, _ = _item(client, admin, "압축")
    method = _cited_method(client, admin, [a_id, b_id])
    client.post("/api/review/refresh", headers=admin.headers)
    row = next(
        one
        for one in _rows(client, admin, "method_test_items")
        if one["subject_id"] == method["id"]
    )
    gone = client.delete(f"/api/methods/{method['id']}", headers=admin.headers)
    assert gone.status_code in (200, 204), gone.text
    client.post("/api/review/refresh", headers=admin.headers)
    after = next(
        one
        for one in _rows(client, admin, "method_test_items", status="gone")
        if one["id"] == row["id"]
    )
    assert after["decided_by"] == "규격이 지워짐"
    assert after["choice"] is None
    # 대상이 없으니 고를 수도, 다시 열 수도 없다.
    assert (
        client.post(
            f"/api/review/method_test_items/{row['id']}/decide",
            json={"choice": ["tensile"]},
            headers=admin.headers,
        ).status_code
        == 409
    )
    queues = {
        one["key"]: one for one in client.get("/api/review", headers=admin.headers).json()
    }
    assert queues["method_test_items"]["gone"] >= 1


def test_정한_것은_다시_열어_다른_걸로_고를_수_있다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    a_id, a = _item(client, admin, "인장")
    b_id, b = _item(client, admin, "압축")
    method = _cited_method(client, admin, [a_id, b_id])
    client.post("/api/review/refresh", headers=admin.headers)
    row = next(
        one
        for one in _rows(client, admin, "method_test_items")
        if one["subject_id"] == method["id"]
    )
    first = client.post(
        f"/api/review/method_test_items/{row['id']}/decide",
        json={"choice": [a]},
        headers=admin.headers,
    )
    assert first.status_code == 200, first.text

    reopened = client.post(
        f"/api/review/method_test_items/{row['id']}/reopen", headers=admin.headers
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "open"
    assert "다시 열림" in (reopened.json()["note"] or "")
    # 실제 데이터는 그대로다 — 다시 여는 것은 되돌리는 것이 아니다.
    shown = client.get(f"/api/methods/{method['id']}", headers=admin.headers).json()
    assert shown["test_item_term_id"] == a_id

    second = client.post(
        f"/api/review/method_test_items/{row['id']}/decide",
        json={"choice": [b]},
        headers=admin.headers,
    )
    assert second.status_code == 200, second.text
    shown = client.get(f"/api/methods/{method['id']}", headers=admin.headers).json()
    assert shown["test_item_term_id"] == b_id
    kinds = [
        one.action
        for one in db.scalars(
            select(AuditEntry).where(AuditEntry.target_id == uuid.UUID(row["id"]))
        )
    ]
    assert kinds.count(audit.REVIEW_DECIDED) == 2 and audit.REVIEW_REOPENED in kinds


def _member(client: TestClient, db: Session, workspace: Any) -> Signed:
    """관리자가 아닌 사람 — 의견은 내되 확정은 못 한다."""
    from app.modules.accounts.models import User
    from app.modules.auth import security
    from app.modules.workspaces.models import WorkspaceMember

    email = f"expert-{uuid.uuid4().hex[:8]}@testscope.local"
    user = User(
        email=email,
        password_hash=security.hash_password("expert-password"),
        display_name="도메인 전문가",
        status="active",
        home_workspace_id=workspace.id,
    )
    db.add(user)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="member"))
    db.commit()
    login = client.post(
        "/api/auth/login", json={"email": email, "password": "expert-password"}
    )
    assert login.status_code == 200, login.text
    return Signed(email=email, token=login.json()["access_token"], workspace=workspace.slug)


def test_의견은_누구나_내고_확정은_관리자가_한다(
    client: TestClient, admin: Signed, db: Session, workspace: Any
) -> None:
    a_id, a = _item(client, admin, "인장")
    b_id, b = _item(client, admin, "압축")
    method = _cited_method(client, admin, [a_id, b_id])
    client.post("/api/review/refresh", headers=admin.headers)
    row = next(
        one
        for one in _rows(client, admin, "method_test_items")
        if one["subject_id"] == method["id"]
    )
    expert = _member(client, db, workspace)

    # 전문가가 의견을 낸다 — 데이터는 안 바뀐다.
    voted = client.post(
        f"/api/review/method_test_items/{row['id']}/vote",
        json={"choice": [a], "note": "규격 4절이 인장"},
        headers=expert.headers,
    )
    assert voted.status_code == 200, voted.text
    assert voted.json()["my_vote"] == [a]
    assert voted.json()["status"] == "open"
    shown = client.get(f"/api/methods/{method['id']}", headers=admin.headers).json()
    assert shown["test_item_term_id"] is None, "의견은 확정이 아니다"

    # 전문가는 확정 못 한다.
    denied = client.post(
        f"/api/review/method_test_items/{row['id']}/decide",
        json={"choice": [a]},
        headers=expert.headers,
    )
    assert denied.status_code == 403

    # 다시 내면 바뀐다(사람당 하나). 관리자도 의견을 낸다.
    client.post(
        f"/api/review/method_test_items/{row['id']}/vote",
        json={"choice": [b]},
        headers=expert.headers,
    )
    client.post(
        f"/api/review/method_test_items/{row['id']}/vote",
        json={"choice": [a]},
        headers=admin.headers,
    )
    seen = next(
        one
        for one in _rows(client, admin, "method_test_items", status="voted")
        if one["id"] == row["id"]
    )
    assert [(one["user"], one["choice"]) for one in seen["votes"]] == [
        ("도메인 전문가", [b]),
        ("관리자", [a]),
    ]
    assert seen["my_vote"] == [a]
    queues = {
        one["key"]: one for one in client.get("/api/review", headers=admin.headers).json()
    }
    assert queues["method_test_items"]["voted"] >= 1

    # 거두면 빠진다.
    gone = client.delete(
        f"/api/review/method_test_items/{row['id']}/vote", headers=expert.headers
    )
    assert gone.status_code == 200, gone.text
    assert [one["user"] for one in gone.json()["votes"]] == ["관리자"]

    # 관리자가 확정하면 적용되고, 그때의 의견이 감사에 남는다.
    decided = client.post(
        f"/api/review/method_test_items/{row['id']}/decide",
        json={"choice": [a]},
        headers=admin.headers,
    )
    assert decided.status_code == 200, decided.text
    entry = db.scalar(
        select(AuditEntry).where(
            AuditEntry.action == audit.REVIEW_DECIDED,
            AuditEntry.target_id == uuid.UUID(row["id"]),
        )
    )
    assert entry is not None and entry.changes["votes"] == [{"user": "관리자", "choice": [a]}]
    late = client.post(
        f"/api/review/method_test_items/{row['id']}/vote",
        json={"choice": [b]},
        headers=expert.headers,
    )
    assert late.status_code == 409, "닫힌 줄에는 의견을 못 낸다"


def test_규격_정리는_지우거나_합치고_합치면_인용이_따라간다(
    client: TestClient, admin: Signed, db: Session, tmp_path: Path
) -> None:
    a_id, _ = _item(client, admin, "인장")
    b_id, _ = _item(client, admin, "압축")
    junk = _cited_method(client, admin, [a_id, b_id])  # 기관 이름 같은 것
    dup = _cited_method(client, admin, [a_id, b_id])  # 표기만 다른 것
    keep = _method(client, admin, a_id)  # 남는 쪽
    (tmp_path / "method_cleanup.json").write_text(
        json.dumps(
            {
                "rows": [
                    {"subject": junk["code"], "recommended": "delete", "reason": "기관 이름"},
                    {
                        "subject": dup["code"],
                        "merge_into": [keep["code"]],
                        "recommended": f"merge:{keep['code']}",
                        "reason": "표기만 다름",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    services.refresh(db, tmp_path)
    db.commit()
    rows = {one["subject_id"]: one for one in _rows(client, admin, "method_cleanup")}
    assert [one["code"] for one in rows[dup["id"]]["candidates"]] == [
        "keep",
        f"merge:{keep['code']}",
        "delete",
    ]
    assert rows[junk["id"]]["context"].startswith("인용한 계열 1")

    deleted = client.post(
        f"/api/review/method_cleanup/{rows[junk['id']]['id']}/decide",
        json={"choice": ["delete"]},
        headers=admin.headers,
    )
    assert deleted.status_code == 200, deleted.text
    assert client.get(f"/api/methods/{junk['id']}", headers=admin.headers).status_code == 404

    merged = client.post(
        f"/api/review/method_cleanup/{rows[dup['id']]['id']}/decide",
        json={"choice": [f"merge:{keep['code']}"]},
        headers=admin.headers,
    )
    assert merged.status_code == 200, merged.text
    assert client.get(f"/api/methods/{dup['id']}", headers=admin.headers).status_code == 404
    # 인용이 남는 쪽으로 갔고, 남는 쪽은 항목이 있으니 계열에 붙었다.
    survivor = client.get(f"/api/methods/{keep['id']}", headers=admin.headers).json()
    assert survivor["series_count"] == 1
    assert survivor["pending_series_count"] == 0
    entry = db.scalar(
        select(AuditEntry).where(
            AuditEntry.action == audit.METHOD_MERGED,
            AuditEntry.target_id == uuid.UUID(keep["id"]),
        )
    )
    assert entry is not None and entry.changes["merged_from"] == dup["code"]


def test_시험이_내는_물성을_잇고_새_축을_세운다(
    client: TestClient, admin: Signed, db: Session, tmp_path: Path
) -> None:
    from tests.api.test_properties import _property

    item_id, code = _item(client, admin, "열저항")
    prop_code = f"thermal.rth_{uuid.uuid4().hex[:6]}"
    prop_id = _property(client, admin, f"열저항-{prop_code[-6:]}", prop_code)
    axis_key = f"pressure_{uuid.uuid4().hex[:6]}"
    (tmp_path / "test_item_properties.json").write_text(
        json.dumps(
            {"rows": [{"subject": code, "recommended": [prop_code], "reason": "곧 이 값"}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "condition_axes.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "subject": axis_key,
                        "axis": {"label": "압력", "dimension": "pressure", "unit": "bar"},
                        "definitions": ["pressure"],
                        "test_items": [code],
                        "recommended": "create",
                        "reason": "내압 시험이 묻는다",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    services.refresh(db, tmp_path)
    db.commit()

    props_row = next(
        one
        for one in _rows(client, admin, "test_item_properties")
        if one["subject_id"] == item_id
    )
    linked = client.post(
        f"/api/review/test_item_properties/{props_row['id']}/decide",
        json={"choice": [prop_code]},
        headers=admin.headers,
    )
    assert linked.status_code == 200, linked.text
    links = client.get(
        "/api/test-item-properties", params={"test_item": item_id}, headers=admin.headers
    ).json()
    assert [(one["property_term_id"], one["status"]) for one in links] == [
        (prop_id, "confirmed")
    ]

    axis_row = next(
        one for one in _rows(client, admin, "condition_axes") if one["subject_key"] == axis_key
    )
    assert axis_row["payload"]["definitions"] == ["pressure"]
    made = client.post(
        f"/api/review/condition_axes/{axis_row['id']}/decide",
        json={"choice": ["create"]},
        headers=admin.headers,
    )
    assert made.status_code == 200, made.text
    keys = {
        one["key"]: one
        for one in client.get("/api/condition-keys", headers=admin.headers).json()
    }
    assert keys[axis_key]["label"] == "압력" and keys[axis_key]["display_unit"] == "bar"
    # 시험 항목이 그 축을 묻게 됐다.
    shown = client.get(f"/api/test-items/{item_id}", headers=admin.headers).json()
    assert axis_key in {one["key"] for one in shown["condition_keys"]}
    # 이미 있으면 다시 세우기가 닫는다.
    services.refresh(db, tmp_path)
    db.commit()
    again = next(
        one
        for one in _rows(client, admin, "condition_axes", status="all")
        if one["subject_key"] == axis_key
    )
    assert again["status"] == "decided"


def test_계열이_하는_규격을_더하면_시험에_붙거나_미정_인용이_된다(
    client: TestClient, admin: Signed, db: Session, tmp_path: Path
) -> None:
    """보강 원료(제조사 웹·대리점·논문)가 세운 후보. 계열은 **이름으로** 찾고, 고른 규격은
    반입과 같은 규칙으로 잇는다 — 시험이 하나뿐이면 그 시험에(소거), 여럿이면 항목 미정
    인용으로."""
    from app.modules.test_items.models import SeriesPendingMethod, SeriesTestItemMethod

    item_id, _ = _item(client, admin, "인장")
    name = f"계열-{uuid.uuid4().hex[:6]}"
    made = client.post("/api/equipment-series", json={"name": name}, headers=admin.headers)
    assert made.status_code == 201, made.text
    series_id = made.json()["id"]
    added = client.post(
        f"/api/equipment-series/{series_id}/test-items",
        json={"test_item_term_id": item_id},
        headers=admin.headers,
    )
    assert added.status_code == 201, added.text
    # 이미 인용 중인 규격은 후보에서 빠진다.
    cited = _method(client, admin, item_id)
    db.add(
        SeriesTestItemMethod(
            series_test_item_id=uuid.UUID(added.json()["id"]), method_id=uuid.UUID(cited["id"])
        )
    )
    db.commit()
    new_code = f"ASTM D{uuid.uuid4().hex[:4].upper()}"
    (tmp_path / "series_standards.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "subject": "obj-x",
                        "series": name,
                        "manufacturer": None,
                        "candidates": [
                            {
                                "code": cited["code"],
                                "reason": "남의 페이지 1쪽",
                                "sources": ["https://a"],
                            },
                            {
                                "code": new_code,
                                "title": "Standard Test Method for Something",
                                "reason": "제조사 페이지 2쪽",
                                "sources": ["https://b", "https://c"],
                            },
                        ],
                        "recommended": [new_code],
                        "reason": "제조사 페이지에 나왔다",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    services.refresh(db, tmp_path)
    db.commit()

    row = next(
        one
        for one in _rows(client, admin, "series_standards")
        if one["subject_key"] == "obj-x"
    )
    assert row["subject_id"] == series_id and row["subject_label"] == name
    assert [one["code"] for one in row["candidates"]] == [new_code]
    assert row["candidates"][0]["recommended"] and row["candidates"][0]["sources"] == [
        "https://b",
        "https://c",
    ]

    decided = client.post(
        f"/api/review/series_standards/{row['id']}/decide",
        json={"choice": [new_code]},
        headers=admin.headers,
    )
    assert decided.status_code == 200, decided.text
    method = db.scalar(select(TestMethod).where(TestMethod.code == new_code))
    assert (
        method is not None and str(method.test_item_term_id) == item_id
    )  # 시험이 하나뿐 → 소거
    assert method.title == "Standard Test Method for Something"  # 정본의 제목이 이름이 된다
    assert (
        db.scalar(
            select(SeriesTestItemMethod).where(SeriesTestItemMethod.method_id == method.id)
        )
        is not None
    )

    # 다시 세우면 후보가 전부 이어졌으니 결정으로 남고, 열린 것은 없다.
    services.refresh(db, tmp_path)
    db.commit()
    again = next(
        one
        for one in _rows(client, admin, "series_standards", status="all")
        if one["subject_key"] == "obj-x"
    )
    assert again["status"] == "decided"

    # 시험이 둘인 계열이면 미정 인용으로 간다.
    other_item, _ = _item(client, admin, "압축")
    added2 = client.post(
        f"/api/equipment-series/{series_id}/test-items",
        json={"test_item_term_id": other_item},
        headers=admin.headers,
    )
    assert added2.status_code == 201, added2.text
    second = f"ISO {uuid.uuid4().hex[:5]}"
    (tmp_path / "series_standards.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "subject": "obj-y",
                        "series": name,
                        "manufacturer": None,
                        "candidates": [
                            {"code": second, "reason": "논문 1편", "sources": ["PMC1"]}
                        ],
                        "recommended": [],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    services.refresh(db, tmp_path)
    db.commit()
    row2 = next(
        one
        for one in _rows(client, admin, "series_standards")
        if one["subject_key"] == "obj-y"
    )
    decided2 = client.post(
        f"/api/review/series_standards/{row2['id']}/decide",
        json={"choice": [second]},
        headers=admin.headers,
    )
    assert decided2.status_code == 200, decided2.text
    method2 = db.scalar(select(TestMethod).where(TestMethod.code == second))
    assert method2 is not None and method2.test_item_term_id is None
    assert (
        db.scalar(
            select(SeriesPendingMethod).where(SeriesPendingMethod.method_id == method2.id)
        )
        is not None
    )


def test_계열에_시험을_더하고_소개_문장을_붙인다(
    client: TestClient, admin: Signed, db: Session, tmp_path: Path
) -> None:
    """논문·제조사 문장이 세운 후보. 시험을 더하면 그 계열이 항목 미정으로 인용해 둔 그 시험의
    규격이 같이 올라오고, 소개 문장은 계열 summary 뒤에 붙는다."""
    from app.modules.equipment.models import EquipmentSeries
    from app.modules.test_items.models import SeriesTestItem, SeriesTestItemMethod

    item_id, code = _item(client, admin, "압축")
    name = f"계열-{uuid.uuid4().hex[:6]}"
    made = client.post(
        "/api/equipment-series",
        json={"name": name, "summary": "제조사 소개."},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    series_id = made.json()["id"]
    # 이 계열이 항목 미정으로 인용해 둔, 압축 규격.
    method = _method(client, admin, item_id)
    _pend(series_id, method["id"])
    (tmp_path / "series_test_items.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "subject": "obj-z",
                        "series": name,
                        "manufacturer": None,
                        "candidates": [
                            {
                                "code": code,
                                "reason": "논문 2편 — 「compression tests…」",
                                "sources": ["PMC1"],
                            },
                            {"code": "no_such_item", "reason": "x", "sources": []},
                        ],
                        "recommended": [code],
                        "reason": "논문 둘",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "series_summary.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "subject": "obj-z",
                        "series": name,
                        "manufacturer": None,
                        "candidates": [
                            {
                                "code": "s1",
                                "label": "Used for compression testing of foams.",
                                "sources": ["https://m"],
                            },
                            {
                                "code": "s2",
                                "label": "Best in class!",
                                "sources": ["https://m"],
                            },
                        ],
                        "recommended": [],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    services.refresh(db, tmp_path)
    db.commit()

    row = next(
        one
        for one in _rows(client, admin, "series_test_items")
        if one["subject_key"] == "obj-z"
    )
    assert [one["code"] for one in row["candidates"]] == [code]  # 모르는 코드는 안 선다
    decided = client.post(
        f"/api/review/series_test_items/{row['id']}/decide",
        json={"choice": [code]},
        headers=admin.headers,
    )
    assert decided.status_code == 200, decided.text
    test_item = db.scalar(
        select(SeriesTestItem).where(
            SeriesTestItem.series_id == uuid.UUID(series_id),
            SeriesTestItem.test_item_term_id == uuid.UUID(item_id),
        )
    )
    assert test_item is not None
    # 미정이던 압축 규격이 그 시험에 붙었다.
    assert (
        db.scalar(
            select(SeriesTestItemMethod).where(
                SeriesTestItemMethod.series_test_item_id == test_item.id
            )
        )
        is not None
    )

    srow = next(
        one for one in _rows(client, admin, "series_summary") if one["subject_key"] == "obj-z"
    )
    # 지금 소개는 근거 자료의 「소개」 줄로 — 물음은 무엇을 붙일지 묻는 완전한 문장이다.
    facts = {one["label"]: one["value"] for one in srow["facts"]}
    assert facts["소개"].startswith("제조사 소개.")
    assert srow["question"] and "소개에 아래 문장을 붙입니까" in srow["question"]
    picked = client.post(
        f"/api/review/series_summary/{srow['id']}/decide",
        json={"choice": ["s1"]},
        headers=admin.headers,
    )
    assert picked.status_code == 200, picked.text
    db.expire_all()
    series = db.get(EquipmentSeries, uuid.UUID(series_id))
    assert series is not None
    assert series.summary == "제조사 소개.\n\nUsed for compression testing of foams."
    # 다시 세우면 들어간 문장은 후보에서 빠지고 안 고른 문장만 남는다 — 정한 줄은 그대로.
    services.refresh(db, tmp_path)
    db.commit()
    again = next(
        one
        for one in _rows(client, admin, "series_summary", status="all")
        if one["subject_key"] == "obj-z"
    )
    assert again["status"] == "decided" and [one["code"] for one in again["candidates"]] == [
        "s2"
    ]


def test_줄마다_물음과_근거_자료가_붙고_다른_판의_결정이_추천이_된다(
    client: TestClient, admin: Signed
) -> None:
    """「3400」 만 주고 「무슨 시험을 하나」 를 묻지 않는다 — 물음은 완전한 문장, 근거 자료에는
    인용한 계열과 그 계열이 하는 시험이 서고, 후보마다 왜 후보인지가 적힌다. 같은 코드의 다른
    판이 이미 정해져 있으면 정본 추천이 없어도 그것이 추천이다."""
    vib_id, vib = _item(client, admin, "진동")
    shock_id, shock = _item(client, admin, "충격")
    method = _cited_method(client, admin, [vib_id, shock_id])
    # 같은 코드의 다른 판 — 이미 「진동」 으로 정해져 있다.
    sibling = client.post(
        "/api/methods",
        json={
            "code": method["code"],
            "edition": "2019",
            "title": "다른 판",
            "test_item_term_id": vib_id,
        },
        headers=admin.headers,
    )
    assert sibling.status_code == 201, sibling.text

    client.post("/api/review/refresh", headers=admin.headers)
    row = next(
        one
        for one in _rows(client, admin, "method_test_items")
        if one["subject_id"] == method["id"]
    )
    assert row["question"] and method["code"] in row["question"]
    labels = {one["label"]: one["value"] for one in row["facts"]}
    assert "인용한 계열" in labels, row["facts"]
    assert "다른 판" in labels and "진동" in labels["다른 판"]
    by_code = {one["code"]: one for one in row["candidates"]}
    assert by_code[shock]["reason"] and "인용한 계열" in by_code[shock]["reason"]
    assert by_code[vib]["recommended"] is True
    assert by_code[vib]["reason"] and "다른 판" in by_code[vib]["reason"]


def test_별칭_후보를_고르면_별칭이_되고_이미_쓰인_표기는_안_선다(
    client: TestClient, admin: Signed, db: Session, tmp_path: Path
) -> None:
    """정본이 세운 별칭 후보 중 이 축에 이미 있는 표기(값이든 별칭이든)는 빠지고, 고른 것과
    직접 적은 것이 별칭이 된다 — 그 뒤 resolve 가 그 표기로 이 시험을 exact 로 찾는다. 다른
    시험의 이름을 별칭으로 고르면 409."""
    shock_id, shock = _item(client, admin, "열충격")
    _other_id, other = _item(client, admin, "충격")
    other_name = f"충격-{other[-6:]}"  # _item 이 붙이는 값 이름
    tag = shock[-6:]
    (tmp_path / "test_item_aliases.json").write_text(
        json.dumps(
            {
                "queue": "test_item_aliases",
                "rows": [
                    {
                        "subject": shock,
                        "candidates": [
                            {"code": f"thermal shock {tag}", "reason": "영문 라벨의 조각"},
                            {"code": f"TS-{tag}", "reason": "규격 제목"},
                            {"code": other_name, "reason": "다른 시험의 이름(빠져야 함)"},
                        ],
                        "recommended": [f"thermal shock {tag}"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    services.refresh(db, tmp_path)
    db.commit()
    row = next(
        one
        for one in _rows(client, admin, "test_item_aliases")
        if one["subject_id"] == shock_id
    )
    codes = [one["code"] for one in row["candidates"]]
    assert f"thermal shock {tag}" in codes and f"TS-{tag}" in codes
    assert other_name not in codes, "다른 시험의 이름은 후보에서 빠진다"
    assert row["question"] and "별칭" in row["question"]
    assert next(one for one in row["candidates"] if one["code"] == f"thermal shock {tag}")[
        "recommended"
    ]

    # 다른 시험의 이름을 직접 적어 고르면 409.
    clash = client.post(
        f"/api/review/test_item_aliases/{row['id']}/decide",
        json={"choice": [other_name]},
        headers=admin.headers,
    )
    assert clash.status_code == 409, clash.text

    decided = client.post(
        f"/api/review/test_item_aliases/{row['id']}/decide",
        json={"choice": [f"thermal shock {tag}", f"직접 적은 표기 {tag}"]},
        headers=admin.headers,
    )
    assert decided.status_code == 200, decided.text
    term = next(
        one
        for one in client.get(
            "/api/vocabularies/test_item/terms", headers=admin.headers
        ).json()
        if one["id"] == shock_id
    )
    assert {f"thermal shock {tag}", f"직접 적은 표기 {tag}"} <= set(term["aliases"])

    found = client.post(
        "/api/resolve",
        json={"kind": "term", "axis": "test_item", "text": f"Thermal Shock {tag}"},
        headers=admin.headers,
    )
    assert found.status_code == 200, found.text
    assert found.json()["match"] == "exact" and found.json()["id"] == shock_id


def test_초안_속성은_합치거나_정식으로_올린다(
    client: TestClient, admin: Signed, db: Session, tmp_path: Path
) -> None:
    """초안 속성은 값을 적는 사람이 새 이름을 쓰면 생긴다 — 두면 온톨로지 밖에 남는다.

    여기서 지키는 것 — 값이 붙은 초안만 묻는다(0건은 정의 화면에서 지우면 그만) · 이름이 같은
    (띄어쓰기·대소문자를 지운) 속성이 하나면 그것을 추천한다 · 합치면 값이 그쪽으로 옮겨 가고
    초안은 꺼진다 · 정식으로 올리면 그 뒤로는 안 묻는다 · 화면에서 먼저 정한 것은 결정으로
    닫힌다.
    """
    tag = uuid.uuid4().hex[:6]
    standard = client.post(
        "/api/attribute-definitions",
        json={
            "target": "reliability_test",
            "label": f"시험 온도 {tag}",
            "key": f"temp_{tag}",
            "kind": "text",
            "status": "standard",
        },
        headers=admin.headers,
    )
    assert standard.status_code == 201, standard.text

    # 부서 사람이 「시험온도」(띄어쓰기만 다름)로 적으면 초안이 생긴다.
    made = client.post(
        "/api/reliability-tests",
        json={
            "workspace_slug": admin.workspace,
            "name": f"고온고습-{tag}",
            "attributes": [
                {"new_label": f"시험온도 {tag}", "new_kind": "text", "text_value": "85"},
                {
                    "new_label": f"포장 낙하 높이 {tag}",
                    "new_kind": "text",
                    "text_value": "이상 없음",
                },
            ],
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    drafts = {
        one["label"]: one for one in made.json()["attributes"] if one["status"] == "draft"
    }
    assert set(drafts) == {f"시험온도 {tag}", f"포장 낙하 높이 {tag}"}

    services.refresh(db, tmp_path)
    db.commit()
    rows = {
        one["subject_label"]: one
        for one in _rows(client, admin, "attribute_drafts", status="open")
    }
    same = rows[f"시험온도 {tag} (신뢰성 시험)"]
    other = rows[f"포장 낙하 높이 {tag} (신뢰성 시험)"]

    # 이름이 같은 정식 속성 하나 → 그것이 추천. 근거가 줄에 적힌다.
    picked = [one for one in same["candidates"] if one["recommended"]]
    assert [one["code"] for one in picked] == [f"merge:temp_{tag}"]
    assert "이름이 같습니다" in (picked[0]["reason"] or "")
    # 근거 자료 — 어디 붙는지 · 종류 · 몇 건 · 값의 예.
    facts = {one["label"]: one["value"] for one in same["facts"]}
    assert facts["붙는 곳"] == "신뢰성 시험" and facts["적힌 값"] == "1건"
    assert facts["값의 예"] == "85"
    assert same["link"] == "/attribute-definitions/reliability-test"
    # 짝이 없는 초안에는 추천이 없다 — 첫 보기를 습관적으로 누르게 두지 않는다.
    # **이름이 정식 속성과 겹치지 않는 것을 고른다**(2026-09-23): 「판정 기준」 을 쓰다가
    # 같은 이름의 정식 속성이 설치에 생기면서 짝이 생겼다 — 시험이 보려는 것은 짝이
    # 없을 때의 보기이지, 그 이름이 특별해서가 아니다.
    assert not any(one["recommended"] for one in other["candidates"])
    assert {one["code"] for one in other["candidates"]} == {"standard", "keep", "off"}

    decided = client.post(
        f"/api/review/attribute_drafts/{same['id']}/decide",
        json={"choice": [f"merge:temp_{tag}"]},
        headers=admin.headers,
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["followed"] is True

    # 값이 정식 쪽으로 옮겨 갔고 초안은 꺼졌다.
    listed = client.get(
        "/api/attribute-definitions",
        params={"target": "reliability_test", "include_inactive": "true"},
        headers=admin.headers,
    ).json()
    by_key = {one["key"]: one for one in listed}
    assert by_key[f"temp_{tag}"]["value_count"] == 1
    merged = next(one for one in listed if one["label"] == f"시험온도 {tag}")
    assert merged["is_active"] is False
    # 합친 속성으로 거를 수 있다 — 값이 옮겨 갔으니 정식 key 로 걸린다.
    found = client.get(
        "/api/reliability-tests",
        params={"attr": f"temp_{tag}=85"},
        headers=admin.headers,
    )
    assert [one["name"] for one in found.json()] == [f"고온고습-{tag}"]

    # 남은 초안을 화면에서 먼저 정식으로 올리면, 다시 세울 때 결정으로 닫힌다.
    promoted = client.patch(
        f"/api/attribute-definitions/{other['subject_id']}",
        json={"status": "standard"},
        headers=admin.headers,
    )
    assert promoted.status_code == 200, promoted.text
    services.refresh(db, tmp_path)
    db.commit()
    closed = next(
        one
        for one in _rows(client, admin, "attribute_drafts", status="decided")
        if one["id"] == other["id"]
    )
    assert closed["choice"] == ["standard"]
    assert closed["decided_by"] == "화면에서 정식으로 올림"
    # 이 시험이 만든 초안 둘은 이제 열린 줄에 없다(다른 시험이 만든 초안은 있을 수 있다).
    open_labels = {
        one["subject_label"] for one in _rows(client, admin, "attribute_drafts", status="open")
    }
    assert not open_labels & {same["subject_label"], other["subject_label"]}

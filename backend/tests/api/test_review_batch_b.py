"""검토함 · 규격 정리의 막힌 자리들(2026-10-13 사용자 보고) — 한 번에 하나씩 지킨다.

1. 코드 없이 만든 시험 항목도 검토함에서 고른다 — 서버가 코드를 짓고, 값 id 로 골라도 된다.
2. 보류는 사유와 메모가 남는다.
3. MCP 로 낸 의견은 「(MCP)」 로 보이고, 모아 보고, 그대로 한꺼번에 확정한다.
4. 규격에 잘못 걸린 시험 항목을 뗀다 — 끊기는 계열을 먼저 말하고 사유를 남긴다. 다시 정하면
   교체다.
5. 후보 밖에서 고른 것은 결정 줄에 이름으로 남는다.
6. 계열 시험 항목 후보는 제 근거로만 추천되고, 분류와 맞지 않으면 경고가 붙는다.
7. 같은 계열의 줄은 하나로 합치고, 이미 둘이면 한쪽을 정할 때 다른 쪽도 닫힌다.
8. 표기만 다른 규격 — 카탈로그 규격으로 묶고, 직접 번호를 받고, 병합하고, 정리 검토함에 선다.
9. 범위 사양은 「min 0 · max 152」 를 읽고, 못 옮긴 기종을 말한다.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.shared.text import method_key
from tests.api.conftest import Signed


def _term(db: Session, slug: str, label: str, *, code: str | None = "auto") -> Any:
    from app.modules.vocabulary.models import Vocabulary, VocabularyTerm

    axis = db.scalar(select(Vocabulary).where(Vocabulary.slug == slug))
    assert axis is not None
    tag = uuid.uuid4().hex[:6]
    term = VocabularyTerm(
        vocabulary_id=axis.id,
        value=f"{label}-{tag}",
        normalized=f"{label}-{tag}",
        code=f"item_{tag}" if code == "auto" else code,
    )
    db.add(term)
    db.commit()
    return term


def _series(client: TestClient, admin: Signed, *items: Any) -> dict[str, Any]:
    made = client.post(
        "/api/equipment-series",
        json={"name": f"계열-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    for term in items:
        added = client.post(
            f"/api/equipment-series/{made.json()['id']}/test-items",
            json={"test_item_term_id": str(term.id)},
            headers=admin.headers,
        )
        assert added.status_code == 201, added.text
    body: dict[str, Any] = made.json()
    return body


def _method(client: TestClient, admin: Signed, code: str | None = None) -> dict[str, Any]:
    code = code or f"ISO {uuid.uuid4().hex[:5]}"
    made = client.post(
        "/api/methods", json={"code": code, "title": code}, headers=admin.headers
    )
    assert made.status_code == 201, made.text
    body: dict[str, Any] = made.json()
    return body


def _proposal(
    db: Session,
    queue: str,
    *,
    subject_id: uuid.UUID | None,
    candidates: list[dict[str, Any]],
    key: str | None = None,
    payload: dict[str, Any] | None = None,
) -> Any:
    from app.modules.review.models import ReviewProposal

    row = ReviewProposal(
        queue=queue,
        subject_key=key or f"k-{uuid.uuid4().hex[:8]}",
        subject_id=subject_id,
        subject_label="시험 줄",
        candidates=candidates,
        payload=payload or {},
        status="open",
    )
    db.add(row)
    db.commit()
    return row


def _token(client: TestClient, admin: Signed) -> dict[str, str]:
    made = client.post(
        "/api/auth/tokens",
        json={"name": f"MCP-검토-{uuid.uuid4().hex[:6]}", "scopes": ["read", "catalog:write"]},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return {"Authorization": f"Bearer {made.json()['token']}", "X-Client": "mcp"}


# --- 1 · 5 코드 없는 시험 항목 · 후보 밖 이름 ---------------------------------------


def test_코드_없이_만든_시험_항목은_코드가_지어지고_값_id_로도_고른다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    from app.modules.vocabulary.models import VocabularyTerm

    made = client.post(
        "/api/vocabularies/test_item/terms",
        json={"value": f"열충격 후 굽힘 {uuid.uuid4().hex[:4]}"},
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    assert made.json()["code"].startswith("custom_")

    bad = client.post(
        "/api/vocabularies/test_item/terms",
        json={"value": f"잘못된 코드 {uuid.uuid4().hex[:4]}", "code": "Bad Code"},
        headers=admin.headers,
    )
    assert bad.status_code == 400
    assert "코드 규칙" in bad.json()["error"]["message"]

    # 자동 생성 전에 코드 없이 만든 값 — 값 id 로 골라도 코드가 지어진다.
    legacy = _term(db, "test_item", "옛 값", code=None)
    method = _method(client, admin)
    row = _proposal(
        db,
        "method_test_items",
        subject_id=uuid.UUID(method["id"]),
        key=method_key(method["code"]),
        candidates=[{"code": "tensile", "label": "인장"}],
    )
    decided = client.post(
        f"/api/review/method_test_items/{row.id}/decide",
        json={"choice": [str(legacy.id)]},
        headers=admin.headers,
    )
    assert decided.status_code == 200, decided.text
    db.expire_all()
    fresh = db.get(VocabularyTerm, legacy.id)
    assert fresh is not None
    code = fresh.code
    assert code is not None and code.startswith("custom_")
    assert decided.json()["choice"] == [code]
    # 결정 줄은 그 이름을 남긴다 — 내부 코드로 보이지 않게.
    assert decided.json()["payload"]["choice_labels"] == {code: legacy.value}


# --- 2 보류 사유 -----------------------------------------------------------------------


def test_보류는_사유와_메모가_남고_해제하면_사유가_지워진다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    row = _proposal(db, "test_item_axes", subject_id=None, candidates=[])
    url = f"/api/review/test_item_axes/{row.id}/skip"

    wrong = client.post(url, json={"reason": "모름"}, headers=admin.headers)
    assert wrong.status_code == 422

    held = client.post(
        url, json={"reason": "expert", "note": "진동 담당 확인"}, headers=admin.headers
    )
    assert held.status_code == 200, held.text
    body = held.json()
    assert body["status"] == "skipped"
    assert body["skip_reason"] == "expert"
    assert body["skip_reason_label"] == "도메인 전문가 확인 필요"
    assert body["note"] == "진동 담당 확인"
    assert body["skipped_by"] and body["skipped_at"]

    listed = client.get(
        "/api/review/test_item_axes", params={"status": "skipped"}, headers=admin.headers
    ).json()
    mine = next(one for one in listed["items"] if one["id"] == str(row.id))
    assert mine["skip_reason_label"] == "도메인 전문가 확인 필요"

    back = client.post(url, headers=admin.headers)
    assert back.json()["status"] == "open"
    assert back.json()["skip_reason"] is None


# --- 3 MCP 의견 ------------------------------------------------------------------------


def test_MCP_의견은_표시되고_모아_보고_그대로_확정한다(
    client: TestClient, admin: Signed, db: Session, workspace: Any
) -> None:
    from tests.api.test_review import _member

    machine = _token(client, admin)
    # 의견은 사람마다 하나다 — MCP 와 다르게 보는 사람은 다른 사람이다.
    expert = _member(client, db, workspace)
    item = _term(db, "test_item", "검색축")
    agreed, dissent, human_only = (
        _proposal(db, "test_item_axes", subject_id=item.id, candidates=[]) for _ in range(3)
    )

    for row in (agreed, dissent):
        voted = client.post(
            f"/api/review/test_item_axes/{row.id}/vote",
            json={"choice": []},
            headers=machine,
        )
        assert voted.status_code == 200, voted.text
        vote = voted.json()["votes"][0]
        assert vote["mcp"] is True
        assert vote["user"].endswith("(MCP)")
    # 사람이 다르게 봤다 — 사람의 판단을 AI 의견으로 덮지 않는다.
    keys = client.get("/api/condition-keys", headers=admin.headers).json()
    client.post(
        f"/api/review/test_item_axes/{dissent.id}/vote",
        json={"choice": [keys[0]["key"]]},
        headers=expert.headers,
    )
    client.post(
        f"/api/review/test_item_axes/{human_only.id}/vote",
        json={"choice": []},
        headers=expert.headers,
    )

    listed = client.get(
        "/api/review/test_item_axes",
        params={"votes": "mcp", "limit": 200},
        headers=admin.headers,
    ).json()
    ids = {one["id"] for one in listed["items"]}
    assert {str(agreed.id), str(dissent.id)} <= ids
    assert str(human_only.id) not in ids

    done = client.post(
        "/api/review/test_item_axes/decide-mcp-votes",
        json={"ids": [str(agreed.id), str(dissent.id), str(human_only.id)]},
        headers=admin.headers,
    )
    assert done.status_code == 200, done.text
    assert done.json()["done"] == [str(agreed.id)]
    failed = {one["id"]: one["code"] for one in done.json()["failed"]}
    assert failed == {
        str(dissent.id): "TSC-REVIEW-0021",
        str(human_only.id): "TSC-REVIEW-0019",
    }


# --- 4 시험 항목 해제 · 재확정 교체 ----------------------------------------------------


def _linked_case(client: TestClient, admin: Signed, db: Session) -> dict[str, Any]:
    """규격 하나가 A · B 를 덮는다. 계열 only_a 는 A 로만, both 는 A · B 로 이어진다."""
    from app.modules.test_items.models import SeriesTestItem, SeriesTestItemMethod

    a = _term(db, "test_item", "굽힘")
    b = _term(db, "test_item", "인장")
    method = _method(client, admin)
    set_items = client.patch(
        f"/api/methods/{method['id']}",
        json={"test_item_term_ids": [str(a.id), str(b.id)]},
        headers=admin.headers,
    )
    assert set_items.status_code == 200, set_items.text
    only_a = _series(client, admin, a)
    both = _series(client, admin, a, b)
    for series in (only_a, both):
        for link in db.scalars(
            select(SeriesTestItem).where(SeriesTestItem.series_id == uuid.UUID(series["id"]))
        ):
            db.add(
                SeriesTestItemMethod(
                    series_test_item_id=link.id, method_id=uuid.UUID(method["id"])
                )
            )
    db.commit()
    return {"a": a, "b": b, "method": method, "only_a": only_a, "both": both}


def test_규격의_시험_항목을_떼면_끊기는_계열을_먼저_말하고_사유를_남긴다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    from app.modules.audit.models import AuditEntry
    from app.modules.test_items.models import SeriesPendingMethod

    case = _linked_case(client, admin, db)
    base = f"/api/methods/{case['method']['id']}/test-items/{case['a'].id}"

    preview = client.get(f"{base}/detach-preview", headers=admin.headers)
    assert preview.status_code == 200, preview.text
    assert preview.json()["cut"] == [case["only_a"]["name"]]
    assert preview.json()["kept"] == [case["both"]["name"]]

    blank = client.post(f"{base}/detach", json={"reason": ""}, headers=admin.headers)
    assert blank.status_code == 422

    done = client.post(
        f"{base}/detach", json={"reason": "이 규격은 인장만 다룸"}, headers=admin.headers
    )
    assert done.status_code == 200, done.text
    assert done.json()["cut"] == [case["only_a"]["name"]]

    method = client.get(f"/api/methods/{case['method']['id']}", headers=admin.headers).json()
    assert [one["value"] for one in method["test_items"]] == [case["b"].value]
    # 끊긴 계열은 「인용했는데 항목 미정」 으로 돌아간다 — 인용 사실은 남는다.
    assert db.scalar(
        select(SeriesPendingMethod.id).where(
            SeriesPendingMethod.series_id == uuid.UUID(case["only_a"]["id"]),
            SeriesPendingMethod.method_id == uuid.UUID(case["method"]["id"]),
        )
    )
    cited = {row["series_name"]: row for row in method["cited_series"]}
    assert cited[case["both"]["name"]]["pending"] is False
    entry = db.scalar(
        select(AuditEntry)
        .where(AuditEntry.action == "method.test_item_detached")
        .order_by(AuditEntry.created_at.desc())
    )
    assert entry is not None and entry.reason == "이 규격은 인장만 다룸"


def test_다시_정하면_교체되고_끊길_계열을_미리_말한다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    case = _linked_case(client, admin, db)
    row = _proposal(
        db,
        "method_test_items",
        subject_id=uuid.UUID(case["method"]["id"]),
        key=method_key(case["method"]["code"]),
        candidates=[
            {"code": case["a"].code, "label": case["a"].value},
            {"code": case["b"].code, "label": case["b"].value},
        ],
    )
    preview = client.get(
        f"/api/review/method_test_items/{row.id}/preview",
        params={"choice": [case["b"].code]},
        headers=admin.headers,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["cut"] == [case["only_a"]["name"]]

    decided = client.post(
        f"/api/review/method_test_items/{row.id}/decide",
        json={"choice": [case["b"].code]},
        headers=admin.headers,
    )
    assert decided.status_code == 200, decided.text
    method = client.get(f"/api/methods/{case['method']['id']}", headers=admin.headers).json()
    assert [one["value"] for one in method["test_items"]] == [case["b"].value]
    assert decided.json()["payload"]["unlinked_series"] == [case["only_a"]["name"]]


# --- 6 · 7 계열 시험 항목: 제 근거 · 분류 · 같은 계열 한 줄 ----------------------------


def test_같은_계열은_한_줄로_합치고_분류와_맞지_않는_후보는_추천하지_않는다(
    client: TestClient, admin: Signed, db: Session, tmp_path: Path
) -> None:
    from app.modules.equipment.models import EquipmentSeries
    from app.modules.review import services
    from app.modules.review.models import ReviewProposal

    category = _term(db, "equipment_category", "나노인덴터")
    usual = _term(db, "test_item", "경도")
    extra = _term(db, "test_item", "긁힘")
    odd = _term(db, "test_item", "배터리 남용")
    mine = _series(client, admin, usual)
    peer = _series(client, admin, usual, extra)
    for one in (mine, peer):
        row = db.get(EquipmentSeries, uuid.UUID(one["id"]))
        assert row is not None
        row.category_term_id = category.id
    db.commit()

    rows = [
        {
            "subject": f"a-{mine['id']}",
            "series": mine["name"],
            "manufacturer": "",
            "candidates": [
                {"code": extra.code, "reason": "제조사 문장 1", "sources": ["https://a"]},
            ],
            "recommended": [extra.code],
        },
        {
            "subject": f"b-{mine['id']}",
            "series": mine["name"],
            "manufacturer": "",
            "candidates": [
                {"code": extra.code, "reason": "논문 2편", "sources": ["PMC1"]},
                {"code": odd.code, "reason": "제조사 문장 2", "sources": ["https://b"]},
            ],
            "recommended": [extra.code, odd.code],
        },
    ]
    (tmp_path / "series_test_items.json").write_text(
        json.dumps({"queue": "series_test_items", "rows": rows}, ensure_ascii=False),
        encoding="utf-8",
    )
    services.refresh(db, tmp_path)

    found = list(
        db.scalars(
            select(ReviewProposal).where(
                ReviewProposal.queue == "series_test_items",
                ReviewProposal.subject_id == uuid.UUID(mine["id"]),
                ReviewProposal.status == "open",
            )
        )
    )
    assert len(found) == 1
    by_code = {one["code"]: one for one in found[0].candidates}
    # 같은 후보는 근거 · 출처를 함께 싣는다.
    assert sorted(by_code[extra.code]["sources"]) == ["PMC1", "https://a"]
    assert by_code[extra.code]["recommended"] is True
    # 같은 분류의 다른 계열이 아무도 안 하는 시험 — 경고하고 추천하지 않는다.
    assert by_code[odd.code]["recommended"] is False
    assert by_code[odd.code]["warning"].startswith("분류와 맞지 않음")


def test_같은_계열의_중복_줄은_한쪽을_정하면_같은_결정으로_닫힌다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    series = _series(client, admin)
    first = _proposal(
        db,
        "series_summary",
        subject_id=uuid.UUID(series["id"]),
        candidates=[{"code": "s1", "label": "문장"}],
    )
    twin = _proposal(
        db,
        "series_summary",
        subject_id=uuid.UUID(series["id"]),
        candidates=[{"code": "s1", "label": "문장"}],
    )
    decided = client.post(
        f"/api/review/series_summary/{first.id}/decide",
        json={"choice": []},
        headers=admin.headers,
    )
    assert decided.status_code == 200, decided.text
    db.expire_all()
    db.refresh(twin)
    assert twin.status == "decided"
    assert twin.choice == []
    assert "결정을 따름" in (twin.note or "")


# --- 8 표기만 다른 규격 ---------------------------------------------------------------


def test_판만_다른_후보는_카탈로그_규격으로_묶인다() -> None:
    from app.modules.methods.models import TestMethod
    from app.modules.review.services import _group_standards

    catalog = TestMethod(code="ASTM D638", title="Tensile Properties of Plastics")
    grouped, picks = _group_standards(
        [
            {"code": "ASTM D638-14", "reason": "제조사 페이지 1쪽", "sources": ["https://a"]},
            {"code": "ASTM E18-20", "reason": "논문 1편", "sources": ["PMC1"]},
            {"code": "ASTM E18-10", "reason": "남의 페이지 1쪽", "sources": ["https://b"]},
        ],
        ["ASTM D638-14"],
        official={method_key("ASTM D638"): catalog},
        linked=set(),
        index={},
    )
    codes = [one["code"] for one in grouped]
    # 카탈로그 규격이 앞에 서고 추천이 그리로 간다. 판만 붙은 표기는 경고와 함께 남는다.
    assert codes[:2] == ["ASTM D638", "ASTM D638-14"]
    assert picks == ["ASTM D638"]
    assert grouped[0]["label"].endswith("(카탈로그 규격)")
    assert "카탈로그 ASTM D638" in grouped[1]["warning"]
    # 카탈로그에 없는 판 둘은 판을 뗀 번호 하나로.
    assert "ASTM E18" in codes and "ASTM E18-20" not in codes
    merged = next(one for one in grouped if one["code"] == "ASTM E18")
    assert sorted(merged["sources"]) == ["PMC1", "https://b"]


def test_계열_인용_규격은_후보_밖_번호도_확정에서_받는다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    catalog = _method(client, admin, f"ASTM Z{uuid.uuid4().int % 10000}")
    series = _series(client, admin)
    row = _proposal(
        db,
        "series_standards",
        subject_id=uuid.UUID(series["id"]),
        candidates=[{"code": "ASTM Q1", "label": "ASTM Q1"}],
    )
    wrong = client.post(
        f"/api/review/series_standards/{row.id}/decide",
        json={"choice": ["아무 글"]},
        headers=admin.headers,
    )
    assert wrong.status_code == 404
    decided = client.post(
        f"/api/review/series_standards/{row.id}/decide",
        json={"choice": [catalog["code"]]},
        headers=admin.headers,
    )
    assert decided.status_code == 200, decided.text
    after = client.get(f"/api/methods/{catalog['id']}", headers=admin.headers).json()
    assert series["name"] in [one["series_name"] for one in after["cited_series"]]


def test_규격을_다른_규격으로_병합하면_옛_번호로도_찾는다(
    client: TestClient, admin: Signed, db: Session, tmp_path: Path
) -> None:
    from app.modules.review import services
    from app.modules.review.models import ReviewProposal

    number = uuid.uuid4().int % 100000
    official = _method(client, admin, f"ASTM Y{number}")
    variant = _method(client, admin, f"ASTM Y{number}-19")

    # 판만 다른 규격은 정리 검토함에 병합 후보로 선다.
    services.refresh(db, tmp_path)
    row = db.scalar(
        select(ReviewProposal).where(
            ReviewProposal.queue == "method_cleanup",
            ReviewProposal.subject_key == method_key(variant["code"]),
        )
    )
    assert row is not None and row.status == "open"
    recommended = [one["code"] for one in row.candidates if one["recommended"]]
    assert recommended == [f"merge:{official['code']}"]

    merged = client.post(
        f"/api/methods/{variant['id']}/merge",
        json={"target_id": official["id"], "reason": "판 표시만 다름"},
        headers=admin.headers,
    )
    assert merged.status_code == 200, merged.text
    assert variant["code"] in merged.json()["former_codes"]
    assert (
        client.get(f"/api/methods/{variant['id']}", headers=admin.headers).status_code == 404
    )
    found = client.get(
        "/api/methods", params={"q": variant["code"]}, headers=admin.headers
    ).json()
    assert official["id"] in [one["id"] for one in found["items"]]


# --- 9 범위 사양 승격 ------------------------------------------------------------------


def test_범위_사양_승격은_min_max_표기를_읽고_못_옮긴_기종을_말한다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    from app.modules.equipment.models import ModelFreeSpec

    series = _series(client, admin)
    names = []
    key = f"stroke_{uuid.uuid4().hex[:6]}"
    for value in ("min 0 · max 152", "약 300"):
        made = client.post(
            "/api/equipment-models",
            json={"series_id": series["id"], "name": f"기종-{uuid.uuid4().hex[:6]}"},
            headers=admin.headers,
        )
        assert made.status_code == 201, made.text
        names.append((made.json()["id"], made.json()["name"]))
        db.add(
            ModelFreeSpec(
                model_id=uuid.UUID(made.json()["id"]),
                label=key,
                value_text=value,
                unit="mm",
                source_key=key,
                origin="catalog",
            )
        )
    db.commit()
    groups = client.get("/api/spec-groups", headers=admin.headers).json()
    row = _proposal(
        db,
        "free_spec_definitions",
        subject_id=uuid.UUID(names[0][0]),
        key=f"{key}|mm",
        candidates=[{"code": "promote", "label": "승격"}, {"code": "keep", "label": "유지"}],
        payload={
            "key": key,
            "label": "스트로크",
            "group_id": groups[0]["id"],
            "kind": "range",
            "unit": "mm",
        },
    )
    preview = client.get(
        f"/api/review/free_spec_definitions/{row.id}/preview",
        params={"choice": ["promote"]},
        headers=admin.headers,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["movable"] == [f"{names[0][1]}: min 0 · max 152"]
    assert preview.json()["unmovable"] == [f"{names[1][1]}: 약 300"]

    decided = client.post(
        f"/api/review/free_spec_definitions/{row.id}/decide",
        json={"choice": ["promote"]},
        headers=admin.headers,
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["payload"]["moved"] == 1
    assert decided.json()["payload"]["unmoved"] == [f"{names[1][1]}: 약 300"]

    # 남은 줄은 기종 화면에 「정식 칸으로 옮기지 못함」 으로 보인다.
    left = client.get(f"/api/equipment-models/{names[1][0]}", headers=admin.headers).json()
    assert [one["promoted_to"] for one in left["free_specs"]] == ["스트로크"]
    moved = client.get(f"/api/equipment-models/{names[0][0]}", headers=admin.headers).json()
    assert moved["free_specs"] == []


def test_범위로_읽을_값이_없으면_검토함에서_할_일을_말한다(
    client: TestClient, admin: Signed, db: Session
) -> None:
    from app.modules.equipment.models import ModelFreeSpec

    series = _series(client, admin)
    made = client.post(
        "/api/equipment-models",
        json={"series_id": series["id"], "name": f"기종-{uuid.uuid4().hex[:6]}"},
        headers=admin.headers,
    ).json()
    key = f"odd_{uuid.uuid4().hex[:6]}"
    db.add(
        ModelFreeSpec(
            model_id=uuid.UUID(made["id"]),
            label=key,
            value_text="약 300",
            unit="mm",
            source_key=key,
            origin="catalog",
        )
    )
    db.commit()
    groups = client.get("/api/spec-groups", headers=admin.headers).json()
    row = _proposal(
        db,
        "free_spec_definitions",
        subject_id=uuid.UUID(made["id"]),
        key=f"{key}|mm",
        candidates=[{"code": "promote", "label": "승격"}, {"code": "keep", "label": "유지"}],
        payload={"key": key, "label": "이상한", "group_id": groups[0]["id"], "kind": "range"},
    )
    refused = client.post(
        f"/api/review/free_spec_definitions/{row.id}/decide",
        json={"choice": ["promote"]},
        headers=admin.headers,
    )
    assert refused.status_code == 400
    assert refused.json()["error"]["code"] == "TSC-REVIEW-0022"
    assert "검토함에서" in refused.json()["error"]["message"]

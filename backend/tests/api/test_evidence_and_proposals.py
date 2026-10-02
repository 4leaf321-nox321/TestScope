"""근거 칸 · 번호 없는 규격서 · 개정 이력 · 시험 항목 제안 · 묶음별 장비 판정.

사내 문서 수백 건을 옮겨 적으며 드러난 것들(2026-09-30). 공통점은 **못 하는 일에 말할
자리가 없었다**는 것이다 — 그래서 옮기는 쪽은 비고 문장에 밀어 넣거나 그냥 비웠고, 문장은
검색이 못 읽고 빈 칸은 「없다」 로 읽혔다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.workspaces.models import Workspace
from tests.api.conftest import Signed, division_term_id
from tests.api.test_reliability_tests import _signed_in


def _lab(db: Session, client: TestClient, tag: str) -> tuple[Signed, str]:
    lab = Workspace(
        slug=f"lab-{tag}", name="신뢰성팀", division_term_id=division_term_id(db, "vd")
    )
    db.add(lab)
    db.commit()
    return _signed_in(client, db, lab, "manager"), f"lab-{tag}"


def _condition(client: TestClient, admin: Signed, label: str, key_id: str) -> str:
    made = client.post(
        "/api/attribute-definitions",
        json={
            "target": "reliability_test",
            "label": label,
            "kind": "condition",
            "unit": "degC",
            "condition_key_id": key_id,
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    return str(made.json()["id"])


# ── 9. 값에 근거를 붙일 칸 ─────────────────────────────────────────────────────


def test_원문과_환산_전_값이_따로_남는다(
    client: TestClient, db: Session, admin: Signed, condition_ids: dict[str, str]
) -> None:
    """`note` 는 옮겨 적은 사람의 **해석**이고 원문은 **증거**다.

    한 칸에 섞이면 검토하는 사람이 「이게 문서에 있는 말인가 옮긴 사람의 말인가」 를 못
    가르고, 값 하나를 확인하려고 원본을 다시 연다. 환산도 남겨야 한다 — `70 degC` 만
    보면 그것이 문서의 값인지 158 °F 를 옮긴 값인지 알 수 없다.
    """
    tag = "a" + uuid.uuid4().hex[:5]
    manager, _ = _lab(db, client, tag)
    temperature = _condition(client, admin, f"시험 온도-{tag}", condition_ids["temperature"])

    made = client.post(
        "/api/reliability-tests",
        json={
            "division_code": "vd",
            "name": f"화씨 문서-{tag}",
            "attributes": [
                {
                    "definition_id": temperature,
                    "num_min": 70,
                    "unit": "degC",
                    "source_text": "Test shall be conducted at 158 °F ± 2 °F",
                    "original_value": "158",
                    "original_unit": "degF",
                    "note": "±2 °F 는 못 담아 최소만 적음",
                }
            ],
        },
        headers=manager.headers,
    )
    assert made.status_code == 201, made.text
    row = made.json()["attributes"][0]
    assert row["original_value"] == "158" and row["original_unit"] == "degF"
    assert row["source_text"].startswith("Test shall be conducted")
    # **해석과 증거가 따로 온다** — 섞였으면 이 둘이 한 칸에 있었을 것이다.
    assert row["note"] == "±2 °F 는 못 담아 최소만 적음"


# ── 1. 조건값 조용한 손실 ──────────────────────────────────────────────────────


def test_term_은_비우고_비고만_실어도_된다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """맞는 축 값이 없을 때 **그 이유를 남길 자리**가 있어야 한다.

    조건은 숫자를 비우고 비고만 실어도 통과하는데 온톨로지 값은 400 이었다 — 그래서 옮겨
    적는 쪽은 「축에 없다」 를 말할 방법이 없어 그냥 비웠고, 빈 칸은 「없다」 로 읽혔다.
    """
    tag = "a" + uuid.uuid4().hex[:5]
    manager, _ = _lab(db, client, tag)
    slug = f"kind_{tag}"
    axis = client.post(
        "/api/vocabularies",
        json={"slug": slug, "label": "유형"},
        headers=admin.headers,
    )
    assert axis.status_code == 201, axis.text
    definition = client.post(
        "/api/attribute-definitions",
        json={
            "target": "reliability_test",
            "label": f"유형-{tag}",
            "kind": "term",
            "vocabulary_id": axis.json()["id"],
        },
        headers=admin.headers,
    )
    assert definition.status_code == 201, definition.text

    made = client.post(
        "/api/reliability-tests",
        json={
            "division_code": "vd",
            "name": f"축에 없음-{tag}",
            "attributes": [
                {
                    "definition_id": definition.json()["id"],
                    "note": "문서는 「복합 환경」 이라 적었는데 축에 그런 값이 없음",
                }
            ],
        },
        headers=manager.headers,
    )
    assert made.status_code == 201, made.text
    row = made.json()["attributes"][0]
    assert row["term_id"] is None
    assert "복합 환경" in (row["note"] or "")

    # **아무 말 없이 비우는 것은 여전히 거절한다** — 그것은 「없다」 로 읽힌다.
    empty = client.post(
        "/api/reliability-tests",
        json={
            "division_code": "vd",
            "name": f"그냥 빔-{tag}",
            "attributes": [{"definition_id": definition.json()["id"]}],
        },
        headers=manager.headers,
    )
    assert empty.status_code == 400, empty.text


# ── 10. 규격서 ────────────────────────────────────────────────────────────────


def test_번호_없는_규격서도_올라가고_여럿_설_수_있다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """필수로 두었더니 옮기는 사람이 번호를 **지어냈다** — 지어낸 번호는 문서관리
    시스템의 번호인 줄 알고 누가 찾으러 간다."""
    tag = "a" + uuid.uuid4().hex[:5]
    manager, slug = _lab(db, client, tag)
    first = client.post(
        "/api/spec-documents",
        json={
            "workspace_slug": slug,
            "title": f"번호 없는 지침-{tag}",
            "pages": "12-18",
            "is_excerpt": True,
            "source_path": r"\\nas\규격\2024\지침.pdf",
        },
        headers=manager.headers,
    )
    assert first.status_code == 201, first.text
    assert first.json()["code"] is None
    assert first.json()["pages"] == "12-18" and first.json()["is_excerpt"] is True
    assert "nas" in first.json()["source_path"]

    # **널끼리는 서로 다르다** — 번호 없는 문서 둘이 한 부서에 설 수 있다.
    second = client.post(
        "/api/spec-documents",
        json={"workspace_slug": slug, "title": f"또 다른 지침-{tag}"},
        headers=manager.headers,
    )
    assert second.status_code == 201, second.text

    # 번호가 있는 것끼리는 예전처럼 하나다.
    client.post(
        "/api/spec-documents",
        json={"workspace_slug": slug, "code": f"MX-{tag}", "title": "첫 번째"},
        headers=manager.headers,
    )
    clash = client.post(
        "/api/spec-documents",
        json={"workspace_slug": slug, "code": f"MX-{tag}", "title": "두 번째"},
        headers=manager.headers,
    )
    assert clash.status_code == 409, clash.text


# ── 4. 개정 이력 ──────────────────────────────────────────────────────────────


def test_개정이_쌓여도_확정은_유지되고_안_본_시험이_세어진다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """**수십 건이 한꺼번에 후보로 내려가면 그날 일이 멈춘다.**

    그래서 확정은 그대로 두고 「이 개정을 아직 안 봤다」 는 표만 붙인다. 사람이 본 것부터
    표가 떨어지고, 남은 수가 곧 남은 일이다.
    """
    tag = "a" + uuid.uuid4().hex[:5]
    manager, slug = _lab(db, client, tag)
    document = client.post(
        "/api/spec-documents",
        json={"workspace_slug": slug, "code": f"MX-REL-{tag}", "title": "환경 시험 기준"},
        headers=manager.headers,
    ).json()

    # **규격서를 주면 판도 줘야 한다**(0049) — 판 없이 올리면 같은 자리에 쌓인다.
    first = client.post(
        f"/api/spec-documents/{document['id']}/revisions",
        json={"label": "14"},
        headers=manager.headers,
    )
    assert first.status_code == 201, first.text

    batch = client.post(
        "/api/reliability-tests/batch",
        json={
            "division_code": "vd",
            "document_id": document["id"],
            "document_revision_id": first.json()["id"],
            "tests": [{"name": f"고온고습-{tag}"}, {"name": f"열충격-{tag}"}],
        },
        headers=manager.headers,
    )
    assert batch.status_code == 207, batch.text
    made = batch.json()["created"]
    for row in made:
        client.post(f"/api/reliability-tests/{row['id']}/confirm", headers=manager.headers)

    revision = client.post(
        f"/api/spec-documents/{document['id']}/revisions",
        json={"label": "18", "summary": "시험 온도 상향(85 → 95 °C)"},
        headers=manager.headers,
    )
    assert revision.status_code == 201, revision.text
    assert revision.json()["stale_test_count"] == 2

    # **확정은 그대로다** — 개정이 왔다고 일이 멈추지 않는다.
    still = client.get(f"/api/reliability-tests/{made[0]['id']}", headers=manager.headers)
    assert still.json()["status"] == "confirmed"

    # 사람이 본 것부터 표가 떨어진다.
    seen = client.post(
        f"/api/reliability-tests/{made[0]['id']}/reviewed-revision",
        params={"revision_id": revision.json()["id"]},
        headers=manager.headers,
    )
    assert seen.status_code == 204, seen.text
    rows = client.get(
        f"/api/spec-documents/{document['id']}/revisions", headers=manager.headers
    ).json()
    assert rows[0]["stale_test_count"] == 1, "본 것이 안 빠졌습니다"


# ── 6. 시험 항목 제안 ─────────────────────────────────────────────────────────


def test_축에_없는_시험_항목은_제안으로_쌓이고_한_번에_걸린다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """스무 건 중 아홉 건이 시험 항목 없이 들어왔는데 **왜 비었는지가 아무 데도 안 남았다.**

    같은 말이 여러 시험에서 나오면 한 줄로 모여, 관리자는 스무 번이 아니라 한 번 판단한다.
    """
    tag = "a" + uuid.uuid4().hex[:5]
    manager, _ = _lab(db, client, tag)
    batch = client.post(
        "/api/reliability-tests/batch",
        json={
            "division_code": "vd",
            "tests": [{"name": f"염수 A-{tag}"}, {"name": f"염수 B-{tag}"}],
        },
        headers=manager.headers,
    )
    made = batch.json()["created"]

    for one, text in zip(made, (f"염수분무({tag})", f"염수 분무({tag})"), strict=True):
        got = client.post(
            "/api/reliability-tests/item-proposals",
            json={
                "reliability_test_id": one["id"],
                "text": text,
                "note": "축에 염수 분무는 있는데 농도별 구분이 없음",
            },
            headers=manager.headers,
        )
        assert got.status_code == 201, got.text

    # **왜 비었는지가 그 시험 줄에 보인다.**
    mine = client.get(
        f"/api/reliability-tests/{made[0]['id']}/item-proposals", headers=manager.headers
    )
    assert mine.status_code == 200 and len(mine.json()) == 1

    # **같은 말끼리 모인다** — 띄어쓰기가 달라도 한 줄이다.
    groups = client.get("/api/reliability-tests/item-proposals", headers=manager.headers)
    assert groups.status_code == 200, groups.text
    mine_group = next(one for one in groups.json() if tag in one["text"].replace(" ", ""))
    assert mine_group["count"] == 2, f"두 줄이 한 묶음이어야 합니다: {mine_group}"

    # 부서 관리자는 못 정한다 — 축은 검색의 첫 축이다.
    refused = client.post(
        "/api/reliability-tests/item-proposals/decide",
        json={"normalized": mine_group["normalized"], "new_value": f"염수분무-{tag}"},
        headers=manager.headers,
    )
    assert refused.status_code == 403, refused.text

    # 시스템 관리자가 한 번 정하면 **두 시험에 함께 걸린다.**
    decided = client.post(
        "/api/reliability-tests/item-proposals/decide",
        json={"normalized": mine_group["normalized"], "new_value": f"염수분무-{tag}"},
        headers=admin.headers,
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["decided"] == 2 and decided.json()["linked"] == 2
    for one in made:
        row = client.get(f"/api/reliability-tests/{one['id']}", headers=manager.headers)
        assert [item["value"] for item in row.json()["test_items"]] == [f"염수분무-{tag}"]


# ── 7. 같은 사업부 동명 검사 ──────────────────────────────────────────────────


def test_표기만_다른_동명은_거절한다(client: TestClient, db: Session, admin: Signed) -> None:
    """**resolve 선행은 규율이고 이것이 장치다** — 규율은 수백 건을 적재하는 동안 한 번은
    깨진다. 둘이 서고 나면 어느 쪽이 정본인지 아무도 모른다."""
    tag = "a" + uuid.uuid4().hex[:5]
    manager, _ = _lab(db, client, tag)
    first = client.post(
        "/api/reliability-tests",
        json={"division_code": "vd", "name": f"고온고습 1000h {tag}"},
        headers=manager.headers,
    )
    assert first.status_code == 201, first.text
    again = client.post(
        "/api/reliability-tests",
        json={"division_code": "vd", "name": f"고온고습1000H{tag}"},
        headers=manager.headers,
    )
    assert again.status_code == 409, again.text
    body = again.json()["error"]
    assert body["code"] == "TSC-RELIABILITY-0003"
    # **어느 줄과 겹쳤는지 준다** — 부른 쪽이 그 줄을 열어 보고 고칠 수 있어야 한다.
    assert body["details"]["id"] == first.json()["id"]


# ── 8. 묶음별 장비 판정 ───────────────────────────────────────────────────────


def test_묶음이_둘이면_판정도_묶음마다_따로_온다(
    client: TestClient, db: Session, admin: Signed, condition_ids: dict[str, str]
) -> None:
    """주 조건 80 °C 와 「불량 시」 70 °C 를 섞어 물으면 **아무도 요구하지 않는 조건**이
    만들어지고, 그 조건으로 장비가 걸러지는데 왜 걸러졌는지 화면 어디에도 안 나온다."""
    tag = "a" + uuid.uuid4().hex[:5]
    manager, _ = _lab(db, client, tag)
    temperature = _condition(client, admin, f"시험 온도-{tag}", condition_ids["temperature"])
    made = client.post(
        "/api/reliability-tests",
        json={
            "division_code": "vd",
            "name": f"주예외-{tag}",
            "attributes": [
                {
                    "definition_id": temperature,
                    "set_label": "주",
                    "num_min": 80,
                    "unit": "degC",
                },
                {
                    "definition_id": temperature,
                    "set_label": "불량 시",
                    "num_min": 70,
                    "unit": "degC",
                },
            ],
        },
        headers=manager.headers,
    )
    assert made.status_code == 201, made.text
    got = client.get(
        f"/api/reliability-tests/{made.json()['id']}/equipment", headers=manager.headers
    )
    assert got.status_code == 200, got.text
    body: dict[str, Any] = got.json()
    labels = [one["set_label"] for one in body["sets"]]
    assert labels == ["불량 시", "주"], f"묶음마다 따로 답해야 합니다: {labels}"
    # 합친 답도 남는다 — 「예외 경로까지 이 시험을 통째로 돌릴 장비」 라는 다른 물음이다.
    assert body["conditions_asked"] == 2
    assert all(one["conditions_asked"] == 1 for one in body["sets"])


def test_묶음이_한_벌이면_묶음별_답을_안_만든다(
    client: TestClient, db: Session, admin: Signed, condition_ids: dict[str, str]
) -> None:
    """같은 표를 두 번 그릴 이유가 없다 — 조건이 한 벌인 시험이 대부분이다."""
    tag = "a" + uuid.uuid4().hex[:5]
    manager, _ = _lab(db, client, tag)
    temperature = _condition(client, admin, f"시험 온도-{tag}", condition_ids["temperature"])
    made = client.post(
        "/api/reliability-tests",
        json={
            "division_code": "vd",
            "name": f"한벌-{tag}",
            "attributes": [
                {"definition_id": temperature, "num_min": -40, "num_max": 125, "unit": "degC"}
            ],
        },
        headers=manager.headers,
    )
    got = client.get(
        f"/api/reliability-tests/{made.json()['id']}/equipment", headers=manager.headers
    )
    assert got.json()["sets"] == []

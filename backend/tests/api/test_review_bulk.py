"""검토함 — **고른 줄들을 각자의 추천대로 한꺼번에** 확정한다.

172건을 하나씩 열어 「추천」 을 누르는 일이 고됐다(2026-10-03). 그런데 이 화면은 처음부터
「합의된 건 훑어 확정하고, 갈린 것만 모여 얘기한다」 를 두고 만들었다 — 고된 것은 「훑어
확정」 쪽이고, 그것만 덜어 준다.

여기서 지키는 것:

1. 추천이 있는 줄은 **그 추천대로** 확정되고, 한 건씩 정할 때와 똑같이 적용된다(규격 →
   시험 항목이 붙는다). 「추천을 따랐다」 로 남는다.
2. **추천이 없는 줄은 확정하지 않는다** — 무엇으로 정할지가 없다.
3. **추천과 다른 의견이 있는 줄은 확정하지 않는다** — 누군가 다르게 봤고, 한꺼번에 넘기면
   그 의견을 아무도 안 읽은 채 지나간다. 추천과 **같은** 의견은 막지 않는다.
4. 줄마다 결과다 — 막힌 줄 때문에 다른 줄이 함께 막히지 않는다.
5. 감사에 「추천대로 한꺼번에 확정」 이 남는다 — 하나씩 정한 것과 갈린다.
6. 시스템 관리자만 한다.
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
from app.modules.review import services
from app.shared import audit
from tests.api.conftest import Signed
from tests.api.test_review import _cited_method, _item, _items, _member, _rows


def _seed(
    client: TestClient, admin: Signed, db: Session, tmp_path: Path
) -> tuple[dict[str, dict[str, Any]], dict[str, str], dict[str, str]]:
    """규격 넷 — 추천만 · 추천 없음 · 다른 의견 · 같은 의견. 줄과 항목 코드를 돌려준다."""
    a_id, a = _item(client, admin, "인장")
    b_id, b = _item(client, admin, "압축")
    methods = {
        name: _cited_method(client, admin, [a_id, b_id])
        for name in ("plain", "bare", "dissent", "agree")
    }
    (tmp_path / "method_test_items.json").write_text(
        json.dumps(
            {
                "queue": "method_test_items",
                # `bare` 는 정본에 없다 — 줄은 파생으로 서지만 추천이 없다.
                "rows": [
                    {"subject": methods[name]["code"], "recommended": a, "reason": "Tensile"}
                    for name in ("plain", "dissent", "agree")
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    services.refresh(db, tmp_path)
    db.commit()
    by_subject = {one["subject_id"]: one for one in _rows(client, admin, "method_test_items")}
    rows = {name: by_subject[methods[name]["id"]] for name in methods}
    return rows, {"a": a, "b": b}, {"a": a_id, "b": b_id}


def _bulk(client: TestClient, who: Signed, ids: list[str], **extra: Any) -> Any:
    return client.post(
        "/api/review/method_test_items/decide-recommended",
        json={"ids": ids, **extra},
        headers=who.headers,
    )


def test_추천대로_한꺼번에_정하고_갈린_줄은_돌려준다(
    client: TestClient, admin: Signed, db: Session, tmp_path: Path, workspace: Any
) -> None:
    rows, codes, ids = _seed(client, admin, db, tmp_path)

    # 의견 둘 — 하나는 추천과 **다르게**, 하나는 추천과 **같게**.
    voter = _member(client, db, workspace)
    for name, choice in (("dissent", codes["b"]), ("agree", codes["a"])):
        voted = client.post(
            f"/api/review/method_test_items/{rows[name]['id']}/vote",
            json={"choice": [choice]},
            headers=voter.headers,
        )
        assert voted.status_code == 200, voted.text

    done = _bulk(
        client, admin, [rows[name]["id"] for name in ("plain", "bare", "dissent", "agree")]
    )
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["requested"] == 4

    # 1 · 3 — 추천만 있는 줄과 **같은 의견**이 있는 줄은 정해진다.
    assert set(body["done"]) == {rows["plain"]["id"], rows["agree"]["id"]}

    # 2 · 3 — 추천 없는 줄, 다른 의견이 있는 줄은 **이유와 함께** 돌아온다.
    refused = {one["id"]: one["code"] for one in body["failed"]}
    assert refused == {
        rows["bare"]["id"]: "TSC-REVIEW-0014",
        rows["dissent"]["id"]: "TSC-REVIEW-0015",
    }

    # 1 — 한 건씩 정할 때와 **같이 적용됐다**: 규격에 추천 항목이 붙었다.
    method = uuid.UUID(rows["plain"]["subject_id"])
    assert _items(db, method) == [ids["a"]]
    decided = {
        one["id"]: one for one in _rows(client, admin, "method_test_items", status="decided")
    }
    assert decided[rows["plain"]["id"]]["followed"] is True

    # 4 — 막힌 줄은 **열린 채** 남는다(반쯤 바뀌지 않았다).
    still = {
        one["id"]
        for one in _rows(client, admin, "method_test_items", status="all")
        if one["status"] in ("open", "voted")
    }
    assert rows["bare"]["id"] in still and rows["dissent"]["id"] in still


def test_감사에_한꺼번에_정한_것이_남는다(
    client: TestClient, admin: Signed, db: Session, tmp_path: Path
) -> None:
    rows, _, _ = _seed(client, admin, db, tmp_path)
    assert _bulk(client, admin, [rows["plain"]["id"]]).status_code == 200

    entry = db.scalar(
        select(AuditEntry)
        .where(
            AuditEntry.action == audit.REVIEW_DECIDED,
            AuditEntry.target_id == uuid.UUID(rows["plain"]["id"]),
        )
        .order_by(AuditEntry.created_at.desc())
    )
    assert entry is not None
    # 하나씩 정한 것과 **갈린다** — 나중에 「이건 사람이 보고 정했나」 를 물을 수 있다.
    assert entry.reason == "추천대로 한꺼번에 확정"
    assert entry.changes["followed"] is True


def test_시스템_관리자만_한다(
    client: TestClient, admin: Signed, db: Session, tmp_path: Path, workspace: Any
) -> None:
    rows, _, _ = _seed(client, admin, db, tmp_path)
    member = _member(client, db, workspace)
    refused = _bulk(client, member, [rows["plain"]["id"]])
    assert refused.status_code == 403, refused.text

"""상태 근거 — **왜 그 상태인가.**

상태는 여섯인데(입고·가동·유휴·점검·고장·폐기) 무엇이 고장인지, 왜 유휴인지가 어디에도
없었다. 그 답은 비고에 섞여 들어갔고, 비고는 온갖 것이 함께 적히는 칸이라 아무도 그것을
상태의 근거로 안 읽는다.

여기서 지키는 것:

1. 등록·수정에서 근거를 적고 되받는다.
2. **상태가 바뀌면 근거는 사라진다.** 고쳐서 가동으로 되돌렸는데 「제어보드 고장」 이 남아
   있으면 목록은 가동 중인 장비에 고장 사유를 그려 준다 — 근거는 상태에 붙는 것이지
   장비에 붙는 것이 아니다.
3. 상태를 바꾸면서 **새 근거를 같이 보내면** 그것이 남는다(고장 → 폐기로 넘길 때).
4. 상태를 안 건드리고 근거만 고치는 것은 된다 — 같은 고장의 사정이 자세해지는 일이다.
5. 폐기는 **왜 버렸는지가 감사에 남는다.**
6. `status_reason=none` 으로 **근거를 안 적은 장비**를 찾는다.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEntry
from tests.api.conftest import Signed, category_id, site_id


def _make(client: TestClient, admin: Signed, tag: str, **extra: Any) -> dict[str, Any]:
    made = client.post(
        "/api/equipment",
        json={
            "asset_no": f"SR-{tag}-{uuid.uuid4().hex[:4]}",
            "name": f"만능기-{tag}",
            "workspace_slug": admin.workspace,
            "site_term_id": site_id(client, admin),
            "location": "3동",
            "category_term_id": category_id(client, admin),
            **extra,
        },
        headers=admin.headers,
    )
    assert made.status_code == 201, made.text
    out: dict[str, Any] = made.json()
    return out


def test_근거는_상태에_붙는다(client: TestClient, admin: Signed) -> None:
    tag = uuid.uuid4().hex[:6]
    one = _make(client, admin, tag, status="repair", status_reason="제어보드 고장, 부품 대기")
    assert one["status_reason"] == "제어보드 고장, 부품 대기"

    def patch(**body: Any) -> dict[str, Any]:
        got = client.patch(f"/api/equipment/{one['id']}", json=body, headers=admin.headers)
        assert got.status_code == 200, got.text
        out: dict[str, Any] = got.json()
        return out

    # 상태를 안 건드리고 근거만 — 같은 고장의 사정이 자세해지는 일이다.
    assert patch(status_reason="제어보드 고장 — 부품 3주")["status_reason"] == (
        "제어보드 고장 — 부품 3주"
    )

    # **상태가 바뀌면 사라진다.** 고친 장비에 고장 사유가 남아 있으면 안 된다.
    fixed = patch(status="operational")
    assert fixed["status"] == "operational"
    assert fixed["status_reason"] is None

    # 상태를 바꾸면서 새 근거를 같이 보내면 그것이 남는다.
    idle = patch(status="idle", status_reason="과제 종료로 유휴")
    assert (idle["status"], idle["status_reason"]) == ("idle", "과제 종료로 유휴")

    # 같은 상태로 다시 보내면 근거는 안 건드린다 — 바뀐 것이 없다.
    assert patch(status="idle")["status_reason"] == "과제 종료로 유휴"


def test_폐기는_왜_버렸는지가_감사에_남는다(
    client: TestClient, db: Session, admin: Signed
) -> None:
    """「누가 언제 폐기했나」 만 있으면 반년 뒤 「그 장비 어디 갔냐」 에 답할 수 없다."""
    tag = uuid.uuid4().hex[:6]
    one = _make(client, admin, tag)
    got = client.patch(
        f"/api/equipment/{one['id']}",
        json={"status": "retired", "status_reason": "침수로 복구 불가"},
        headers=admin.headers,
    )
    assert got.status_code == 200, got.text
    assert got.json()["status_reason"] == "침수로 복구 불가"

    entry = db.scalar(
        select(AuditEntry)
        .where(AuditEntry.target_id == uuid.UUID(one["id"]))
        .order_by(AuditEntry.created_at.desc())
    )
    assert entry is not None
    assert entry.changes["status_reason"] == "침수로 복구 불가"


def test_근거를_안_적은_장비를_찾는다(client: TestClient, admin: Signed) -> None:
    """**폐기인데 왜 버렸는지가 없다** — 이 물음이 이 칸을 만든 이유다."""
    tag = uuid.uuid4().hex[:6]
    said = _make(client, admin, tag, status="repair", status_reason=f"제어보드-{tag}")
    blank = _make(client, admin, tag, status="retired")

    def assets(**params: str) -> set[str]:
        got = client.get(
            "/api/equipment",
            params={"q": tag, "limit": 200, **params},
            headers=admin.headers,
        )
        assert got.status_code == 200, got.text
        return {one["asset_no"] for one in got.json()["items"]}

    assert assets() == {said["asset_no"], blank["asset_no"]}
    assert assets(status_reason=tag) == {said["asset_no"]}
    assert assets(status_reason="none") == {blank["asset_no"]}

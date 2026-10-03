"""접근 로그 — **보존 기간이 지나면 스스로 지운다.**

전에는 아무도 안 지워서 끝없이 자랐다. 여기서 지키는 것 — 보존 기간보다 오래된 줄만 지운다 ·
0 이면 안 지운다 · 상태를 바꾸는 요청 뒤에 하루 한 번 돈다(다음 날까지는 다시 안 돈다).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.audit.models import AccessLog
from app.shared import access_log
from tests.api.conftest import Signed


def _row(db: Session, days_ago: int) -> uuid.UUID:
    row = AccessLog(
        action="API",
        path=f"/api/retention-{uuid.uuid4().hex[:6]}",
        method="POST",
        status_code=200,
        created_at=datetime.now(UTC) - timedelta(days=days_ago),
    )
    db.add(row)
    db.commit()
    return row.id


def _alive(db: Session, row_id: uuid.UUID) -> bool:
    db.expire_all()
    return db.get(AccessLog, row_id) is not None


def test_보존_기간보다_오래된_줄만_지운다(db: Session) -> None:
    old = _row(db, 400)
    fresh = _row(db, 10)

    # 0 이면 안 지운다 — 「끝없이 둔다」 를 고를 수 있어야 한다.
    assert access_log.prune(db, days=0) == 0
    assert _alive(db, old)

    assert access_log.prune(db, days=365) >= 1
    assert not _alive(db, old)
    assert _alive(db, fresh)


def test_상태를_바꾸는_요청_뒤에_하루_한_번_스스로_지운다(
    client: TestClient, admin: Signed, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = _row(db, 400)
    monkeypatch.setattr(access_log, "_next_prune", 0.0)

    # 남는 요청이면 무엇이든 — 응답이 오류여도 접근 로그는 남고, 그 뒤에 지우기가 돈다.
    client.post("/api/resolve", json={}, headers=admin.headers)
    assert not _alive(db, old)

    # 다음 날까지는 다시 안 돈다 — 요청마다 지우기를 돌리면 쓰기 요청이 전부 느려진다.
    again = _row(db, 400)
    client.post("/api/resolve", json={}, headers=admin.headers)
    assert _alive(db, again)
    access_log.prune(db, days=365)

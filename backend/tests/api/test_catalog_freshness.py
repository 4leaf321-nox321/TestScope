"""카탈로그 신선도 — 정본(파일)과 DB 에 반입된 시점이 다르면 **화면이 말한다.**

배포는 `source/catalog` 를 새로 놓지만 반입은 사람이 돌린다. 안 돌린 사실이 어디에도
안 적히면 「카탈로그에 없던데」 가 반입을 안 한 것인지 정본에도 없는 것인지 구별되지 않는다.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEntry
from app.modules.server import catalog_state
from app.shared.audit import record
from tests.api.conftest import Signed


@pytest.fixture
def no_imports(db: Session) -> Iterator[None]:
    """반입 기록을 비운 채로 시작하고, 끝나면 이 시험이 남긴 것을 지운다."""
    db.execute(delete(AuditEntry).where(AuditEntry.action == catalog_state.IMPORTED_ACTION))
    db.commit()
    yield
    db.execute(delete(AuditEntry).where(AuditEntry.action == catalog_state.IMPORTED_ACTION))
    db.commit()


def _stamp(db: Session, digest: str, objects: int) -> None:
    record(
        db,
        action=catalog_state.IMPORTED_ACTION,
        actor=None,
        target_table="catalog",
        target_id=None,
        target_label="시험",
        changes={"digest": digest, "objects": objects},
    )
    db.commit()


def _keys(client: TestClient, admin: Signed) -> set[str]:
    response = client.get("/api/server/maintenance", headers=admin.headers)
    assert response.status_code == 200, response.text
    return {row["key"] for row in response.json()}


def test_지문은_반입이_읽는_파일에서만_나온다() -> None:
    source = catalog_state.fingerprint()
    assert source is not None, "저장소에 정본이 있어야 한다"
    assert source.objects > 0
    # 같은 파일이면 같은 지문 — 다시 빌드만 한 것을 「뒤짐」 으로 읽으면 경고는 곧 무시된다.
    assert catalog_state.fingerprint() == source


def test_한_번도_반입하지_않았으면_그렇다고_말한다(
    client: TestClient, admin: Signed, no_imports: None
) -> None:
    status = client.get("/api/server/status", headers=admin.headers)
    assert status.status_code == 200, status.text
    catalog = status.json()["catalog"]
    assert catalog["available"] is True
    assert catalog["never"] is True
    assert catalog["behind"] is False
    assert catalog["imported_at"] is None
    assert "catalog_behind" in _keys(client, admin)


def test_정본과_같은_지문이면_조용하고_다르면_뒤짐이다(
    client: TestClient, admin: Signed, db: Session, no_imports: None
) -> None:
    source = catalog_state.fingerprint()
    assert source is not None
    _stamp(db, source.digest, source.objects)
    catalog = client.get("/api/server/status", headers=admin.headers).json()["catalog"]
    assert (catalog["never"], catalog["behind"]) == (False, False)
    assert catalog["imported_digest"] == source.digest
    assert "catalog_behind" not in _keys(client, admin)

    # 정본이 바뀐 뒤(지문이 다른 반입 기록만 있음) — 마지막 것으로 본다.
    _stamp(db, "0000000000000000", source.objects - 1)
    catalog = client.get("/api/server/status", headers=admin.headers).json()["catalog"]
    assert catalog["behind"] is True
    assert catalog["imported_objects"] == source.objects - 1
    assert "catalog_behind" in _keys(client, admin)

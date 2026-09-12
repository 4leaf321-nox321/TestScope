"""카탈로그 신선도 — **정본은 파일이고, DB 는 그것을 반입한 어느 시점이다.**

운영 서버의 카탈로그는 사람이 `scripts/import_catalog.py` 를 돌려야 들어간다. 배포는
`source/catalog` 를 새로 놓지만 DB 는 안 건드리므로, 안 돌리면 화면은 지난 카탈로그를
새 것처럼 보여 준다 — 그리고 그 사실은 어디에도 안 적힌다. 「이 기종 카탈로그에 없던데」
가 「반입을 안 돌렸다」 인지 「정본에도 없다」 인지 구별할 길이 없다.

그래서 둘을 잰다:

- **정본의 지문** — 반입이 읽는 파일(`equipment/**/*.json` · `ontology/*.json`)의 sha256.
  시각이 아니라 내용이다: 운영 서버엔 git 이 없고, 다시 빌드만 한 파일은 내용이 같다.
- **마지막 반입** — 반입이 끝에 남기는 감사 기록 `catalog.imported` 의 시각과 그때의 지문.

둘이 다르면 「뒤짐」 이다. 며칠 뒤졌는지는 말할 수 없다(정본에 날짜가 없다) — 대신
언제 반입했고 객체 수가 어떻게 달라졌는지를 말한다.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import REPO_DIR
from app.modules.audit.models import AuditEntry

#: 반입이 끝에 남기는 감사 기록의 action. 스크립트와 여기가 같은 글자를 봐야 한다.
IMPORTED_ACTION = "catalog.imported"

#: 정본이 사는 곳. 반입 스크립트의 기본값과 같다(`scripts/import_catalog.py`).
DEFAULT_ROOT = REPO_DIR / "source" / "catalog"

#: 지문에 넣는 것 — **반입이 읽는 파일만.** `urls.json` 이나 `graph.json` 을 넣으면
#: PDF 하나 더 받거나 그래프만 다시 빌드해도 「뒤짐」 이 되고, 그 경고는 곧 무시된다.
INPUT_GLOBS = ("equipment/**/*.json", "ontology/*.json")


@dataclass(frozen=True)
class CatalogSource:
    digest: str
    objects: int


@dataclass(frozen=True)
class CatalogImport:
    imported_at: datetime
    digest: str | None
    objects: int | None


def fingerprint(root: Path = DEFAULT_ROOT) -> CatalogSource | None:
    """정본의 지문과 객체 수. 정본이 없으면 None — 지어내지 않는다."""
    if not (root / "equipment").is_dir():
        return None
    digest = hashlib.sha256()
    objects = 0
    for pattern in INPUT_GLOBS:
        for path in sorted(root.glob(pattern)):
            rel = path.relative_to(root).as_posix()
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
            if rel.startswith("equipment/"):
                objects += 1
    return CatalogSource(digest=digest.hexdigest()[:16], objects=objects)


def last_import(db: Session) -> CatalogImport | None:
    """마지막 반입. 한 번도 없으면 None."""
    entry = db.scalar(
        select(AuditEntry)
        .where(AuditEntry.action == IMPORTED_ACTION)
        .order_by(AuditEntry.created_at.desc())
        .limit(1)
    )
    if entry is None:
        return None
    changes = entry.changes or {}
    digest = changes.get("digest")
    objects = changes.get("objects")
    return CatalogImport(
        imported_at=entry.created_at,
        digest=str(digest) if digest else None,
        objects=int(objects) if isinstance(objects, int) else None,
    )

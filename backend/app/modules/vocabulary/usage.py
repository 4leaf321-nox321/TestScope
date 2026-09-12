"""쓰임 — 무엇이 이 값을 가리키나, 그 자리에서 떼기·옮기기.

`services.py` 에서 갈라 나온 것(2026-09-13). 글자는 그대로, 자리만 옮겼다.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.vocabulary.models import (
    Vocabulary,
    VocabularyTerm,
)
from app.modules.vocabulary.references import BY_KEY
from app.modules.vocabulary.schemas import (
    ReferenceGroupOut,
    ReferenceRowOut,
)
from app.modules.vocabulary.terms import (
    _twin_exists,
    get_term,
)
from app.shared import audit
from app.shared.errors import AppError, Conflict, NotFound

# --- 쓰임 — 무엇이 이 값을 가리키나, 떼기, 옮기기 ---------------------------------


def term_references(db: Session, term_id: uuid.UUID) -> list[ReferenceGroupOut]:
    """이 값을 가리키는 것 전부, 종류별로. **쓰임 수와 같은 표에서 센다.**"""
    term = get_term(db, term_id)
    vocabulary = db.get(Vocabulary, term.vocabulary_id)
    if vocabulary is None:  # pragma: no cover - FK 가 막는다
        return []
    out: list[ReferenceGroupOut] = []
    for kind in BY_KEY.values():
        if kind.axis != vocabulary.slug:
            continue
        stmt = select(kind.model).where(kind.column == term.id)
        deleted = getattr(kind.model, "deleted_at", None)
        if deleted is not None:
            stmt = stmt.where(deleted.is_(None))
        rows = list(db.scalars(stmt))
        if not rows:
            continue
        described = [
            ReferenceRowOut(id=row.id, label=label, href=href)
            for row in rows
            for label, href in (kind.describe(db, row),)
        ]
        described.sort(key=lambda one: one.label)
        out.append(
            ReferenceGroupOut(
                key=kind.key, label=kind.label, detach=kind.detach, rows=described
            )
        )
    return out


def _reference_row(db: Session, term: VocabularyTerm, kind_key: str, row_id: uuid.UUID) -> Any:
    kind = BY_KEY.get(kind_key)
    if kind is None:
        raise NotFound("TSC-VOCAB-0012", f"모르는 쓰임 종류입니다: {kind_key}")
    row = db.get(kind.model, row_id)
    if row is None or getattr(row, kind.column.key) != term.id:
        raise NotFound("TSC-VOCAB-0013", "그 줄이 이 값을 가리키고 있지 않습니다.")
    return kind, row


def detach_reference(
    db: Session, *, term_id: uuid.UUID, kind_key: str, row_id: uuid.UUID, actor: User
) -> None:
    """이 값을 가리키는 줄 하나를 뗀다 — 연결 줄이면 지우고, 비워도 되는 칸이면 비운다.

    **비울 수 없는 칸은 못 뗀다**(장비의 거점). 그때는 옮기기만 된다 — 거점 없는 장비는
    찾아도 소용이 없어서 비울 수 없게 했다(0008).
    """
    term = get_term(db, term_id)
    kind, row = _reference_row(db, term, kind_key, row_id)
    label, _ = kind.describe(db, row)
    if kind.detach == "delete":
        db.delete(row)
    elif kind.detach == "null":
        setattr(row, kind.column.key, None)
    else:
        raise AppError(
            "TSC-VOCAB-0014",
            f"{kind.label}은(는) 비울 수 없는 칸입니다. 다른 값으로 옮기세요.",
            status=400,
        )
    audit.record(
        db,
        action=audit.VOCABULARY_REFERENCE_CHANGED,
        actor=actor,
        target_table="vocabulary_terms",
        target_id=term.id,
        target_label=term.value,
        changes={kind.key: {"before": label, "after": None}},
    )
    db.commit()


def reassign_reference(
    db: Session,
    *,
    term_id: uuid.UUID,
    kind_key: str,
    row_id: uuid.UUID,
    target_term_id: uuid.UUID,
    actor: User,
) -> None:
    """이 값을 가리키는 줄 하나를 **같은 축의 다른 값**으로 옮긴다.

    옮긴 자리에 같은 줄이 이미 있으면(그 계열에 「인장」 이 벌써 있는데 「인장시험」 줄을
    「인장」 으로) 연결 줄은 하나로 합치고, 그 밖의 칸은 거절한다.
    """
    term = get_term(db, term_id)
    target = get_term(db, target_term_id)
    if target.vocabulary_id != term.vocabulary_id:
        raise AppError("TSC-VOCAB-0007", "다른 축의 값으로는 옮길 수 없습니다.", status=400)
    if target.id == term.id:
        raise AppError("TSC-VOCAB-0006", "같은 값입니다.", status=400)
    kind, row = _reference_row(db, term, kind_key, row_id)
    label, _ = kind.describe(db, row)
    if _twin_exists(db, kind.model, kind.column, row, target.id):
        if kind.detach != "delete":
            raise Conflict("TSC-VOCAB-0015", f"옮긴 자리에 같은 줄이 이미 있습니다: {label}")
        db.delete(row)
    else:
        setattr(row, kind.column.key, target.id)
    audit.record(
        db,
        action=audit.VOCABULARY_REFERENCE_CHANGED,
        actor=actor,
        target_table="vocabulary_terms",
        target_id=term.id,
        target_label=term.value,
        changes={
            kind.key: {
                "before": f"{label} → {term.value}",
                "after": f"{label} → {target.value}",
            }
        },
    )
    db.commit()

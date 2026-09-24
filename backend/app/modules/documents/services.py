"""사내 규격서 — 읽기는 로그인한 누구나, 쓰기는 그 부서의 관리자와 시스템 관리자.

**신뢰성 시험과 같은 규칙이다.** MX-REL-012 는 그 부서가 만들고 그 부서가 고친다 —
시스템 관리자를 거치게 하면 문서가 안 올라온다. 보는 것은 누구나인 것도 같은 이유다:
옆 부서가 무슨 기준으로 시험하는지 보는 것이 이 플랫폼의 쓸모다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, true
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.attachments.models import Attachment
from app.modules.attributes.models import AttributeValue
from app.modules.documents.models import SpecDocument
from app.modules.documents.schemas import SpecDocumentOut
from app.modules.workspaces.models import Workspace
from app.shared import audit
from app.shared.errors import AppError, Conflict, NotFound
from app.shared.permissions import membership_of, require_manager, workspace_by_slug
from app.shared.text import clean

_WHAT = "사내 규격서"


def _can_edit(db: Session, user: User, workspace_id: uuid.UUID) -> bool:
    if user.is_system_admin:
        return True
    membership = membership_of(db, workspace_id=workspace_id, user_id=user.id)
    return membership is not None and membership.role == "manager"


def get(db: Session, document_id: uuid.UUID) -> SpecDocument:
    row = db.get(SpecDocument, document_id)
    if row is None or row.deleted_at is not None:
        raise NotFound("TSC-DOCS-0001", "사내 규격서를 찾을 수 없습니다.")
    return row


def require_editable(db: Session, user: User, document_id: uuid.UUID) -> None:
    """고칠 수 있나. **첨부도 같은 물음을 쓴다** — 판정이 두 벌이면 「문서는 못 고치는데
    파일은 붙는」 사람이 생긴다."""
    row = get(db, document_id)
    workspace = db.get(Workspace, row.workspace_id)
    assert workspace is not None
    require_manager(db, workspace=workspace, user=user)


def _outs(db: Session, user: User, rows: list[SpecDocument]) -> list[SpecDocumentOut]:
    """목록 하나를 질의 몇 번으로 — 줄마다 세면 스무 줄이 왕복 예순 번이 된다."""
    if not rows:
        return []
    ids = [row.id for row in rows]
    workspaces = {
        one.id: one
        for one in db.scalars(
            select(Workspace).where(Workspace.id.in_({r.workspace_id for r in rows}))
        )
    }
    files = {
        object_id: int(count)
        for object_id, count in db.execute(
            select(Attachment.object_id, func.count())
            .where(Attachment.target == "spec_document", Attachment.object_id.in_(ids))
            .group_by(Attachment.object_id)
        ).all()
    }
    # 이 문서를 가리키는 신뢰성 시험 수 — 「아무도 안 쓰는 문서」 를 가리는 칸이다.
    linked = {
        document_id: int(count)
        for document_id, count in db.execute(
            select(AttributeValue.ref_document_id, func.count())
            .where(AttributeValue.ref_document_id.in_(ids))
            .group_by(AttributeValue.ref_document_id)
        ).all()
    }
    editable = {wid: _can_edit(db, user, wid) for wid in workspaces}
    out: list[SpecDocumentOut] = []
    for row in rows:
        workspace = workspaces[row.workspace_id]
        out.append(
            SpecDocumentOut(
                id=row.id,
                workspace_slug=workspace.slug,
                workspace_name=workspace.name,
                code=row.code,
                title=row.title,
                revision=row.revision,
                note=row.note,
                file_count=files.get(row.id, 0),
                linked_test_count=linked.get(row.id, 0),
                can_edit=editable[row.workspace_id],
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
        )
    return out


def document_out(db: Session, user: User, row: SpecDocument) -> SpecDocumentOut:
    return _outs(db, user, [row])[0]


def list_documents(
    db: Session, user: User, *, workspace: str | None = None, query: str | None = None
) -> list[SpecDocumentOut]:
    """사내 규격서 — `workspace` 를 주면 그 부서 것만, 안 주면 전사 전부(부서 순).

    **읽기는 누구나다.** 옆 부서가 무슨 기준으로 시험하는지 보는 것이 이 플랫폼의 물음이다.
    """
    stmt = (
        select(SpecDocument)
        .join(Workspace, Workspace.id == SpecDocument.workspace_id)
        .where(SpecDocument.deleted_at.is_(None))
        .order_by(Workspace.sort_order, Workspace.name, SpecDocument.code)
    )
    if workspace:
        stmt = stmt.where(SpecDocument.workspace_id == workspace_by_slug(db, workspace).id)
    if query:
        text = f"%{clean(query)}%"
        stmt = stmt.where(SpecDocument.code.ilike(text) | SpecDocument.title.ilike(text))
    return _outs(db, user, list(db.scalars(stmt)))


def _check_code_free(
    db: Session, workspace_id: uuid.UUID, code: str, *, except_id: uuid.UUID | None
) -> None:
    clash = db.scalar(
        select(SpecDocument).where(
            SpecDocument.workspace_id == workspace_id,
            SpecDocument.deleted_at.is_(None),
            func.lower(SpecDocument.code) == code.lower(),
            SpecDocument.id != except_id if except_id else true(),
        )
    )
    if clash is not None:
        raise Conflict(
            "TSC-DOCS-0003",
            f"이 부서에 같은 번호의 규격서가 있습니다: {code}",
            details={"id": str(clash.id)},
        )


def create(db: Session, user: User, payload: dict[str, Any]) -> SpecDocument:
    workspace = workspace_by_slug(db, payload["workspace_slug"])
    require_manager(db, workspace=workspace, user=user)
    code = clean(str(payload["code"]))
    if not code:
        raise AppError("TSC-DOCS-0004", "문서 번호를 적어 주십시오.")
    _check_code_free(db, workspace.id, code, except_id=None)
    row = SpecDocument(
        workspace_id=workspace.id,
        code=code,
        title=clean(str(payload["title"])),
        revision=clean(str(payload.get("revision") or "")) or None,
        note=payload.get("note") or None,
        created_by_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update(
    db: Session, user: User, document_id: uuid.UUID, changes: dict[str, Any]
) -> SpecDocument:
    """`changes` 는 `exclude_unset` 으로 온다 — 안 보낸 칸은 안 건드린다."""
    row = get(db, document_id)
    require_editable(db, user, document_id)

    if changes.get("workspace_slug"):
        moved = workspace_by_slug(db, changes["workspace_slug"])
        require_manager(db, workspace=moved, user=user)
        row.workspace_id = moved.id
    if "code" in changes and changes["code"] is not None:
        code = clean(str(changes["code"]))
        if not code:
            raise AppError("TSC-DOCS-0004", "문서 번호를 적어 주십시오.")
        _check_code_free(db, row.workspace_id, code, except_id=row.id)
        row.code = code
    if "title" in changes and changes["title"] is not None:
        row.title = clean(str(changes["title"]))
    if "revision" in changes:
        row.revision = clean(str(changes["revision"] or "")) or None
    if "note" in changes:
        row.note = changes["note"] or None
    db.commit()
    db.refresh(row)
    return row


def delete(db: Session, user: User, document_id: uuid.UUID) -> None:
    """지우지 않고 `deleted_at` 만 채운다.

    **걸려 있는 시험이 있으면 거절한다.** 지우고 나면 그 시험이 무엇을 따랐는지 알 수
    없게 되는데, 그 사실은 화면 어디에도 안 보인다.
    """
    row = get(db, document_id)
    require_editable(db, user, document_id)
    workspace = db.get(Workspace, row.workspace_id)
    assert workspace is not None
    linked = (
        db.scalar(
            select(func.count())
            .select_from(AttributeValue)
            .where(AttributeValue.ref_document_id == row.id)
        )
        or 0
    )
    if linked:
        raise Conflict(
            "TSC-DOCS-0005",
            f"이 규격서를 가리키는 신뢰성 시험이 {linked}건 있습니다 — 먼저 끊어 주십시오.",
            details={"linked_test_count": linked},
        )
    row.deleted_at = datetime.now(UTC)
    audit.record(
        db,
        action=audit.SPEC_DOCUMENT_DELETED,
        actor=user,
        target_table="spec_documents",
        target_id=row.id,
        target_label=f"{workspace.name} · {row.code} {row.title}",
        workspace_id=workspace.id,
    )
    db.commit()

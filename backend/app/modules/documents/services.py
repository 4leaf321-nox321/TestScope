"""사내 규격서 — 읽기는 로그인한 누구나, 쓰기는 그 부서의 관리자와 시스템 관리자.

**신뢰성 시험과 같은 규칙이다.** MX-REL-012 는 그 부서가 만들고 그 부서가 고친다 —
시스템 관리자를 거치게 하면 문서가 안 올라온다. 보는 것은 누구나인 것도 같은 이유다:
옆 부서가 무슨 기준으로 시험하는지 보는 것이 이 플랫폼의 쓸모다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select, true
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.attachments.models import Attachment
from app.modules.attributes.models import AttributeValue
from app.modules.documents.models import SpecDocument, SpecDocumentRevision
from app.modules.documents.schemas import SpecDocumentOut, SpecDocumentRevisionOut
from app.modules.reliability.models import ReliabilityTest
from app.modules.workspaces.models import Workspace
from app.shared import audit
from app.shared.errors import AppError, Conflict, NotFound
from app.shared.permissions import membership_of, require_manager, workspace_by_slug
from app.shared.request_context import get_actor_token
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
        raise NotFound("TSC-DOCS-0001", "사내 규격서를 찾을 수 없음.")
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
                pages=row.pages,
                is_excerpt=row.is_excerpt,
                source_path=row.source_path,
                note=row.note,
                submitted_via=row.submitted_via,
                file_count=files.get(row.id, 0),
                linked_test_count=linked.get(row.id, 0),
                can_edit=editable[row.workspace_id],
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
        )
    return out


def document_out(db: Session, user: User, row: SpecDocument) -> SpecDocumentOut:
    """한 건을 읽을 때는 **개정 이력도 함께.** 목록은 안 싣는다 — 스무 줄이면 왕복이
    스무 번이 된다(파일 수를 수로만 보내는 것과 같은 이유)."""
    out = _outs(db, user, [row])[0]
    out.revisions = revisions_of(db, row.id)
    return out


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
            f"이 부서에 같은 번호의 규격서 있음: {code}",
            details={"id": str(clash.id)},
        )


def create(db: Session, user: User, payload: dict[str, Any]) -> SpecDocument:
    workspace = workspace_by_slug(db, payload["workspace_slug"])
    require_manager(db, workspace=workspace, user=user)
    # **번호는 없을 수 있다.** 필수로 두었더니 옮기는 사람이 번호를 지어냈고, 지어낸
    # 번호는 문서관리 시스템의 번호인 줄 알고 누가 찾으러 간다 — 없으면 없다고 둔다.
    code = clean(str(payload.get("code") or "")) or None
    if code:
        _check_code_free(db, workspace.id, code, except_id=None)
    row = SpecDocument(
        workspace_id=workspace.id,
        code=code,
        title=clean(str(payload["title"])),
        revision=clean(str(payload.get("revision") or "")) or None,
        pages=clean(str(payload.get("pages") or "")) or None,
        is_excerpt=bool(payload.get("is_excerpt")),
        source_path=clean(str(payload.get("source_path") or "")) or None,
        note=payload.get("note") or None,
        # **누가 넣었는지 줄에 남긴다.** 사람이 등록한 것과 구별이 안 되면, 검토하는
        # 사람이 무엇을 더 봐야 하는지 모른다.
        submitted_via=get_actor_token(),
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
    if "code" in changes:
        code = clean(str(changes["code"] or "")) or None
        if code:
            _check_code_free(db, row.workspace_id, code, except_id=row.id)
        row.code = code
    if "title" in changes and changes["title"] is not None:
        row.title = clean(str(changes["title"]))
    if "revision" in changes:
        row.revision = clean(str(changes["revision"] or "")) or None
    if "pages" in changes:
        row.pages = clean(str(changes["pages"] or "")) or None
    if "is_excerpt" in changes and changes["is_excerpt"] is not None:
        row.is_excerpt = bool(changes["is_excerpt"])
    if "source_path" in changes:
        row.source_path = clean(str(changes["source_path"] or "")) or None
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
            f"이 규격서를 참조하는 신뢰성 시험 {linked}건 있음. 연결 해제 후 삭제 가능.",
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


def revisions_of(db: Session, document_id: uuid.UUID) -> list[SpecDocumentRevisionOut]:
    """개정 이력 — **나중 판이 먼저.** 읽는 사람이 찾는 것은 대개 최신판이다."""
    rows = list(
        db.scalars(
            select(SpecDocumentRevision)
            .where(SpecDocumentRevision.document_id == document_id)
            .order_by(
                SpecDocumentRevision.sort_order.desc(),
                SpecDocumentRevision.label.desc(),
            )
        )
    )
    if not rows:
        return []
    latest = rows[0]
    # **이 개정을 아직 안 본 시험 수.** 개정이 올라와도 확정은 그대로 두므로(사람이 고른
    # 규칙), 이 수가 곧 「남은 일」 이다. 최신판에만 센다 — 지나간 판의 밀린 수는 이제
    # 아무도 안 본다.
    stale = _stale_count(db, document_id, latest.id)
    return [
        SpecDocumentRevisionOut(
            id=one.id,
            label=one.label,
            issued_on=one.issued_on,
            summary=one.summary,
            sort_order=one.sort_order,
            submitted_via=one.submitted_via,
            stale_test_count=stale if one.id == latest.id else 0,
            created_at=one.created_at,
        )
        for one in rows
    ]


def _stale_count(db: Session, document_id: uuid.UUID, revision_id: uuid.UUID) -> int:
    """그 문서를 가리키면서 **이 개정을 아직 안 본** 시험 수."""
    return int(
        db.scalar(
            select(func.count())
            .select_from(ReliabilityTest)
            .where(
                ReliabilityTest.deleted_at.is_(None),
                ReliabilityTest.id.in_(
                    select(AttributeValue.reliability_test_id).where(
                        AttributeValue.ref_document_id == document_id
                    )
                ),
                or_(
                    ReliabilityTest.reviewed_revision_id.is_(None),
                    ReliabilityTest.reviewed_revision_id != revision_id,
                ),
            )
        )
        or 0
    )


def revision_of(db: Session, revision_id: uuid.UUID) -> SpecDocumentRevision:
    row = db.get(SpecDocumentRevision, revision_id)
    if row is None:
        raise NotFound("TSC-DOCS-0008", "해당 규격서 판을 찾을 수 없음.")
    return row


def add_revision(
    db: Session, user: User, document_id: uuid.UUID, payload: dict[str, Any]
) -> SpecDocumentRevision:
    """개정 한 줄을 쌓는다.

    **딸린 시험을 후보로 내리지 않는다.** 수십 건이 한꺼번에 내려가면 그날 일이 멈추고,
    멈춘 일은 미뤄진다 — 미뤄진 확인은 안 한 확인과 같다. 대신 그 시험들에 「이 개정을
    아직 안 봤다」 는 표가 붙고(`reviewed_revision_id` 가 이 개정이 아닌 것), 사람이 본
    것부터 표가 떨어진다.

    그래서 `summary` 가 중요하다 — 「오타 수정」 이면 딸린 시험을 다시 볼 이유가 없고,
    「시험 온도 상향」 이면 전부 다시 봐야 한다. 그 판단을 사람이 하려면 무엇이 바뀌었는지가
    줄에 있어야 한다.
    """
    document = get(db, document_id)
    require_editable(db, user, document_id)
    label = clean(str(payload["label"]))
    if not label:
        raise AppError("TSC-DOCS-0006", "판 이름 입력 필요.")
    clash = db.scalar(
        select(SpecDocumentRevision).where(
            SpecDocumentRevision.document_id == document_id,
            func.lower(SpecDocumentRevision.label) == label.lower(),
        )
    )
    if clash is not None:
        raise Conflict("TSC-DOCS-0007", f"이미 있는 판: {clash.label}")
    order = payload.get("sort_order")
    if order is None:
        # 비우면 **지금 있는 것 다음 자리.** 날짜만으로는 못 가른다 — 날짜 없는 개정이 있다.
        highest = db.scalar(
            select(func.max(SpecDocumentRevision.sort_order)).where(
                SpecDocumentRevision.document_id == document_id
            )
        )
        order = int(highest or 0) + 10
    row = SpecDocumentRevision(
        document_id=document_id,
        label=label,
        issued_on=payload.get("issued_on"),
        summary=payload.get("summary") or None,
        sort_order=int(order),
        submitted_via=get_actor_token(),
        created_by_id=user.id,
    )
    db.add(row)
    # 문서의 「지금 판」 도 따라 올린다 — 두 자리가 갈리면 목록과 상세가 다른 말을 한다.
    if int(order) >= int(
        db.scalar(
            select(func.max(SpecDocumentRevision.sort_order)).where(
                SpecDocumentRevision.document_id == document_id
            )
        )
        or 0
    ):
        document.revision = label
    audit.record(
        db,
        action=audit.SPEC_DOCUMENT_REVISED,
        actor=user,
        target_table="spec_document_revisions",
        target_id=row.id,
        target_label=f"{document.code or document.title} · {label}",
        workspace_id=document.workspace_id,
    )
    db.commit()
    db.refresh(row)
    return row


def mark_reviewed(
    db: Session, user: User, test_id: uuid.UUID, revision_id: uuid.UUID | None
) -> None:
    """이 시험을 **어느 개정까지 봤다**고 적는다. `None` 이면 표를 도로 붙인다.

    **사람만 한다** — 기계가 「봤다」 고 적으면 사람의 확인이 이름만 남는다. 확정과 같은
    규칙이다(ADR 0009).
    """
    from app.modules.reliability import services as reliability

    test = reliability.get(db, test_id)
    reliability.require_editable(db, user, test_id)
    reliability._human_only(test, "개정 확인")
    if revision_id is not None:
        found = db.get(SpecDocumentRevision, revision_id)
        if found is None:
            raise NotFound("TSC-DOCS-0008", "해당 개정을 찾을 수 없음.")
    test.reviewed_revision_id = revision_id
    db.commit()

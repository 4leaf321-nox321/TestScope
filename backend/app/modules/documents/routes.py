"""사내 규격서 라우터 — 부서가 만든 시험 문서. 읽기는 누구나, 쓰기는 그 부서의 관리자."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.documents import services
from app.modules.documents.schemas import (
    SpecDocumentCreateRequest,
    SpecDocumentOut,
    SpecDocumentUpdateRequest,
)
from app.shared.auth import current_user

router = APIRouter(prefix="/spec-documents", tags=["documents"])


@router.get("", response_model=list[SpecDocumentOut])
def list_spec_documents(
    workspace: str | None = Query(default=None, max_length=64),
    q: str | None = Query(default=None, max_length=200),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[SpecDocumentOut]:
    """사내 규격서 — **공개 규격(`/methods`)과 다른 표다.** 부서가 만들고 부서가 고친다.

    줄마다 붙은 파일 수와 **이 문서를 가리키는 신뢰성 시험 수**가 온다. 0 이면 아무도
    안 쓰는 문서다.
    """
    return services.list_documents(db, user, workspace=workspace, query=q)


@router.post("", response_model=SpecDocumentOut, status_code=201)
def create_spec_document(
    payload: SpecDocumentCreateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> SpecDocumentOut:
    """등록 — 그 부서의 관리자 또는 시스템 관리자. 파일은 만든 뒤에 첨부로 붙인다
    (`POST /attachments` · `target="spec_document"`)."""
    row = services.create(db, user, payload.model_dump())
    return services.document_out(db, user, row)


@router.get("/{document_id}", response_model=SpecDocumentOut)
def read_spec_document(
    document_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> SpecDocumentOut:
    return services.document_out(db, user, services.get(db, document_id))


@router.patch("/{document_id}", response_model=SpecDocumentOut)
def update_spec_document(
    document_id: uuid.UUID,
    payload: SpecDocumentUpdateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> SpecDocumentOut:
    """부분 수정. **판(`revision`)을 고치는 것이 개정이다** — 줄을 새로 만들지 않는다.
    걸어 둔 신뢰성 시험의 링크가 안 끊긴다."""
    row = services.update(db, user, document_id, payload.model_dump(exclude_unset=True))
    return services.document_out(db, user, row)


@router.delete("/{document_id}", status_code=204)
def delete_spec_document(
    document_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    """지우지 않고 `deleted_at` 만 채운다. **걸려 있는 시험이 있으면 409.**"""
    services.delete(db, user, document_id)

"""시험법 라우터."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.methods import services
from app.modules.methods.schemas import (
    MethodCreateRequest,
    MethodOut,
    MethodUpdateRequest,
    RequirementOut,
    RequirementUpsertRequest,
)
from app.shared.auth import current_user
from app.shared.pagination import MAX_LIMIT, Page, clamp_limit

router = APIRouter(prefix="/methods", tags=["methods"])


@router.get("", response_model=Page[MethodOut])
def list_methods(
    q: str | None = Query(default=None, max_length=200),
    test_item: uuid.UUID | None = Query(default=None),
    include_superseded: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Page[MethodOut]:
    return services.list_methods(
        db,
        user,
        query=q,
        test_item_term_id=test_item,
        include_superseded=include_superseded,
        limit=clamp_limit(limit),
        offset=offset,
    )


@router.post("", response_model=MethodOut, status_code=201)
def create_method(
    payload: MethodCreateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> MethodOut:
    row = services.create(db, user, payload.model_dump())
    return services.method_out(db, row, user)


@router.get("/{method_id}", response_model=MethodOut)
def read_method(
    method_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> MethodOut:
    return services.method_out(db, services.get_method(db, user, method_id), user)


@router.patch("/{method_id}", response_model=MethodOut)
def update_method(
    method_id: uuid.UUID,
    payload: MethodUpdateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> MethodOut:
    row = services.update(db, user, method_id, payload.model_dump(exclude_unset=True))
    return services.method_out(db, row, user)


@router.delete("/{method_id}", status_code=204)
def delete_method(
    method_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    services.delete(db, user, method_id)


@router.put("/{method_id}/requirements", response_model=RequirementOut)
def upsert_requirement(
    method_id: uuid.UUID,
    payload: RequirementUpsertRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> RequirementOut:
    """요구 조건 하나를 넣거나 덮어쓴다.

    PUT 인 이유: 같은 조건이 둘이면 어느 쪽이 맞는지 알 수 없으므로, 이 자원은
    조건 키마다 하나뿐인 한 벌이다.
    """
    return services.upsert_requirement(db, user, method_id, payload.model_dump())


@router.delete("/{method_id}/requirements/{requirement_id}", status_code=204)
def delete_requirement(
    method_id: uuid.UUID,
    requirement_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    services.delete_requirement(db, user, method_id, requirement_id)

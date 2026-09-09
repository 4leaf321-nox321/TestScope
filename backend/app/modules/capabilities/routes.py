"""역량 라우터.

목록이 **장비 아래**에 있다. 역량은 홀로 서는 자원이 아니라 장비의 능력이고,
그래서 목록을 부르는 자리도 장비다.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.capabilities import services
from app.modules.capabilities.schemas import (
    CapabilityCreateRequest,
    CapabilityOut,
    CapabilityUpdateRequest,
    LimitOut,
    LimitUpsertRequest,
)
from app.shared.auth import current_user

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


@router.get("", response_model=list[CapabilityOut])
def list_capabilities(
    equipment_id: uuid.UUID = Query(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[CapabilityOut]:
    return services.list_for_equipment(db, user, equipment_id)


@router.post("", response_model=CapabilityOut, status_code=201)
def create_capability(
    payload: CapabilityCreateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> CapabilityOut:
    row = services.create(db, user, payload.model_dump())
    return services.capability_out(db, row, user)


@router.patch("/{capability_id}", response_model=CapabilityOut)
def update_capability(
    capability_id: uuid.UUID,
    payload: CapabilityUpdateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> CapabilityOut:
    row = services.update(db, user, capability_id, payload.model_dump(exclude_unset=True))
    return services.capability_out(db, row, user)


@router.delete("/{capability_id}", status_code=204)
def delete_capability(
    capability_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    services.delete(db, user, capability_id)


@router.put("/{capability_id}/limits", response_model=LimitOut)
def upsert_limit(
    capability_id: uuid.UUID,
    payload: LimitUpsertRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> LimitOut:
    return services.upsert_limit(db, user, capability_id, payload.model_dump())


@router.delete("/{capability_id}/limits/{limit_id}", status_code=204)
def delete_limit(
    capability_id: uuid.UUID,
    limit_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    services.delete_limit(db, user, capability_id, limit_id)

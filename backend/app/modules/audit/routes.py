"""변경 이력 라우터.

**만들기·고치기·지우기가 없다.** 고칠 수 있으면 감사가 아니다 — 쓰는 길은
shared/audit.record 하나뿐이고 그것은 도메인 코드가 부른다.
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.audit.models import AccessLog, AuditEntry
from app.modules.audit.schemas import AccessLogOut, AuditEntryOut
from app.shared.auth import current_user, require_system_admin
from app.shared.errors import Forbidden
from app.shared.pagination import MAX_LIMIT, Page, clamp_limit
from app.shared.permissions import is_any_manager
from app.shared.request_context import CONFIRMED_CLIENT

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/entries", response_model=Page[AuditEntryOut])
def list_entries(
    action: str | None = Query(default=None, max_length=60),
    target_table: str | None = Query(default=None, max_length=60),
    target_id: uuid.UUID | None = Query(default=None),
    channel: Literal["screen", "mcp", "confirmed"] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Page[AuditEntryOut]:
    """무엇이 바뀌었는가.

    부서 관리자도 본다 — 자기 부서의 장비가 왜 폐기됐는지 물을 사람은 시스템
    관리자가 아니라 그 부서다.

    `target_id` 는 **그 대상 하나의 이력**(「이 시험을 누가 언제 확정했나」). `channel` 은
    통로 — `screen`(화면) · `mcp`(AI 혼자, 증표 없이) · `confirmed`(AI 화면의 확인 창에서
    사람이 수락, ADR 0013). 사람이 정한 것과 AI 가 혼자 한 것을 갈라 보는 물음이 실제로 온다.
    """
    if not is_any_manager(db, user):
        raise Forbidden("TSC-AUDIT-0001", "부서 관리자만 조회 가능.")

    stmt = select(AuditEntry)
    if action:
        stmt = stmt.where(AuditEntry.action == action)
    if target_table:
        stmt = stmt.where(AuditEntry.target_table == target_table)
    if target_id is not None:
        stmt = stmt.where(AuditEntry.target_id == target_id)
    if channel == "confirmed":
        stmt = stmt.where(AuditEntry.actor_client == CONFIRMED_CLIENT)
    elif channel == "mcp":
        # 토큰으로 들어왔는데 확인 증표가 없던 것 — `X-Client` 는 누구나 적으니 토큰으로 본다.
        stmt = stmt.where(
            AuditEntry.actor_token.is_not(None),
            AuditEntry.actor_client.is_distinct_from(CONFIRMED_CLIENT),
        )
    elif channel == "screen":
        stmt = stmt.where(AuditEntry.actor_token.is_(None))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(AuditEntry.created_at.desc()).limit(limit).offset(offset))
    return Page(
        items=[AuditEntryOut.model_validate(row) for row in rows],
        total=total,
        limit=clamp_limit(limit),
        offset=offset,
    )


@router.get("/access", response_model=Page[AccessLogOut])
def list_access(
    limit: int = Query(default=50, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> Page[AccessLogOut]:
    """누가 언제 무엇을 호출했는가 — **사용자 지원용**이다.

    감사와 목적이 달라서 화면도 권한도 다르다. 이쪽은 시스템 관리자만 본다:
    남의 활동 이력이라 부서 관리자에게까지 열 이유가 없다.
    """
    stmt = select(AccessLog, User).outerjoin(User, User.id == AccessLog.user_id)
    total = db.scalar(select(func.count()).select_from(AccessLog)) or 0
    rows = db.execute(
        stmt.order_by(AccessLog.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return Page(
        items=[
            AccessLogOut(
                id=log.id,
                user_label=actor.display_name if actor else None,
                action=log.action,
                path=log.path,
                method=log.method,
                status_code=log.status_code,
                request_id=log.request_id,
                client_ip=log.client_ip,
                created_at=log.created_at,
            )
            for log, actor in rows
        ],
        total=total,
        limit=clamp_limit(limit),
        offset=offset,
    )

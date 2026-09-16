"""부서 라우터.

/options 만 인증 없이 열려 있다 — 가입 신청 화면에서 희망 부서를 골라야 하는데,
그 화면은 로그인 전이다. 이름과 주소만 나가고 멤버 수나 내부 식별자는 안 담는다.
"""

from __future__ import annotations

import csv
import io
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.workspaces import imports, services
from app.modules.workspaces.schemas import (
    MemberAddRequest,
    MemberOut,
    MemberRoleRequest,
    WorkspaceCreateRequest,
    WorkspaceImportRequest,
    WorkspaceImportResult,
    WorkspaceImportRowOut,
    WorkspaceMoveRequest,
    WorkspaceOption,
    WorkspaceOut,
    WorkspaceReferenceOut,
    WorkspaceReorderRequest,
    WorkspaceUpdateRequest,
)
from app.shared.auth import current_user, require_system_admin
from app.shared.errors import Conflict, Forbidden
from app.shared.permissions import require_manager, require_member, workspace_by_slug

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("/options", response_model=list[WorkspaceOption])
def options(db: Session = Depends(get_db)) -> list[WorkspaceOption]:
    """가입 신청 화면용. 로그인 전에 부르므로 인증이 없다."""
    return services.options(db)


@router.get("/reliability-listed", response_model=list[WorkspaceOption])
def reliability_listed(
    _: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[WorkspaceOption]:
    """사이드바 「신뢰성 시험」 아래에 설 부서들 — 관리자가 「부서 정보」 에서 고른 것.

    소속과 무관하게 로그인한 누구나 본다. 이 시스템의 물음은 부서를 가로지른다.
    """
    return services.reliability_listed(db)


@router.get("", response_model=list[WorkspaceOut])
def list_workspaces(
    all_workspaces: bool = Query(default=False, alias="all"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[WorkspaceOut]:
    if all_workspaces and not user.is_system_admin:
        raise Forbidden(
            "TSC-WORKSPACES-0013", "전체 부서 목록은 시스템 관리자만 볼 수 있습니다."
        )
    return services.list_for(db, user, all_workspaces=all_workspaces)


@router.get("/export.csv", include_in_schema=False)
def export_csv(
    _: User = Depends(require_system_admin), db: Session = Depends(get_db)
) -> Response:
    """부서 정보를 CSV 로 — **ReportArchive 와 같은 형식.**

    컬럼도 순서도 저쪽 `/api/workspaces/export.csv` 와 같다. 한쪽으로만 들어가는
    것은 호환이 아니라 이사다.

    ## BOM 을 붙인다

    안 붙이면 Excel 이 한글을 깬다. 저쪽과 같은 규약이다.

    ## 스키마에 안 싣는다

    `include_in_schema=False` — 생성되는 프론트 타입에 CSV 응답이 끼면 그 타입은
    `unknown` 이 되고, 그것을 쓰는 화면이 타입 검사를 통과해 버린다. 이 경로는
    파일을 내려받는 자리지 데이터를 읽는 자리가 아니다.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(services.EXPORT_HEADER)
    writer.writerows(services.export_rows(db))

    # 파일 이름은 둘로 낸다 — ASCII 는 옛 브라우저용, UTF-8 은 한글 이름용.
    # f-string 을 안 쓴다: 이 값에는 따옴표가 섞여 있어 읽기 어려워진다.
    disposition = "attachment; filename=\"workspaces.csv\"; filename*=UTF-8''" + quote(
        "부서정보.csv"
    )
    return Response(
        content="﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": disposition},
    )


@router.post("/import", response_model=WorkspaceImportResult)
def import_workspaces(
    payload: WorkspaceImportRequest,
    dry_run: bool = Query(default=True),
    admin: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> WorkspaceImportResult:
    """ReportArchive 「부서 정보 내보내기」 를 붙여넣어 조직도를 들인다.

    `dry_run=true`(기본)면 **무엇이 만들어질지만** 준다 — 조직도는 한 번 잘못 들어가면 지우기
    어렵다(부서마다 장비가 매달린다). 계획을 보고 사람이 `dry_run=false` 로 다시 부른다.
    둘은 같은 코드로 판정한다. 적용은 한 트랜잭션이다 — 절반만 들어간 조직도는 없느니만 못하다.
    이미 있는 부서는 건너뛴다(`update_existing` 으로 덮음). 공개 정책(external_view_default)은
    다른 물음이라 옮기지 않는다.
    """
    rows = imports.parse(payload.text)
    if dry_run:
        planned = imports.plan(db, rows, update_existing=payload.update_existing)
    else:
        planned = imports.apply(
            db, rows, creator=admin, update_existing=payload.update_existing
        )
        try:
            db.commit()
        except IntegrityError as exc:
            # 미리보기와 commit 사이에 다른 관리자가 같은 slug 를 만들었다 — 500 대신 말한다.
            db.rollback()
            raise Conflict(
                "TSC-WORKSPACES-0021",
                "같은 순간에 다른 관리자가 부서를 만들고 있습니다. 다시 시도해 주세요.",
            ) from exc
    return WorkspaceImportResult(
        rows=[
            WorkspaceImportRowOut(
                line=one.line,
                slug=one.slug,
                name=one.name,
                parent_slug=one.parent_slug,
                action=one.action,
                reason=one.reason,
            )
            for one in planned
        ],
        created=sum(1 for one in planned if one.action == "create"),
        updated=sum(1 for one in planned if one.action == "update"),
        skipped=sum(1 for one in planned if one.action.startswith("skip")),
        errors=sum(1 for one in planned if one.action == "error"),
        dry_run=dry_run,
    )


@router.post("", response_model=WorkspaceOut, status_code=201)
def create_workspace(
    payload: WorkspaceCreateRequest,
    admin: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> WorkspaceOut:
    workspace = services.create(
        db,
        slug=payload.slug,
        name=payload.name,
        creator=admin,
        parent_slug=payload.parent_slug,
    )
    return services.workspace_out(db, workspace, admin)


@router.patch("/{slug}", response_model=WorkspaceOut)
def update_workspace(
    slug: str,
    payload: WorkspaceUpdateRequest,
    admin: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> WorkspaceOut:
    workspace = services.update(
        db,
        slug=slug,
        name=payload.name,
        is_active=payload.is_active,
        restricted=payload.restricted,
        reliability_listed=payload.reliability_listed,
    )
    return services.workspace_out(db, workspace, admin)


@router.post("/{slug}/move", response_model=WorkspaceOut)
def move_workspace(
    slug: str,
    payload: WorkspaceMoveRequest,
    admin: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> WorkspaceOut:
    workspace = services.move(db, slug=slug, parent_slug=payload.parent_slug)
    return services.workspace_out(db, workspace, admin)


@router.post("/{slug}/reorder", response_model=WorkspaceOut)
def reorder_workspace(
    slug: str,
    payload: WorkspaceReorderRequest,
    admin: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> WorkspaceOut:
    workspace = services.reorder(db, slug=slug, direction=payload.direction)
    return services.workspace_out(db, workspace, admin)


@router.get("/{slug}/references", response_model=list[WorkspaceReferenceOut])
def workspace_references(
    slug: str,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> list[WorkspaceReferenceOut]:
    """무엇이 이 부서를 가리키는가. 삭제 확인 화면이 부른다."""
    return services.references(db, slug=slug)


@router.delete("/{slug}", status_code=204)
def delete_workspace(
    slug: str,
    admin: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> Response:
    services.delete(db, slug=slug, actor=admin)
    return Response(status_code=204)


# --- 멤버 --------------------------------------------------------------------


@router.get("/{slug}/members", response_model=list[MemberOut])
def list_members(
    slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[MemberOut]:
    workspace = workspace_by_slug(db, slug)
    # 조회는 멤버면 된다 — 같은 부서 사람이 누군지는 알아야 일이 된다.
    require_member(db, workspace=workspace, user=user)
    return services.members(db, workspace=workspace)


@router.post("/{slug}/members", response_model=MemberOut, status_code=201)
def add_member(
    slug: str,
    payload: MemberAddRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> MemberOut:
    workspace = workspace_by_slug(db, slug)
    require_manager(db, workspace=workspace, user=user)
    return services.add_member(db, workspace=workspace, email=payload.email, role=payload.role)


@router.patch("/{slug}/members/{user_id}", response_model=MemberOut)
def set_member_role(
    slug: str,
    user_id: uuid.UUID,
    payload: MemberRoleRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> MemberOut:
    workspace = workspace_by_slug(db, slug)
    require_manager(db, workspace=workspace, user=user)
    return services.set_role(db, workspace=workspace, user_id=user_id, role=payload.role)


@router.delete("/{slug}/members/{user_id}", status_code=204)
def remove_member(
    slug: str,
    user_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    workspace = workspace_by_slug(db, slug)
    require_manager(db, workspace=workspace, user=user)
    services.remove_member(db, workspace=workspace, user_id=user_id)

"""시험법 라우터."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.equipment.schemas import ImportColumn
from app.modules.methods import imports, services
from app.modules.methods.schemas import (
    MethodCreateRequest,
    MethodOut,
    MethodUpdateRequest,
    RequirementImportRequest,
    RequirementImportResult,
    RequirementOut,
    RequirementUpsertRequest,
)
from app.shared.auth import current_user
from app.shared.pagination import MAX_LIMIT, Page, clamp_limit

router = APIRouter(prefix="/methods", tags=["methods"])


@router.get("", response_model=Page[MethodOut])
def list_methods(
    q: str | None = Query(default=None, max_length=200),
    test_item: str | None = Query(default=None),
    requirement: str | None = Query(default=None, pattern="^none$"),
    cited: str | None = Query(default=None, pattern="^none$"),
    used: str | None = Query(default=None, pattern="^owned$"),
    include_superseded: bool = Query(default=False),
    attr: list[str] = Query(default_factory=list, max_length=10),
    limit: int = Query(default=50, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Page[MethodOut]:
    """규격 목록.

    `attr` 은 **속성 값으로 거른다** — 여러 번 주면 모두 만족해야 한다(`attr=<키><연산><값>`,
    연산은 `>=` `<=` `>` `<` `=` `!=` `~`(포함) `*`(적혀 있기만 하면)). 왼쪽은 속성 정의의
    `key` 다 — 이름은 관리자가 고치면 바뀌고, 그때 저장해 둔 주소가 조용히 빈 답을 낸다.
    """
    return services.list_methods(
        db,
        user,
        query=q,
        requirement=requirement,
        # `test_item=none` 은 「안 정해진 것」 이고, 그 밖은 값 id 다.
        test_item_term_id=(
            uuid.UUID(test_item) if test_item and test_item != "none" else None
        ),
        test_item="none" if test_item == "none" else None,
        cited=cited,
        used=used,
        include_superseded=include_superseded,
        attrs=attr,
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


@router.get("/requirements/import/columns", response_model=list[ImportColumn])
def requirement_import_columns(_: User = Depends(current_user)) -> list[dict[str, Any]]:
    """요구 조건 표의 열. `/{method_id}` 보다 **먼저 선언한다.**"""
    return imports.columns()


@router.get("/requirements/import/template")
def requirement_import_template(_: User = Depends(current_user)) -> Response:
    """서식(CSV). 보기 줄은 **실제 규격의 값**이다 — 지어낸 숫자는 그대로 들어온다."""
    return Response(
        content=imports.template_csv().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="testscope-requirements.csv"'},
    )


@router.post("/requirements/import", response_model=RequirementImportResult)
def import_requirements(
    payload: RequirementImportRequest,
    dry_run: bool = Query(default=True),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> RequirementImportResult:
    """규격서를 보고 적은 요구 조건 표를 통째로 받는다.

    장비 대장 반입과 같은 규칙이다 — 붙여넣기(파일이 아니다) · `dry_run=true` 가 기본이라
    먼저 판정만 보고, 사람이 확인하면 `dry_run=false` 로 같은 글자를 다시 보낸다 · 문제
    없는 줄은 넣고 문제 있는 줄은 남긴다 · 넣기로 한 것은 전부 되거나 전부 안 되거나.

    규격은 표기 차이를 무시하고 찾는다(「JIS K7210」 = 「JIS K 7210」). 판이 여럿이면 현행
    하나가 있을 때만 그것으로 잡고, 아니면 판 열을 요구한다 — 옛 판에 조건을 적으면 검색이
    옛 규격으로 장비를 좁힌다.
    """
    return imports.run(db, user, payload.text, dry_run=dry_run)


@router.get("/{method_id}", response_model=MethodOut)
def read_method(
    method_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> MethodOut:
    return services.method_out(
        db, services.get_method(db, user, method_id), user, with_series=True
    )


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

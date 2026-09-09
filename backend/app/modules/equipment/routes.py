"""장비 라우터."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.equipment import catalog, services, specs
from app.modules.equipment.schemas import (
    CalibrationCreateRequest,
    CalibrationOut,
    EquipmentCreateRequest,
    EquipmentModelCreateRequest,
    EquipmentModelOut,
    EquipmentModelUpdateRequest,
    EquipmentOut,
    EquipmentSeriesCreateRequest,
    EquipmentSeriesOut,
    EquipmentSeriesUpdateRequest,
    EquipmentUpdateRequest,
    ModelCapabilityCreateRequest,
    ModelCapabilityOut,
    ModelLimitOut,
    ModelLimitUpsertRequest,
    ModelSpecSaveResult,
    ModelSpecSheetOut,
    ModelSpecValueUpsertRequest,
    SeriesRelationCreateRequest,
    SeriesRelationOut,
    SpecSourceOut,
)
from app.shared.auth import current_user, require_system_admin
from app.shared.pagination import MAX_LIMIT, Page, clamp_limit
from app.shared.permissions import get_equipment

router = APIRouter(prefix="/equipment", tags=["equipment"])


@router.get("", response_model=Page[EquipmentOut])
def list_equipment(
    q: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None),
    workspace: str | None = Query(default=None),
    model_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Page[EquipmentOut]:
    return services.list_equipment(
        db,
        user,
        query=q,
        status=status,
        workspace_slug=workspace,
        model_id=model_id,
        limit=clamp_limit(limit),
        offset=offset,
    )


@router.post("", response_model=EquipmentOut, status_code=201)
def create_equipment(
    payload: EquipmentCreateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> EquipmentOut:
    row = services.create(db, user, payload.model_dump())
    return services.equipment_out(db, row, user)


@router.get("/{equipment_id}", response_model=EquipmentOut)
def read_equipment(
    equipment_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> EquipmentOut:
    return services.equipment_out(db, get_equipment(db, user, equipment_id), user)


@router.patch("/{equipment_id}", response_model=EquipmentOut)
def update_equipment(
    equipment_id: uuid.UUID,
    payload: EquipmentUpdateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> EquipmentOut:
    # **exclude_unset 이 핵심이다.** 안 쓰면 "안 보낸 것" 과 "비운 것" 이 둘 다
    # None 으로 와서, 상태 하나 바꿀 때마다 담당자와 위치가 지워진다.
    row = services.update(db, user, equipment_id, payload.model_dump(exclude_unset=True))
    return services.equipment_out(db, row, user)


@router.delete("/{equipment_id}", status_code=204)
def delete_equipment(
    equipment_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    services.delete(db, user, equipment_id)


@router.get("/{equipment_id}/calibrations", response_model=list[CalibrationOut])
def list_calibrations(
    equipment_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[CalibrationOut]:
    return services.calibrations(db, user, equipment_id)


@router.post("/{equipment_id}/calibrations", response_model=CalibrationOut, status_code=201)
def add_calibration(
    equipment_id: uuid.UUID,
    payload: CalibrationCreateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> CalibrationOut:
    return services.add_calibration(db, user, equipment_id, payload.model_dump())


# --- 카탈로그: 계열 -----------------------------------------------------------
#
# **읽기는 누구나 한다.** 장비를 등록하는 사람이 기종을 골라야 하고, 아직 없는
# 계열을 「사면 무엇이 되나」 보는 것도 여기다. 고치는 것은 시스템 관리자다 —
# 전사 공용이라 한 부서가 고치면 다른 부서가 가리키던 뜻이 바뀐다.

series_router = APIRouter(prefix="/equipment-series", tags=["catalog"])


@series_router.get("", response_model=Page[EquipmentSeriesOut])
def list_series(
    q: str | None = Query(default=None, max_length=200),
    kind: str | None = Query(default=None),
    category_term_id: uuid.UUID | None = Query(default=None),
    owned: bool = Query(default=False),
    issue: str | None = Query(default=None, pattern="^(capabilities)$"),
    limit: int = Query(default=50, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Page[EquipmentSeriesOut]:
    # owned·issue 는 홈의 「남은 일」 이 거는 손잡이다 — 전부를 채우라고 하면
    # 아무도 안 채운다.
    return catalog.list_series(
        db,
        user,
        query=q,
        kind=kind,
        category_term_id=category_term_id,
        owned=owned,
        issue=issue,
        limit=clamp_limit(limit),
        offset=offset,
    )


@series_router.post("", response_model=EquipmentSeriesOut, status_code=201)
def create_series(
    payload: EquipmentSeriesCreateRequest,
    admin: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> EquipmentSeriesOut:
    """계열을 만든다.

    **먼저 `POST /api/resolve` 로 찾는다.** 같은 계열이 두 줄로 갈리면 보유 장비가
    어느 쪽을 가리켰는지에 따라 검색 결과가 나뉜다.

    이미 있으면 409 와 함께 `details.series_id` 가 온다 — **409 는 실패가 아니라
    답이다.** 그 id 를 그대로 쓰면 된다.

    제조사·분류는 id 대신 이름(`maker`·`category`)으로 줘도 된다. 하나로 정해지지
    않으면 400 과 후보 목록이 온다 — **고르지 말고 사람에게 물어라.**
    """
    row = catalog.create_series(db, admin, payload.model_dump())
    return catalog.series_out(db, row, admin)


@series_router.get("/{series_id}", response_model=EquipmentSeriesOut)
def read_series(
    series_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> EquipmentSeriesOut:
    return catalog.series_out(db, catalog.get_series(db, series_id), user)


@series_router.patch("/{series_id}", response_model=EquipmentSeriesOut)
def update_series(
    series_id: uuid.UUID,
    payload: EquipmentSeriesUpdateRequest,
    admin: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> EquipmentSeriesOut:
    row = catalog.update_series(db, series_id, payload.model_dump(exclude_unset=True))
    return catalog.series_out(db, row, admin)


@series_router.delete("/{series_id}", status_code=204)
def delete_series(
    series_id: uuid.UUID,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> None:
    catalog.delete_series(db, series_id)


@series_router.post(
    "/{series_id}/capabilities", response_model=ModelCapabilityOut, status_code=201
)
def add_series_capability(
    series_id: uuid.UUID,
    payload: ModelCapabilityCreateRequest,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> ModelCapabilityOut:
    """이 계열이 무슨 시험을 하나.

    **조건 수치는 여기 적지 않는다.** 여기 적는 조건은 계열 전체가 만족하는 것만이고,
    기종마다 갈리는 값은 그 기종의 사양(`PUT /equipment-models/{id}/specs`)에 적으면
    보유 장비를 만들 때 합쳐진다.

    시험 항목은 **닫힌 축**이라 없는 이름은 안 받는다 — 오타가 값이 되면 그 계열의
    장비는 영영 검색에 안 걸린다. `test_item`(이름)으로 주면 별칭까지 본다.
    """
    return catalog.add_capability(db, series_id, payload.model_dump())


@series_router.delete("/{series_id}/capabilities/{capability_id}", status_code=204)
def delete_series_capability(
    series_id: uuid.UUID,
    capability_id: uuid.UUID,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> None:
    catalog.delete_capability(db, series_id, capability_id)


@series_router.put(
    "/{series_id}/capabilities/{capability_id}/limits", response_model=ModelLimitOut
)
def upsert_series_limit(
    series_id: uuid.UUID,
    capability_id: uuid.UUID,
    payload: ModelLimitUpsertRequest,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> ModelLimitOut:
    return catalog.upsert_limit(db, series_id, capability_id, payload.model_dump())


@series_router.delete(
    "/{series_id}/capabilities/{capability_id}/limits/{limit_id}", status_code=204
)
def delete_series_limit(
    series_id: uuid.UUID,
    capability_id: uuid.UUID,
    limit_id: uuid.UUID,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> None:
    catalog.delete_limit(db, series_id, capability_id, limit_id)


@series_router.post(
    "/{series_id}/relations", response_model=SeriesRelationOut, status_code=201
)
def add_series_relation(
    series_id: uuid.UUID,
    payload: SeriesRelationCreateRequest,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> SeriesRelationOut:
    return catalog.add_relation(db, series_id, payload.model_dump())


@series_router.delete("/{series_id}/relations/{relation_id}", status_code=204)
def delete_series_relation(
    series_id: uuid.UUID,
    relation_id: uuid.UUID,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> None:
    catalog.delete_relation(db, series_id, relation_id)


# --- 카탈로그: 기종 -----------------------------------------------------------
#
# 보유 장비가 가리키는 것은 기종이다. 역량은 계열이 갖고, **조건은 이 기종의
# 사양이 좁힌다**(ADR 0006).

catalog_router = APIRouter(prefix="/equipment-models", tags=["catalog"])


@catalog_router.get("", response_model=Page[EquipmentModelOut])
def list_models(
    q: str | None = Query(default=None, max_length=200),
    series_id: uuid.UUID | None = Query(default=None),
    owned: bool = Query(default=False),
    issue: str | None = Query(default=None, pattern="^(specs|uncertain)$"),
    limit: int = Query(default=50, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Page[EquipmentModelOut]:
    return catalog.list_models(
        db,
        user,
        query=q,
        series_id=series_id,
        owned=owned,
        issue=issue,
        limit=clamp_limit(limit),
        offset=offset,
    )


@catalog_router.post("", response_model=EquipmentModelOut, status_code=201)
def create_model(
    payload: EquipmentModelCreateRequest,
    admin: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> EquipmentModelOut:
    """기종을 만든다. **계열이 먼저 있어야 한다.**

    보유 장비가 가리키는 것은 계열이 아니라 이 기종이다 — 수치가 여기서 갈리기
    때문이다(한 계열 안에서 하중이 중앙값 60배 차이 난다).

    `series_id` 대신 `series`(계열 이름)를 줘도 된다. 만들기 전에 resolve 로 찾고,
    없으면 계열을 먼저 만든다. **비슷한 계열에 끼워 넣지 마라.**
    """
    row = catalog.create_model(db, admin, payload.model_dump())
    return catalog.model_out(db, row, admin)


@catalog_router.get("/{model_id}", response_model=EquipmentModelOut)
def read_model(
    model_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> EquipmentModelOut:
    return catalog.model_out(db, catalog.get_model(db, model_id), user)


@catalog_router.patch("/{model_id}", response_model=EquipmentModelOut)
def update_model(
    model_id: uuid.UUID,
    payload: EquipmentModelUpdateRequest,
    admin: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> EquipmentModelOut:
    row = catalog.update_model(db, model_id, payload.model_dump(exclude_unset=True))
    return catalog.model_out(db, row, admin)


@catalog_router.delete("/{model_id}", status_code=204)
def delete_model(
    model_id: uuid.UUID,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> None:
    catalog.delete_model(db, model_id)


# --- 기종 사양 ---------------------------------------------------------------
#
# 값이 **적힌 것만** 온다. 빈 칸 목록은 `/spec-definitions?category_term_id=…` 다 —
# 화면이 둘을 겹쳐 그린다(ADR 0005).


@catalog_router.get("/{model_id}/specs", response_model=ModelSpecSheetOut)
def read_model_specs(
    model_id: uuid.UUID,
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ModelSpecSheetOut:
    return specs.sheet(db, catalog.get_model(db, model_id))


@catalog_router.put("/{model_id}/specs", response_model=ModelSpecSaveResult)
def upsert_model_spec(
    model_id: uuid.UUID,
    payload: ModelSpecValueUpsertRequest,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> ModelSpecSaveResult:
    """사양 한 칸을 넣거나 덮어쓴다.

    **정의의 종류에 맞는 칸만 채운다** — 수치는 `num_value`, 구간은 `num_min`/
    `num_max`, 고른 값과 문장은 `text_value`, 참거짓은 `bool_value`. 틀린 칸에 담긴
    값은 저장은 되지만 화면이 못 그리고, 그때 사람은 「저장이 안 됐다」 고 말한다.

    쓸 수 있는 칸은 `GET /api/spec-definitions?category_term_id=…` 가 준다.
    **없는 사양은 만들지 말고 보류하라** — 정의를 늘리는 것은 사람의 판단이다.

    응답의 `search_axis` 가 채워져 있으면 이 값은 앞으로 이 기종으로 등록하는 장비의
    역량 조건이 된다. `existing_units` 는 **이미 등록된 대수**이고, 그들에게는
    반영되지 않는다.
    """
    value, axis, units = specs.upsert(
        db, catalog.get_model(db, model_id), payload.model_dump()
    )
    return ModelSpecSaveResult(value=value, search_axis=axis, existing_units=units)


@catalog_router.delete("/{model_id}/specs/{definition_id}", status_code=204)
def delete_model_spec(
    model_id: uuid.UUID,
    definition_id: uuid.UUID,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> None:
    specs.delete(db, catalog.get_model(db, model_id), definition_id)


# --- 사양 출처 ---------------------------------------------------------------
#
# 어느 카탈로그에서 옮겨 적은 값인지 대는 자리. **읽기만 있다** — 문서는 반입
# 스크립트가 등록한다. 손으로 만들게 두면 같은 PDF 가 여러 줄로 갈린다.

sources_router = APIRouter(prefix="/spec-sources", tags=["specs"])


@sources_router.get("", response_model=Page[SpecSourceOut])
def list_spec_sources(
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Page[SpecSourceOut]:
    return catalog.list_sources(db, query=q, limit=clamp_limit(limit), offset=offset)

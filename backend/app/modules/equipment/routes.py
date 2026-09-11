"""장비 라우터."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.equipment import (
    catalog,
    equipment_specs,
    imports,
    services,
    specs,
)
from app.modules.equipment.schemas import (
    CalibrationCreateRequest,
    CalibrationOut,
    CatalogFilterOptionsOut,
    EquipmentCreateRequest,
    EquipmentFilterOptionsOut,
    EquipmentImportRequest,
    EquipmentImportResult,
    EquipmentModelCreateRequest,
    EquipmentModelOut,
    EquipmentModelRow,
    EquipmentModelUpdateRequest,
    EquipmentOut,
    EquipmentSeriesCreateRequest,
    EquipmentSeriesOut,
    EquipmentSeriesRow,
    EquipmentSeriesUpdateRequest,
    EquipmentSpecSaveRequest,
    EquipmentSpecSaveResult,
    EquipmentSpecSheetOut,
    EquipmentUpdateRequest,
    ImportColumn,
    ModelLimitOut,
    ModelLimitUpsertRequest,
    ModelSpecSaveResult,
    ModelSpecSheetOut,
    ModelSpecValueUpsertRequest,
    SeriesRelationCreateRequest,
    SeriesRelationOut,
    SeriesTestItemCreateRequest,
    SeriesTestItemOut,
    SpecSourceOut,
)
from app.shared.auth import current_user, require_system_admin
from app.shared.pagination import MAX_LIMIT, Page, clamp_limit
from app.shared.permissions import get_equipment, require_owner_edit

router = APIRouter(prefix="/equipment", tags=["equipment"])


@router.get("", response_model=Page[EquipmentOut])
def list_equipment(
    q: str | None = Query(default=None, max_length=200),
    asset_no: str | None = Query(default=None, max_length=50),
    name: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None),
    workspace: str | None = Query(default=None),
    model_id: uuid.UUID | None = Query(default=None),
    category_term_id: uuid.UUID | None = Query(default=None),
    site_term_id: uuid.UUID | None = Query(default=None),
    test_item_term_id: uuid.UUID | None = Query(default=None),
    test_item: str | None = Query(default=None, pattern="^none$"),
    catalog: str | None = Query(default=None, pattern="^unlinked$"),
    calibration: str | None = Query(
        default=None, pattern="^(required|exempt|missing|overdue)$"
    ),
    shared_use: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Page[EquipmentOut]:
    """보유 장비 목록. **거르기는 서버가 한다.**

    화면이 한 쪽을 받아 놓고 거르면 상한을 넘는 순간 나머지가 조용히 빠지고, 그때
    목록은 「그 조건에 맞는 장비가 이것뿐」 이라고 거짓말한다.

    `calibration` 은 넷이다 — `required` 대상 전부 · `exempt` 대상 아님 ·
    `missing` 대상인데 이력 없음 · `overdue` 기한 지남.

    `q` 는 자산번호와 이름을 함께 보고, `asset_no`·`name` 은 **그 열만** 본다 —
    화면은 열마다 거르므로 뒤엣것을 쓴다.

    `test_item=none` 은 **시험 항목이 하나도 없는 장비**다. 홈의 「남은 일」 이 그 줄로
    링크하므로, 세는 조건과 여기 거르는 조건이 같아야 한다.

    `catalog=unlinked` 는 **기종을 안 고른 장비**다. 그 기종이 카탈로그에 없어서 비운
    경우가 실제로 있고, 시스템 관리자가 이 목록을 보고 카탈로그를 채운다.
    """
    return services.list_equipment(
        db,
        user,
        query=q,
        asset_no=asset_no,
        name=name,
        status=status,
        workspace_slug=workspace,
        model_id=model_id,
        category_term_id=category_term_id,
        site_term_id=site_term_id,
        test_item_term_id=test_item_term_id,
        test_item=test_item,
        catalog=catalog,
        calibration=calibration,
        shared_use=shared_use,
        limit=clamp_limit(limit),
        offset=offset,
    )


@router.get("/filter-options", response_model=EquipmentFilterOptionsOut)
def equipment_filter_options(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> EquipmentFilterOptionsOut:
    """목록의 열마다 **고를 수 있는 값**과 그 수.

    기준정보 전체가 아니라 **지금 목록에 있는 값만** 준다 — 골라도 0 건인 선택지가
    섞이면 사람은 거르기를 안 믿게 된다.

    `/{equipment_id}` 보다 **먼저 선언한다.** 뒤에 두면 `filter-options` 가 장비 id 로
    읽혀 422 가 난다.
    """
    return services.filter_options(db, user)


@router.get("/import/columns", response_model=list[ImportColumn])
def equipment_import_columns(_: User = Depends(current_user)) -> list[ImportColumn]:
    """반입 표의 열. **화면이 자기 목록을 따로 들지 않게** 서버가 준다.

    두 벌로 두면 열을 하나 더한 날 한쪽만 고쳐지고, 그때 사람이 채운 칸이 조용히
    버려진다 — 그리고 그 손실은 넣은 사람 눈에 안 보인다.

    `/{equipment_id}` 보다 **먼저 선언한다.**
    """
    return imports.columns()


@router.get("/import/template")
def equipment_import_template(_: User = Depends(current_user)) -> Response:
    """대장 서식(CSV)을 내려받는다.

    **빈 서식만 주지 않는다** — 보기 한 줄을 함께 넣는다. 「공용여부에 뭘 적나」 를
    사람이 물어야 하면 그 서식은 절반만 쓸모가 있다.

    `/{equipment_id}` 보다 **먼저 선언한다.**
    """
    return Response(
        content=imports.template_csv().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="testscope-equipment.csv"'},
    )


@router.post("/import", response_model=EquipmentImportResult)
def import_equipment(
    payload: EquipmentImportRequest,
    dry_run: bool = Query(default=True),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> EquipmentImportResult:
    """부서 대장을 통째로 받는다. **엑셀에서 복사해 붙여넣은 글자다.**

    ## 왜 파일이 아닌가

    문서 보안(DRM)이 걸린 환경에서는 파일을 올릴 수 없다. 서식을 내려받는 것은 되는데
    그 파일을 다시 고르는 것이 막힌다 — 실제로 그랬다. 붙여넣기는 DRM 이 막지 못한다.

    엑셀이 클립보드에 넣는 것은 **탭으로 나뉜 글자**이고 서식 파일은 쉼표다. 둘 다
    받는다 — 첫 줄에 탭이 있으면 탭으로 본다.

    ## 두 걸음이다

    `dry_run=true`(기본)이면 **아무것도 저장하지 않고** 줄마다 판정만 돌려준다.
    300줄 중 틀린 12줄을 넣기 전에 알아야 하고, 그 12줄이 파일의 몇 번째 줄인지
    말해 줘야 사람이 엑셀에서 찾는다.

    화면은 같은 글자를 두 번 보낸다: 먼저 미리보기, 사람이 확인하면 `dry_run=false`.

    ## 넣을 수 있는 줄은 넣는다

    문제가 있는 줄 때문에 멀쩡한 줄까지 막으면, 300줄 중 12줄이 틀렸을 때 288줄을
    다시 보내야 한다. 줄마다 `imported` 가 실제로 들어갔는지를 말해 주므로, 부르는
    쪽은 **못 들어간 줄만 고쳐서 다시 보내면 된다.**

    **넣기로 한 것은 전부 되거나 전부 안 되거나다.** 문제 없는 줄들을 한 트랜잭션에
    담고, 그중 하나라도 막히면 통째로 되돌린다(그때 `created` 는 0 이다).

    ## 이름으로 적는다

    부서·거점·장비유형·기종을 **이름으로** 적는다. 후보가 여럿이면 고르지 않고
    거절한다(ADR 0003) — 비슷한 기종에 끼워 넣으면 그 장비의 하중·온도가 남의 것이
    되고, 검색은 그 남의 수치로 「됩니다」 라고 답한다.

    기준정보에 없는 거점·분류는 **여기서 만들지 않는다.** 반입이 값을 만들면 오타가
    그대로 축이 되고, 「본사」 와 「본사 」 가 서로 다른 거점이 된다.
    """
    return imports.run(db, user, payload.text, dry_run=dry_run)


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


# --- 개체 사양 (카탈로그 위에 덮는 실측) --------------------------------------
#
# **기종 사양과 겹쳐서 준다.** 개체는 다른 값만 갖고, 나머지는 기종 것이 그대로
# 보인다 — 복사해 두면 카탈로그가 개정돼도 안 따라오고, 어느 값이 실측인지 구별이
# 사라진다.


@router.get("/{equipment_id}/specs", response_model=EquipmentSpecSheetOut)
def read_equipment_specs(
    equipment_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> EquipmentSpecSheetOut:
    """이 장비의 사양 — 한 줄에 **카탈로그 값과 실측이 함께** 온다.

    화면은 둘을 겹쳐 그린다: 「실측 300 kN (사양서 250 kN)」. 하나만 보여 주면 사람은
    그 수치가 잰 값인지 사양서 값인지 알 수 없고, 그 둘은 믿는 정도가 다르다.
    """
    return equipment_specs.sheet(db, get_equipment(db, user, equipment_id))


@router.put("/{equipment_id}/specs", response_model=EquipmentSpecSaveResult)
def upsert_equipment_spec(
    equipment_id: uuid.UUID,
    payload: EquipmentSpecSaveRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> EquipmentSpecSaveResult:
    """실측 한 칸을 넣거나 덮어쓴다. **이 장비의 값이지 기종의 값이 아니다.**

    기종 사양과 같은 규칙으로 검증한다 — 정의의 종류에 맞는 칸만 채운다.

    응답의 `condition_label` 이 채워져 있으면 그 값은 검색이 묻는 축이고, `reflected`
    가 참이면 이 장비의 시험 조건이 실제로 갱신됐다는 뜻이다. **손으로 고쳐 둔 조건은
    안 덮는다** — 그때는 거짓으로 온다.
    """
    row = get_equipment(db, user, equipment_id)
    require_owner_edit(
        db, user, row.owner_workspace_id, what="장비", code="TSC-EQUIPMENT-0002"
    )
    value, label, reflected = equipment_specs.upsert(db, row, payload.model_dump(), user)
    return EquipmentSpecSaveResult(value=value, condition_label=label, reflected=reflected)


@router.delete("/{equipment_id}/specs/{definition_id}", status_code=204)
def delete_equipment_spec(
    equipment_id: uuid.UUID,
    definition_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    """실측을 지운다 — 그 칸은 다시 카탈로그 값으로 보인다.

    **따라 들어간 시험 조건은 안 지운다.** 이미 이 장비의 것이고, 그 사이에 사람이
    고쳐 뒀을 수 있다.
    """
    row = get_equipment(db, user, equipment_id)
    require_owner_edit(
        db, user, row.owner_workspace_id, what="장비", code="TSC-EQUIPMENT-0002"
    )
    equipment_specs.delete(db, row, definition_id)


# --- 카탈로그: 계열 -----------------------------------------------------------
#
# **읽기는 누구나 한다.** 장비를 등록하는 사람이 기종을 골라야 하고, 아직 없는
# 계열을 「사면 무엇이 되나」 보는 것도 여기다. 고치는 것은 시스템 관리자다 —
# 전사 공용이라 한 부서가 고치면 다른 부서가 가리키던 뜻이 바뀐다.

series_router = APIRouter(prefix="/equipment-series", tags=["catalog"])


@series_router.get("", response_model=Page[EquipmentSeriesRow])
def list_series(
    q: str | None = Query(default=None, max_length=200),
    name: str | None = Query(default=None, max_length=200),
    kind: str | None = Query(default=None),
    category_term_id: uuid.UUID | None = Query(default=None),
    maker_term_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    models: str | None = Query(default=None, pattern="^none$"),
    test_item: str | None = Query(default=None, pattern="^none$"),
    owned: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Page[EquipmentSeriesRow]:
    """계열 목록. **거르는 것은 서버다.**

    화면이 한 쪽을 받아 놓고 거르면 상한을 넘는 순간 나머지가 조용히 빠지고, 그때
    목록은 「그 조건에 맞는 계열이 이것뿐」 이라고 거짓말한다.

    `q` 는 계열명·한글명·제조사를 함께 보고, `name` 은 **그 열만** 본다 — 화면은
    열마다 거르므로 뒤엣것을 쓴다.

    `test_item=none` 은 시험 항목이 하나도 안 적힌 계열, `models=none` 은 기종이
    없는 계열이다. 둘 다 홈의 「남은 일」 이 링크하는 자리라, 세는 조건과 여기
    거르는 조건이 같아야 한다.
    """
    return catalog.list_series(
        db,
        user,
        query=q,
        name=name,
        kind=kind,
        category_term_id=category_term_id,
        maker_term_id=maker_term_id,
        status=status,
        models=models,
        test_item=test_item,
        owned=owned,
        limit=clamp_limit(limit),
        offset=offset,
    )


@series_router.get("/filter-options", response_model=CatalogFilterOptionsOut)
def series_filter_options(
    _: User = Depends(current_user), db: Session = Depends(get_db)
) -> CatalogFilterOptionsOut:
    """계열 목록의 열마다 **고를 수 있는 값**과 그 수.

    기준정보 전체가 아니라 **카탈로그에 실제로 쓰인 값만** 준다.

    `/{series_id}` 보다 **먼저 선언한다.** 뒤에 두면 `filter-options` 가 계열 id 로
    읽혀 422 가 난다.
    """
    return catalog.series_filter_options(db)


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
    "/{series_id}/test-items", response_model=SeriesTestItemOut, status_code=201
)
def add_series_test_item(
    series_id: uuid.UUID,
    payload: SeriesTestItemCreateRequest,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> SeriesTestItemOut:
    """이 계열이 무슨 시험을 하나.

    **조건 수치는 여기 적지 않는다.** 여기 적는 조건은 계열 전체가 만족하는 것만이고,
    기종마다 갈리는 값은 그 기종의 사양(`PUT /equipment-models/{id}/specs`)에 적으면
    보유 장비를 만들 때 합쳐진다.

    시험 항목은 **닫힌 축**이라 없는 이름은 안 받는다 — 오타가 값이 되면 그 계열의
    장비는 영영 검색에 안 걸린다. `test_item`(이름)으로 주면 별칭까지 본다.
    """
    return catalog.add_test_item(db, series_id, payload.model_dump())


@series_router.delete("/{series_id}/test-items/{equipment_test_item_id}", status_code=204)
def delete_series_test_item(
    series_id: uuid.UUID,
    equipment_test_item_id: uuid.UUID,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> None:
    catalog.delete_test_item(db, series_id, equipment_test_item_id)


@series_router.put(
    "/{series_id}/test-items/{equipment_test_item_id}/limits", response_model=ModelLimitOut
)
def upsert_series_limit(
    series_id: uuid.UUID,
    equipment_test_item_id: uuid.UUID,
    payload: ModelLimitUpsertRequest,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> ModelLimitOut:
    return catalog.upsert_limit(db, series_id, equipment_test_item_id, payload.model_dump())


@series_router.delete(
    "/{series_id}/test-items/{equipment_test_item_id}/limits/{limit_id}", status_code=204
)
def delete_series_limit(
    series_id: uuid.UUID,
    equipment_test_item_id: uuid.UUID,
    limit_id: uuid.UUID,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> None:
    catalog.delete_limit(db, series_id, equipment_test_item_id, limit_id)


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
# 보유 장비가 가리키는 것은 기종이다. 시험 항목은 계열이 갖고, **조건은 이 기종의
# 사양이 좁힌다**(ADR 0006).

catalog_router = APIRouter(prefix="/equipment-models", tags=["catalog"])


@catalog_router.get("", response_model=Page[EquipmentModelRow])
def list_models(
    q: str | None = Query(default=None, max_length=200),
    name: str | None = Query(default=None, max_length=200),
    series_id: uuid.UUID | None = Query(default=None),
    maker_term_id: uuid.UUID | None = Query(default=None),
    category_term_id: uuid.UUID | None = Query(default=None),
    spec: str | None = Query(default=None, pattern="^(none|uncertain)$"),
    test_item: str | None = Query(default=None, pattern="^none$"),
    owned: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Page[EquipmentModelRow]:
    """기종 목록. **거르는 것은 서버다.**

    `q` 는 기종명·계열명·제조사를 함께 보고, `name` 은 **그 열만** 본다.

    제조사·분류는 계열이 갖는 값이라(ADR 0006) 계열을 거쳐 거른다.

    `spec=none` 은 사양이 하나도 안 적힌 기종, `spec=uncertain` 은 반입이 원본을
    잘못 읽었을 수 있다고 표시한 기종이다 — 홈의 「남은 일」 이 그 둘로 링크한다.
    """
    return catalog.list_models(
        db,
        user,
        query=q,
        name=name,
        series_id=series_id,
        maker_term_id=maker_term_id,
        category_term_id=category_term_id,
        spec=spec,
        test_item=test_item,
        owned=owned,
        limit=clamp_limit(limit),
        offset=offset,
    )


@catalog_router.get("/filter-options", response_model=CatalogFilterOptionsOut)
def model_filter_options(
    _: User = Depends(current_user), db: Session = Depends(get_db)
) -> CatalogFilterOptionsOut:
    """기종 목록의 열마다 **고를 수 있는 값**과 그 수.

    `/{model_id}` 보다 **먼저 선언한다.**
    """
    return catalog.model_filter_options(db)


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
    시험 조건이 된다. `existing_units` 는 **이미 등록된 대수**이고, 그들에게는
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

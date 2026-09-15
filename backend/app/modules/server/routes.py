"""서버·시스템 관리 라우터.

**한 화면이 답해야 하는 물음이 셋이다**: 지금 뭐가 깔렸나, DB 는 맞춰져 있나,
남은 일이 뭔가. 셋을 따로 두면 아무도 다 보지 않는다.
"""

from __future__ import annotations

import shutil
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app import schema_version, version
from app.config import get_settings
from app.database import engine, get_db
from app.jobs import queue
from app.modules.accounts.models import User
from app.modules.equipment.models import (
    Equipment,
    EquipmentCalibration,
    EquipmentModel,
    EquipmentSeries,
    ModelSpecValue,
)
from app.modules.methods.models import MethodRequirement, TestMethod
from app.modules.server import catalog_state
from app.modules.server.schemas import (
    CalibrationDueOut,
    CatalogStateOut,
    DiskOut,
    JobsStateOut,
    MaintenanceItemOut,
    SemanticStateOut,
    ServerStatusOut,
    TableCountOut,
)
from app.modules.test_items.models import (
    EquipmentTestItem,
    SeriesTestItem,
    SeriesTestItemMethod,
)
from app.modules.vocabulary.models import VocabularyTerm
from app.shared import embeddings, semantic
from app.shared.auth import current_user, require_system_admin

router = APIRouter(prefix="/server", tags=["server"])

#: 프로세스가 언제 떴나. 재시작을 눈으로 확인할 수 있는 유일한 값이다.
STARTED_AT = datetime.now(UTC)

#: 교정 만료를 "곧" 으로 볼 기간. 60일이면 외부 교정 업체를 잡을 시간이 된다.
CALIBRATION_HORIZON_DAYS = 60


def _safe_url(url: str) -> str:
    """비밀번호를 지운 접속 문자열. **화면에 그대로 뜨는 값이다.**"""
    if "@" not in url:
        return url
    head, tail = url.rsplit("@", 1)
    if ":" in head:
        scheme_user = head.rsplit(":", 1)[0]
        return f"{scheme_user}:***@{tail}"
    return f"{head}@{tail}"


def _catalog(db: Session) -> CatalogStateOut:
    """정본의 지문과 마지막 반입을 견준다."""
    source = catalog_state.fingerprint()
    imported = catalog_state.last_import(db)
    return CatalogStateOut(
        available=source is not None,
        digest=source.digest if source else None,
        objects=source.objects if source else None,
        imported_at=imported.imported_at if imported else None,
        imported_digest=imported.digest if imported else None,
        imported_objects=imported.objects if imported else None,
        never=source is not None and imported is None,
        behind=(
            source is not None and imported is not None and imported.digest != source.digest
        ),
    )


def _count(db: Session, model: type[Any], *conditions: ColumnElement[bool]) -> int:
    stmt = select(func.count()).select_from(model)
    for condition in conditions:
        stmt = stmt.where(condition)
    return db.scalar(stmt) or 0


@router.get("/status", response_model=ServerStatusOut)
def status(
    _: User = Depends(require_system_admin), db: Session = Depends(get_db)
) -> ServerStatusOut:
    settings = get_settings()
    head = schema_version.code_head()
    current = schema_version.db_revision(engine)

    disk: DiskOut | None = None
    try:
        usage = shutil.disk_usage(settings.filestore_dir.parent)
        disk = DiskOut(
            path=str(settings.filestore_dir.parent),
            total_bytes=usage.total,
            free_bytes=usage.free,
            used_percent=round((usage.total - usage.free) / usage.total * 100, 1),
        )
    except OSError:
        # 경로가 없거나 권한이 없다. **화면은 떠야 한다** — 디스크를 못 읽는다고
        # 서버 상태 전체를 못 보면 정작 원인을 볼 데가 없어진다.
        disk = None

    # 의미 검색 — 엔진은 실제로 한 번 재 본다(Ollama 가 죽어 있는지는 그래야만 안다).
    engine_state = embeddings.health()
    counted = semantic.stats(db)
    semantic_state = SemanticStateOut(
        backend=str(engine_state["backend"]),
        engine_ready=bool(engine_state["ready"]),
        engine_note=str(engine_state["note"]) if engine_state.get("note") else None,
        extension=bool(counted.get("extension")),
        table=semantic.table_ready(db),
        chunks=int(counted["chunks"]),
        kinds=dict(counted["kinds"]),
    )
    jobs = queue.summary(db)
    jobs_state = JobsStateOut(
        queued=jobs.get("queued", 0),
        running=jobs.get("running", 0),
        done=jobs.get("done", 0),
        failed=jobs.get("failed", 0),
    )

    return ServerStatusOut(
        version=version.current(),
        app_env=settings.app_env,
        database_url_safe=_safe_url(settings.database_url),
        schema_head=head,
        schema_current=current,
        schema_behind=bool(head and current and head != current),
        disk=disk,
        counts=[
            TableCountOut(
                label="장비", count=_count(db, Equipment, Equipment.deleted_at.is_(None))
            ),
            TableCountOut(label="시험 항목", count=_count(db, EquipmentTestItem)),
            TableCountOut(
                label="시험법", count=_count(db, TestMethod, TestMethod.deleted_at.is_(None))
            ),
            TableCountOut(label="기준정보 값", count=_count(db, VocabularyTerm)),
            TableCountOut(label="계정", count=_count(db, User, User.deleted_at.is_(None))),
        ],
        started_at=STARTED_AT,
        catalog=_catalog(db),
        semantic=semantic_state,
        jobs=jobs_state,
    )


@router.get("/catalog", response_model=CatalogStateOut)
def catalog(_: User = Depends(current_user), db: Session = Depends(get_db)) -> CatalogStateOut:
    """카탈로그 신선도만. **누구나 본다** — 「카탈로그에 없다」 고 답하기 전에 반입이
    정본보다 뒤졌는지 볼 수 있어야 한다. 관리자 화면(`/status`)은 DB 주소까지 실어 관리자만."""
    return _catalog(db)


@router.get("/maintenance", response_model=list[MaintenanceItemOut])
def maintenance(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[MaintenanceItemOut]:
    """남은 일. **홈이 이것을 보여 준다.**

    관리 화면에 들어가야만 보이는 목록은 아무도 안 본다 — 승인 대기가 며칠씩
    방치되고, 시험 항목이 안 적힌 장비는 영영 안 적힌다.

    **0 건인 항목은 안 내보낸다.** 다 0 인 목록을 매일 보면 사람은 그 자리를
    아예 안 읽게 되고, 그때 진짜 하나가 떠도 눈에 안 들어온다.
    """
    today = date.today()
    items: list[MaintenanceItemOut] = []

    registered = select(EquipmentTestItem.equipment_id).distinct()
    unregistered = _count(
        db,
        Equipment,
        Equipment.deleted_at.is_(None),
        Equipment.id.not_in(registered),
    )
    if unregistered:
        items.append(
            MaintenanceItemOut(
                key="equipment_without_test_item",
                label="시험 항목이 안 적힌 장비",
                count=unregistered,
                link="/equipment?test_item=none",
                # **경고다.** 이 장비들은 검색에 절대 안 걸린다 — 시스템이 있는데도
                # 사람들은 여전히 전화를 돌리게 된다.
                severity="warning",
            )
        )

    # **카탈로그에 안 이어진 장비.** 기종이 없으면 시험 항목이 복사될 자리가 없다.
    #
    # 「카탈로그에 그 기종이 없더라」 는 사실이 반입한 사람 머릿속에만 남으면, 그 장비는
    # 대장에 있는 채로 영영 안 찾아진다. 여기 세워 두면 시스템 관리자가 카탈로그를
    # 채우거나, 부서가 손으로 시험 항목을 붙인다.
    unlinked = _count(
        db,
        Equipment,
        Equipment.deleted_at.is_(None),
        Equipment.model_id.is_(None),
    )
    if unlinked:
        items.append(
            MaintenanceItemOut(
                key="equipment_without_model",
                label="카탈로그에 안 이어진 장비",
                count=unlinked,
                link="/equipment?catalog=unlinked",
                severity="info",
            )
        )

    # **대상인데 한 번도 안 받은 장비.** 이력이 없다는 사실만으로는 대상이 아닌
    # 장비와 구별되지 않아서, 여기 안 세우면 빠뜨린 장비가 영영 안 보인다.
    calibrated = select(EquipmentCalibration.equipment_id).distinct()
    never = _count(
        db,
        Equipment,
        Equipment.deleted_at.is_(None),
        Equipment.calibration_required.is_(True),
        Equipment.id.not_in(calibrated),
    )
    if never:
        items.append(
            MaintenanceItemOut(
                key="calibration_never",
                label="교정 대상인데 이력이 없는 장비",
                count=never,
                link="/equipment?calibration=missing",
                severity="warning",
            )
        )

    # **우리가 인용한 규격 중 조건이 안 적힌 것.** 카탈로그가 인용한 453건 전부를
    # 세지 않는다 — 우리 계열이 실제로 가리키는 것만 세야 목록에 끝이 있다.
    cited = select(SeriesTestItemMethod.method_id).distinct()
    without = _count(
        db,
        TestMethod,
        TestMethod.deleted_at.is_(None),
        TestMethod.id.in_(cited),
        TestMethod.id.not_in(select(MethodRequirement.method_id).distinct()),
    )
    if without:
        items.append(
            MaintenanceItemOut(
                key="method_without_requirement",
                label="요구 조건이 안 적힌 인용 규격",
                count=without,
                link="/methods?requirement=none",
                # **경고가 아니다.** 규격의 조건은 원문을 봐야 아는 것이라 하루에
                # 되는 일이 아니다 — 다만 이것이 비어 있으면 검색은 조건으로
                # 좁히지 못하고, 사람이 매번 직접 입력해야 한다.
                severity="info",
            )
        )

    undecided = _count(
        db, TestMethod, TestMethod.deleted_at.is_(None), TestMethod.test_item_term_id.is_(None)
    )
    if undecided:
        items.append(
            MaintenanceItemOut(
                key="method_without_test_item",
                label="어느 시험의 규격인지 안 정해진 시험법",
                count=undecided,
                link="/methods?test_item=none",
                # 카탈로그가 인용했는데 만능시험기처럼 시험이 여럿인 계열이라 반입이 못
                # 정한 것. 정하는 순간 인용한 계열에 붙는다 — 그 전까지는 「가능 장비 없음」
                # 으로 서서 못 하는 시험처럼 읽힌다.
                severity="info",
            )
        )

    overdue = _count(
        db,
        EquipmentCalibration,
        EquipmentCalibration.next_due_on.is_not(None),
        EquipmentCalibration.next_due_on < today,
    )
    if overdue:
        items.append(
            MaintenanceItemOut(
                key="calibration_overdue",
                label="교정 기한이 지난 장비",
                count=overdue,
                link="/equipment?calibration=overdue",
                severity="warning",
            )
        )

    # --- 카탈로그의 빈 자리 ------------------------------------------------
    #
    # **우리가 가진 것만 센다.** 카탈로그에는 아직 안 산 계열도 들어 있고, 그것까지
    # 채우라고 하면 목록에 끝이 없어 보여서 아무도 시작하지 않는다.
    owned_models = select(Equipment.model_id).where(
        Equipment.model_id.is_not(None), Equipment.deleted_at.is_(None)
    )

    no_specs = _count(
        db,
        EquipmentModel,
        EquipmentModel.deleted_at.is_(None),
        EquipmentModel.id.in_(owned_models),
        EquipmentModel.id.not_in(select(ModelSpecValue.model_id).distinct()),
    )
    if no_specs:
        items.append(
            MaintenanceItemOut(
                key="model_without_specs",
                label="사양이 안 적힌 보유 기종",
                count=no_specs,
                link="/catalog/equipment-models?owned=1&spec=none",
                # 사양이 없으면 다음에 그 기종으로 등록하는 장비가 조건 없이
                # 복사된다 — 검색은 그것을 「모름」 으로 답한다(ADR 0003).
                severity="info",
            )
        )

    no_test_items = _count(
        db,
        EquipmentSeries,
        EquipmentSeries.deleted_at.is_(None),
        EquipmentSeries.id.in_(
            select(EquipmentModel.series_id).where(EquipmentModel.id.in_(owned_models))
        ),
        EquipmentSeries.id.not_in(select(SeriesTestItem.series_id).distinct()),
    )
    if no_test_items:
        items.append(
            MaintenanceItemOut(
                key="series_without_test_item",
                label="시험 항목이 안 적힌 보유 계열",
                count=no_test_items,
                link="/catalog/equipment-series?owned=1&test_item=none",
                # **경고다.** 이 계열의 기종으로 장비를 등록해도 복사될 시험 항목이 없다.
                severity="warning",
            )
        )

    unverified = _count(
        db,
        EquipmentModel,
        EquipmentModel.deleted_at.is_(None),
        EquipmentModel.id.in_(owned_models),
        EquipmentModel.spec_note.ilike("%원본 확인 필요%"),
    )
    if unverified:
        items.append(
            MaintenanceItemOut(
                key="model_spec_unverified",
                label="원본 확인이 필요한 보유 기종",
                count=unverified,
                link="/catalog/equipment-models?owned=1&spec=uncertain",
                # 반입이 표를 잘못 읽었을 수 있다고 표시한 것. 확인하지 않으면
                # 의심스러운 숫자가 확인된 숫자와 똑같이 앉아 있는다.
                severity="warning",
            )
        )

    if user.is_system_admin:
        # **카탈로그가 정본보다 뒤졌다.** 배포는 파일을 새로 놓지만 반입은 사람이 돌린다 —
        # 안 돌린 사실을 여기 세워 두지 않으면 「카탈로그에 없던데」 가 반입을 안 한
        # 것인지 정본에도 없는 것인지 아무도 구별 못 한다. 돌리는 사람이 관리자라 관리자에게만.
        state = _catalog(db)
        if state.never or state.behind:
            items.append(
                MaintenanceItemOut(
                    key="catalog_behind",
                    label=(
                        "카탈로그가 아직 반입되지 않음"
                        if state.never
                        else "카탈로그 반입이 정본보다 뒤짐"
                    ),
                    count=1,
                    link="/server",
                    severity="warning",
                )
            )

        pending = _count(db, User, User.status == "pending", User.deleted_at.is_(None))
        if pending:
            items.append(
                MaintenanceItemOut(
                    key="accounts_pending",
                    label="가입 승인 대기",
                    count=pending,
                    link="/admin/accounts?status=pending",
                    severity="warning",
                )
            )

    return items


@router.get("/calibrations-due", response_model=list[CalibrationDueOut])
def calibrations_due(
    _: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[CalibrationDueOut]:
    """곧 만료되거나 이미 지난 교정.

    **지난 것을 목록에서 빼지 않는다.** 빼면 만료된 장비가 조용히 계속 쓰이고,
    그것으로 낸 값은 나중에 통째로 못 믿게 된다.
    """
    today = date.today()
    rows = db.execute(
        select(EquipmentCalibration, Equipment)
        .join(Equipment, Equipment.id == EquipmentCalibration.equipment_id)
        .where(
            Equipment.deleted_at.is_(None),
            Equipment.status != "retired",
            EquipmentCalibration.next_due_on.is_not(None),
        )
        .order_by(EquipmentCalibration.next_due_on)
    ).all()

    # 장비마다 **가장 최근 교정 하나**만 본다. 이력을 다 세면 옛 교정의 지난
    # 예정일이 매번 경고로 뜬다 — 이미 다시 받은 장비인데도.
    latest: dict[str, tuple[EquipmentCalibration, Equipment]] = {}
    for calibration, equipment in rows:
        key = str(equipment.id)
        current = latest.get(key)
        if current is None or calibration.calibrated_on > current[0].calibrated_on:
            latest[key] = (calibration, equipment)

    out: list[CalibrationDueOut] = []
    for calibration, equipment in latest.values():
        due = calibration.next_due_on
        if due is None:
            continue
        days = (due - today).days
        if days > CALIBRATION_HORIZON_DAYS:
            continue
        out.append(
            CalibrationDueOut(
                equipment_id=str(equipment.id),
                asset_no=equipment.asset_no,
                name=equipment.name,
                next_due_on=due,
                days_left=days,
            )
        )
    out.sort(key=lambda one: one.days_left)
    return out

"""보유 장비 로직 — **우리가 가진 것.**

모델 카탈로그(제조사가 파는 것)는 `catalog.py` 가 맡는다. 나눈 이유는 ADR 0004.
"""

from __future__ import annotations

import logging
import uuid
from calendar import monthrange
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.equipment import catalog
from app.modules.equipment.models import (
    EQUIPMENT_STATUSES,
    Equipment,
    EquipmentCalibration,
    EquipmentModel,
    EquipmentSeries,
    EquipmentSpecValue,
)
from app.modules.equipment.schemas import (
    CalibrationOut,
    EquipmentFilterOptionsOut,
    EquipmentOut,
    FilterOption,
)
from app.modules.test_items.models import EquipmentTestItem
from app.modules.vocabulary.models import VocabularyTerm
from app.modules.workspaces.models import Workspace
from app.shared import audit
from app.shared.errors import AppError, Conflict
from app.shared.pagination import Page
from app.shared.permissions import (
    get_equipment,
    require_owner_edit,
    resolve_owner_workspace,
    visible_equipment,
)
from app.shared.text import clean

logger = logging.getLogger(__name__)

_WHAT = "장비"
_CODE = "TSC-EQUIPMENT-0002"


def _term_value(db: Session, term_id: uuid.UUID | None) -> str | None:
    if term_id is None:
        return None
    term = db.get(VocabularyTerm, term_id)
    return term.value if term else None


def _test_item_count(db: Session, equipment_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(EquipmentTestItem)
            .where(EquipmentTestItem.equipment_id == equipment_id)
        )
        or 0
    )


def _test_items(db: Session, equipment_id: uuid.UUID) -> list[str]:
    """이 장비가 하는 시험 항목 이름들. **목록 한 줄에서 바로 보여야 한다.**

    시험 항목을 열어 봐야 아는 화면은 「우리가 무슨 시험을 할 수 있나」 에 답하지 못한다 —
    그 물음이 이 시스템이 존재하는 이유다.
    """
    rows = db.scalars(
        select(VocabularyTerm.value)
        .join(EquipmentTestItem, EquipmentTestItem.test_item_term_id == VocabularyTerm.id)
        .where(EquipmentTestItem.equipment_id == equipment_id)
        .order_by(VocabularyTerm.value)
        .distinct()
    )
    return list(rows)


def _category_group(db: Session, term_id: uuid.UUID | None) -> str | None:
    """장비군 — 그 유형의 **최상위 조상.**

    분류 축은 21군 / 87유형의 트리라, 군은 유형에서 따라 나온다. 칸으로 저장하지
    않는 이유: 저장하면 유형만 고친 날 군이 어긋나고, 그 어긋남은 아무 화면에도
    안 보인다.
    """
    seen: set[uuid.UUID] = set()
    term = db.get(VocabularyTerm, term_id) if term_id else None
    while term is not None and term.parent_term_id is not None:
        # 트리가 고리를 이루면 여기서 영원히 돈다. 데이터가 그럴 리 없다고 믿지 않는다.
        if term.id in seen:
            break
        seen.add(term.id)
        parent = db.get(VocabularyTerm, term.parent_term_id)
        if parent is None:
            break
        term = parent
    return term.value if term else None


def _due(db: Session, row: Equipment) -> tuple[date | None, bool, bool]:
    """다음 교정일 · 그것이 계산값인가 · 대상인데 이력이 없나.

    **성적서에 적힌 날이 언제나 이긴다** — 기관이 정한 날이 진실이고, 주기는 우리가
    적어 둔 짐작이다. 성적서에 없을 때만 마지막 교정일 + 주기로 계산하고, 그때는
    계산값임을 함께 말한다: 안 말하면 사람은 그것을 성적서로 읽는다.
    """
    last = db.execute(
        select(EquipmentCalibration.calibrated_on, EquipmentCalibration.next_due_on)
        .where(EquipmentCalibration.equipment_id == row.id)
        .order_by(EquipmentCalibration.calibrated_on.desc())
        .limit(1)
    ).first()
    if last is None:
        # 대상인데 한 번도 안 받았다. **이력이 없다는 사실만으로는 못 가른다** —
        # 대상이 아닌 장비와 빠뜨린 장비가 같아 보인다.
        return None, False, row.calibration_required
    calibrated_on, stated = last
    if stated is not None:
        return stated, False, False
    months = row.calibration_interval_months
    if not row.calibration_required or not months:
        return None, False, False
    # 달을 더한다. 말일 문제는 그 달의 마지막 날로 눕힌다 — 1/31 + 1개월은 2/28 이다.
    total = calibrated_on.month - 1 + months
    year = calibrated_on.year + total // 12
    month = total % 12 + 1
    last_day = monthrange(year, month)[1]
    return date(year, month, min(calibrated_on.day, last_day)), True, False


def _override_count(db: Session, equipment_id: uuid.UUID) -> int:
    """카탈로그 위에 덮어 둔 실측이 몇 칸인가."""
    return (
        db.scalar(
            select(func.count())
            .select_from(EquipmentSpecValue)
            .where(EquipmentSpecValue.equipment_id == equipment_id)
        )
        or 0
    )


def _can_edit(db: Session, user: User, row: Equipment) -> bool:
    """고칠 수 있는가. **판정 로직을 재사용한다** — 화면이 스스로 계산하면
    버튼은 보이는데 누르면 403 인 상태가 생긴다."""
    try:
        require_owner_edit(db, user, row.owner_workspace_id, what=_WHAT, code=_CODE)
    except AppError:
        return False
    return True


def equipment_out(db: Session, row: Equipment, viewer: User) -> EquipmentOut:
    workspace = db.get(Workspace, row.owner_workspace_id) if row.owner_workspace_id else None
    contact = db.get(User, row.contact_user_id) if row.contact_user_id else None
    model = db.get(EquipmentModel, row.model_id) if row.model_id else None
    series = db.get(EquipmentSeries, model.series_id) if model else None
    # **카탈로그가 있으면 카탈로그가 이긴다.** 개체가 적어 둔 글자는 미연결일 때만
    # 쓰이고, 연결하는 순간 서버가 비운다 — 같은 사실이 두 곳에 남으면 안 된다.
    category_term_id = series.category_term_id if series else row.category_term_id
    due_on, due_estimated, due_missing = _due(db, row)
    return EquipmentOut(
        id=row.id,
        asset_no=row.asset_no,
        name=row.name,
        dept_asset_no=row.dept_asset_no,
        model_id=row.model_id,
        model_name=model.name if model else row.model_text,
        series_id=model.series_id if model else None,
        series_name=series.name if series else None,
        category=_term_value(db, category_term_id),
        category_group=_category_group(db, category_term_id),
        manufacturer=(_term_value(db, series.maker_term_id) if series else row.maker_text),
        catalog_linked=model is not None,
        serial_no=row.serial_no,
        workspace_slug=workspace.slug if workspace else None,
        workspace_name=workspace.name if workspace else None,
        shared_use=row.shared_use,
        site=_term_value(db, row.site_term_id),
        location=row.location,
        status=row.status,
        acquired_on=row.acquired_on,
        manufactured_year=row.manufactured_year,
        retired_on=row.retired_on,
        contact_name=contact.display_name if contact else None,
        note=row.note,
        test_item_count=_test_item_count(db, row.id),
        test_items=_test_items(db, row.id),
        calibration_required=row.calibration_required,
        calibration_interval_months=row.calibration_interval_months,
        calibration_due_on=due_on,
        calibration_due_estimated=due_estimated,
        calibration_missing=due_missing,
        spec_override_count=_override_count(db, row.id),
        created_at=row.created_at,
        can_edit=_can_edit(db, viewer, row),
    )


#: 교정으로 거르는 방법들. **「대상 아님」 과 「이력 없음」 은 다른 물음이다** —
#: 하나로 뭉치면 빠뜨린 장비가 대상 아닌 장비 뒤에 숨는다.
CALIBRATION_FILTERS = ("required", "exempt", "missing", "overdue")


def _by_calibration(stmt: Any, how: str) -> Any:
    """교정으로 거른다.

        required  교정 대상 전부
        exempt    대상이 아닌 것
        missing   대상인데 이력이 한 건도 없는 것   ← 「남은 일」 이 거는 자리
        overdue   차기일이 지난 것

    **`missing` 과 `exempt` 를 나눠 두는 이유**: 이력이 없다는 사실만으로는 둘을 못
    가른다. 뭉쳐 두면 빠뜨린 장비가 대상 아닌 장비 뒤에 숨는다.
    """
    calibrated = select(EquipmentCalibration.equipment_id).distinct()
    if how == "required":
        return stmt.where(Equipment.calibration_required.is_(True))
    if how == "exempt":
        return stmt.where(Equipment.calibration_required.is_(False))
    if how == "missing":
        return stmt.where(
            Equipment.calibration_required.is_(True), Equipment.id.not_in(calibrated)
        )
    if how == "overdue":
        overdue = (
            select(EquipmentCalibration.equipment_id)
            .where(
                EquipmentCalibration.next_due_on.is_not(None),
                EquipmentCalibration.next_due_on < date.today(),
            )
            .distinct()
        )
        return stmt.where(Equipment.id.in_(overdue))
    return stmt


def list_equipment(
    db: Session,
    user: User,
    *,
    query: str | None,
    asset_no: str | None = None,
    name: str | None = None,
    status: str | None,
    workspace_slug: str | None,
    model_id: uuid.UUID | None = None,
    category_term_id: uuid.UUID | None = None,
    site_term_id: uuid.UUID | None = None,
    test_item_term_id: uuid.UUID | None = None,
    test_item: str | None = None,
    catalog: str | None = None,
    calibration: str | None = None,
    shared_use: bool | None = None,
    limit: int,
    offset: int,
) -> Page[EquipmentOut]:
    """보유 장비 목록.

    ## 거르기는 **서버가 한다**

    화면이 한 쪽을 받아 놓고 거르면, 상한을 넘는 순간 나머지가 조용히 빠진다 — 그리고
    그때 목록은 「그 조건에 맞는 장비가 이것뿐」 이라고 거짓말한다. 기종 목록에서 같은
    일이 있었다.
    """
    stmt = visible_equipment(db, user)
    if query:
        text = f"%{clean(query)}%"
        # 자산번호와 이름 둘 다 본다 — 사람은 현장에서 라벨의 번호를 치고, 회의
        # 에서는 이름을 친다. **열마다 따로 거를 때는 아래 둘을 쓴다.**
        stmt = stmt.where(Equipment.asset_no.ilike(text) | Equipment.name.ilike(text))
    if asset_no:
        stmt = stmt.where(Equipment.asset_no.ilike(f"%{clean(asset_no)}%"))
    if name:
        stmt = stmt.where(Equipment.name.ilike(f"%{clean(name)}%"))
    if model_id is not None:
        # **서버가 거른다.** 화면이 전체 목록을 받아 걸러 내면, 상한(200)을 넘는
        # 순간 나머지가 조용히 안 보인다 — 그리고 그때 그 기종은 「보유 없음」 이
        # 되어 카탈로그가 거짓말을 한다.
        stmt = stmt.where(Equipment.model_id == model_id)
    if status:
        stmt = stmt.where(Equipment.status == status)
    if site_term_id is not None:
        stmt = stmt.where(Equipment.site_term_id == site_term_id)
    if shared_use is not None:
        stmt = stmt.where(Equipment.shared_use.is_(shared_use))
    if category_term_id is not None:
        # **분류는 두 곳에서 온다.** 기종이 있으면 그 계열이 갖고, 없으면 개체가 직접
        # 가리킨다 — 한쪽만 보면 카탈로그 미연결 장비가 통째로 빠진다.
        in_catalog = select(EquipmentModel.id).where(
            EquipmentModel.series_id.in_(
                select(EquipmentSeries.id).where(
                    EquipmentSeries.category_term_id == category_term_id
                )
            )
        )
        stmt = stmt.where(
            or_(
                Equipment.model_id.in_(in_catalog),
                Equipment.category_term_id == category_term_id,
            )
        )
    if test_item_term_id is not None:
        stmt = stmt.where(
            Equipment.id.in_(
                select(EquipmentTestItem.equipment_id).where(
                    EquipmentTestItem.test_item_term_id == test_item_term_id
                )
            )
        )
    if test_item == "none":
        # **검색에 절대 안 걸리는 장비들.** 홈의 「남은 일」 이 세는 것과 같은 조건이라야
        # 그 줄을 눌러 온 사람이 같은 목록을 본다 — 수와 목록이 어긋나면 둘 다 안 믿는다.
        stmt = stmt.where(
            Equipment.id.not_in(select(EquipmentTestItem.equipment_id).distinct())
        )
    if catalog == "unlinked":
        # **카탈로그에 안 이어진 장비.** 기종이 없으면 시험 항목이 복사될 자리가
        # 없고, 사람이 손으로 채우지 않는 한 그 장비는 검색에 안 걸린다.
        #
        # 그 기종이 카탈로그에 없어서 비운 경우가 실제로 있다(자작 장비도 있다).
        # 시스템 관리자가 이 목록을 보고 카탈로그를 채울 수 있어야 한다 — 안 그러면
        # 「카탈로그에 없더라」 는 사실이 반입한 사람 머릿속에만 남는다.
        stmt = stmt.where(Equipment.model_id.is_(None))
    if calibration:
        stmt = _by_calibration(stmt, calibration)
    if workspace_slug:
        workspace = db.scalar(select(Workspace).where(Workspace.slug == workspace_slug))
        stmt = stmt.where(
            Equipment.owner_workspace_id == (workspace.id if workspace else None)
        )

    # **total 을 함께 준다.** 없으면 화면이 다음 쪽 유무를 알려고 한 건 더 요청하는
    # 편법을 쓰게 되고, 그 편법은 화면마다 달라진다.
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Equipment.asset_no).limit(limit).offset(offset))
    return Page(
        items=[equipment_out(db, row, user) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def owner_workspace(db: Session, user: User, slug: Any) -> uuid.UUID:
    """보유 부서를 정한다. **비울 수 없다.**

    전에는 비우면 「전사 공용」 이었는데, 그러면 공용으로 표시하는 순간 관리 부서를
    잃었다. 공용인지는 `shared_use` 가 따로 말한다 — 두 물음을 한 칸에 담지 않는다.
    """
    owner = resolve_owner_workspace(db, user, slug, what=_WHAT, code=_CODE)
    if owner is None:
        raise AppError(
            "TSC-EQUIPMENT-0008",
            "장비에는 보유 부서가 있어야 합니다. 공용 장비도 관리하는 부서는 하나입니다.",
            status=400,
        )
    return owner


#: 부분 수정에서 **비우면 거절하는** 칸들. 필수인 것을 지우려는 요청은 조용히
#: 성공시키면 안 된다 — DB 가 거절하면 500 이 나가고, 그때 사람은 서버가 고장 났다고
#: 읽는다. 무엇이 왜 안 되는지는 400 으로 말한다.
_NOT_EMPTY = {
    "location": "설치위치",
    "site_term_id": "거점",
    "workspace_slug": "보유 부서",
    "name": "장비명",
}


def _check_not_emptied(changes: dict[str, Any]) -> None:
    for field, label in _NOT_EMPTY.items():
        if field in changes and changes[field] is None:
            raise AppError(
                "TSC-EQUIPMENT-0009", f"{label}은(는) 비울 수 없습니다.", status=400
            )


def _check_status(status: str) -> None:
    if status not in EQUIPMENT_STATUSES:
        raise AppError("TSC-EQUIPMENT-0004", f"모르는 상태입니다: {status}", status=400)


def _check_calibration(required: bool, months: int | None) -> None:
    """교정 대상이면 주기를 함께 받는다.

    **주기가 없으면 차기일을 계산할 수 없다.** 성적서가 차기일을 적어 오면 그때는
    그 날이 이기지만, 첫 교정 전까지는 계산 말고는 방법이 없다 — 비워 두면 「곧 만료」
    목록이 이 장비를 영원히 안 부른다.
    """
    if required and not months:
        raise AppError(
            "TSC-EQUIPMENT-0005",
            "교정 대상 장비는 교정 주기(개월)를 함께 적어야 합니다.",
            status=400,
        )


def _check_retired(status: str, retired_on: Any) -> None:
    """폐기일은 **폐기일 때만** 받는다. 가동 중인 장비에 폐기일이 붙어 있으면
    목록은 그것을 그대로 그리고, 그 줄을 본 사람은 장비가 없어졌다고 믿는다."""
    if retired_on is not None and status != "retired":
        raise AppError(
            "TSC-EQUIPMENT-0006",
            "폐기일은 상태가 「폐기」 일 때만 적을 수 있습니다.",
            status=400,
        )


def _check_identity(db: Session, category_term_id: Any, model_id: Any) -> None:
    """무슨 종류의 장비인지는 **반드시 답한다.**

    기종을 골랐으면 분류는 그 계열이 갖는다(ADR 0006). 안 골랐으면 개체가 직접
    가리켜야 한다 — 유형이 없는 장비는 분류로 좁히는 모든 화면에서 통째로 빠지고,
    빠진 줄은 아무도 못 찾는다.
    """
    if model_id is not None or category_term_id is not None:
        return
    raise AppError(
        "TSC-EQUIPMENT-0007",
        "카탈로그의 기종을 고르거나, 장비유형을 골라야 합니다.",
        status=400,
    )


def filter_options(db: Session, user: User) -> EquipmentFilterOptionsOut:
    """열마다 고를 수 있는 값과 그 수.

    **목록에 실제로 있는 값만 준다.** 기준정보 전체를 내려보내면 분류 108종 중 100종이
    골라도 0 건인 선택지가 되고, 사람은 거르기를 안 믿게 된다.

    부서를 따로 세는 이유가 하나 더 있다: `/api/workspaces` 는 **내 소속만** 준다.
    그것으로 목록을 거르게 두면, 열린 부서의 장비가 목록에는 보이는데 그 부서로는
    거를 수 없는 상태가 된다.
    """
    visible = visible_equipment(db, user).subquery()

    def counted(column: Any) -> list[tuple[Any, int]]:
        rows = db.execute(
            select(column, func.count())
            .select_from(visible)
            .where(column.is_not(None))
            .group_by(column)
        ).all()
        return [(row[0], row[1]) for row in rows]

    categories: dict[uuid.UUID, int] = {}
    for model_id, count in counted(visible.c.model_id):
        model = db.get(EquipmentModel, model_id)
        series = db.get(EquipmentSeries, model.series_id) if model else None
        if series and series.category_term_id:
            categories[series.category_term_id] = (
                categories.get(series.category_term_id, 0) + count
            )
    for term_id, count in counted(visible.c.category_term_id):
        categories[term_id] = categories.get(term_id, 0) + count

    items: dict[uuid.UUID, int] = {}
    for term_id, count in db.execute(
        select(
            EquipmentTestItem.test_item_term_id,
            func.count(func.distinct(EquipmentTestItem.equipment_id)),
        )
        .where(EquipmentTestItem.equipment_id.in_(select(visible.c.id)))
        .group_by(EquipmentTestItem.test_item_term_id)
    ).all():
        items[term_id] = count

    def terms(counts: dict[uuid.UUID, int]) -> list[FilterOption]:
        out = [
            FilterOption(value=str(key), label=_term_value(db, key) or "—", count=count)
            for key, count in counts.items()
        ]
        return sorted(out, key=lambda one: (-one.count, one.label))

    workspaces: list[FilterOption] = []
    for workspace_id, count in counted(visible.c.owner_workspace_id):
        workspace = db.get(Workspace, workspace_id)
        if workspace:
            workspaces.append(
                FilterOption(value=workspace.slug, label=workspace.name, count=count)
            )

    statuses = [
        FilterOption(value=status, label=status, count=count)
        for status, count in counted(visible.c.status)
    ]

    return EquipmentFilterOptionsOut(
        categories=terms(categories),
        workspaces=sorted(workspaces, key=lambda one: (-one.count, one.label)),
        sites=terms(dict(counted(visible.c.site_term_id))),
        # 상태는 **화면이 순서를 안다**(생애 순서). 여기서는 있는 것만 알려 준다.
        statuses=sorted(statuses, key=lambda one: one.label),
        test_items=terms(items),
    )


def create(
    db: Session, user: User, payload: dict[str, Any], *, commit: bool = True
) -> Equipment:
    """장비 한 대를 만든다.

    `commit=False` 는 **일괄 반입**을 위한 것이다. 300줄을 넣다 12줄째에서 막혔을 때
    앞의 11줄이 이미 커밋돼 있으면, 사람은 파일을 고쳐 다시 올리다가 그 11줄에서
    「이미 등록된 자산번호」 를 만나고 무엇을 지워야 할지 모른다 — 전부 되거나
    전부 안 되거나여야 한다(`imports.py`).
    """
    asset_no = clean(payload["asset_no"])
    if db.scalar(select(Equipment).where(Equipment.asset_no == asset_no)) is not None:
        raise Conflict("TSC-EQUIPMENT-0003", f"이미 등록된 자산번호입니다: {asset_no}")

    status = payload.get("status") or "operational"
    _check_status(status)
    _check_retired(status, payload.get("retired_on"))
    _check_calibration(
        bool(payload.get("calibration_required")),
        payload.get("calibration_interval_months"),
    )
    _check_identity(db, payload.get("category_term_id"), payload.get("model_id"))

    owner = owner_workspace(db, user, payload.get("workspace_slug"))
    linked = payload.get("model_id") is not None
    row = Equipment(
        asset_no=asset_no,
        name=clean(payload["name"]),
        dept_asset_no=payload.get("dept_asset_no"),
        owner_workspace_id=owner,
        shared_use=bool(payload.get("shared_use")),
        model_id=payload.get("model_id"),
        serial_no=payload.get("serial_no"),
        # 카탈로그에 이어지면 개체가 적은 글자는 안 받는다 — 둘이 갈리면 어느 쪽이
        # 맞는지 알 수 없고, 검색이 보는 것은 언제나 카탈로그 쪽이다.
        category_term_id=None if linked else payload.get("category_term_id"),
        maker_text=None if linked else payload.get("maker_text"),
        model_text=None if linked else payload.get("model_text"),
        site_term_id=payload.get("site_term_id"),
        location=clean(payload["location"]),
        status=status,
        acquired_on=payload.get("acquired_on"),
        manufactured_year=payload.get("manufactured_year"),
        retired_on=payload.get("retired_on"),
        calibration_required=bool(payload.get("calibration_required")),
        calibration_interval_months=payload.get("calibration_interval_months"),
        contact_user_id=payload.get("contact_user_id"),
        note=payload.get("note"),
        created_by_id=user.id,
    )
    db.add(row)
    db.flush()

    # **모델을 골랐으면 시험 가능한 사양을 이 장비로 복사한다.** 같은 트랜잭션이어야
    # "장비는 생겼는데 시험 항목만 없는" 상태가 안 생긴다(ADR 0004).
    copied = catalog.copy_test_items_to(db, row, user)

    if not commit:
        # 부른 쪽이 트랜잭션을 들고 있다. 여기서 커밋하면 그 쪽의 「전부 아니면
        # 전무」 가 깨진다.
        return row
    db.commit()
    db.refresh(row)
    if copied:
        logger.info("장비 %s: 카탈로그 시험 항목 %d건 복사", row.asset_no, copied)
    return row


#: 부분 수정에서 그대로 옮겨 담는 칸들. 이 목록에 없는 것(부서 이관·상태)은
#: 판단이 따로 붙으므로 아래에서 손으로 다룬다.
_PLAIN_FIELDS = (
    "name",
    "dept_asset_no",
    "serial_no",
    "site_term_id",
    "location",
    "shared_use",
    "acquired_on",
    "manufactured_year",
    "contact_user_id",
    "note",
    "category_term_id",
    "maker_text",
    "model_text",
)


def update(
    db: Session,
    user: User,
    equipment_id: uuid.UUID,
    changes: dict[str, Any],
    *,
    commit: bool = True,
) -> Equipment:
    """**보낸 것만 바꾼다.** changes 는 exclude_unset 으로 만들어진 dict 다.

    `commit=False` 는 일괄 반입의 갱신을 위한 것이다(`create` 와 같은 이유) — 30대를
    갱신하다 12대째에서 막혔을 때 앞의 11대가 이미 커밋돼 있으면 반쯤 갱신된 대장이
    된다.
    """
    row = get_equipment(db, user, equipment_id)
    require_owner_edit(db, user, row.owner_workspace_id, what=_WHAT, code=_CODE)
    _check_not_emptied(changes)

    if "workspace_slug" in changes:
        # 이관은 **양쪽 다 관리자**여야 한다. 받는 쪽 권한을 안 보면 남의 부서에
        # 장비를 밀어 넣을 수 있고, 그 부서는 자기가 안 만든 장비를 떠안는다.
        row.owner_workspace_id = owner_workspace(db, user, changes["workspace_slug"])

    if "status" in changes and changes["status"] is not None:
        status = changes["status"]
        _check_status(status)
        if status != row.status:
            # **폐기만 감사에 남긴다.** 점검·수리는 오가는 상태라 다 남기면 그
            # 안에서 정작 찾을 것을 못 찾는다. 폐기는 목록에서 사라지는 일이다.
            if status == "retired":
                audit.record(
                    db,
                    action=audit.EQUIPMENT_RETIRED,
                    actor=user,
                    target_table="equipment",
                    target_id=row.id,
                    target_label=f"{row.asset_no} {row.name}",
                    workspace_id=row.owner_workspace_id,
                    changes={"status": {"before": row.status, "after": status}},
                )
            row.status = status

    if "model_id" in changes:
        row.model_id = changes["model_id"]
        if row.model_id is not None:
            # **연결하면 개체가 적어 둔 글자를 비운다.** 남겨 두면 같은 사실이 두 곳에
            # 있고, 그 둘이 갈린 뒤에는 어느 쪽이 맞는지 알 방법이 없다.
            row.category_term_id = None
            row.maker_text = None
            row.model_text = None

    for field in _PLAIN_FIELDS:
        if field in changes and not (
            row.model_id is not None
            and field in ("category_term_id", "maker_text", "model_text")
        ):
            setattr(row, field, changes[field])

    if "calibration_required" in changes and changes["calibration_required"] is not None:
        row.calibration_required = changes["calibration_required"]
    if "calibration_interval_months" in changes:
        row.calibration_interval_months = changes["calibration_interval_months"]
    _check_calibration(row.calibration_required, row.calibration_interval_months)

    if "retired_on" in changes:
        # **보낸 값은 상태와 맞아야 한다.** 아래에서 조용히 비워 버리면, 폐기가 아닌
        # 장비에 폐기일을 적은 요청이 성공한 것처럼 보이고 값만 사라진다.
        _check_retired(row.status, changes["retired_on"])
        row.retired_on = changes["retired_on"]
    if row.status != "retired":
        # **폐기를 되돌리면 폐기일도 지운다.** 남겨 두면 가동 중인 장비에 폐기일이
        # 붙어 있고, 목록은 그것을 그대로 그린다.
        row.retired_on = None
    _check_identity(db, row.category_term_id, row.model_id)

    if not commit:
        return row
    db.commit()
    db.refresh(row)
    return row


def delete(db: Session, user: User, equipment_id: uuid.UUID) -> None:
    """소프트 삭제. **행은 남는다** — 이 장비로 잰 데이터가 밖에 있고, 몇 년 뒤에도
    그것이 어느 장비였는지는 물어질 수 있다."""
    row = get_equipment(db, user, equipment_id)
    require_owner_edit(db, user, row.owner_workspace_id, what=_WHAT, code=_CODE)
    audit.record(
        db,
        action=audit.EQUIPMENT_DELETED,
        actor=user,
        target_table="equipment",
        target_id=row.id,
        target_label=f"{row.asset_no} {row.name}",
        workspace_id=row.owner_workspace_id,
    )
    row.deleted_at = datetime.now(UTC)
    db.commit()


# --- 교정 -------------------------------------------------------------------


def calibration_out(db: Session, row: EquipmentCalibration) -> CalibrationOut:
    """교정 한 줄. **기관은 이름까지 준다** — id 만 주면 목록 한 줄을 그리려고 화면이
    기준정보를 또 조회해야 하고, 그 조회가 빠진 화면은 빈 칸을 보여 준다."""
    return CalibrationOut(
        id=row.id,
        calibrated_on=row.calibrated_on,
        next_due_on=row.next_due_on,
        certificate_no=row.certificate_no,
        provider=_term_value(db, row.provider_term_id),
        provider_term_id=row.provider_term_id,
        note=row.note,
    )


def calibrations(db: Session, user: User, equipment_id: uuid.UUID) -> list[CalibrationOut]:
    get_equipment(db, user, equipment_id)
    rows = db.scalars(
        select(EquipmentCalibration)
        .where(EquipmentCalibration.equipment_id == equipment_id)
        .order_by(EquipmentCalibration.calibrated_on.desc())
    )
    return [calibration_out(db, row) for row in rows]


def add_calibration(
    db: Session, user: User, equipment_id: uuid.UUID, payload: dict[str, Any]
) -> CalibrationOut:
    row = get_equipment(db, user, equipment_id)
    require_owner_edit(db, user, row.owner_workspace_id, what=_WHAT, code=_CODE)
    record = EquipmentCalibration(equipment_id=row.id, **payload)
    db.add(record)
    db.commit()
    db.refresh(record)
    return calibration_out(db, record)

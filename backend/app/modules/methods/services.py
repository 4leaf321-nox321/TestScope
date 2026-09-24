"""시험법 로직."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.attributes import filters as attribute_filters
from app.modules.attributes import services as attributes
from app.modules.attributes.schemas import AttributeValueIn
from app.modules.equipment.models import EquipmentSeries
from app.modules.methods.models import MethodRequirement, TestMethod, TestMethodItem
from app.modules.methods.schemas import (
    CitedSeriesOut,
    MethodOut,
    MethodTestItemOut,
    RequirementOut,
)
from app.modules.review.models import ReviewProposal
from app.modules.test_items.models import (
    EquipmentTestItem,
    SeriesPendingMethod,
    SeriesTestItem,
    SeriesTestItemMethod,
)
from app.modules.vocabulary.models import ConditionKey, VocabularyTerm
from app.modules.workspaces.models import Workspace
from app.shared import audit
from app.shared.errors import AppError, Conflict, NotFound
from app.shared.pagination import Page
from app.shared.permissions import (
    require_owner_edit,
    resolve_owner_workspace,
    visible_owner_clause,
)
from app.shared.request_context import get_actor_token
from app.shared.text import clean

_WHAT = "시험법"
_CODE = "TSC-METHODS-0002"


def visible(db: Session, user: User) -> Select[tuple[TestMethod]]:
    """전역 시험법 + 내 부서 시험법. 목록·상세·검색이 **같은 것**을 봐야 한다."""
    return select(TestMethod).where(
        TestMethod.deleted_at.is_(None),
        visible_owner_clause(user, TestMethod.owner_workspace_id),
    )


def get_method(db: Session, user: User, method_id: uuid.UUID) -> TestMethod:
    found = db.scalar(visible(db, user).where(TestMethod.id == method_id))
    if found is None:
        raise NotFound("TSC-METHODS-0001", "시험법을 찾을 수 없습니다.")
    return found


def _requirements(db: Session, method_id: uuid.UUID) -> list[RequirementOut]:
    rows = db.execute(
        select(MethodRequirement, ConditionKey)
        .join(ConditionKey, ConditionKey.id == MethodRequirement.condition_key_id)
        .where(MethodRequirement.method_id == method_id)
        .order_by(ConditionKey.sort_order, ConditionKey.label)
    ).all()
    return [
        RequirementOut(
            id=req.id,
            condition_key_id=key.id,
            condition_key=key.key,
            condition_label=key.label,
            si_unit=key.si_unit,
            display_unit=key.display_unit,
            min_value=req.min_value,
            max_value=req.max_value,
            text_value=req.text_value,
            is_mandatory=req.is_mandatory,
            note=req.note,
        )
        for req, key in rows
    ]


def promote_pending(db: Session, method: TestMethod) -> int:
    """항목 미정 인용을 **그 시험 항목의 링크로 올린다.** 올린 수를 돌려준다. 커밋은 부르는 쪽.

    시험 항목이 정해진 규격에 대해, 그것을 인용해 둔 계열마다 그 계열이 그 시험 항목을
    갖고 있으면 `series_test_item_methods` 에 잇고 미정 줄을 지운다. 계열에 그 시험 항목이
    없으면 미정으로 남는다 — 사람이 계열에 그 시험을 더하거나 규격의 항목을 다시 볼 자리다.
    """
    # **규격이 덮는 항목 전부**를 본다. 하나만 보면 IEC 60529 를 인용한 계열이
    # 방진으로는 이어지고 방수로는 안 이어진다.
    wanted = item_ids(db, method.id)
    if not wanted:
        return 0
    moved = 0
    for pending in list(
        db.scalars(
            select(SeriesPendingMethod).where(SeriesPendingMethod.method_id == method.id)
        )
    ):
        target = db.scalar(
            select(SeriesTestItem).where(
                SeriesTestItem.series_id == pending.series_id,
                SeriesTestItem.test_item_term_id.in_(wanted),
            )
        )
        if target is None:
            continue
        linked = db.scalar(
            select(SeriesTestItemMethod).where(
                SeriesTestItemMethod.series_test_item_id == target.id,
                SeriesTestItemMethod.method_id == method.id,
            )
        )
        if linked is None:
            db.add(SeriesTestItemMethod(series_test_item_id=target.id, method_id=method.id))
        db.delete(pending)
        moved += 1
    db.flush()
    return moved


def series_counts(
    db: Session, method_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[int, int]]:
    """규격마다 (이어진 계열 수, 항목 미정으로 인용한 계열 수). **한 번에 센다.**"""
    linked: dict[uuid.UUID, set[uuid.UUID]] = {}
    for method_id, series_id in db.execute(
        select(SeriesTestItemMethod.method_id, SeriesTestItem.series_id)
        .join(SeriesTestItem, SeriesTestItem.id == SeriesTestItemMethod.series_test_item_id)
        .where(SeriesTestItemMethod.method_id.in_(method_ids))
    ).all():
        linked.setdefault(method_id, set()).add(series_id)
    for method_id, series_id in db.execute(
        select(SeriesTestItem.method_id, SeriesTestItem.series_id).where(
            SeriesTestItem.method_id.in_(method_ids)
        )
    ).all():
        linked.setdefault(method_id, set()).add(series_id)
    pending: dict[uuid.UUID, int] = {
        method_id: count
        for method_id, count in db.execute(
            select(SeriesPendingMethod.method_id, func.count())
            .where(SeriesPendingMethod.method_id.in_(method_ids))
            .group_by(SeriesPendingMethod.method_id)
        ).all()
    }
    return {one: (len(linked.get(one, set())), pending.get(one, 0)) for one in method_ids}


def cited_series(db: Session, method_id: uuid.UUID) -> list[CitedSeriesOut]:
    """이 규격을 인용한 계열 — 이어진 것과 항목 미정인 것 함께. 상세 화면이 그린다."""
    out: dict[uuid.UUID, CitedSeriesOut] = {}
    rows = db.execute(
        select(EquipmentSeries, VocabularyTerm.value)
        .join(SeriesTestItem, SeriesTestItem.series_id == EquipmentSeries.id)
        .join(
            SeriesTestItemMethod, SeriesTestItemMethod.series_test_item_id == SeriesTestItem.id
        )
        .join(VocabularyTerm, VocabularyTerm.id == SeriesTestItem.test_item_term_id)
        .where(
            SeriesTestItemMethod.method_id == method_id, EquipmentSeries.deleted_at.is_(None)
        )
    ).all()
    for series, item in rows:
        out[series.id] = CitedSeriesOut(
            series_id=series.id, series_name=series.name, test_item=item, pending=False
        )
    for series in db.scalars(
        select(EquipmentSeries)
        .join(SeriesPendingMethod, SeriesPendingMethod.series_id == EquipmentSeries.id)
        .where(
            SeriesPendingMethod.method_id == method_id, EquipmentSeries.deleted_at.is_(None)
        )
    ):
        out.setdefault(
            series.id,
            CitedSeriesOut(
                series_id=series.id, series_name=series.name, test_item=None, pending=True
            ),
        )
    return sorted(out.values(), key=lambda one: (one.pending, one.series_name))


def _can_edit(db: Session, user: User, row: TestMethod) -> bool:
    try:
        require_owner_edit(db, user, row.owner_workspace_id, what=_WHAT, code=_CODE)
    except AppError:
        return False
    return True


def method_out(
    db: Session,
    row: TestMethod,
    viewer: User,
    *,
    counts: dict[uuid.UUID, tuple[int, int]] | None = None,
    with_series: bool = False,
) -> MethodOut:
    items = items_of(db, [row.id])[row.id]
    linked, pending = (counts or series_counts(db, [row.id]))[row.id]
    body = db.get(VocabularyTerm, row.body_term_id) if row.body_term_id else None
    workspace = db.get(Workspace, row.owner_workspace_id) if row.owner_workspace_id else None
    successor = db.get(TestMethod, row.superseded_by_id) if row.superseded_by_id else None
    equipment_count = (
        db.scalar(
            select(func.count(func.distinct(EquipmentTestItem.equipment_id))).where(
                EquipmentTestItem.method_id == row.id
            )
        )
        or 0
    )
    return MethodOut(
        id=row.id,
        code=row.code,
        edition=row.edition,
        title=row.title,
        test_items=[MethodTestItemOut(term_id=one.id, value=one.value) for one in items],
        body=body.value if body else None,
        status=row.status,
        superseded_by_code=successor.code if successor else None,
        summary=row.summary,
        workspace_slug=workspace.slug if workspace else None,
        equipment_count=equipment_count,
        series_count=linked,
        pending_series_count=pending,
        cited_series=cited_series(db, row.id) if with_series else [],
        requirements=_requirements(db, row.id),
        attributes=attributes.values_of(db, target="method", object_ids=[row.id])[row.id],
        created_at=row.created_at,
        can_edit=_can_edit(db, viewer, row),
    )


def list_methods(
    db: Session,
    user: User,
    *,
    query: str | None,
    requirement: str | None = None,
    test_item_term_id: uuid.UUID | None,
    test_item: str | None = None,
    cited: str | None = None,
    used: str | None = None,
    include_superseded: bool,
    attrs: list[str] | None = None,
    limit: int,
    offset: int,
) -> Page[MethodOut]:
    stmt = visible(db, user)
    if query:
        text = f"%{clean(query)}%"
        stmt = stmt.where(TestMethod.code.ilike(text) | TestMethod.title.ilike(text))
    if test_item_term_id:
        # 규격 하나가 항목 여럿을 덮으므로 **있는가**를 묻는다(N:M).
        stmt = stmt.where(
            TestMethod.id.in_(
                select(TestMethodItem.method_id).where(
                    TestMethodItem.test_item_term_id == test_item_term_id
                )
            )
        )
    if test_item == "none":
        # **어느 시험의 규격인지 안 정해진 것.** 인용한 계열이 있어도 못 이어진다 — 홈의
        # 「남은 일」 이 이 조건으로 온다. 세는 조건과 거르는 조건이 같아야 한다.
        stmt = stmt.where(TestMethod.id.not_in(select(TestMethodItem.method_id).distinct()))
    if cited == "none":
        # 어느 계열의 시험 항목에도 안 이어진 규격. 「못 하는 시험」 과 「끊긴 연결」 을
        # 여기서 가른다 — 항목 미정 인용(pending)이 있으면 끊긴 것이다.
        stmt = stmt.where(
            TestMethod.id.not_in(select(SeriesTestItemMethod.method_id).distinct()),
            TestMethod.id.not_in(
                select(SeriesTestItem.method_id).where(SeriesTestItem.method_id.is_not(None))
            ),
        )
    if requirement == "none":
        # **우리가 인용한 규격 중 조건이 안 적힌 것.** 홈의 「남은 일」 이 이 조건으로
        # 링크한다 — 세는 조건과 거르는 조건이 다르면 그 줄을 눌러 온 사람이 다른
        # 목록을 보고, 그때 둘 다 안 믿게 된다.
        stmt = stmt.where(TestMethod.id.not_in(select(MethodRequirement.method_id).distinct()))
    if used == "owned":
        # **보유 장비의 시험 항목이 실제로 가리키는 규격만.** 464 는 카탈로그가 인용한
        # 수이고, 우리가 하는 시험의 규격은 그중 일부다 — 요구 조건은 여기부터 채운다.
        stmt = stmt.where(
            TestMethod.id.in_(
                select(EquipmentTestItem.method_id).where(
                    EquipmentTestItem.method_id.is_not(None)
                )
            )
        )
    if not include_superseded:
        # **기본은 현행만.** 대체된 판이 섞여 있으면 사람이 옛 규격을 고르고,
        # 그 사실은 시험이 끝난 뒤에야 드러난다.
        stmt = stmt.where(TestMethod.status != "superseded")

    stmt = attribute_filters.apply(
        db, stmt, "method", TestMethod.id, attribute_filters.parse(db, "method", attrs or [])
    )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        db.scalars(
            stmt.order_by(TestMethod.code, TestMethod.edition).limit(limit).offset(offset)
        )
    )
    counts = series_counts(db, [row.id for row in rows])
    return Page(
        items=[method_out(db, row, user, counts=counts) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def create(db: Session, user: User, payload: dict[str, Any]) -> TestMethod:
    code = clean(payload["code"])
    edition = clean(payload.get("edition") or "") or None
    clash = db.scalar(
        select(TestMethod).where(
            TestMethod.code == code,
            TestMethod.edition.is_(edition)
            if edition is None
            else TestMethod.edition == edition,
            TestMethod.deleted_at.is_(None),
        )
    )
    if clash is not None:
        raise Conflict("TSC-METHODS-0003", f"이미 등록된 규격입니다: {code} {edition or ''}")

    owner = resolve_owner_workspace(
        db, user, payload.get("workspace_slug"), what=_WHAT, code=_CODE
    )
    row = TestMethod(
        code=code,
        edition=edition,
        title=clean(payload["title"]),
        body_term_id=payload.get("body_term_id"),
        summary=payload.get("summary"),
        owner_workspace_id=owner,
        created_by_id=user.id,
    )
    db.add(row)
    db.flush()
    set_test_items(db, row.id, list(payload.get("test_item_term_ids") or []))
    db.commit()
    db.refresh(row)
    return row


_PLAIN_FIELDS = ("title", "edition", "body_term_id", "summary")


def item_ids(db: Session, method_id: uuid.UUID) -> list[uuid.UUID]:
    """이 규격이 덮는 시험 항목 id 들."""
    return list(
        db.scalars(
            select(TestMethodItem.test_item_term_id).where(
                TestMethodItem.method_id == method_id
            )
        )
    )


def items_of(
    db: Session, method_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[VocabularyTerm]]:
    """여러 규격의 시험 항목을 **한 번에** — 줄마다 물으면 목록이 줄 수만큼 왕복한다."""
    out: dict[uuid.UUID, list[VocabularyTerm]] = {one: [] for one in method_ids}
    if not method_ids:
        return out
    for method_id, term in db.execute(
        select(TestMethodItem.method_id, VocabularyTerm)
        .join(VocabularyTerm, VocabularyTerm.id == TestMethodItem.test_item_term_id)
        .where(TestMethodItem.method_id.in_(method_ids))
        .order_by(VocabularyTerm.value)
    ).all():
        out[method_id].append(term)
    return out


def set_test_items(db: Session, method_id: uuid.UUID, term_ids: list[uuid.UUID]) -> None:
    """**통째로** 바꾼다. 같은 값이 두 번 와도 한 줄만 남는다."""
    for link in db.scalars(
        select(TestMethodItem).where(TestMethodItem.method_id == method_id)
    ):
        db.delete(link)
    db.flush()
    for term_id in dict.fromkeys(term_ids):
        db.add(TestMethodItem(method_id=method_id, test_item_term_id=term_id))
    db.flush()


def _refuse_machine_decision(db: Session, row: TestMethod) -> None:
    """검토함에 열린 물음이 있는 규격의 시험 항목은 **기계 자격으로 못 정한다.**

    검토함의 확정은 범위 표에 없어 AI 가 못 누르는데, 규격의 시험 항목을 직접 고치는 길은
    열려 있었다 — 그 길로 가면 결과는 확정과 같다(인용한 계열에 붙고, 검토함 줄만 open 으로
    남는다). 실측: 「검토함 첫 줄 추천대로 확정해줘」 에 AI 가 정확히 이 우회로를 썼다
    (2026-09-20 측정, q22). 사람 세션은 막지 않는다 — 그 사람의 권한이 이미 한계다.
    """
    if get_actor_token() is None:
        return
    pending = db.scalar(
        select(ReviewProposal.id).where(
            ReviewProposal.queue == "method_test_items",
            ReviewProposal.subject_id == row.id,
            ReviewProposal.status.in_(("open", "skipped")),
        )
    )
    if pending is not None:
        raise Conflict(
            "TSC-METHODS-0007",
            "이 규격은 검토함에 물음이 열려 있습니다 — 시험 항목은 사람이 검토함에서 정합니다",
        )


def update(
    db: Session, user: User, method_id: uuid.UUID, changes: dict[str, Any]
) -> TestMethod:
    row = get_method(db, user, method_id)
    require_owner_edit(db, user, row.owner_workspace_id, what=_WHAT, code=_CODE)

    for field in _PLAIN_FIELDS:
        if field in changes:
            setattr(row, field, changes[field])
    if changes.get("test_item_term_ids") is not None:
        _refuse_machine_decision(db, row)
        set_test_items(db, row.id, list(changes["test_item_term_ids"]))
        # 시험 항목이 정해지는 순간 항목 미정 인용이 그 계열의 시험 항목에 붙는다 —
        # 사람이 계열마다 다시 이을 필요가 없다.
        promote_pending(db, row)

    if changes.get("status") == "superseded" and row.status != "superseded":
        # **대체는 되돌릴 수 없는 부류다.** 이 규격을 걸고 있던 시험 항목 전부의 뜻이
        # 바뀌고, 그 사실을 반년 뒤에 물을 자리가 감사 기록밖에 없다.
        successor = (
            db.get(TestMethod, changes["superseded_by_id"])
            if changes.get("superseded_by_id")
            else None
        )
        audit.record(
            db,
            action=audit.METHOD_SUPERSEDED,
            actor=user,
            target_table="test_methods",
            target_id=row.id,
            target_label=f"{row.code} {row.edition or ''}".strip(),
            workspace_id=row.owner_workspace_id,
            changes={
                "superseded_by": {
                    "before": None,
                    "after": successor.code if successor else None,
                }
            },
        )
    if "status" in changes and changes["status"] is not None:
        row.status = changes["status"]
    if "superseded_by_id" in changes:
        row.superseded_by_id = changes["superseded_by_id"]
    if changes.get("attributes") is not None:
        attributes.set_values(
            db,
            user,
            target="method",
            object_id=row.id,
            items=[AttributeValueIn.model_validate(one) for one in changes["attributes"]],
        )

    db.commit()
    db.refresh(row)
    return row


def delete(db: Session, user: User, method_id: uuid.UUID) -> None:
    """소프트 삭제.

    **대체된 규격은 지우는 것이 아니다** — 옛 판으로 잰 데이터가 있고, 그것이
    어느 판이었는지는 남아야 한다. 삭제는 잘못 등록한 행을 위한 것이다.
    """
    row = get_method(db, user, method_id)
    require_owner_edit(db, user, row.owner_workspace_id, what=_WHAT, code=_CODE)
    using = (
        db.scalar(
            select(func.count())
            .select_from(EquipmentTestItem)
            .where(EquipmentTestItem.method_id == row.id)
        )
        or 0
    )
    if using:
        raise Conflict(
            "TSC-METHODS-0004",
            f"이 시험법을 거는 시험 항목이 {using}건 있습니다. "
            f"지우는 대신 상태를 대체됨으로 바꾸십시오.",
        )
    row.deleted_at = datetime.now(UTC)
    db.commit()


def detach_citations(db: Session, method_id: uuid.UUID) -> int:
    """계열이 건 인용(연결·항목 미정)을 뗀다 — 규격을 지우기 전에. 뗀 수."""
    removed = 0
    for row in db.scalars(
        select(SeriesTestItemMethod).where(SeriesTestItemMethod.method_id == method_id)
    ):
        db.delete(row)
        removed += 1
    for pending in db.scalars(
        select(SeriesPendingMethod).where(SeriesPendingMethod.method_id == method_id)
    ):
        db.delete(pending)
        removed += 1
    return removed


def merge_into(
    db: Session, actor: User | None, source_id: uuid.UUID, target_id: uuid.UUID
) -> TestMethod:
    """표기만 다른 규격 둘을 하나로. **인용·요구 조건·장비 시험 항목이 남는 쪽으로 옮겨 가고**
    원래 줄은 소프트 삭제된다.

    같은 자리에 이미 이어져 있으면 옮기지 않고 버린다(유일 제약). 요구 조건은 남는 쪽에 그
    축이 없을 때만 옮긴다 — 남는 쪽 값이 더 낫다고 본다(사람이 봤을 가능성이 높다).
    """
    source = db.get(TestMethod, source_id)
    target = db.get(TestMethod, target_id)
    if source is None or target is None or source.id == target.id:
        raise NotFound("TSC-METHODS-0005", "합칠 규격을 찾을 수 없습니다.")
    for link in db.scalars(
        select(SeriesTestItemMethod).where(SeriesTestItemMethod.method_id == source.id)
    ):
        held = db.scalar(
            select(SeriesTestItemMethod).where(
                SeriesTestItemMethod.series_test_item_id == link.series_test_item_id,
                SeriesTestItemMethod.method_id == target.id,
            )
        )
        if held is None:
            link.method_id = target.id
        else:
            db.delete(link)
    for pending in db.scalars(
        select(SeriesPendingMethod).where(SeriesPendingMethod.method_id == source.id)
    ):
        held_pending = db.scalar(
            select(SeriesPendingMethod).where(
                SeriesPendingMethod.series_id == pending.series_id,
                SeriesPendingMethod.method_id == target.id,
            )
        )
        if held_pending is None:
            pending.method_id = target.id
        else:
            db.delete(pending)
    target_keys = set(
        db.scalars(
            select(MethodRequirement.condition_key_id).where(
                MethodRequirement.method_id == target.id
            )
        )
    )
    for requirement in db.scalars(
        select(MethodRequirement).where(MethodRequirement.method_id == source.id)
    ):
        if requirement.condition_key_id in target_keys:
            db.delete(requirement)
        else:
            requirement.method_id = target.id
    for item in db.scalars(
        select(EquipmentTestItem).where(EquipmentTestItem.method_id == source.id)
    ):
        item.method_id = target.id
    for other in db.scalars(
        select(TestMethod).where(TestMethod.superseded_by_id == source.id)
    ):
        other.superseded_by_id = target.id
    # **합집합이다.** 한쪽만 남기면 합치면서 연결이 준다 — 합치기는 정보를 잃지 않는
    # 일이어야 한다.
    set_test_items(db, target.id, item_ids(db, target.id) + item_ids(db, source.id))
    db.flush()
    promote_pending(db, target)
    audit.record(
        db,
        action=audit.METHOD_MERGED,
        actor=actor,
        target_table="test_methods",
        target_id=target.id,
        target_label=target.code,
        changes={"merged_from": source.code, "into": target.code},
    )
    source.deleted_at = datetime.now(UTC)
    return target


def upsert_requirement(
    db: Session, user: User, method_id: uuid.UUID, payload: dict[str, Any]
) -> RequirementOut:
    """요구 조건 하나를 넣거나 덮어쓴다.

    같은 조건이 둘이면 어느 쪽이 맞는지 알 수 없으므로 **덮어쓰기가 기본**이다.
    """
    row = get_method(db, user, method_id)
    require_owner_edit(db, user, row.owner_workspace_id, what=_WHAT, code=_CODE)

    key = db.get(ConditionKey, payload["condition_key_id"])
    if key is None:
        raise NotFound("TSC-METHODS-0005", "조건 정의를 찾을 수 없습니다.")

    existing = db.scalar(
        select(MethodRequirement).where(
            MethodRequirement.method_id == row.id,
            MethodRequirement.condition_key_id == key.id,
        )
    )
    target = existing or MethodRequirement(method_id=row.id, condition_key_id=key.id)
    target.min_value = payload.get("min_value")
    target.max_value = payload.get("max_value")
    target.text_value = payload.get("text_value")
    target.is_mandatory = payload.get("is_mandatory", True)
    target.note = payload.get("note")
    if existing is None:
        db.add(target)
    db.commit()

    return next(one for one in _requirements(db, row.id) if one.condition_key_id == key.id)


def delete_requirement(
    db: Session, user: User, method_id: uuid.UUID, requirement_id: uuid.UUID
) -> None:
    row = get_method(db, user, method_id)
    require_owner_edit(db, user, row.owner_workspace_id, what=_WHAT, code=_CODE)
    target = db.get(MethodRequirement, requirement_id)
    if target is None or target.method_id != row.id:
        raise NotFound("TSC-METHODS-0006", "요구 조건을 찾을 수 없습니다.")
    db.delete(target)
    db.commit()

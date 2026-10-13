"""시험법 로직."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, Text, func, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.attributes import filters as attribute_filters
from app.modules.attributes import services as attributes
from app.modules.attributes.schemas import AttributeValueIn
from app.modules.equipment.models import EquipmentSeries
from app.modules.methods.models import MethodRequirement, TestMethod, TestMethodItem
from app.modules.methods.schemas import (
    CitedSeriesOut,
    DetachImpact,
    LinkCitationsResult,
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
from app.shared.errors import AppError, Conflict, Forbidden, NotFound
from app.shared.pagination import Page
from app.shared.permissions import (
    require_owner_edit,
    resolve_owner_workspace,
    visible_owner_clause,
)
from app.shared.request_context import get_actor_token
from app.shared.text import clean, method_key

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
        raise NotFound("TSC-METHODS-0001", "시험법을 찾을 수 없음.")
    return found


def _requirements(db: Session, method_id: uuid.UUID) -> list[RequirementOut]:
    rows = db.execute(
        select(MethodRequirement, ConditionKey)
        .join(ConditionKey, ConditionKey.id == MethodRequirement.condition_key_id)
        .where(MethodRequirement.method_id == method_id)
        .order_by(ConditionKey.sort_order, ConditionKey.label)
    ).all()
    return [_requirement_out(req, key) for req, key in rows]


def _requirement_out(req: MethodRequirement, key: ConditionKey) -> RequirementOut:
    """요구 조건 한 줄. **낱개로 읽을 때와 묶어 읽을 때가 같은 글자를 내야 한다.**"""
    return RequirementOut(
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


def citing_split(
    db: Session, method_id: uuid.UUID, item_ids_: list[uuid.UUID]
) -> tuple[list[EquipmentSeries], list[EquipmentSeries]]:
    """항목 미정으로 인용한 계열을 (이 항목들로 이어질 것, 안 이어질 것)으로 가른다.

    규격의 시험 항목을 정하면 **그 시험 항목을 가진 계열만** 이어진다(`promote_pending`).
    후보 밖 항목을 고르면 나머지는 미정으로 남는데, 그 사실이 화면 어디에도 안 보여 처리가 끝난
    것으로 읽혔다(2026-10-13). 정하기 전에 이것으로 미리 보여 준다.
    """
    wanted = set(item_ids_)
    has: dict[uuid.UUID, set[uuid.UUID]] = {}
    for series_id, term_id in db.execute(
        select(SeriesTestItem.series_id, SeriesTestItem.test_item_term_id)
        .join(SeriesPendingMethod, SeriesPendingMethod.series_id == SeriesTestItem.series_id)
        .where(SeriesPendingMethod.method_id == method_id)
    ):
        has.setdefault(series_id, set()).add(term_id)
    linked: list[EquipmentSeries] = []
    unlinked: list[EquipmentSeries] = []
    for series in db.scalars(
        select(EquipmentSeries)
        .join(SeriesPendingMethod, SeriesPendingMethod.series_id == EquipmentSeries.id)
        .where(
            SeriesPendingMethod.method_id == method_id, EquipmentSeries.deleted_at.is_(None)
        )
        .order_by(EquipmentSeries.name)
    ):
        (linked if has.get(series.id, set()) & wanted else unlinked).append(series)
    return linked, unlinked


def add_items_to_citing(db: Session, method: TestMethod) -> list[str]:
    """**안 이어진 인용 계열에 규격의 시험 항목을 더하고 잇는다.** 더한 계열 이름을 돌려준다.

    「이 계열이 그 규격을 인용했다」 는 카탈로그의 말을 믿는 쪽이다 — 규격의 시험 항목을 그
    계열이 한다는 뜻이니 계열에 그 시험을 더한다. 계열이 그 시험을 정말 하는지는 사람이 정한
    것이라(검토함 확정 · 규격 화면) 여기서 묻지 않는다. 커밋은 부르는 쪽.
    """
    items = item_ids(db, method.id)
    if not items:
        return []
    _, unlinked = citing_split(db, method.id, items)
    added: list[str] = []
    for series in unlinked:
        have = set(
            db.scalars(
                select(SeriesTestItem.test_item_term_id).where(
                    SeriesTestItem.series_id == series.id
                )
            )
        )
        for term_id in items:
            if term_id in have:
                continue
            db.add(
                SeriesTestItem(
                    series_id=series.id,
                    test_item_term_id=term_id,
                    note=f"규격 {method.code} 인용으로 더함",
                )
            )
        added.append(series.name)
    db.flush()
    promote_pending(db, method)
    return added


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


@dataclass(frozen=True)
class _Bulk:
    """`method_out` 이 **줄마다** 묻던 것을 한 번씩 담아 둔 것.

    묶기 전 실측(2026-09-24, 개발 DB): 규격 목록 50줄에 질의 **253회**, 10줄에 53회 —
    줄마다 다섯씩 붙었다. 보유 장비에서 같은 것을 고쳤을 때가 593 → 13 이었다.
    질의 수가 **줄 수를 따라 늘지 않는 것**이 규칙이고, `test_catalog_list_cost.py` 가 본다.
    """

    items: dict[uuid.UUID, list[VocabularyTerm]]
    counts: dict[uuid.UUID, tuple[int, int]]
    bodies: dict[uuid.UUID, VocabularyTerm]
    workspaces: dict[uuid.UUID, Workspace]
    successors: dict[uuid.UUID, TestMethod]
    equipment: dict[uuid.UUID, int]
    requirements: dict[uuid.UUID, list[RequirementOut]]
    attributes: dict[uuid.UUID, list[Any]]
    editable: dict[uuid.UUID | None, bool]


def _bulk(db: Session, rows: list[TestMethod], viewer: User) -> _Bulk:
    ids = [row.id for row in rows]
    if not ids:
        # **자리마다 새 사전을 준다.** 하나를 아홉에 나눠 주면 그 뒤로는 같은 것이라,
        # 한 곳에 적으면 여덟 곳이 함께 바뀐다(frozen 은 묶는 것을 막지 사전 안을 막지 않는다).
        return _Bulk(*({} for _ in range(9)))

    def _by_id(model: Any, wanted: set[uuid.UUID]) -> dict[uuid.UUID, Any]:
        if not wanted:
            return {}
        return {one.id: one for one in db.scalars(select(model).where(model.id.in_(wanted)))}

    equipment: dict[uuid.UUID, int] = {
        method_id: count
        for method_id, count in db.execute(
            select(
                EquipmentTestItem.method_id,
                func.count(func.distinct(EquipmentTestItem.equipment_id)),
            )
            .where(EquipmentTestItem.method_id.in_(ids))
            .group_by(EquipmentTestItem.method_id)
        ).all()
    }

    requirements: dict[uuid.UUID, list[RequirementOut]] = {one: [] for one in ids}
    for req, key in db.execute(
        select(MethodRequirement, ConditionKey)
        .join(ConditionKey, ConditionKey.id == MethodRequirement.condition_key_id)
        .where(MethodRequirement.method_id.in_(ids))
        .order_by(ConditionKey.sort_order, ConditionKey.label)
    ).all():
        requirements[req.method_id].append(_requirement_out(req, key))

    # **고칠 수 있나는 부서마다 한 번이면 된다** — 규격 쉰 건이 한 부서 것이면 판정도 하나다.
    editable: dict[uuid.UUID | None, bool] = {}
    for row in rows:
        if row.owner_workspace_id not in editable:
            editable[row.owner_workspace_id] = _can_edit(db, viewer, row)

    return _Bulk(
        items=items_of(db, ids),
        counts=series_counts(db, ids),
        bodies=_by_id(VocabularyTerm, {r.body_term_id for r in rows if r.body_term_id}),
        workspaces=_by_id(
            Workspace, {r.owner_workspace_id for r in rows if r.owner_workspace_id}
        ),
        successors=_by_id(
            TestMethod, {r.superseded_by_id for r in rows if r.superseded_by_id}
        ),
        equipment=equipment,
        requirements=requirements,
        attributes=attributes.values_of(db, target="method", object_ids=ids),
        editable=editable,
    )


def method_out(
    db: Session,
    row: TestMethod,
    viewer: User,
    *,
    bulk: _Bulk | None = None,
    with_series: bool = False,
) -> MethodOut:
    """규격 한 줄. **목록은 묶음을 주고 상세는 안 준다** — 글자는 어느 쪽이든 같다.

    묶음이 없으면 이 한 줄만큼을 여기서 읽는다(상세 화면). 목록이 줄마다 이 길로 오면
    질의가 줄 수를 따라 늘어난다 — 그래서 목록은 `_bulk` 를 한 번 만들어 건넨다.
    """
    at_hand = bulk or _bulk(db, [row], viewer)
    items = at_hand.items[row.id]
    linked, pending = at_hand.counts[row.id]
    body = at_hand.bodies.get(row.body_term_id) if row.body_term_id else None
    workspace = (
        at_hand.workspaces.get(row.owner_workspace_id) if row.owner_workspace_id else None
    )
    successor = at_hand.successors.get(row.superseded_by_id) if row.superseded_by_id else None
    equipment_count = at_hand.equipment.get(row.id, 0)
    return MethodOut(
        id=row.id,
        code=row.code,
        former_codes=list(row.former_codes or []),
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
        requirements=at_hand.requirements[row.id],
        attributes=at_hand.attributes[row.id],
        created_at=row.created_at,
        can_edit=at_hand.editable[row.owner_workspace_id],
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
        # 옛 번호로도 찾는다 — 번호를 고친 뒤에도 사람은 한동안 옛 번호로 묻는다.
        stmt = stmt.where(
            TestMethod.code.ilike(text)
            | TestMethod.title.ilike(text)
            | TestMethod.former_codes.cast(Text).ilike(text)
        )
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
    if cited == "unlinked":
        # **끊긴 연결.** 시험 항목은 정했는데(`TestMethodItem`) 인용한 계열이 미정으로 남은
        # 것 — 그 계열에 그 시험 항목이 없어서다. 홈의 「남은 일」 과 같은 조건.
        stmt = stmt.where(
            TestMethod.id.in_(select(TestMethodItem.method_id).distinct()),
            TestMethod.id.in_(select(SeriesPendingMethod.method_id).distinct()),
        )
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
    bulk = _bulk(db, rows, user)
    return Page(
        items=[method_out(db, row, user, bulk=bulk) for row in rows],
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
        raise Conflict("TSC-METHODS-0003", f"이미 등록된 규격: {code} {edition or ''}")

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


def code_index(db: Session) -> dict[str, TestMethod]:
    """비교키(`method_key`) -> 규격. **옛 번호(`former_codes`)도 그 규격을 가리킨다.**

    번호를 열쇠로 쓰는 곳(카탈로그 반입 · 요구 조건 표 반입 · 검토함)이 이것을 쓴다. 번호를
    고친 규격을 옛 번호로 못 찾으면 반입이 같은 규격을 하나 더 만든다. 지금 번호가 다른 규격의
    옛 번호와 겹치면 지금 번호가 이긴다.
    """
    rows = list(db.scalars(select(TestMethod).where(TestMethod.deleted_at.is_(None))))
    out: dict[str, TestMethod] = {}
    for row in rows:
        for old in row.former_codes or []:
            out.setdefault(method_key(old), row)
    for row in rows:
        out[method_key(row.code)] = row
    return out


def _ensure_unique(db: Session, row: TestMethod, code: str, edition: str | None) -> None:
    """(번호, 판)이 다른 규격과 겹치지 않는가. **다른 규격의 옛 번호와도** 안 겹쳐야 한다 —
    겹치면 그 번호로 들어오는 반입 · 검토함이 어느 규격인지 가를 수 없다."""
    key = method_key(code)
    for other in db.scalars(
        select(TestMethod).where(TestMethod.deleted_at.is_(None), TestMethod.id != row.id)
    ):
        if method_key(other.code) == key and (other.edition or None) == (edition or None):
            raise Conflict(
                "TSC-METHODS-0003",
                f"이미 등록된 규격: {other.code} {other.edition or ''}".strip(),
                details={"method_id": str(other.id)},
            )
        if key in {method_key(old) for old in other.former_codes or []}:
            raise Conflict(
                "TSC-METHODS-0011",
                f"다른 규격({other.code})의 옛 번호와 같은 번호. "
                "그 규격과 합칠지 먼저 확인 필요.",
                details={"method_id": str(other.id)},
            )


def _change_code(db: Session, user: User, row: TestMethod, code: str) -> str | None:
    """번호를 바꾼다 — **시스템 관리자만.** 옛 번호를 `former_codes` 에 남기고 돌려준다
    (안 바뀌었으면 None).

    규격은 여러 부서와 카탈로그가 함께 가리키는 열쇠라 번호를 고치는 자격을 좁힌다. 제목이
    번호 그대로였으면(반입이 만든 규격) 제목도 새 번호로 바꾼다 — 안 바꾸면 옛 번호가 제목으로
    보인다.
    """
    if not user.is_system_admin:
        raise Forbidden("TSC-METHODS-0010", "규격 번호 수정은 시스템 관리자 전용.")
    code = clean(code)
    if not code:
        raise AppError("TSC-METHODS-0012", "규격 번호 입력 필요.", status=400)
    old = row.code
    if code == old:
        return None
    former = [one for one in row.former_codes or [] if method_key(one) != method_key(code)]
    if method_key(old) != method_key(code) and old not in former:
        former.append(old)
    row.former_codes = former
    if row.title == old:
        row.title = code
    row.code = code
    return old


def _rekey_review(db: Session, row: TestMethod) -> None:
    """검토함의 규격 물음 줄을 새 번호로 옮긴다 — 열쇠가 번호라 안 옮기면 그 줄이 「규격이
    지워짐」 으로 닫히고, 새 번호로 같은 물음이 또 선다."""
    key = method_key(row.code)
    label = row.code if row.title == row.code else f"{row.code} — {row.title}"
    for proposal in db.scalars(
        select(ReviewProposal).where(
            ReviewProposal.queue == "method_test_items", ReviewProposal.subject_id == row.id
        )
    ):
        clash = db.scalar(
            select(ReviewProposal.id).where(
                ReviewProposal.queue == "method_test_items",
                ReviewProposal.subject_key == key,
                ReviewProposal.id != proposal.id,
            )
        )
        if clash is None:
            proposal.subject_key = key
        proposal.subject_label = label


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


def set_test_items(db: Session, method_id: uuid.UUID, term_ids: list[uuid.UUID]) -> list[str]:
    """**통째로** 바꾼다. 같은 값이 두 번 와도 한 줄만 남는다. 끊긴 계열 이름을 돌려준다.

    **빠진 항목으로 걸린 계열 연결도 걷는다.** 전에는 규격의 항목만 바뀌고 그 항목으로 이어진
    계열 연결은 남아, 잘못 걸린 항목을 고쳐도 검색이 옛 항목으로 그 규격을 찾았다
    (2026-10-13). 다른 항목으로도 이어진 계열은 그대로 남고, 그것으로만 이어졌던 계열은
    「인용했는데 항목 미정」 으로 돌아간다 — 인용했다는 사실은 잃지 않는다.
    """
    wanted = list(dict.fromkeys(term_ids))
    before = set(item_ids(db, method_id))
    cut, _ = detach_split(db, method_id, before - set(wanted))
    _unlink_items(db, method_id, before - set(wanted), cut)
    for link in db.scalars(
        select(TestMethodItem).where(TestMethodItem.method_id == method_id)
    ):
        db.delete(link)
    db.flush()
    for term_id in wanted:
        db.add(TestMethodItem(method_id=method_id, test_item_term_id=term_id))
    db.flush()
    return [one.name for one in cut]


def detach_split(
    db: Session, method_id: uuid.UUID, gone: set[uuid.UUID]
) -> tuple[list[EquipmentSeries], list[EquipmentSeries]]:
    """이 항목들을 규격에서 빼면 (**끊기는** 계열, 다른 항목으로 **남는** 계열).

    끊기는 계열 = 빠질 항목으로만 이 규격에 이어진 계열. 그 계열의 장비는 빼고 나면 이 규격으로
    검색되지 않는다 — 빼기 전에 사람에게 보여 준다.
    """
    if not gone:
        return [], []
    via: dict[uuid.UUID, set[uuid.UUID]] = {}
    for series_id, term_id in db.execute(
        select(SeriesTestItem.series_id, SeriesTestItem.test_item_term_id)
        .join(
            SeriesTestItemMethod, SeriesTestItemMethod.series_test_item_id == SeriesTestItem.id
        )
        .where(SeriesTestItemMethod.method_id == method_id)
    ):
        via.setdefault(series_id, set()).add(term_id)
    touched = [series_id for series_id, terms in via.items() if terms & gone]
    if not touched:
        return [], []
    cut: list[EquipmentSeries] = []
    kept: list[EquipmentSeries] = []
    for series in db.scalars(
        select(EquipmentSeries)
        .where(EquipmentSeries.id.in_(touched), EquipmentSeries.deleted_at.is_(None))
        .order_by(EquipmentSeries.name)
    ):
        (kept if via[series.id] - gone else cut).append(series)
    return cut, kept


def _unlink_items(
    db: Session, method_id: uuid.UUID, gone: set[uuid.UUID], cut: list[EquipmentSeries]
) -> None:
    """빠질 항목으로 걸린 계열 연결을 걷고, 끊기는 계열은 항목 미정 인용으로 되돌린다."""
    if not gone:
        return
    for link in db.scalars(
        select(SeriesTestItemMethod)
        .join(SeriesTestItem, SeriesTestItem.id == SeriesTestItemMethod.series_test_item_id)
        .where(
            SeriesTestItemMethod.method_id == method_id,
            SeriesTestItem.test_item_term_id.in_(gone),
        )
    ):
        db.delete(link)
    pending = set(
        db.scalars(
            select(SeriesPendingMethod.series_id).where(
                SeriesPendingMethod.method_id == method_id
            )
        )
    )
    for series in cut:
        if series.id not in pending:
            db.add(SeriesPendingMethod(series_id=series.id, method_id=method_id))
    db.flush()


def detach_preview(
    db: Session, user: User, method_id: uuid.UUID, term_id: uuid.UUID
) -> DetachImpact:
    """해제하기 **전에** 끊기는 계열 · 남는 계열."""
    row = get_method(db, user, method_id)
    if term_id not in set(item_ids(db, row.id)):
        raise NotFound("TSC-METHODS-0015", "이 규격에 걸린 시험 항목이 아님.")
    cut, kept = detach_split(db, row.id, {term_id})
    return DetachImpact(cut=[one.name for one in cut], kept=[one.name for one in kept])


def detach_test_item(
    db: Session, user: User, method_id: uuid.UUID, term_id: uuid.UUID, reason: str
) -> DetachImpact:
    """규격에 **잘못 걸린 시험 항목을 뗀다** — 시스템 관리자, 사유는 감사 기록에 남는다.

    전에는 뗄 길이 없었다 — 화면은 더하기만 했고 검토함은 결정한 줄을 다시 열어도 걸린 항목이
    그대로였다(2026-10-13). 그 항목으로만 이어진 계열은 항목 미정 인용으로 돌아간다. 항목이
    하나도 안 남으면 검토함의 결정 줄을 다시 연다 — 물음이 다시 살아 있어야 누가 정한다.
    """
    if not user.is_system_admin:
        raise Forbidden("TSC-METHODS-0016", "규격의 시험 항목 해제는 시스템 관리자 전용.")
    said = reason.strip()
    if not said:
        raise AppError("TSC-METHODS-0017", "해제 사유 필요.", status=400)
    row = get_method(db, user, method_id)
    have = item_ids(db, row.id)
    if term_id not in set(have):
        raise NotFound("TSC-METHODS-0015", "이 규격에 걸린 시험 항목이 아님.")
    term = db.get(VocabularyTerm, term_id)
    _, kept = detach_split(db, row.id, {term_id})
    cut = set_test_items(db, row.id, [one for one in have if one != term_id])
    reopened = False
    if len(have) == 1:
        decided = db.scalar(
            select(ReviewProposal).where(
                ReviewProposal.queue == "method_test_items",
                ReviewProposal.subject_id == row.id,
                ReviewProposal.status == "decided",
            )
        )
        if decided is not None:
            decided.status = "open"
            decided.note = (
                f"시험 항목 해제로 다시 열림. 이전 결정: {decided.choice} "
                f"({decided.decided_by_label})"
            )
            decided.choice = None
            decided.followed = None
            decided.decided_by_id = None
            decided.decided_by_label = None
            decided.decided_at = None
            reopened = True
    audit.record(
        db,
        action=audit.METHOD_TEST_ITEM_DETACHED,
        actor=user,
        target_table="test_methods",
        target_id=row.id,
        target_label=f"{row.code} {row.edition or ''}".strip(),
        workspace_id=row.owner_workspace_id,
        changes={
            "test_item": term.value if term else str(term_id),
            "reason": said,
            "cut_series": cut,
            "kept_series": [one.name for one in kept],
            "review_reopened": reopened,
        },
        reason=said,
    )
    db.commit()
    return DetachImpact(cut=cut, kept=[one.name for one in kept], reopened=reopened)


def _refuse_machine_decision(db: Session, row: TestMethod) -> None:
    """검토함에 열린 물음이 있는 규격의 시험 항목은 **기계 자격으로 직접 못 정한다.**

    규격의 시험 항목을 직접 고치는 길로 가면 결과는 확정과 같은데(인용한 계열에 붙는다)
    **검토함 줄만 open 으로 남는다** — 정한 기록도, 추천을 따랐는지도 안 남는다. 실측:
    「검토함 첫 줄 추천대로 확정해줘」 에 AI 가 정확히 이 우회로를 썼다(2026-09-20, q22).
    시스템 관리자의 토큰은 이제 검토함에서 정할 수 있으므로(2026-10-04) 그 길로 보낸다.
    사람 세션은 막지 않는다 — 그 사람의 권한이 이미 한계다.
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
            "이 규격에 대한 검토함 질문이 열려 있음. "
            "시험 항목은 검토함에서 결정(decide_review_item).",
        )


def update(
    db: Session, user: User, method_id: uuid.UUID, changes: dict[str, Any]
) -> TestMethod:
    row = get_method(db, user, method_id)
    require_owner_edit(db, user, row.owner_workspace_id, what=_WHAT, code=_CODE)

    edition = changes.get("edition", row.edition)
    renamed: str | None = None
    if changes.get("code") is not None:
        _ensure_unique(db, row, clean(changes["code"]), edition)
        renamed = _change_code(db, user, row, changes["code"])
    elif "edition" in changes and edition != row.edition:
        # 판만 바꿔도 (번호, 판)이 겹칠 수 있다 — 유일 제약에 걸려 500 이 되기 전에 말한다.
        _ensure_unique(db, row, row.code, edition)
    for field in _PLAIN_FIELDS:
        if field in changes:
            setattr(row, field, changes[field])
    if renamed is not None:
        _rekey_review(db, row)
        audit.record(
            db,
            action=audit.METHOD_CODE_CHANGED,
            actor=user,
            target_table="test_methods",
            target_id=row.id,
            target_label=f"{row.code} {row.edition or ''}".strip(),
            workspace_id=row.owner_workspace_id,
            changes={"code": {"before": renamed, "after": row.code}},
        )
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


def link_citations(db: Session, user: User, method_id: uuid.UUID) -> LinkCitationsResult:
    """안 이어진 인용 계열에 규격의 시험 항목을 더해 잇는다 — 시스템 관리자."""
    if not user.is_system_admin:
        raise Forbidden("TSC-METHODS-0013", "인용 계열에 시험 항목 추가는 시스템 관리자 전용.")
    row = get_method(db, user, method_id)
    if not item_ids(db, row.id):
        raise AppError(
            "TSC-METHODS-0014",
            "규격의 시험 항목이 아직 없음. 시험 항목을 먼저 지정 필요.",
            status=400,
        )
    added = add_items_to_citing(db, row)
    _, unlinked = citing_split(db, row.id, item_ids(db, row.id))
    if added:
        audit.record(
            db,
            action=audit.METHOD_CITATIONS_LINKED,
            actor=user,
            target_table="test_methods",
            target_id=row.id,
            target_label=f"{row.code} {row.edition or ''}".strip(),
            changes={"added_to_series": added},
        )
    db.commit()
    return LinkCitationsResult(added_to=added, still_unlinked=len(unlinked))


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
            f"이 시험법을 참조하는 시험 항목 {using}건 있음. "
            f"삭제 대신 상태를 대체됨으로 변경 필요.",
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


def merge_by_admin(
    db: Session, user: User, source_id: uuid.UUID, target_id: uuid.UUID, reason: str
) -> TestMethod:
    """규격 상세의 「다른 규격으로 병합」 — 시스템 관리자. 사유는 감사 기록에 남는다.

    검토함에서 더한 규격이 카탈로그의 같은 규격과 표기만 달라 둘이 서도 합칠 길이 검토함의
    정본 줄뿐이었다(2026-10-13). 지운 쪽의 번호는 남는 쪽의 옛 번호가 된다 — 반입 · 검색 ·
    검토함이 그 번호로 와도 남는 쪽을 찾는다.
    """
    if not user.is_system_admin:
        raise Forbidden("TSC-METHODS-0018", "규격 병합은 시스템 관리자 전용.")
    source = get_method(db, user, source_id)
    target = get_method(db, user, target_id)
    if source.id == target.id:
        raise AppError("TSC-METHODS-0019", "같은 규격으로는 병합 불가.", status=400)
    merge_into(db, user, source.id, target.id, reason=reason.strip() or None)
    db.commit()
    db.refresh(target)
    return target


def merge_into(
    db: Session,
    actor: User | None,
    source_id: uuid.UUID,
    target_id: uuid.UUID,
    *,
    reason: str | None = None,
) -> TestMethod:
    """표기만 다른 규격 둘을 하나로. **인용·요구 조건·장비 시험 항목이 남는 쪽으로 옮겨 가고**
    원래 줄은 소프트 삭제된다.

    같은 자리에 이미 이어져 있으면 옮기지 않고 버린다(유일 제약). 요구 조건은 남는 쪽에 그
    축이 없을 때만 옮긴다 — 남는 쪽 값이 더 낫다고 본다(사람이 봤을 가능성이 높다).
    """
    source = db.get(TestMethod, source_id)
    target = db.get(TestMethod, target_id)
    if source is None or target is None or source.id == target.id:
        raise NotFound("TSC-METHODS-0005", "병합할 규격을 찾을 수 없음.")
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
        reason=reason,
    )
    # **지운 쪽 번호는 옛 번호로 남는다** — 반입 · 검색 · 검토함이 그 번호로 와도 남는 쪽을
    # 찾게(번호 고치기와 같은 규칙).
    known = {method_key(one) for one in [target.code, *(target.former_codes or [])]}
    for code in [source.code, *(source.former_codes or [])]:
        if method_key(code) not in known:
            target.former_codes = [*(target.former_codes or []), code]
            known.add(method_key(code))
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
        raise NotFound("TSC-METHODS-0005", "조건 정의를 찾을 수 없음.")

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
        raise NotFound("TSC-METHODS-0006", "요구 조건을 찾을 수 없음.")
    db.delete(target)
    db.commit()

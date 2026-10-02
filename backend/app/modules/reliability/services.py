"""신뢰성 시험 — 읽기는 로그인한 누구나, 쓰기는 그 부서의 관리자와 시스템 관리자.

**그리고 기계 자격(PAT)으로 들어온 쓰기는 후보가 된다**(ADR 0009). AI 는 시험 표준서를
읽어 스물두 칸을 한 번에 채울 수 있는데, 틀려도 그만큼 빠르다 — 그 값으로 장비를 고르고
그 장비로 보고서가 나간다. 사람이 읽고 확인해야 확정이다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, or_, select, true, tuple_
from sqlalchemy.orm import Session, aliased

from app.modules.accounts.models import User
from app.modules.attachments import services as attachments
from app.modules.attachments.models import Attachment
from app.modules.attributes import filters as attribute_filters
from app.modules.attributes import services as attributes
from app.modules.attributes.models import AttributeDefinition, AttributeValue
from app.modules.attributes.schemas import AttributeValueIn
from app.modules.documents import services as documents
from app.modules.documents.models import SpecDocument, SpecDocumentRevision
from app.modules.equipment.models import Equipment
from app.modules.reliability.models import ReliabilityTest, ReliabilityTestItem
from app.modules.reliability.schemas import (
    DivisionOut,
    ReliabilityTestItemOut,
    ReliabilityTestOut,
    RevisionBriefOut,
    RevisionChangedOut,
    RevisionCompareOut,
    RevisionDifferenceOut,
    RevisionTestBriefOut,
    SiblingTestOut,
)
from app.modules.test_items.models import EquipmentTestItem
from app.modules.vocabulary.models import Vocabulary, VocabularyTerm
from app.shared import audit
from app.shared.errors import AppError, Conflict, Forbidden, NotFound
from app.shared.pagination import MAX_LIMIT, Page, clamp_limit
from app.shared.permissions import (
    division_map,
    my_division_term_ids,
    visible_equipment_ids,
)
from app.shared.request_context import get_actor_token
from app.shared.text import compare_key

#: 사업부 축의 slug. 코드가 축을 이 이름으로 건다.
DIVISION_AXIS = "division"

CANDIDATE = "candidate"
CONFIRMED = "confirmed"


def _machine() -> str | None:
    """기계 자격으로 들어온 요청이면 그 토큰 이름. 사람 세션이면 None.

    **`user` 로는 못 가른다** — PAT 의 소유자도 사람이라 `created_by` 는 같은 값이 된다.
    통로를 아는 곳은 인증 의존성뿐이고, 그것이 `request_context` 에 남긴다.
    """
    return get_actor_token()


def _can_edit(db: Session, user: User, division_term_id: uuid.UUID) -> bool:
    """**그 사업부에 속한 부서의 관리자**인가. 시스템 관리자는 전부.

    부서가 아니라 사업부로 묻는다 — HE팀 관리자가 MX 사업부의 시험을 고친다.
    """
    if user.is_system_admin:
        return True
    return division_term_id in my_division_term_ids(db, user)


def _equipment_counts(
    db: Session, user: User, division_term_id: uuid.UUID, term_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """시험 항목마다 **이 사업부의** 장비 수 — 사업부에 속한 부서 전부를 합친다.

    시험이 사업부의 것이 된 뒤로 「이 팀에 없다」 는 답이 되지 않는다. 장비는 여전히
    팀이 갖지만(실물이라 놓인 팀이 갖는 것이 맞다), 세는 단위는 사업부다.
    """
    if not term_ids:
        return {}
    in_division = [wid for wid, found in division_map(db).items() if found == division_term_id]
    if not in_division:
        return {}
    owned = visible_equipment_ids(db, user).where(
        Equipment.owner_workspace_id.in_(in_division)
    )
    rows = db.execute(
        select(
            EquipmentTestItem.test_item_term_id,
            func.count(func.distinct(EquipmentTestItem.equipment_id)),
        )
        .where(
            EquipmentTestItem.equipment_id.in_(owned),
            EquipmentTestItem.test_item_term_id.in_(term_ids),
        )
        .group_by(EquipmentTestItem.test_item_term_id)
    ).all()
    return {term_id: int(count) for term_id, count in rows}


def _items_of(db: Session, test_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[VocabularyTerm]]:
    out: dict[uuid.UUID, list[VocabularyTerm]] = {one: [] for one in test_ids}
    if not test_ids:
        return out
    for test_id, term in db.execute(
        select(ReliabilityTestItem.reliability_test_id, VocabularyTerm)
        .join(VocabularyTerm, VocabularyTerm.id == ReliabilityTestItem.test_item_term_id)
        .where(ReliabilityTestItem.reliability_test_id.in_(test_ids))
        .order_by(VocabularyTerm.value)
    ).all():
        out[test_id].append(term)
    return out


def _outs(db: Session, user: User, rows: list[ReliabilityTest]) -> list[ReliabilityTestOut]:
    """목록 하나를 질의 몇 번으로 — 줄마다 세면 부서 하나에 시험 50건이 질의 150번이 된다."""
    if not rows:
        return []
    division_ids = {r.division_term_id for r in rows}
    divisions = {
        one.id: one
        for one in db.scalars(
            select(VocabularyTerm).where(VocabularyTerm.id.in_(division_ids))
        )
    }
    items = _items_of(db, [r.id for r in rows])
    attribute_values = attributes.values_of(
        db, target="reliability_test", object_ids=[r.id for r in rows]
    )
    counts_by_division: dict[uuid.UUID, dict[uuid.UUID, int]] = {}
    for division_id in divisions:
        term_ids = sorted(
            {t.id for r in rows if r.division_term_id == division_id for t in items[r.id]}
        )
        counts_by_division[division_id] = _equipment_counts(db, user, division_id, term_ids)
    editable = {did: _can_edit(db, user, did) for did in divisions}
    # 확인한 사람의 이름 — **한 번에** 받는다. 줄마다 찾으면 목록 하나가 질의 스무 번이 된다.
    confirmers = {
        one.id: one.display_name
        for one in db.scalars(
            select(User).where(
                User.id.in_({r.confirmed_by_id for r in rows if r.confirmed_by_id})
            )
        )
    }
    # **한 번에 센다** — 줄마다 세면 스무 줄에 스무 번 왕복한다.
    shots = {
        object_id: count
        for object_id, count in db.execute(
            select(Attachment.object_id, func.count())
            .where(
                Attachment.target == "reliability_test",
                Attachment.object_id.in_([row.id for row in rows]),
            )
            .group_by(Attachment.object_id)
        ).all()
    }
    # 판 이름도 **한 번에** — id 만 오면 사람이 못 읽는다.
    labels = {
        one.id: one.label
        for one in db.scalars(
            select(SpecDocumentRevision).where(
                SpecDocumentRevision.id.in_(
                    {r.document_revision_id for r in rows if r.document_revision_id}
                )
            )
        )
    }
    out: list[ReliabilityTestOut] = []
    for row in rows:
        division = divisions[row.division_term_id]
        counts = counts_by_division[row.division_term_id]
        out.append(
            ReliabilityTestOut(
                id=row.id,
                division_code=division.code or "",
                division_name=division.value,
                name=row.name,
                purpose=row.purpose,
                document_revision_id=row.document_revision_id,
                document_revision_label=labels.get(row.document_revision_id)
                if row.document_revision_id
                else None,
                status=row.status,
                submitted_via=row.submitted_via,
                confirmed_by=confirmers.get(row.confirmed_by_id)
                if row.confirmed_by_id
                else None,
                confirmed_at=row.confirmed_at,
                test_items=[
                    ReliabilityTestItemOut(
                        term_id=t.id, value=t.value, equipment_count=counts.get(t.id, 0)
                    )
                    for t in items[row.id]
                ],
                attributes=attribute_values[row.id],
                attachment_count=shots.get(row.id, 0),
                can_edit=editable[row.division_term_id],
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
        )
    return out


def test_out(db: Session, user: User, row: ReliabilityTest) -> ReliabilityTestOut:
    return _outs(db, user, [row])[0]


def _by_status(
    stmt: Select[tuple[ReliabilityTest]], status: str | None, *, default: str
) -> Select[tuple[ReliabilityTest]]:
    """`candidate` · `confirmed` · `all`. 안 주면 부르는 쪽의 기본값."""
    picked = status or default
    if picked == "all":
        return stmt
    return stmt.where(ReliabilityTest.status == picked)


def list_for_division(
    db: Session,
    user: User,
    code: str,
    attrs: list[str] | None = None,
    status: str | None = None,
    document_id: uuid.UUID | None = None,
    revision_id: uuid.UUID | None = None,
    limit: int = MAX_LIMIT,
    offset: int = 0,
    query: str | None = None,
    rows: RowFilters | None = None,
    include_superseded: bool = False,
) -> Page[ReliabilityTestOut]:
    """그 사업부의 시험 — **후보까지 보인다.** 후보를 검토하는 자리가 여기다.

    후보가 먼저 온다. 목록 아래쪽에 섞여 있으면 아무도 안 본다.

    **쪽으로 끊는다.** 운영에서 한 사업부에 1784건이 들어왔고, 그것을 한 화면에 통째로
    그리면 브라우저가 멎는다 — 줄마다 속성과 시험 항목과 장비 수가 딸려 오므로 응답부터
    무겁다(2026-09-30)."""
    division = division_by_code(db, code)
    stmt = (
        select(ReliabilityTest)
        .where(
            ReliabilityTest.division_term_id == division.id,
            ReliabilityTest.deleted_at.is_(None),
        )
        # 후보(candidate)가 확정(confirmed)보다 앞 — 글자 순이 마침 그렇다.
        .order_by(ReliabilityTest.status, ReliabilityTest.name)
    )
    narrowed = _by_text(
        _latest_only(
            _by_revision(
                _by_document(_by_status(stmt, status, default="all"), document_id),
                revision_id,
            ),
            # 판을 집어 물었으면 그 판을 보여 준다 — 대개 지난 판이라 가리면 늘 0건이다.
            include_superseded or revision_id is not None,
        ),
        query,
    )
    return _page(
        db, user, _by_rows(db, user, _by_attributes(db, narrowed, attrs), rows), limit, offset
    )


def _page(
    db: Session,
    user: User,
    stmt: Select[tuple[ReliabilityTest]],
    limit: int,
    offset: int,
) -> Page[ReliabilityTestOut]:
    """한 쪽만 만든다 — **자르고 나서 살을 붙인다.**

    `_outs` 는 줄마다 시험 항목·장비 수·첨부 수를 붙인다. 전부 붙인 뒤 자르면 1784건에
    그 일을 다 하고 쉰 건만 보내는 셈이라, 쪽을 나눈 뜻이 없어진다.
    """
    total = int(
        db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    )
    rows = list(db.scalars(stmt.limit(clamp_limit(limit)).offset(max(0, offset))))
    return Page(
        items=_outs(db, user, rows),
        total=total,
        limit=clamp_limit(limit),
        offset=max(0, offset),
    )


def _by_text(
    stmt: Select[tuple[ReliabilityTest]], query: str | None
) -> Select[tuple[ReliabilityTest]]:
    """이름·목적에 든 글자로 좁힌다.

    **쪽을 나누면 찾기도 서버가 해야 한다.** 화면 안에서 훑으면 지금 쪽의 쉰 줄만 뒤지고,
    사람은 「없다」 로 읽는다 — 1784건 중 뒤쪽에 있는 줄은 영영 안 걸린다.
    """
    said = (query or "").strip()
    if not said:
        return stmt
    like = f"%{said}%"
    return stmt.where(ReliabilityTest.name.ilike(like) | ReliabilityTest.purpose.ilike(like))


@dataclass(frozen=True)
class RowFilters:
    """표의 **속성 아닌 열**로 거르기 — 이름 · 목적 · 시험 항목 · 보유 장비.

    속성에는 `attr` 문법이 있는데 이 넷에는 없었다. 그래서 1784건에서 「목적을 안 적은 줄」
    을 찾으려면 서른여섯 쪽을 눈으로 훑어야 했다 — **화면이 열로 보여 주는 것은 열로 거를
    수 있어야 한다.**

    `none` 은 「안 적힌 것」 이다(목적 · 시험 항목 · 보유 장비). 채워야 할 자리를 찾는
    물음이라 실제로 가장 자주 쓰인다 — 속성의 `!*` 와 같은 쓸모다.
    """

    name: str | None = None
    purpose: str | None = None
    test_item: str | None = None
    equipment: str | None = None


#: 「안 적힘」 을 묻는 말. 목록 API 가 이미 `test_item=none` · `models=none` 으로 쓰고 있다 —
#: 한 시스템 안에서 같은 물음은 같은 말이라야 한다.
NONE = "none"


def _by_rows(
    db: Session,
    user: User,
    stmt: Select[tuple[ReliabilityTest]],
    rows: RowFilters | None,
) -> Select[tuple[ReliabilityTest]]:
    """속성 아닌 열의 조건을 한 번에 — 여러 개면 **모두** 만족해야 한다(속성과 같다)."""
    if rows is None:
        return stmt
    return _by_equipment(
        db,
        user,
        _by_item(_by_purpose(_by_name(stmt, rows.name), rows.purpose), rows.test_item),
        rows.equipment,
    )


def _by_name(
    stmt: Select[tuple[ReliabilityTest]], said: str | None
) -> Select[tuple[ReliabilityTest]]:
    """이름에 든 글자. `q` 와 달리 **이름만** 본다 — 「목적에 걸린 것까지 왜 나오나」 를
    묻게 하지 않는다."""
    want = (said or "").strip()
    return stmt if not want else stmt.where(ReliabilityTest.name.ilike(f"%{want}%"))


def _by_purpose(
    stmt: Select[tuple[ReliabilityTest]], said: str | None
) -> Select[tuple[ReliabilityTest]]:
    """목적에 든 글자, 또는 `none` 으로 **목적이 빈 줄.**

    빈 글자와 NULL 을 함께 본다 — 칸은 NOT NULL 이라 안 적으면 빈 글자로 들어오는데,
    한쪽만 보면 같은 「안 적음」 이 둘로 갈려 수가 안 맞는다.
    """
    want = (said or "").strip()
    if not want:
        return stmt
    if want == NONE:
        return stmt.where(
            or_(
                ReliabilityTest.purpose.is_(None),
                func.trim(ReliabilityTest.purpose) == "",
            )
        )
    return stmt.where(ReliabilityTest.purpose.ilike(f"%{want}%"))


def _by_item(
    stmt: Select[tuple[ReliabilityTest]], said: str | None
) -> Select[tuple[ReliabilityTest]]:
    """시험 항목 이름에 든 글자, 또는 `none` 으로 **하나도 안 정한 줄.**

    「안 정함」 은 「장비 없음」 과 다르다 — 앞은 시험 항목을 아직 안 이은 것이고, 뒤는
    이었는데 그 항목이 되는 장비가 그 사업부에 없는 것이다. 해야 할 일이 다르다.
    """
    want = (said or "").strip()
    if not want:
        return stmt
    mine = select(ReliabilityTestItem.id).where(
        ReliabilityTestItem.reliability_test_id == ReliabilityTest.id
    )
    if want == NONE:
        return stmt.where(~mine.exists())
    named = mine.join(
        VocabularyTerm, VocabularyTerm.id == ReliabilityTestItem.test_item_term_id
    ).where(VocabularyTerm.value.ilike(f"%{want}%"))
    return stmt.where(named.exists())


def _by_equipment(
    db: Session,
    user: User,
    stmt: Select[tuple[ReliabilityTest]],
    said: str | None,
) -> Select[tuple[ReliabilityTest]]:
    """`none` — **그 사업부에 돌릴 장비가 한 대도 없는 시험.**

    목록이 줄마다 「0대」 를 노랗게 적고 있는데 그것으로 좁힐 길이 없었다. 1784건에서 0대인
    줄을 찾으려면 서른여섯 쪽을 눈으로 훑어야 했다 — 그러면 아무도 안 찾는다.

    **(사업부, 시험 항목) 짝으로 본다.** 같은 항목이라도 저 사업부에는 장비가 있고 이
    사업부에는 없다 — 항목만 보면 「어딘가에는 있다」 를 「우리가 할 수 있다」 로 읽는다.
    짝은 파이썬에서 모은다: 부서의 사업부는 조직도를 거슬러 정해지므로(`division_map`)
    SQL 안에 그 규칙이 없다.
    """
    if (said or "").strip() != NONE:
        return stmt
    by_workspace = division_map(db)
    pairs = db.execute(
        select(Equipment.owner_workspace_id, EquipmentTestItem.test_item_term_id)
        .join(EquipmentTestItem, EquipmentTestItem.equipment_id == Equipment.id)
        .where(Equipment.id.in_(visible_equipment_ids(db, user)))
        .distinct()
    ).all()
    covered = {
        (by_workspace[workspace_id], term_id)
        for workspace_id, term_id in pairs
        if by_workspace.get(workspace_id) is not None
    }
    if not covered:
        # 볼 수 있는 장비가 하나도 없으면 **전부**가 「돌릴 장비 없음」 이다.
        return stmt
    # 바깥 쿼리의 `ReliabilityTest` 와 **다른 이름**으로 든다 — 같은 이름이면 상관 하위
    # 쿼리가 되어 「자기 자신인 줄」 만 보고, 조건이 통째로 무너진다.
    inner = aliased(ReliabilityTest)
    able = (
        select(ReliabilityTestItem.reliability_test_id)
        .join(inner, inner.id == ReliabilityTestItem.reliability_test_id)
        .where(
            tuple_(inner.division_term_id, ReliabilityTestItem.test_item_term_id).in_(
                sorted(covered)
            )
        )
    )
    return stmt.where(~ReliabilityTest.id.in_(able))


def _latest_only(
    stmt: Select[tuple[ReliabilityTest]], include_superseded: bool
) -> Select[tuple[ReliabilityTest]]:
    """**기본은 최신판만.** 판마다 줄이 서므로(0049) 안 가리면 목록이 판 수만큼 부푼다.

    「개정 14의 열충격」 과 「개정 18의 열충격」 은 다른 줄인데, 사람이 목록에서 찾는 것은
    대개 지금 쓰는 판 하나다. 지난 판은 「과거 판 포함」 으로 펼치거나 `revision=` 으로
    그 판을 집어 본다 — 집어 볼 때는 가리면 안 되므로 그쪽이 이 필터를 끈다.
    """
    if include_superseded:
        return stmt
    return stmt.where(ReliabilityTest.superseded_by_id.is_(None))


def _by_document(
    stmt: Select[tuple[ReliabilityTest]], document_id: uuid.UUID | None
) -> Select[tuple[ReliabilityTest]]:
    """그 사내 규격서를 가리키는 시험만 — **문서 단위로 검토하려는 자리다.**

    한 문서에서 뽑힌 줄들은 **같은 실수를 함께 한다**(옮겨 적은 사람도 AI 도 한 번에
    읽었다). 스무 건을 스무 개의 따로 난 일로 보면 그 결이 안 보이고, 한 건씩 판단하다
    같은 오답을 스무 번 통과시킨다.
    """
    if document_id is None:
        return stmt
    return stmt.where(
        ReliabilityTest.id.in_(
            select(AttributeValue.reliability_test_id).where(
                AttributeValue.ref_document_id == document_id,
                AttributeValue.is_current.is_(True),
            )
        )
    )


def _by_revision(
    stmt: Select[tuple[ReliabilityTest]], revision_id: uuid.UUID | None
) -> Select[tuple[ReliabilityTest]]:
    """**「이 판의 목록」** — 그 판의 줄, 또는 그 판에서 값이 적힌 줄.

    판이 자리가 된 뒤로(0049) 줄 자체가 판을 갖는다. 그런데 0046 때 들어온 줄은 한 줄에
    여러 판의 값을 들고 있으므로 **둘 다 본다** — 값으로만 보면 조건을 안 적은 줄이
    자기 판의 목록에서 빠지고, 줄로만 보면 옛 데이터가 통째로 안 걸린다.
    """
    if revision_id is None:
        return stmt
    return stmt.where(
        or_(
            ReliabilityTest.document_revision_id == revision_id,
            ReliabilityTest.id.in_(
                select(AttributeValue.reliability_test_id).where(
                    AttributeValue.document_revision_id == revision_id
                )
            ),
        )
    )


def _by_attributes(
    db: Session, stmt: Select[tuple[ReliabilityTest]], attrs: list[str] | None
) -> Select[tuple[ReliabilityTest]]:
    """속성 값으로 거르기 — 「-40 °C 이하로 내려가는 시험」 을 못 물으면 조건을 적을 이유가
    없다. 문법은 장비·계열·규격 목록과 같은 것 하나다(`attributes/filters.py`)."""
    return attribute_filters.apply(
        db,
        stmt,
        "reliability_test",
        ReliabilityTest.id,
        attribute_filters.parse(db, "reliability_test", attrs or []),
    )


def list_all(
    db: Session,
    user: User,
    attrs: list[str] | None = None,
    status: str | None = None,
    document_id: uuid.UUID | None = None,
    revision_id: uuid.UUID | None = None,
    limit: int = MAX_LIMIT,
    offset: int = 0,
    query: str | None = None,
    rows: RowFilters | None = None,
    include_superseded: bool = False,
) -> Page[ReliabilityTestOut]:
    """전사의 신뢰성 시험 — **「저 부서는 무슨 시험을 하나」 를 부서를 가로질러 묻는 표.**
    읽기는 누구나(부서를 가로지르는 것이 이 시스템의 물음), 고치기는 각 부서 화면에서.
    부서 순서(조직도) → 이름.

    **기본은 확정된 것만이다.** 이 표는 「저 부서가 무슨 시험을 하나」 에 답하는데, 아직
    확인 안 된 후보는 그 답이 아니다 — 옆 부서 사람은 배지를 안 보고 읽는다. 후보는 그
    부서 화면에서 보고, 여기서는 `status="all"` 로 일부러 열어야 보인다."""
    stmt = (
        select(ReliabilityTest)
        .join(VocabularyTerm, VocabularyTerm.id == ReliabilityTest.division_term_id)
        .where(ReliabilityTest.deleted_at.is_(None))
        .order_by(VocabularyTerm.sort_order, VocabularyTerm.value, ReliabilityTest.name)
    )
    narrowed = _by_text(
        _latest_only(
            _by_revision(
                _by_document(_by_status(stmt, status, default=CONFIRMED), document_id),
                revision_id,
            ),
            include_superseded or revision_id is not None,
        ),
        query,
    )
    return _page(
        db, user, _by_rows(db, user, _by_attributes(db, narrowed, attrs), rows), limit, offset
    )


def get(db: Session, test_id: uuid.UUID) -> ReliabilityTest:
    row = db.get(ReliabilityTest, test_id)
    if row is None or row.deleted_at is not None:
        raise NotFound("TSC-RELIABILITY-0001", "신뢰성 시험을 찾을 수 없습니다.")
    return row


def _check_test_item_terms(db: Session, term_ids: list[uuid.UUID]) -> None:
    """**시험 항목 축의 살아 있는 값만** 받는다. 다른 축의 id 를 받아 두면 화면이
    「인장」 자리에 「3동」 을 그린다."""
    if not term_ids:
        return
    axis = db.scalar(select(Vocabulary).where(Vocabulary.slug == "test_item"))
    if axis is None:
        raise AppError("TSC-RELIABILITY-0002", "시험 항목 축이 없습니다.")
    valid = set(
        db.scalars(
            select(VocabularyTerm.id).where(
                VocabularyTerm.vocabulary_id == axis.id,
                VocabularyTerm.id.in_(term_ids),
                VocabularyTerm.status == "active",
            )
        )
    )
    missing = [str(one) for one in term_ids if one not in valid]
    if missing:
        raise AppError(
            "TSC-RELIABILITY-0002",
            "시험 항목이 아니거나 없는 값이 있습니다.",
            details={"term_ids": missing},
        )


def name_key(name: str) -> str:
    """이름의 비교키 — **띄어쓰기까지 지운다.**

    `lower()` 만으로는 「고온고습 1000h」 와 「고온고습1000h」 가 다른 시험이 된다. 사람이
    하나씩 적을 때는 드문 일이지만, **수백 건을 적재하면 동명이 쌓인다** — 옮겨 적는 쪽이
    문서마다 띄어쓰기를 다르게 읽기 때문이다. 둘이 서고 나면 어느 쪽이 정본인지 아무도
    모르고, 「이 시험 되는 장비」 가 절반만 답한다.

    전각·반각도 모은다(`compare_key` 의 NFKC) — 전각으로 친 ASTM 과 반각 ASTM 이 갈리지 않게.
    속성 이름이 쓰는 규칙(`_attribute_name_key`)과 같은 것이다.
    """
    return "".join(compare_key(name).split())


#: 이름이 같아도 **다른 시험으로 가르는** 칸.
PRODUCT_GROUP_KEY = "reliability_product_group"
SPEC_DOCUMENT_KEY = "reliability_spec_document"
NAME_SCOPE_KEYS = (PRODUCT_GROUP_KEY, SPEC_DOCUMENT_KEY)

#: 이름 유일성의 자리 — (적용군 값 id, 규격서 id). 둘 다 비면 예전과 같은 「이름 하나」 다.
#:
#: **판은 자리가 아니다**(0046). 시험의 정체는 규격서 + 이름 + 적용군이고, 판은 그 시험의
#: 값에 붙는 꼬리표다 — 개정 14와 18은 **같은 시험의 두 시점**이지 두 시험이 아니다.
#: 판을 자리에 넣었더니(0045) 같은 시험이 판 수만큼 줄로 늘어나, 고칠 때 어느 줄을 고칠지
#: 사람이 정해야 하고 장비 판정·검색·색인이 같은 시험을 여러 건으로 셌다.
NameScope = tuple[str, str]


def _scope_of_items(db: Session, items: list[AttributeValueIn]) -> NameScope:
    """보낼 값에서 (적용군, 규격서)를 뽑는다."""
    ids = {one.definition_id for one in items if one.definition_id}
    if not ids:
        return "", ""
    keys = {
        row[0]: row[1]
        for row in db.execute(
            select(AttributeDefinition.id, AttributeDefinition.key).where(
                AttributeDefinition.id.in_(ids)
            )
        ).all()
    }
    group = document = ""
    for one in items:
        key = keys.get(one.definition_id)
        if key == PRODUCT_GROUP_KEY and one.term_id:
            group = str(one.term_id)
        elif key == SPEC_DOCUMENT_KEY and one.document_id:
            document = str(one.document_id)
    return group, document


def _scope_of_rows(db: Session, test_ids: list[uuid.UUID]) -> dict[uuid.UUID, NameScope]:
    """이미 있는 줄들의 (적용군, 규격서). 질의 한 번으로."""
    out: dict[uuid.UUID, NameScope] = {one: ("", "") for one in test_ids}
    if not test_ids:
        return out
    rows = db.execute(
        select(
            AttributeValue.reliability_test_id,
            AttributeDefinition.key,
            AttributeValue.term_id,
            AttributeValue.ref_document_id,
        )
        .join(AttributeDefinition, AttributeDefinition.id == AttributeValue.definition_id)
        .where(
            AttributeValue.reliability_test_id.in_(test_ids),
            AttributeDefinition.key.in_(NAME_SCOPE_KEYS),
            AttributeValue.is_current.is_(True),
        )
    ).all()
    for test_id, key, term_id, document_id in rows:
        group, document = out.get(test_id, ("", ""))
        if key == PRODUCT_GROUP_KEY and term_id:
            group = str(term_id)
        if key == SPEC_DOCUMENT_KEY and document_id:
            document = str(document_id)
        out[test_id] = (group, document)
    return out


def _checked_revision(db: Session, raw: Any) -> uuid.UUID | None:
    """준 판이 실재하나. **없는 판을 그대로 받으면** 그 줄은 어느 판에도 안 속한 채로
    남고, 「이 판의 목록」 에서 영영 빠진다 — 올린 사람은 올렸다고 안다."""
    if not raw:
        return None
    found = uuid.UUID(str(raw))
    if db.get(SpecDocumentRevision, found) is None:
        raise NotFound("TSC-RELIABILITY-0016", "그 규격서 판을 찾을 수 없습니다.")
    return found


def _check_name_free(
    db: Session,
    division_term_id: uuid.UUID,
    name: str,
    *,
    except_id: uuid.UUID | None,
    scope: NameScope = ("", ""),
    revision_id: uuid.UUID | None = None,
) -> None:
    """이 사업부에 **같은 이름이면서 같은 자리인** 시험이 있나.

    **자리는 (적용군, 규격서)다.** 이름만으로 유일하게 두었더니 실제 문서와 부딪혔다
    (2026-09-30): 같은 이름이지만 **적용군이 다른 별개의 시험**이 있고, 제품군마다 제
    규격서가 제 판을 갖는다. 634장 중 202장이 그렇게 막혔고, 이름을 선점당한 17건은 아예
    못 들어왔다 — 막은 것이 중복이 아니라 **서로 다른 시험**이었다.

    셋 다 같아야 같은 시험이다:

        같은 이름 · 적용군 다름    -> 다른 시험. 들어간다
        같은 이름 · 규격서 다름    -> 다른 시험. 들어간다
        같은 이름 · 둘 다 같음     -> **같은 시험.** 판이 달라도 같다 — 값에 판을 붙인다
        같은 이름 · 둘 다 안 적힘   -> 가를 근거가 없다. 막는다(예전 그대로)

    **판도 자리다**(0049). 0046 은 「판은 값에」 로 갔는데 운영에서 그 약속이 깨졌다:
    개정 14와 18을 올리니 겹치는 87건이 18 하나로 흡수되고 **내용이 다른 36건은 개정 14
    값이 저장되지 않았다.** 판을 자리로 두면 같은 시험이 판 수만큼 줄로 늘지만, 목록이
    부푸는 쪽은 `superseded_by_id` 로 푼다 — 기본은 최신판만 보인다.

    마지막 줄이 중요하다. **가를 근거가 하나도 없으면 예전과 똑같이 이름 하나다** — 수백
    건을 적재하는 동안 동명이 쌓이는 것을 막는 장치가 거기 남아 있어야 한다. 가르고 싶으면
    **가르는 근거를 적으라**는 뜻이기도 하다.

    한쪽만 적힌 것과 안 적힌 것은 **다른 자리로 본다**(적용군 「A」 와 빈 적용군은 다르다).
    안 적은 것을 「아무거나」 로 받아 주면, 적어 둔 사람의 줄이 안 적은 사람의 줄에 밀린다.
    """
    key = name_key(name)
    rows = list(
        db.scalars(
            select(ReliabilityTest).where(
                ReliabilityTest.division_term_id == division_term_id,
                ReliabilityTest.deleted_at.is_(None),
                ReliabilityTest.id != except_id if except_id else true(),
            )
        )
    )
    # **판이 다르면 다른 자리다.** 이것이 없으면 개정 18을 올릴 때 14가 선점한 이름에
    # 막히고, 그 409 는 「이미 다 있다」 로 읽힌다.
    same = [
        one
        for one in rows
        if name_key(one.name) == key and one.document_revision_id == revision_id
    ]
    if not same:
        return
    scopes = _scope_of_rows(db, [one.id for one in same])
    clash = next((one for one in same if scopes.get(one.id, ("", "")) == scope), None)
    if clash is None:
        return
    group, document = scope
    parts = [label for label, filled in (("적용군", group), ("규격서", document)) if filled]
    where = f"같은 {'·'.join(parts)}" if parts else "적용군도 규격서도 안 적힌 채"
    raise Conflict(
        "TSC-RELIABILITY-0003",
        f"이 사업부에 {where}로 같은 이름의 신뢰성 시험이 있습니다: {clash.name}"
        + (
            " — 별개의 시험이면 적용군이나 규격서를 적어 가르십시오."
            " (다른 판이면 그 판을 적으십시오 — 판마다 줄이 섭니다.)"
            if not parts
            else ""
        ),
        details={
            "id": str(clash.id),
            "name": clash.name,
            "product_group_term_id": group or None,
            "spec_document_id": document or None,
        },
    )


def _set_items(db: Session, test_id: uuid.UUID, term_ids: list[uuid.UUID]) -> None:
    for link in db.scalars(
        select(ReliabilityTestItem).where(ReliabilityTestItem.reliability_test_id == test_id)
    ):
        db.delete(link)
    db.flush()
    for term_id in dict.fromkeys(term_ids):
        db.add(ReliabilityTestItem(reliability_test_id=test_id, test_item_term_id=term_id))


def _attribute_items(raw: Any) -> list[AttributeValueIn]:
    """`model_dump` 를 거쳐 dict 로 온 것을 되돌린다 — 값 검증은 attributes 서비스가 한다."""
    return [
        one if isinstance(one, AttributeValueIn) else AttributeValueIn.model_validate(one)
        for one in (raw or [])
    ]


def division_by_code(db: Session, code: str) -> VocabularyTerm:
    """사업부 코드로 값 하나. `division` 축의 것만 받는다.

    코드로 거는 이유: 주소와 API 가 `mx` 로 걸리면 사업부 이름이 바뀌어도 안 깨진다.
    """
    axis = db.scalar(select(Vocabulary).where(Vocabulary.slug == DIVISION_AXIS))
    found = (
        db.scalar(
            select(VocabularyTerm).where(
                VocabularyTerm.vocabulary_id == axis.id,
                VocabularyTerm.code == code,
                VocabularyTerm.status == "active",
            )
        )
        if axis is not None
        else None
    )
    if found is None:
        raise NotFound("TSC-RELIABILITY-0008", f"사업부를 찾을 수 없습니다: {code}")
    return found


def divisions(db: Session, user: User) -> list[DivisionOut]:
    """사업부 목록과 **내가 올릴 수 있나.**

    사이드바가 이것으로 서고, 등록 창이 고를 것을 이것으로 좁힌다. 목록은 누구나 본다 —
    이 시스템의 물음은 사업부를 가로지른다(「저 사업부는 무슨 시험을 하나」). 올릴 수
    있는지는 줄마다 말한다: 못 고를 것을 숨기면 「왜 우리 사업부가 없지」 가 되고, 아무
    표시 없이 보여 주면 다 적고 나서 거절당한다.
    """
    axis = db.scalar(select(Vocabulary).where(Vocabulary.slug == DIVISION_AXIS))
    if axis is None:
        return []
    mine = my_division_term_ids(db, user)
    return [
        DivisionOut(
            code=term.code or "",
            name=term.value,
            can_register=user.is_system_admin or term.id in mine,
        )
        for term in db.scalars(
            select(VocabularyTerm)
            .where(VocabularyTerm.vocabulary_id == axis.id, VocabularyTerm.status == "active")
            # **회사가 정한 차례다** — 이름순으로 두면 「왜 CS 가 먼저지」 가 된다.
            .order_by(VocabularyTerm.sort_order, VocabularyTerm.value)
        )
    ]


def _require_can_register(db: Session, user: User, division_term_id: uuid.UUID) -> None:
    """**내 부서가 속한 사업부에만 올린다.** 시스템 관리자는 전부.

    부서(팀)가 아니라 사업부로 묻는다 — 실제로 시험을 돌리는 것은 팀이고, 그 팀의
    관리자면 제 사업부에 올릴 수 있어야 한다. 어느 사업부인지는 조직도가 정한다
    (부서에 붙은 값, 없으면 위에서 물려받은 값).
    """
    if user.is_system_admin:
        return
    if division_term_id not in my_division_term_ids(db, user):
        raise Forbidden(
            "TSC-RELIABILITY-0007",
            "이 사업부에 올릴 수 없습니다 — 내 소속 부서 중 관리자인 곳이 그 사업부에"
            " 속해 있어야 합니다. 관리 → 부서 정보에서 부서의 사업부를 확인하십시오.",
        )


def create(db: Session, user: User, payload: dict[str, Any]) -> ReliabilityTest:
    division = division_by_code(db, payload["division_code"])
    _require_can_register(db, user, division.id)
    name = str(payload["name"]).strip()
    if not name:
        raise AppError("TSC-RELIABILITY-0004", "이름을 적어 주십시오.")
    # **자리를 먼저 뽑는다.** 이름 검사가 속성보다 앞서므로, 보낼 값에서 적용군·규격서를
    # 읽어 함께 넘긴다 — 안 그러면 「가르는 근거」 가 아직 없는 채로 판정하게 된다.
    items = _attribute_items(payload.get("attributes"))
    revision_id = _checked_revision(db, payload.get("document_revision_id"))
    scope = _scope_of_items(db, items)
    _check_name_free(
        db,
        division.id,
        name,
        except_id=None,
        scope=scope,
        revision_id=revision_id,
    )
    term_ids: list[uuid.UUID] = list(payload.get("test_item_term_ids") or [])
    _check_test_item_terms(db, term_ids)

    # **어느 통로로 들어왔나.** 기계 자격이면 후보로 선다 — 사람이 읽고 확인해야 확정이다.
    via = _machine()
    row = ReliabilityTest(
        division_term_id=division.id,
        name=name,
        purpose=str(payload.get("purpose") or "").strip(),
        # `is not None` 이다 — 이름이 빈 토큰도 기계 자격이다. 참/거짓으로 보면 그런
        # 토큰이 사람으로 통과한다.
        status=CANDIDATE if via is not None else CONFIRMED,
        submitted_via=via,
        document_revision_id=revision_id,
        created_by=user.id,
    )
    db.add(row)
    db.flush()
    _set_items(db, row.id, term_ids)
    attributes.set_values(
        db,
        user,
        target="reliability_test",
        object_id=row.id,
        items=items,
        # **값에 판이 붙는다.** 시험은 한 줄이고, 개정 18을 올려도 14의 값은 이력으로 남는다.
        revision_id=revision_id,
    )
    # **판들 사이에 누가 최신인가**를 여기서 적는다. 목록이 이 칸 하나만 보므로, 새 판이
    # 들어온 순간 지난 판은 비켜야 한다 — 안 적으면 같은 시험이 목록에 두 줄로 선다.
    _resupersede(db, _siblings_of(db, division.id, name, scope))
    db.commit()
    db.refresh(row)
    return row


def _refuse_machine_edit(row: ReliabilityTest) -> None:
    """**확정된 시험은 기계 자격으로 못 고친다.**

    후보로 받는 것만으로는 부족하다 — AI 가 후보를 만들고, 사람이 확인한 뒤, AI 가 그 줄을
    다시 고치면 확인은 지나간 일이 되고 아무도 그것을 모른다. 확정은 **그 시점의 내용**에
    대한 보증이므로, 내용이 바뀌려면 보증이 먼저 풀려야 한다.

    푸는 길은 있다 — 사람이 화면에서 「다시 후보로」 를 누르면 그때부터 AI 가 채운다.
    그 문을 누가 열었는지는 감사에 남는다.

    사람 세션은 안 막는다. 그 사람의 권한이 이미 한계다.
    """
    if _machine() is None or row.status != CONFIRMED:
        return
    raise Conflict(
        "TSC-RELIABILITY-0005",
        "확정된 신뢰성 시험은 기계 자격으로 못 고칩니다 — "
        "사람이 화면에서 「다시 후보로」 를 누른 뒤에 고칠 수 있습니다.",
        details={"test_id": str(row.id), "status": row.status},
    )


def require_editable(db: Session, user: User, test_id: uuid.UUID) -> None:
    """이 시험을 고칠 수 있나. **첨부도 같은 물음을 쓴다** — 판정이 두 벌이면
    「시험은 못 고치는데 그림은 붙는」 사람이 생긴다.

    그래서 기계 자격 판정도 여기 있다. 내용을 고치는 길이 둘(칸 · 그림)인데 한 쪽만
    막으면, 확정된 시험에 AI 가 그림을 붙이는 길이 그대로 열려 있게 된다.
    """
    row = get(db, test_id)
    if not _can_edit(db, user, row.division_term_id):
        raise Forbidden(
            "TSC-RELIABILITY-0007",
            "이 사업부의 신뢰성 시험을 고칠 수 없습니다 — 그 사업부에 속한 부서의"
            " 관리자여야 합니다.",
        )
    _refuse_machine_edit(row)


def update(
    db: Session, user: User, test_id: uuid.UUID, changes: dict[str, Any]
) -> ReliabilityTest:
    """`changes` 는 `exclude_unset` 으로 온다 — 안 보낸 칸은 안 건드린다."""
    row = get(db, test_id)
    require_editable(db, user, test_id)
    division = db.get(VocabularyTerm, row.division_term_id)
    assert division is not None

    # **판을 먼저 반영한다** — 아래 값 쓰기가 이 칸을 보고 어느 판에 쓸지 정한다.
    if "document_revision_id" in changes:
        row.document_revision_id = _checked_revision(db, changes["document_revision_id"])
    if "name" in changes:
        name = str(changes["name"]).strip()
        if not name:
            raise AppError("TSC-RELIABILITY-0004", "이름을 적어 주십시오.")
        # 속성을 **함께** 보냈으면 그것이 새 자리다(적용군을 바꾸면서 이름을 바꾸는 일이
        # 실제로 있다). 안 보냈으면 지금 줄의 자리를 쓴다.
        scope = (
            _scope_of_items(db, _attribute_items(changes["attributes"]))
            if changes.get("attributes") is not None
            else _scope_of_rows(db, [row.id])[row.id]
        )
        _check_name_free(
            db,
            division.id,
            name,
            except_id=row.id,
            scope=scope,
            revision_id=row.document_revision_id,
        )
        row.name = name
    if "purpose" in changes:
        row.purpose = str(changes["purpose"] or "").strip()
    if changes.get("test_item_term_ids") is not None:
        term_ids = list(changes["test_item_term_ids"])
        _check_test_item_terms(db, term_ids)
        _set_items(db, row.id, term_ids)
    if changes.get("attributes") is not None:
        # **어느 판의 값인가** — 보낸 판이 있으면 그것, 없으면 이 시험의 현재 판. 판을
        # 안 정하면 사람이 고친 값이 판 없는 자리에 떨어져, 판을 적은 값 아래로 숨는다.
        attributes.set_values(
            db,
            user,
            target="reliability_test",
            object_id=row.id,
            items=_attribute_items(changes["attributes"]),
            revision_id=row.document_revision_id,
        )
    # **고쳤으면 고친 때가 남아야 한다.**
    #
    # `updated_at` 은 `onupdate=func.now()` 인데, 그것은 **이 행이 UPDATE 될 때만** 돈다.
    # 속성이나 시험 항목만 바꾸면 값은 딴 표에 있어서 이 행은 안 더러워지고, 그러면 UPDATE
    # 가 아예 안 나가서 날짜가 그대로다 — 목록을 「최근 고친 것」 으로 보는 사람은 방금
    # 고친 줄을 못 찾고, 「언제 고쳤나」 에 옛 날짜가 답한다(운영 보고, 2026-10-03).
    #
    # 손으로 적는다. 칸을 본 사람이 「왜 안 바뀌나」 를 되짚을 자리가 여기여야 한다.
    if changes:
        row.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return row


def _human_only(row: ReliabilityTest, what: str) -> None:
    """확인하고 다시 여는 것은 **사람만.**

    기계 자격이 스스로 확인할 수 있으면 후보라는 상태에 아무 뜻이 없다 — AI 가 올리고
    AI 가 확인하면 그냥 바로 쓰는 것과 같다. MCP 에 도구를 안 만드는 것만으로는 부족하다:
    PAT 는 이 경로를 직접 부를 수 있다.
    """
    if _machine() is None:
        return
    raise Forbidden(
        "TSC-RELIABILITY-0006",
        # `what` 에 조사까지 실어 받는다 — 여기서 「는」 을 붙이면 받침에 따라 틀린다
        # (「확인는」). 한국어 조사는 앞말을 봐야 정해지므로 부르는 쪽이 준다.
        f"{what} 사람이 화면에서 합니다 — 기계 자격으로는 못 합니다.",
        details={"test_id": str(row.id)},
    )


def confirm(db: Session, user: User, test_id: uuid.UUID) -> ReliabilityTest:
    """후보를 **확인했다** — 사람이 내용을 읽고 맞다고 했다.

    이미 확정인 것을 또 확인하는 것은 아무 일도 아니다(오류가 아니다) — 두 사람이 같은
    줄을 동시에 보고 둘 다 누를 수 있다.
    """
    row = get(db, test_id)
    _human_only(row, "확인은")
    require_editable(db, user, test_id)
    if row.status == CONFIRMED:
        return row
    division = db.get(VocabularyTerm, row.division_term_id)
    assert division is not None
    row.status = CONFIRMED
    row.confirmed_by_id = user.id
    row.confirmed_at = datetime.now(UTC)
    audit.record(
        db,
        action=audit.RELIABILITY_TEST_CONFIRMED,
        actor=user,
        target_table="reliability_tests",
        target_id=row.id,
        target_label=f"{division.value} · {row.name}",
        # **누가 올린 것을 확인했나.** 줄에는 지금 상태만 남고, 「AI 가 올린 것을 사람이
        # 봤다」 는 사실은 여기에만 남는다.
        changes={
            "status": {"before": CANDIDATE, "after": CONFIRMED},
            "submitted_via": row.submitted_via,
        },
    )
    db.commit()
    db.refresh(row)
    return row


def reopen(
    db: Session, user: User, test_id: uuid.UUID, reason: str | None = None
) -> ReliabilityTest:
    """확정을 풀어 **다시 후보로.** 그 순간부터 AI 가 다시 채울 수 있다.

    확인을 지우지 않는다 — `confirmed_by_id` · `confirmed_at` 은 그대로 두고 상태만 돌린다.
    「전에 누가 봤었나」 는 다시 확인할 때 도움이 된다.

    **여럿을 한 번에 풀 때는 사유를 받는다**(`bulk`). 한 건씩 누를 때는 그 자리에서 보고
    누르는 것이라 안 받지만, 서른 건이 한꺼번에 풀리면 반년 뒤에 「왜 풀렸나」 를 묻는
    사람이 반드시 있다 — 감사에 「누가 열었나」 만 있고 「왜」 가 없으면 답할 수 없다.
    반려가 사유를 받는 것과 같은 이유다.
    """
    row = get(db, test_id)
    _human_only(row, "다시 후보로 여는 것은")
    require_editable(db, user, test_id)
    if row.status == CANDIDATE:
        return row
    division = db.get(VocabularyTerm, row.division_term_id)
    assert division is not None
    row.status = CANDIDATE
    said = (reason or "").strip()
    audit.record(
        db,
        action=audit.RELIABILITY_TEST_REOPENED,
        actor=user,
        target_table="reliability_tests",
        target_id=row.id,
        target_label=f"{division.value} · {row.name}",
        changes={"status": {"before": CONFIRMED, "after": CANDIDATE}},
        reason=said or None,
    )
    db.commit()
    db.refresh(row)
    return row


def _take_down(
    db: Session, user: User, row: ReliabilityTest, *, action: str, reason: str | None
) -> None:
    """줄을 내린다 — **지우기와 반려가 같이 쓴다.**

    가는 자리(`deleted_at`)는 같고 **뜻이 다르다**: 지우기는 「이제 안 하는 시험」, 반려는
    「애초에 틀린 줄」 이다. 그 차이는 감사의 action 과 사유에만 남으므로, 거기 안 적으면
    영영 못 가른다.
    """
    division = db.get(VocabularyTerm, row.division_term_id)
    assert division is not None
    # **그림도 같이 간다.** 시험이 안 보이는데 파일만 남으면 디스크를 먹고, 그것을
    # 알아챌 자리가 없다. 파일 자체는 다른 시험이 그 그림을 안 쓸 때만 지워진다.
    removed = attachments.remove_all(db, target="reliability_test", object_id=row.id)
    row.deleted_at = datetime.now(UTC)
    audit.record(
        db,
        action=action,
        actor=user,
        target_table="reliability_tests",
        target_id=row.id,
        # **그림이 몇 장 같이 갔는지 적는다** — 「사진이 없어졌어요」 를 나중에 물을 때
        # 그것이 이 삭제 때문인지 가릴 자리가 여기뿐이다.
        target_label=f"{division.value} · {row.name}"
        + (f" (그림 {removed}장 함께 지움)" if removed else ""),
        reason=reason,
    )


def reject(db: Session, user: User, test_id: uuid.UUID, reason: str) -> None:
    """**AI 가 올린 후보를 아니라고 한다.** 사람만, 후보만.

    확정된 줄은 못 반려한다 — 이미 사람이 보증한 것이라, 되돌리려면 「다시 후보로」 를
    거쳐야 그 과정이 감사에 남는다.

    **사유를 받는다.** 없으면 AI 가 무엇을 자주 틀리는지 셀 수 없고, 같은 것을 또 올려도
    아무도 모른다 — 계정 거절이 사유를 받는 것과 같은 이유다.
    """
    row = get(db, test_id)
    _human_only(row, "반려는")
    require_editable(db, user, test_id)
    if row.status != CANDIDATE:
        raise Conflict(
            "TSC-RELIABILITY-0009",
            "확정된 시험은 반려할 수 없습니다 — 「다시 후보로」 를 거치십시오.",
        )
    said = reason.strip()
    if not said:
        raise AppError("TSC-RELIABILITY-0009", "반려 사유를 적어 주십시오.")
    _take_down(db, user, row, action=audit.RELIABILITY_TEST_REJECTED, reason=said)
    db.commit()


#: 한 번에 다룰 수 있는 줄 수. **줄마다 화면을 여는 것을 없애려고 만든 길**이라 넉넉해야
#: 하는데, 무한이면 한 번의 실수가 되돌릴 수 없는 크기가 된다. 몇천 건을 몇 번에 나눠
#: 누르는 것은 할 만하고, 그 사이에 결과를 보고 멈출 수 있다.
BULK_LIMIT = 500


def bulk(
    db: Session, user: User, *, ids: list[uuid.UUID], action: str, reason: str | None
) -> dict[str, Any]:
    """여러 줄을 한 번에 — 확인 · 반려 · 지우기 · **다시 후보로.**

    **AI 가 몇천 건을 올린다.** 줄마다 창을 열어 확인을 누르는 것은 사람이 할 수 있는
    일이 아니고, 못 하면 후보가 쌓인 채로 아무도 안 본다 — 그러면 확인이라는 단계가
    이름만 남는다.

    **줄마다 결과를 돌려준다.** 전부 되거나 전부 안 되거나로 두면, 오백 줄 중 한 줄이
    남의 사업부라는 이유로 사백구십구 줄이 함께 막힌다. 안 된 줄은 **왜**와 함께 온다 —
    「12건 실패」 만으로는 다시 누를지 고칠지 알 수 없다.

    **반려와 「다시 후보로」 는 사유를 받는다.** 한 건씩 누를 때는 그 자리에서 보고 누르는
    것이지만, 서른 건이 한꺼번에 풀리면 반년 뒤에 「왜 풀렸나」 를 묻는 사람이 반드시
    있다 — 그때 감사에 「누가 열었나」 만 있으면 답할 수 없다.
    """
    if not ids:
        raise AppError("TSC-RELIABILITY-0011", "고른 줄이 없습니다.")
    if len(ids) > BULK_LIMIT:
        raise AppError(
            "TSC-RELIABILITY-0011",
            f"한 번에 {BULK_LIMIT}건까지입니다 — {len(ids)}건을 골랐습니다. 나눠 누르십시오.",
        )
    run = {
        "confirm": confirm,
        "reject": reject,
        "delete": delete,
        "reopen": reopen,
    }.get(action)
    if run is None:
        raise AppError("TSC-RELIABILITY-0011", f"알 수 없는 동작입니다: {action}")
    # **사유를 먼저 본다.** 줄마다 거절하면 오백 줄이 같은 이유로 실패하고, 그 목록을
    # 읽는 사람은 무엇이 잘못됐는지 못 찾는다.
    said = (reason or "").strip()
    if action in ("reject", "reopen") and not said:
        what = "반려" if action == "reject" else "다시 후보로 여는"
        raise AppError("TSC-RELIABILITY-0011", f"{what} 사유를 적어 주십시오.")

    done: list[str] = []
    failed: list[dict[str, str]] = []
    for test_id in ids:
        try:
            if action in ("reject", "reopen"):
                run(db, user, test_id, said)  # type: ignore[operator]
            else:
                run(db, user, test_id)  # type: ignore[operator]
            done.append(str(test_id))
        except AppError as refused:
            # **한 줄이 막혀도 나머지는 간다.** 줄을 되돌려 놓고 다음으로 넘어간다 —
            # 안 그러면 실패한 줄의 반쯤 바뀐 상태가 다음 줄의 커밋에 묻어 간다.
            db.rollback()
            failed.append(
                {"id": str(test_id), "code": refused.code, "message": refused.message}
            )
    return {"done": done, "failed": failed, "requested": len(ids)}


#: 사내 규격서를 가리키는 속성의 key. 묶음 등록이 이 칸에 문서를 건다.
SPEC_DOCUMENT_KEY = "reliability_spec_document"


def _spec_document_definition(db: Session) -> AttributeDefinition | None:
    """「규격서」 칸의 정의. **없으면 안 건다** — 설치가 덜 된 DB 에서 묶음 등록이 통째로
    막히면, 문서를 못 걸어서가 아니라 시험을 못 올려서 문제가 된다."""
    return db.scalar(
        select(AttributeDefinition).where(
            AttributeDefinition.target == "reliability_test",
            AttributeDefinition.key == SPEC_DOCUMENT_KEY,
        )
    )


def _with_document(
    items: list[dict[str, Any]], definition: AttributeDefinition | None, document_id: uuid.UUID
) -> list[dict[str, Any]]:
    """줄의 속성에 규격서를 건다 — **이미 적힌 줄은 안 덮는다.**

    AI 가 줄마다 다른 규격서를 적었을 수 있다(한 문서가 다른 문서를 인용한다). 묶음이
    준 문서로 그것을 덮으면, 더 정확한 값이 덜 정확한 값에 밀린다.
    """
    if definition is None:
        return items
    out = list(items)
    if any(str(one.get("definition_id") or "") == str(definition.id) for one in out):
        return out
    out.append(
        {"definition_id": definition.id, "document_id": document_id, "new_kind": "document"}
    )
    return out


def _siblings_of(
    db: Session, division_term_id: uuid.UUID, name: str, scope: NameScope
) -> list[ReliabilityTest]:
    """같은 시험의 **모든 판.** 규격서 + 이름 + 적용군이 같으면 같은 시험이다."""
    key = name_key(name)
    rows = db.scalars(
        select(ReliabilityTest).where(
            ReliabilityTest.division_term_id == division_term_id,
            ReliabilityTest.deleted_at.is_(None),
        )
    )
    same = [one for one in rows if name_key(one.name) == key]
    if not same:
        return []
    scopes = _scope_of_rows(db, [one.id for one in same])
    return [one for one in same if scopes.get(one.id, ("", "")) == scope]


def _same_test(
    db: Session,
    division_term_id: uuid.UUID,
    name: str,
    scope: NameScope,
    revision_id: uuid.UUID | None,
) -> ReliabilityTest | None:
    """**같은 판의** 같은 시험이 이미 있나.

    판이 자리가 되면서(0049) 개정 18은 14의 줄에 붙지 않는다 — 붙였더니 14의 값이
    조용히 사라졌다. 같은 판을 다시 올린 것만 병합이다.
    """
    return next(
        (
            one
            for one in _siblings_of(db, division_term_id, name, scope)
            if one.document_revision_id == revision_id
        ),
        None,
    )


def sibling_ids(db: Session, test_id: uuid.UUID) -> list[uuid.UUID]:
    """이 시험의 **모든 판의 줄** — 판 순서대로, 지난 판이 앞.

    판이 자리가 된 뒤로(0049) 「과거 판의 값」 은 다른 줄에 있다. 값 이력과 비교 화면이
    그 줄들을 가로질러 봐야 「개정 14에서는 얼마였나」 에 답할 수 있다.
    """
    row = get(db, test_id)
    scope = _scope_of_rows(db, [row.id]).get(row.id, ("", ""))
    rows = _siblings_of(db, row.division_term_id, row.name, scope)
    orders = {
        one.id: one.sort_order
        for one in db.scalars(
            select(SpecDocumentRevision).where(
                SpecDocumentRevision.id.in_(
                    {one.document_revision_id for one in rows if one.document_revision_id}
                )
            )
        )
    }
    rows.sort(
        key=lambda one: (
            (1, orders.get(one.document_revision_id, 0))
            if one.document_revision_id
            else (0, 0),
            one.created_at,
        )
    )
    return [one.id for one in rows] or [test_id]


def _resupersede(db: Session, rows: list[ReliabilityTest]) -> None:
    """한 시험의 판들에 **최신 하나만 남긴다** — 나머지는 그 줄을 가리킨다.

    목록이 기본으로 `superseded_by_id IS NULL` 만 보여 주므로, 이 한 줄이 「무엇이
    최신판인가」 의 정본이다. 판 없는 줄은 **가장 앞**으로 본다: 판을 안 적은 것은 어느
    개정의 것인지 모른다는 뜻이고, 아는 것이 모르는 것을 밀어내는 쪽이 맞다.
    """
    if len(rows) <= 1:
        for one in rows:
            one.superseded_by_id = None
        return
    orders = {
        one.id: one.sort_order
        for one in db.scalars(
            select(SpecDocumentRevision).where(
                SpecDocumentRevision.id.in_(
                    {row.document_revision_id for row in rows if row.document_revision_id}
                )
            )
        )
    }

    def rank(row: ReliabilityTest) -> tuple[int, int]:
        if row.document_revision_id is None:
            return (0, 0)
        # 같은 순서면 나중에 만든 줄이 뒤다 — 판 이름이 같은 두 줄이 실제로 생긴다.
        return (1, orders.get(row.document_revision_id, 0))

    latest = max(rows, key=lambda row: (rank(row), row.created_at))
    for one in rows:
        one.superseded_by_id = None if one.id == latest.id else latest.id


def _merge_revision(
    db: Session,
    user: User,
    row: ReliabilityTest,
    sent: dict[str, Any],
    items: list[AttributeValueIn],
    revision_id: uuid.UUID | None,
) -> tuple[ReliabilityTest, str, list[str]]:
    """**같은 판을 다시 올렸다.** 그 판의 값을 갈아 끼우고 **무엇을 덮었는지 돌려준다.**

    판이 자리가 된 뒤로(0049) 여기 오는 것은 다른 개정이 아니라 **같은 판의 재적재**다.
    갈아 끼우는 것 자체는 맞지만, 그동안 `merged` 한 줄로만 세어서 **버린 값이 아무 데도
    안 드러났다** — 운영에서 36건의 값이 그렇게 사라졌다(2026-10-01).

    돌려주는 것: `updated` 면 바뀐 칸 이름, `skipped` 면 바뀐 것이 없다는 뜻이다.
    """
    require_editable(db, user, row.id)
    _refuse_machine_edit(row)
    # **덮기 전에 지금 값을 적어 둔다.** 덮고 나서는 무엇이 있었는지 알 길이 없다.
    before = _value_marks(db, row.id, revision_id)
    if revision_id is not None and _is_later(db, revision_id, row.document_revision_id):
        row.document_revision_id = revision_id
    if sent.get("purpose"):
        row.purpose = str(sent["purpose"]).strip()
    if sent.get("test_item_term_ids"):
        term_ids = list(sent["test_item_term_ids"])
        _check_test_item_terms(db, term_ids)
        _set_items(db, row.id, term_ids)
    attributes.set_values(
        db,
        user,
        target="reliability_test",
        object_id=row.id,
        items=items,
        revision_id=revision_id,
    )
    db.flush()
    after = _value_marks(db, row.id, revision_id)
    changed = sorted({label for label, _ in before.items() - after.items()})
    action = "updated" if changed or before.keys() != after.keys() else "skipped"
    # **바뀐 때만 민다.** 같은 판을 다시 적재하는 일이 흔한데(`skipped`), 그때마다 날짜가
    # 움직이면 「최근 고친 것」 목록이 적재 기록으로 가득 차서 쓸모가 없어진다. 값이 딴 표에
    # 있어 이 행은 저절로 안 더러워지므로 손으로 적는다(`update()` 와 같은 이유).
    if action == "updated":
        row.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return row, action, changed


def _value_marks(
    db: Session, test_id: uuid.UUID, revision_id: uuid.UUID | None
) -> dict[str, str]:
    """그 판의 값을 **「칸 이름 → 지금 글자」** 로. 덮기 전후를 견주려는 것이다.

    `display` 를 쓰는 이유: 사람에게 「무엇이 바뀌었나」 를 말할 글자가 그것이고, 화면과
    MCP 가 이미 같은 글자를 쓴다.
    """
    rows = attributes.values_of(db, target="reliability_test", object_ids=[test_id])[test_id]
    return {
        f"{one.label}{f'({one.set_label})' if one.set_label else ''}": one.display
        for one in rows
        if one.document_revision_id == revision_id
    }


def _is_later(db: Session, one: uuid.UUID, other: uuid.UUID | None) -> bool:
    """`one` 판이 `other` 보다 뒤인가. 판이 없으면 무엇이든 뒤다."""
    if other is None:
        return True
    rows = {
        row.id: row.sort_order
        for row in db.scalars(
            select(SpecDocumentRevision).where(SpecDocumentRevision.id.in_({one, other}))
        )
    }
    return rows.get(one, -1) >= rows.get(other, -1)


def create_many(db: Session, user: User, payload: dict[str, Any]) -> dict[str, Any]:
    """문서 하나에서 뽑은 시험들을 **한 번에** 올린다.

    한 건씩 스무 번 부르는 것과 무엇이 다른가 — **중간에 막혔을 때의 자리**가 다르다.
    열 번째에서 끊기면 앞의 아홉은 들어가 있고 뒤의 열은 없는데, 부른 쪽은 그 경계를
    모른다. 다시 부르면 아홉이 이름 겹침으로 막히고, 그 오류를 보고 사람은 「안 올라갔나」
    라고 읽는다. 여기서는 **줄마다 결과가 온다** — 무엇이 들어가고 무엇이 왜 막혔는지가
    한 답에 있다.

    그리고 **한 문서에서 나왔다는 사실이 줄에 남는다**(`document_id`). 그것이 없으면
    검토하는 사람은 스무 줄을 스무 건으로 본다 — 같은 문서에서 나온 줄은 같은 실수를
    함께 하고, 함께 봐야 그것이 보인다.

    **이미 있는 시험이면 줄을 새로 만들지 않고 그 시험의 값에 판을 붙인다**(`merged`).
    시험의 정체는 규격서 + 이름 + 적용군이고 판은 값에 붙으므로(0046), 개정 18을 올리는
    것은 새 시험 이백 건이 아니라 **있던 시험 이백 건의 새 판**이다 — 이것이 없으면 그
    이백 줄이 전부 409 로 막히고, 부른 쪽은 그것을 「이미 다 있다」 로 읽는다.

    **줄마다 커밋한다.** 한 덩이로 묶으면 한 줄의 이름 겹침이 열아홉을 되돌린다.
    """
    division = division_by_code(db, str(payload["division_code"]))
    # **권한은 줄마다가 아니라 먼저 본다** — 못 올릴 사업부면 오백 번 시도할 이유가 없다.
    _require_can_register(db, user, division.id)

    tests: list[dict[str, Any]] = list(payload.get("tests") or [])
    if not tests:
        raise AppError("TSC-RELIABILITY-0012", "올릴 줄이 없습니다.")
    if len(tests) > BULK_LIMIT:
        raise AppError(
            "TSC-RELIABILITY-0012",
            f"한 번에 {BULK_LIMIT}건까지입니다 — {len(tests)}건을 보냈습니다."
            " 나눠 보내십시오.",
        )

    document_id = payload.get("document_id")
    definition = _spec_document_definition(db) if document_id else None
    if document_id is not None:
        # 없는 문서에 걸면 줄마다 같은 오류가 오백 번 난다 — 여기서 한 번에 막는다.
        documents.get(db, uuid.UUID(str(document_id)))
    # 판도 마찬가지다. **없는 판을 그대로 받으면** 오백 줄이 어느 판에도 안 속한 채로 남고,
    # 「이 판의 목록」 에서 통째로 빠진다 — 올린 사람은 올렸다고 안다.
    batch_revision = _checked_revision(db, payload.get("document_revision_id"))
    # **규격서를 줬으면 판도 줘야 한다.** 판 없이 올리면 같은 자리에 쌓여 뒤엣것이
    # 앞엣것을 조용히 덮는다 — 운영에서 1509건이 판 없이 들어갔고, 그 길로 개정 14의
    # 값 36건이 사라졌다(2026-10-01). 규격서가 없는 묶음은 개정을 말할 것이 없으므로
    # 그대로 둔다.
    if (
        document_id is not None
        and batch_revision is None
        and any(one.get("document_revision_id") is None for one in tests)
    ):
        raise AppError(
            "TSC-RELIABILITY-0016",
            "규격서를 주면 판(document_revision_id)도 함께 주십시오 — 판이 없으면"
            " 같은 자리에 쌓여 먼저 올린 값이 조용히 덮입니다."
            " 규격서의 판 목록은 `GET /spec-documents/{id}` 에 있습니다.",
        )

    created: list[ReliabilityTest] = []
    merged: list[tuple[ReliabilityTest, str, list[str]]] = []
    failed: list[dict[str, str]] = []
    for one in tests:
        name = str(one.get("name") or "")
        raw_items = [dict(each) for each in (one.get("attributes") or [])]
        if document_id is not None:
            raw_items = _with_document(raw_items, definition, uuid.UUID(str(document_id)))
        items = _attribute_items(raw_items)
        row_revision = _checked_revision(db, one.get("document_revision_id")) or batch_revision
        try:
            scope = _scope_of_items(db, items)
            found = _same_test(db, division.id, name, scope, row_revision)
            if found is not None:
                # **같은 시험의 다른 판이다.** 줄을 새로 만들지 않고 그 시험의 값에 판을
                # 붙인다 — 이것이 없으면 개정 18을 올릴 때 이백 줄이 전부 409 로 막히고,
                # 부른 쪽은 그것을 「이미 다 있다」 로 읽는다.
                merged.append(_merge_revision(db, user, found, one, items, row_revision))
                _resupersede(db, _siblings_of(db, division.id, name, scope))
                db.commit()
                continue
            created.append(
                create(
                    db,
                    user,
                    {
                        "division_code": str(payload["division_code"]),
                        "name": name,
                        "purpose": one.get("purpose") or "",
                        # **줄이 제 판을 적으면 묶음이 준 판을 안 덮는다** — 한 묶음에 두
                        # 판이 섞인다(개정 18에서 안 바뀐 시험은 14의 판으로 남긴다).
                        "document_revision_id": row_revision,
                        "test_item_term_ids": one.get("test_item_term_ids") or [],
                        "attributes": raw_items,
                    },
                )
            )
        except AppError as refused:
            # **한 줄이 막혀도 나머지는 간다.** 반쯤 만들어진 줄을 되돌리고 다음으로 —
            # 안 그러면 실패한 줄의 조각이 다음 줄의 커밋에 묻어 간다.
            db.rollback()
            failed.append({"name": name, "code": refused.code, "message": refused.message})
    # **병합이 무엇을 했는지 돌려준다.** 예전에는 `merged` 로 세기만 해서, 보낸 값이
    # 안 반영돼도 성공처럼 보였다 — 버린 값이 아무 데도 안 드러났다(2026-10-01).
    shown = {
        row.id: out
        for row, out in zip(
            [row for row, _, _ in merged],
            _outs(db, user, [row for row, _, _ in merged]),
            strict=True,
        )
    }
    return {
        "requested": len(tests),
        "created": _outs(db, user, created),
        "merged": [
            {
                "test": shown[row.id],
                "action": action,
                "changed": changed,
                "reason": (
                    "보낸 값이 지금 값과 같습니다 — 바뀐 것이 없습니다."
                    if action == "skipped"
                    else None
                ),
            }
            for row, action, changed in merged
        ],
        "failed": failed,
    }


def delete(db: Session, user: User, test_id: uuid.UUID) -> None:
    row = get(db, test_id)
    require_editable(db, user, test_id)
    # **확정된 것은 기계가 못 내린다.** 고치는 것을 막고 지우는 것을 열어 두면, 그 길로
    # 가면 결과는 더 나쁘다. 제가 만든 후보를 거두는 것은 된다.
    _refuse_machine_edit(row)
    # **반년 뒤에 「그 시험 어디 갔어」 를 묻는다.** 지운 줄은 화면에서 사라지므로
    # 감사에 남는다.
    _take_down(db, user, row, action=audit.RELIABILITY_TEST_DELETED, reason=None)
    db.commit()


def _values_at(db: Session, revision_id: uuid.UUID) -> dict[uuid.UUID, dict[str, str]]:
    """그 판에 적힌 값 — {시험: {자리: 사람이 읽는 글자}}.

    자리는 `칸key@묶음#차례` 다. **정의 id 로 잡으면** 판마다 다른 초안이 낀 순간 전부
    「바뀜」 이 된다. **글자로 견주는 이유**: 숫자만 보면 단위가 바뀐 것(85 °C -> 185 °F)을
    「안 바뀜」 으로 읽고, 행을 통째로 보면 사람이 못 읽는다.
    """
    rows = db.execute(
        select(AttributeValue, AttributeDefinition)
        .join(AttributeDefinition, AttributeDefinition.id == AttributeValue.definition_id)
        .join(ReliabilityTest, ReliabilityTest.id == AttributeValue.reliability_test_id)
        .where(
            AttributeValue.document_revision_id == revision_id,
            ReliabilityTest.deleted_at.is_(None),
        )
    ).all()
    out: dict[uuid.UUID, dict[str, str]] = {}
    for value, definition in rows:
        step = value.step_order if value.step_order is not None else ""
        where = f"{definition.key}@{value.set_label or ''}#{step}"
        shown = attributes.display_of(value, definition, term_value=None, method_code=None)
        assert value.reliability_test_id is not None
        out.setdefault(value.reliability_test_id, {})[where] = shown or (value.note or "")
    return out


def compare_revisions(
    db: Session, user: User, left_id: uuid.UUID, right_id: uuid.UUID
) -> RevisionCompareOut:
    """두 판을 견준다 — **더해진 시험 · 없어진 시험 · 조건이 바뀐 시험** 셋으로.

    개정이 오면 딸린 수십 건 중 **무엇을 다시 봐야 하는지**가 문제다. 「전부 다시」 는
    그날 일을 멈추고, 「아무것도 안 봄」 은 바뀐 조건을 놓친다. 그 사이를 이 답이 메운다.

    판마다 줄이 서므로(0049) 앞뒤는 **다른 줄**이다. 그래서 줄 id 가 아니라 **정체**로
    짝을 맞춘다 — 규격서 + 이름 + 적용군이 같으면 같은 시험의 두 판이다. id 로 맞추면
    갈린 줄이 전부 「더해짐 + 없어짐」 으로 나오고, 읽는 사람은 개정 하나에 백 건이
    새로 생겼다고 읽는다.
    """
    left = documents.revision_of(db, left_id)
    right = documents.revision_of(db, right_id)
    if left.document_id != right.document_id:
        raise AppError(
            "TSC-RELIABILITY-0017",
            "다른 규격서의 판끼리는 못 견줍니다 — 견주려면 같은 문서의 두 판이어야 합니다.",
            status=400,
        )
    before, after = _values_at(db, left_id), _values_at(db, right_id)
    rows = {
        one.id: one
        for one in db.scalars(
            select(ReliabilityTest).where(ReliabilityTest.id.in_(set(before) | set(after)))
        )
    }
    # **정체로 짝을 맞춘다.** 줄 id 로 맞추면 판마다 갈린 줄이 전부 「더해짐 + 없어짐」 이
    # 되고, 그 답은 개정 하나에 백 건이 새로 생겼다고 말한다.
    scopes = _scope_of_rows(db, list(rows))
    marks = {one: (name_key(rows[one].name), scopes.get(one, ("", ""))) for one in rows}
    left_by = {marks[one]: one for one in before if one in rows}
    right_by = {marks[one]: one for one in after if one in rows}

    added = [_brief(rows[right_by[mark]]) for mark in right_by if mark not in left_by]
    removed = [_brief(rows[left_by[mark]]) for mark in left_by if mark not in right_by]
    changed: list[RevisionChangedOut] = []
    same = 0
    for mark, old_id in left_by.items():
        new_id = right_by.get(mark)
        if new_id is None:
            continue
        gone, fresh = before[old_id], after[new_id]
        differences = [
            RevisionDifferenceOut(
                at=one, before=gone.get(one) or None, after=fresh.get(one) or None
            )
            for one in sorted(set(gone) | set(fresh))
            if gone.get(one) != fresh.get(one)
        ]
        if differences:
            changed.append(
                RevisionChangedOut(
                    name=rows[new_id].name,
                    before_id=old_id,
                    after_id=new_id,
                    differences=differences,
                )
            )
        else:
            same += 1

    added.sort(key=lambda one: one.name)
    removed.sort(key=lambda one: one.name)
    changed.sort(key=lambda one: one.name)
    return RevisionCompareOut(
        document_id=left.document_id,
        before=RevisionBriefOut(id=left.id, label=left.label, test_count=len(before)),
        after=RevisionBriefOut(id=right.id, label=right.label, test_count=len(after)),
        added=added,
        removed=removed,
        changed=changed,
        unchanged_count=same,
    )


def _brief(row: ReliabilityTest) -> RevisionTestBriefOut:
    return RevisionTestBriefOut(id=row.id, name=row.name, status=row.status)


def siblings(
    db: Session, division_code: str, name: str, except_id: uuid.UUID | None
) -> list[SiblingTestOut]:
    """이름이 같은 다른 시험 — **무엇으로 갈렸는지** 함께.

    같은 이름이 적용군·규격서마다 여럿 있을 수 있다(0044). 적으면서 그 목록이 보이면
    중복으로 올리다 409 를 받는 일이 줄고, 옆 제품군이 어떤 조건으로 하는지 보면서 적을
    수 있다 — 같은 시험의 다른 벌이 서로 다른 값을 갖는 것을 그 자리에서 안다.
    """
    division = division_by_code(db, division_code)
    key = name_key(name)
    rows = [
        one
        for one in db.scalars(
            select(ReliabilityTest).where(
                ReliabilityTest.division_term_id == division.id,
                ReliabilityTest.deleted_at.is_(None),
                ReliabilityTest.id != except_id if except_id else true(),
            )
        )
        if name_key(one.name) == key
    ]
    if not rows:
        return []
    scopes = _scope_of_rows(db, [one.id for one in rows])
    terms = {
        one.id: one.value
        for one in db.scalars(
            select(VocabularyTerm).where(
                VocabularyTerm.id.in_({uuid.UUID(g) for g, _ in scopes.values() if g})
            )
        )
    }
    papers = {
        one.id: one.code or one.title
        for one in db.scalars(
            select(SpecDocument).where(
                SpecDocument.id.in_({uuid.UUID(d) for _, d in scopes.values() if d})
            )
        )
    }
    labels = {
        one.id: one.label
        for one in db.scalars(
            select(SpecDocumentRevision).where(
                SpecDocumentRevision.id.in_(
                    {r.document_revision_id for r in rows if r.document_revision_id}
                )
            )
        )
    }
    out = []
    for one in rows:
        group, document = scopes.get(one.id, ("", ""))
        out.append(
            SiblingTestOut(
                id=one.id,
                name=one.name,
                status=one.status,
                product_group=terms.get(uuid.UUID(group)) if group else None,
                spec_document_code=papers.get(uuid.UUID(document)) if document else None,
                document_revision_label=labels.get(one.document_revision_id)
                if one.document_revision_id
                else None,
            )
        )
    out.sort(key=lambda one: (one.product_group or "", one.spec_document_code or ""))
    return out

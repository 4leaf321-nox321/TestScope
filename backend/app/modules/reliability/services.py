"""신뢰성 시험 — 읽기는 로그인한 누구나, 쓰기는 그 부서의 관리자와 시스템 관리자.

**그리고 기계 자격(PAT)으로 들어온 쓰기는 후보가 된다**(ADR 0009). AI 는 시험 표준서를
읽어 스물두 칸을 한 번에 채울 수 있는데, 틀려도 그만큼 빠르다 — 그 값으로 장비를 고르고
그 장비로 보고서가 나간다. 사람이 읽고 확인해야 확정이다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, select, true
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.attachments import services as attachments
from app.modules.attachments.models import Attachment
from app.modules.attributes import filters as attribute_filters
from app.modules.attributes import services as attributes
from app.modules.attributes.models import AttributeDefinition, AttributeValue
from app.modules.attributes.schemas import AttributeValueIn
from app.modules.documents import services as documents
from app.modules.equipment.models import Equipment
from app.modules.reliability.models import ReliabilityTest, ReliabilityTestItem
from app.modules.reliability.schemas import (
    DivisionOut,
    ReliabilityTestItemOut,
    ReliabilityTestOut,
)
from app.modules.test_items.models import EquipmentTestItem
from app.modules.vocabulary.models import Vocabulary, VocabularyTerm
from app.shared import audit
from app.shared.errors import AppError, Conflict, Forbidden, NotFound
from app.shared.permissions import (
    division_map,
    my_division_term_ids,
    visible_equipment_ids,
)
from app.shared.request_context import get_actor_token

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
) -> list[ReliabilityTestOut]:
    """그 사업부의 시험 — **후보까지 보인다.** 후보를 검토하는 자리가 여기다.

    후보가 먼저 온다. 목록 아래쪽에 섞여 있으면 아무도 안 본다."""
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
    narrowed = _by_document(_by_status(stmt, status, default="all"), document_id)
    rows = list(db.scalars(_by_attributes(db, narrowed, attrs)))
    return _outs(db, user, rows)


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
                AttributeValue.ref_document_id == document_id
            )
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
) -> list[ReliabilityTestOut]:
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
    narrowed = _by_document(_by_status(stmt, status, default=CONFIRMED), document_id)
    rows = list(db.scalars(_by_attributes(db, narrowed, attrs)))
    return _outs(db, user, rows)


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


def _check_name_free(
    db: Session, division_term_id: uuid.UUID, name: str, *, except_id: uuid.UUID | None
) -> None:
    clash = db.scalar(
        select(ReliabilityTest).where(
            ReliabilityTest.division_term_id == division_term_id,
            ReliabilityTest.deleted_at.is_(None),
            func.lower(ReliabilityTest.name) == name.lower(),
            ReliabilityTest.id != except_id if except_id else true(),
        )
    )
    if clash is not None:
        raise Conflict(
            "TSC-RELIABILITY-0003", f"이 사업부에 같은 이름의 신뢰성 시험이 있습니다: {name}"
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
    _check_name_free(db, division.id, name, except_id=None)
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
        items=_attribute_items(payload.get("attributes")),
    )
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

    if "name" in changes:
        name = str(changes["name"]).strip()
        if not name:
            raise AppError("TSC-RELIABILITY-0004", "이름을 적어 주십시오.")
        _check_name_free(db, division.id, name, except_id=row.id)
        row.name = name
    if "purpose" in changes:
        row.purpose = str(changes["purpose"] or "").strip()
    if changes.get("test_item_term_ids") is not None:
        term_ids = list(changes["test_item_term_ids"])
        _check_test_item_terms(db, term_ids)
        _set_items(db, row.id, term_ids)
    if changes.get("attributes") is not None:
        attributes.set_values(
            db,
            user,
            target="reliability_test",
            object_id=row.id,
            items=_attribute_items(changes["attributes"]),
        )
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


def reopen(db: Session, user: User, test_id: uuid.UUID) -> ReliabilityTest:
    """확정을 풀어 **다시 후보로.** 그 순간부터 AI 가 다시 채울 수 있다.

    확인을 지우지 않는다 — `confirmed_by_id` · `confirmed_at` 은 그대로 두고 상태만 돌린다.
    「전에 누가 봤었나」 는 다시 확인할 때 도움이 된다.
    """
    row = get(db, test_id)
    _human_only(row, "다시 후보로 여는 것은")
    require_editable(db, user, test_id)
    if row.status == CANDIDATE:
        return row
    division = db.get(VocabularyTerm, row.division_term_id)
    assert division is not None
    row.status = CANDIDATE
    audit.record(
        db,
        action=audit.RELIABILITY_TEST_REOPENED,
        actor=user,
        target_table="reliability_tests",
        target_id=row.id,
        target_label=f"{division.value} · {row.name}",
        changes={"status": {"before": CONFIRMED, "after": CANDIDATE}},
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
    """여러 줄을 한 번에 — 확인 · 반려 · 지우기.

    **AI 가 몇천 건을 올린다.** 줄마다 창을 열어 확인을 누르는 것은 사람이 할 수 있는
    일이 아니고, 못 하면 후보가 쌓인 채로 아무도 안 본다 — 그러면 확인이라는 단계가
    이름만 남는다.

    **줄마다 결과를 돌려준다.** 전부 되거나 전부 안 되거나로 두면, 오백 줄 중 한 줄이
    남의 사업부라는 이유로 사백구십구 줄이 함께 막힌다. 안 된 줄은 **왜**와 함께 온다 —
    「12건 실패」 만으로는 다시 누를지 고칠지 알 수 없다.
    """
    if not ids:
        raise AppError("TSC-RELIABILITY-0011", "고른 줄이 없습니다.")
    if len(ids) > BULK_LIMIT:
        raise AppError(
            "TSC-RELIABILITY-0011",
            f"한 번에 {BULK_LIMIT}건까지입니다 — {len(ids)}건을 골랐습니다. 나눠 누르십시오.",
        )
    run = {"confirm": confirm, "reject": reject, "delete": delete}.get(action)
    if run is None:
        raise AppError("TSC-RELIABILITY-0011", f"알 수 없는 동작입니다: {action}")

    done: list[str] = []
    failed: list[dict[str, str]] = []
    for test_id in ids:
        try:
            if action == "reject":
                reject(db, user, test_id, reason or "")
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

    created: list[ReliabilityTest] = []
    failed: list[dict[str, str]] = []
    for one in tests:
        name = str(one.get("name") or "")
        items = [dict(each) for each in (one.get("attributes") or [])]
        if document_id is not None:
            items = _with_document(items, definition, uuid.UUID(str(document_id)))
        try:
            created.append(
                create(
                    db,
                    user,
                    {
                        "division_code": str(payload["division_code"]),
                        "name": name,
                        "purpose": one.get("purpose") or "",
                        "test_item_term_ids": one.get("test_item_term_ids") or [],
                        "attributes": items,
                    },
                )
            )
        except AppError as refused:
            # **한 줄이 막혀도 나머지는 간다.** 반쯤 만들어진 줄을 되돌리고 다음으로 —
            # 안 그러면 실패한 줄의 조각이 다음 줄의 커밋에 묻어 간다.
            db.rollback()
            failed.append({"name": name, "code": refused.code, "message": refused.message})
    return {
        "requested": len(tests),
        "created": _outs(db, user, created),
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

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
from app.modules.attributes.schemas import AttributeValueIn
from app.modules.equipment.models import Equipment
from app.modules.reliability.models import ReliabilityTest, ReliabilityTestItem
from app.modules.reliability.schemas import ReliabilityTestItemOut, ReliabilityTestOut
from app.modules.test_items.models import EquipmentTestItem
from app.modules.vocabulary.models import Vocabulary, VocabularyTerm
from app.modules.workspaces.models import Workspace
from app.shared import audit
from app.shared.errors import AppError, Conflict, Forbidden, NotFound
from app.shared.permissions import (
    membership_of,
    require_manager,
    visible_equipment_ids,
    workspace_by_slug,
)
from app.shared.request_context import get_actor_token

CANDIDATE = "candidate"
CONFIRMED = "confirmed"


def _machine() -> str | None:
    """기계 자격으로 들어온 요청이면 그 토큰 이름. 사람 세션이면 None.

    **`user` 로는 못 가른다** — PAT 의 소유자도 사람이라 `created_by` 는 같은 값이 된다.
    통로를 아는 곳은 인증 의존성뿐이고, 그것이 `request_context` 에 남긴다.
    """
    return get_actor_token()


def _can_edit(db: Session, user: User, workspace_id: uuid.UUID) -> bool:
    if user.is_system_admin:
        return True
    membership = membership_of(db, workspace_id=workspace_id, user_id=user.id)
    return membership is not None and membership.role == "manager"


def _equipment_counts(
    db: Session, user: User, workspace_id: uuid.UUID, term_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """시험 항목마다 **이 부서의** 장비 수. 카탈로그의 `?workspace=` 와 같은 셈이다."""
    if not term_ids:
        return {}
    owned = visible_equipment_ids(db, user).where(Equipment.owner_workspace_id == workspace_id)
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
    workspace_ids = {r.workspace_id for r in rows}
    workspaces = {
        w.id: w for w in db.scalars(select(Workspace).where(Workspace.id.in_(workspace_ids)))
    }
    items = _items_of(db, [r.id for r in rows])
    attribute_values = attributes.values_of(
        db, target="reliability_test", object_ids=[r.id for r in rows]
    )
    counts_by_workspace: dict[uuid.UUID, dict[uuid.UUID, int]] = {}
    for workspace_id in workspaces:
        term_ids = sorted(
            {t.id for r in rows if r.workspace_id == workspace_id for t in items[r.id]}
        )
        counts_by_workspace[workspace_id] = _equipment_counts(db, user, workspace_id, term_ids)
    editable = {wid: _can_edit(db, user, wid) for wid in workspaces}
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
        workspace = workspaces[row.workspace_id]
        counts = counts_by_workspace[row.workspace_id]
        out.append(
            ReliabilityTestOut(
                id=row.id,
                workspace_slug=workspace.slug,
                workspace_name=workspace.name,
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
                can_edit=editable[row.workspace_id],
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


def list_for_workspace(
    db: Session,
    user: User,
    slug: str,
    attrs: list[str] | None = None,
    status: str | None = None,
) -> list[ReliabilityTestOut]:
    """그 부서의 시험 — **후보까지 보인다.** 후보를 검토하는 자리가 여기다.

    후보가 먼저 온다. 목록 아래쪽에 섞여 있으면 아무도 안 본다."""
    workspace = workspace_by_slug(db, slug)
    stmt = (
        select(ReliabilityTest)
        .where(
            ReliabilityTest.workspace_id == workspace.id,
            ReliabilityTest.deleted_at.is_(None),
        )
        # 후보(candidate)가 확정(confirmed)보다 앞 — 글자 순이 마침 그렇다.
        .order_by(ReliabilityTest.status, ReliabilityTest.name)
    )
    rows = list(db.scalars(_by_attributes(db, _by_status(stmt, status, default="all"), attrs)))
    return _outs(db, user, rows)


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
    db: Session, user: User, attrs: list[str] | None = None, status: str | None = None
) -> list[ReliabilityTestOut]:
    """전사의 신뢰성 시험 — **「저 부서는 무슨 시험을 하나」 를 부서를 가로질러 묻는 표.**
    읽기는 누구나(부서를 가로지르는 것이 이 시스템의 물음), 고치기는 각 부서 화면에서.
    부서 순서(조직도) → 이름.

    **기본은 확정된 것만이다.** 이 표는 「저 부서가 무슨 시험을 하나」 에 답하는데, 아직
    확인 안 된 후보는 그 답이 아니다 — 옆 부서 사람은 배지를 안 보고 읽는다. 후보는 그
    부서 화면에서 보고, 여기서는 `status="all"` 로 일부러 열어야 보인다."""
    stmt = (
        select(ReliabilityTest)
        .join(Workspace, Workspace.id == ReliabilityTest.workspace_id)
        .where(ReliabilityTest.deleted_at.is_(None))
        .order_by(Workspace.sort_order, Workspace.name, ReliabilityTest.name)
    )
    rows = list(
        db.scalars(_by_attributes(db, _by_status(stmt, status, default=CONFIRMED), attrs))
    )
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
    db: Session, workspace_id: uuid.UUID, name: str, *, except_id: uuid.UUID | None
) -> None:
    clash = db.scalar(
        select(ReliabilityTest).where(
            ReliabilityTest.workspace_id == workspace_id,
            ReliabilityTest.deleted_at.is_(None),
            func.lower(ReliabilityTest.name) == name.lower(),
            ReliabilityTest.id != except_id if except_id else true(),
        )
    )
    if clash is not None:
        raise Conflict(
            "TSC-RELIABILITY-0003", f"이 부서에 같은 이름의 신뢰성 시험이 있습니다: {name}"
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


def create(db: Session, user: User, payload: dict[str, Any]) -> ReliabilityTest:
    workspace = workspace_by_slug(db, payload["workspace_slug"])
    require_manager(db, workspace=workspace, user=user)
    name = str(payload["name"]).strip()
    if not name:
        raise AppError("TSC-RELIABILITY-0004", "이름을 적어 주십시오.")
    _check_name_free(db, workspace.id, name, except_id=None)
    term_ids: list[uuid.UUID] = list(payload.get("test_item_term_ids") or [])
    _check_test_item_terms(db, term_ids)

    # **어느 통로로 들어왔나.** 기계 자격이면 후보로 선다 — 사람이 읽고 확인해야 확정이다.
    via = _machine()
    row = ReliabilityTest(
        workspace_id=workspace.id,
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
    workspace = db.get(Workspace, row.workspace_id)
    assert workspace is not None
    require_manager(db, workspace=workspace, user=user)
    _refuse_machine_edit(row)


def update(
    db: Session, user: User, test_id: uuid.UUID, changes: dict[str, Any]
) -> ReliabilityTest:
    """`changes` 는 `exclude_unset` 으로 온다 — 안 보낸 칸은 안 건드린다."""
    row = get(db, test_id)
    require_editable(db, user, test_id)
    workspace = db.get(Workspace, row.workspace_id)
    assert workspace is not None

    if "name" in changes:
        name = str(changes["name"]).strip()
        if not name:
            raise AppError("TSC-RELIABILITY-0004", "이름을 적어 주십시오.")
        _check_name_free(db, workspace.id, name, except_id=row.id)
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
    workspace = db.get(Workspace, row.workspace_id)
    assert workspace is not None
    row.status = CONFIRMED
    row.confirmed_by_id = user.id
    row.confirmed_at = datetime.now(UTC)
    audit.record(
        db,
        action=audit.RELIABILITY_TEST_CONFIRMED,
        actor=user,
        target_table="reliability_tests",
        target_id=row.id,
        target_label=f"{workspace.name} · {row.name}",
        workspace_id=workspace.id,
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
    workspace = db.get(Workspace, row.workspace_id)
    assert workspace is not None
    row.status = CANDIDATE
    audit.record(
        db,
        action=audit.RELIABILITY_TEST_REOPENED,
        actor=user,
        target_table="reliability_tests",
        target_id=row.id,
        target_label=f"{workspace.name} · {row.name}",
        workspace_id=workspace.id,
        changes={"status": {"before": CONFIRMED, "after": CANDIDATE}},
    )
    db.commit()
    db.refresh(row)
    return row


def delete(db: Session, user: User, test_id: uuid.UUID) -> None:
    row = get(db, test_id)
    workspace = db.get(Workspace, row.workspace_id)
    assert workspace is not None
    require_manager(db, workspace=workspace, user=user)
    # **확정된 것은 기계가 못 내린다.** 고치는 것을 막고 지우는 것을 열어 두면, 그 길로
    # 가면 결과는 더 나쁘다. 제가 만든 후보를 거두는 것은 된다.
    _refuse_machine_edit(row)
    # **그림도 같이 간다.** 시험이 안 보이는데 파일만 남으면 디스크를 먹고, 그것을
    # 알아챌 자리가 없다. 파일 자체는 다른 시험이 그 그림을 안 쓸 때만 지워진다.
    removed = attachments.remove_all(db, target="reliability_test", object_id=row.id)
    row.deleted_at = datetime.now(UTC)
    # **반년 뒤에 「그 시험 어디 갔어」 를 묻는다.** 지운 줄은 화면에서 사라지므로 여기 남는다.
    audit.record(
        db,
        action=audit.RELIABILITY_TEST_DELETED,
        actor=user,
        target_table="reliability_tests",
        target_id=row.id,
        # **그림이 몇 장 같이 갔는지 적는다** — 「사진이 없어졌어요」 를 나중에 물을 때
        # 그것이 이 삭제 때문인지 가릴 자리가 여기뿐이다.
        target_label=f"{workspace.name} · {row.name}"
        + (f" (그림 {removed}장 함께 지움)" if removed else ""),
        workspace_id=workspace.id,
    )
    db.commit()

"""시험 항목 제안 — **축에 맞는 값이 없을 때 그 사실을 남길 자리.**

시험 항목 축은 closed 다. 검색의 첫 축이라 오타 하나가 값이 되면 그 뒤로 아무도 못 찾는다 —
그래서 기계가 값을 못 더하는 것은 **옳다.** 그런데 못 더하는 쪽에 **말할 자리도** 없었다:
스무 건 중 아홉 건이 시험 항목 없이 들어왔고, 왜 비었는지가 아무 데도 안 남아 검토하는
사람은 그 아홉 건을 「안 적은 것」 과 구별할 수 없었다(2026-09-30).

**두 가지를 함께 한다.** 제안은 그 시험에 붙어(왜 비었는지가 그 줄에 보인다) 동시에 같은
말끼리 모여 검토 목록에 선다(스무 번이 아니라 한 번 판단한다). 관리자가 정하면 그 제안을
낸 시험들에 **한꺼번에** 걸린다.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.reliability.models import (
    ReliabilityTest,
    ReliabilityTestItem,
    TestItemProposal,
)
from app.modules.reliability.schemas import (
    TestItemProposalGroupOut,
    TestItemProposalOut,
)
from app.modules.vocabulary.models import Vocabulary, VocabularyTerm
from app.shared import audit
from app.shared.errors import AppError, Forbidden, NotFound
from app.shared.request_context import get_actor_token
from app.shared.text import clean, compare_key

OPEN = "open"
#: 정한 것들 — 기존 값에 이었다 · 축에 세웠다 · 아니라고 했다.
DECIDED = ("linked", "created", "rejected")


def proposal_key(text: str) -> str:
    """같은 말을 모으는 비교키 — 띄어쓰기까지 지운다.

    「염수 분무」 와 「염수분무」 가 다른 줄로 서면 관리자가 같은 판단을 두 번 한다.
    신뢰성 시험 이름(`name_key`)·속성 이름과 같은 규칙이다.
    """
    return "".join(compare_key(text).split())


def _out(db: Session, row: TestItemProposal) -> TestItemProposalOut:
    test = db.get(ReliabilityTest, row.reliability_test_id)
    term = db.get(VocabularyTerm, row.term_id) if row.term_id else None
    return TestItemProposalOut(
        id=row.id,
        text=row.text,
        note=row.note,
        status=row.status,
        reliability_test_id=row.reliability_test_id,
        reliability_test_name=test.name if test else "(시험 없음)",
        term_id=row.term_id,
        term_value=term.value if term else None,
        submitted_via=row.submitted_via,
        created_at=row.created_at,
    )


def of_test(db: Session, test_id: uuid.UUID) -> list[TestItemProposalOut]:
    """그 시험에 붙은 제안 — **왜 시험 항목이 비었는지가 그 줄에 보인다.**"""
    rows = db.scalars(
        select(TestItemProposal)
        .where(TestItemProposal.reliability_test_id == test_id)
        .order_by(TestItemProposal.created_at)
    )
    return [_out(db, one) for one in rows]


def add(db: Session, user: User, payload: dict[str, Any]) -> TestItemProposal:
    """제안 한 줄. **시험을 고칠 수 있는 사람이면 낼 수 있다** — 기계 자격도 된다.

    축에 값을 더하는 것이 아니라 「이런 말이 문서에 있었다」 를 적는 것이라, closed 축의
    빗장을 건드리지 않는다.
    """
    from app.modules.reliability import services

    test = services.get(db, uuid.UUID(str(payload["reliability_test_id"])))
    services.require_editable(db, user, test.id)
    text = clean(str(payload["text"]))
    if not text:
        raise AppError("TSC-RELIABILITY-0013", "제안할 말을 적어 주십시오.")
    key = proposal_key(text)
    if not key:
        raise AppError("TSC-RELIABILITY-0013", "제안할 말을 적어 주십시오.")
    found = db.scalar(
        select(TestItemProposal).where(
            TestItemProposal.reliability_test_id == test.id,
            TestItemProposal.normalized == key,
        )
    )
    if found is not None:
        # **같은 말을 두 번 내도 거절하지 않는다.** 적재를 다시 돌리는 일이 흔하고, 그때
        # 409 가 오면 부른 쪽은 그 줄을 실패로 세어 사람에게 없는 문제를 보고한다.
        if payload.get("note"):
            found.note = str(payload["note"])
            db.commit()
        return found
    row = TestItemProposal(
        text=text,
        normalized=key,
        reliability_test_id=test.id,
        note=payload.get("note") or None,
        status=OPEN,
        submitted_via=get_actor_token(),
        created_by_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def groups(db: Session, *, include_decided: bool = False) -> list[TestItemProposalGroupOut]:
    """같은 말끼리 모은 검토 목록 — **건수가 큰 것이 먼저.**

    같은 말이 스무 시험에서 나왔으면 그것은 축에 없는 것이 거의 확실하고, 한 번 정하면
    스무 건이 함께 풀린다. 한 번 나온 말은 오타일 수 있어 뒤에 둔다.
    """
    stmt = select(TestItemProposal)
    if not include_decided:
        stmt = stmt.where(TestItemProposal.status == OPEN)
    rows = list(db.scalars(stmt))
    buckets: dict[str, list[TestItemProposal]] = {}
    for one in rows:
        buckets.setdefault(one.normalized, []).append(one)
    out = [
        TestItemProposalGroupOut(
            normalized=key,
            # 표기가 갈리면 **가장 많이 쓰인 것**을 대표로 — 「염수분무」 셋과 「염수 분무」
            # 하나면 앞의 것이 문서의 말일 가능성이 높다.
            text=max(
                {one.text for one in mine},
                key=lambda t: sum(1 for x in mine if x.text == t),
            ),
            count=len(mine),
            proposals=[_out(db, one) for one in sorted(mine, key=lambda x: x.created_at)],
        )
        for key, mine in buckets.items()
    ]
    out.sort(key=lambda one: (-one.count, one.text))
    return out


def decide(db: Session, user: User, payload: dict[str, Any]) -> dict[str, Any]:
    """제안 한 묶음을 정한다 — **시스템 관리자만.**

    `term_id` 를 주면 기존 값에 잇고, `new_value` 를 주면 축에 값을 세운 뒤 잇는다. 둘 다
    없으면 아니라고 한 것이다(`rejected`).

    이은 값은 **그 제안을 낸 시험들에 한꺼번에 걸린다** — 스무 건을 스무 번 여는 것이
    이 기능이 없앤 일이다.
    """
    if not user.is_system_admin:
        raise Forbidden(
            "TSC-RELIABILITY-0014",
            "시험 항목 축은 시스템 관리자가 세웁니다 — 검색의 첫 축이라 값이 갈리면"
            " 그 뒤로 아무도 못 찾습니다.",
        )
    key = proposal_key(str(payload["normalized"]))
    rows = list(
        db.scalars(
            select(TestItemProposal).where(
                TestItemProposal.normalized == key, TestItemProposal.status == OPEN
            )
        )
    )
    if not rows:
        raise NotFound("TSC-RELIABILITY-0015", "그 제안을 찾을 수 없습니다.")

    term: VocabularyTerm | None = None
    status = "rejected"
    if payload.get("term_id"):
        term = db.get(VocabularyTerm, uuid.UUID(str(payload["term_id"])))
        if term is None:
            raise NotFound("TSC-RELIABILITY-0015", "그 온톨로지 값을 찾을 수 없습니다.")
        status = "linked"
    elif payload.get("new_value"):
        term = _create_term(db, user, str(payload["new_value"]))
        status = "created"

    linked = 0
    for one in rows:
        one.status = status
        one.term_id = term.id if term else None
        one.decided_at = datetime.now(UTC)
        one.decided_by_id = user.id
        if term is not None and _attach(db, one.reliability_test_id, term.id):
            linked += 1
    audit.record(
        db,
        action=audit.TEST_ITEM_PROPOSAL_DECIDED,
        actor=user,
        target_table="test_item_proposals",
        target_id=rows[0].id,
        target_label=f"{rows[0].text} → {term.value if term else '아니오'} ({len(rows)}건)",
    )
    db.commit()
    return {
        "normalized": key,
        "status": status,
        "term_id": str(term.id) if term else None,
        "decided": len(rows),
        "linked": linked,
    }


def _create_term(db: Session, user: User, value: str) -> VocabularyTerm:
    """축에 값을 세운다 — **같은 말이 이미 있으면 그것을 쓴다.**

    모델을 손으로 만들지 않고 **온톨로지의 제 경로를 지난다**(`terms.create_term`). 값 한
    줄에는 비교키·코드 유일성·closed 정책 같은 불변식이 걸려 있고, 여기서 다시 세우면
    그중 하나를 빠뜨린다 — 실제로 `normalized` 를 빠뜨려 NOT NULL 에 걸렸다.
    """
    from app.modules.vocabulary import terms as vocabulary_terms

    text = clean(value)
    if not text:
        raise AppError("TSC-RELIABILITY-0013", "세울 값을 적어 주십시오.")
    axis = db.scalar(select(Vocabulary).where(Vocabulary.slug == "test_item"))
    if axis is None:  # pragma: no cover - 설치가 심는다
        raise AppError("TSC-RELIABILITY-0002", "시험 항목 축이 없습니다.")
    key = proposal_key(text)
    for one in db.scalars(
        select(VocabularyTerm).where(VocabularyTerm.vocabulary_id == axis.id)
    ):
        if proposal_key(one.value) == key:
            return one
    return vocabulary_terms.create_term(
        db,
        slug="test_item",
        value=text,
        code=None,
        parent_term_id=None,
        attributes={},
        actor=user,
        is_admin=True,
    )


def _attach(db: Session, test_id: uuid.UUID, term_id: uuid.UUID) -> bool:
    """그 시험에 시험 항목을 건다. 이미 걸려 있으면 아무것도 안 한다."""
    found = db.scalar(
        select(func.count())
        .select_from(ReliabilityTestItem)
        .where(
            ReliabilityTestItem.reliability_test_id == test_id,
            ReliabilityTestItem.test_item_term_id == term_id,
        )
    )
    if found:
        return False
    db.add(ReliabilityTestItem(reliability_test_id=test_id, test_item_term_id=term_id))
    db.flush()
    return True

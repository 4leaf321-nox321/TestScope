"""신뢰성 시험 라우터 — 부서가 수행하는 시험. 읽기는 누구나, 쓰기는 그 부서의 관리자."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.attributes import services as attributes
from app.modules.attributes.schemas import AttributeValueOut
from app.modules.reliability import capability as capability_service
from app.modules.reliability import proposals as proposal_service
from app.modules.reliability import services
from app.modules.reliability.schemas import (
    CapabilityOut,
    CapabilityPreviewRequest,
    DivisionOut,
    ReliabilityBatchOut,
    ReliabilityBatchRequest,
    ReliabilityBulkOut,
    ReliabilityBulkRequest,
    ReliabilityRejectRequest,
    ReliabilityTestCreateRequest,
    ReliabilityTestOut,
    ReliabilityTestUpdateRequest,
    RevisionCompareOut,
    SiblingTestOut,
    TestItemProposalDecision,
    TestItemProposalGroupOut,
    TestItemProposalOut,
    TestItemProposalRequest,
)
from app.shared.auth import current_user

router = APIRouter(prefix="/reliability-tests", tags=["reliability"])


@router.get("", response_model=list[ReliabilityTestOut])
def list_reliability_tests(
    division: str | None = Query(default=None, max_length=120),
    attr: list[str] = Query(default_factory=list, max_length=10),
    status: Literal["candidate", "confirmed", "all"] | None = Query(default=None),
    document: uuid.UUID | None = Query(default=None),
    revision: uuid.UUID | None = Query(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[ReliabilityTestOut]:
    """신뢰성 시험 — **부서가 등록한 절차**다. 「시험 항목」(장비가 할 수 있는 측정, 전사
    공용)과 다르다. `division` 에 사업부 코드(`mx`…)를 주면 그 사업부 것만, 안 주면 전사
    전부(사업부 순). 시험마다 쓰는 시험 항목과, 그 항목이 되는 **그 사업부의** 장비 수를
    함께 준다 — 0 이면 시험은 정했는데
    돌릴 장비가 없다는 뜻이다.

    `attr` 은 **속성 값으로 거른다** — 여러 번 주면 모두 만족해야 한다(`attr=<키><연산><값>`,
    연산은 `>=` `<=` `>` `<` `=` `!=` `~`(포함) `*`(적혀 있기만 하면)). 왼쪽은 속성 정의의
    `key` 다 — 이름은 관리자가 고치면 바뀌고, 그때 저장해 둔 주소가 조용히 빈 답을 낸다.

    `status` 를 **안 주면 자리에 따라 다르다** — 사업부를 주면 후보까지(검토하는 자리라서),
    전사면 확정된 것만(「저 사업부가 무슨 시험을 하나」 에 후보는 아직 답이 아니다). 일부러
    보려면 `status="all"`, 후보만 세려면 `status="candidate"`.

    `revision` 에 규격서 판 id 를 주면 **그 판의 목록**이 온다 — 판마다 한 벌이라 계산이
    없다. `document` 에 사내 규격서 id 를 주면 **그 문서에서 나온 줄만** 온다 — 묶음으로 올라온
    스무 건을 한 자리에서 보고 한 번에 확인·반려하는 길이다.
    """
    if division:
        return services.list_for_division(db, user, division, attr, status, document, revision)
    return services.list_all(db, user, attr, status, document, revision)


@router.get("/divisions", response_model=list[DivisionOut])
def list_divisions(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[DivisionOut]:
    """사업부 목록 — 줄마다 **내가 올릴 수 있는지**를 함께 준다.

    `/reliability-tests/{id}` 보다 **먼저** 선언한다 — 뒤에 두면 `divisions` 가 id 로
    읽혀서 「신뢰성 시험을 찾을 수 없습니다」 가 온다.
    """
    return services.divisions(db, user)


@router.post("", response_model=ReliabilityTestOut, status_code=201)
def create_reliability_test(
    payload: ReliabilityTestCreateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ReliabilityTestOut:
    """등록 — 그 부서의 관리자 또는 시스템 관리자. `test_item_term_ids` 는 시험 항목 축의
    값이어야 한다(`POST /api/resolve` 로 먼저 찾는다)."""
    row = services.create(db, user, payload.model_dump())
    return services.test_out(db, user, row)


@router.post("/capability-preview", response_model=CapabilityOut)
def capability_preview(
    payload: CapabilityPreviewRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> CapabilityOut:
    """**아직 저장하지 않은 조건**으로 장비를 본다 — 적으면서 보는 자리.

    지금은 저장한 뒤 따로 열어야 보여서, 「95 °C 로 올리면 돌릴 장비가 0대」 를 저장하고
    나서 안다. 단위 환산은 서버가 한다 — 화면이 SI 로 바꿔 보내면 그 환산이 두 벌이 된다.

    **`/{test_id}` 보다 먼저 선언한다.**
    """
    return capability_service.preview(
        db,
        user,
        test_item_term_ids=payload.test_item_term_ids,
        items=payload.attributes,
    )


@router.get("/siblings", response_model=list[SiblingTestOut])
def siblings(
    division: str = Query(max_length=120),
    name: str = Query(max_length=200),
    exclude: uuid.UUID | None = Query(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[SiblingTestOut]:
    """이름이 같은 다른 시험 — **무엇으로 갈렸는지**(적용군·규격서·판) 함께.

    적으면서 이 목록이 보이면 중복으로 올리다 409 를 받는 일이 줄고, 옆 제품군이 어떤
    조건으로 하는지 보면서 적을 수 있다.
    """
    return services.siblings(db, division, name, exclude)


@router.get("/revision-compare", response_model=RevisionCompareOut)
def compare_revisions(
    before: uuid.UUID = Query(description="앞 판"),
    after: uuid.UUID = Query(description="뒤 판"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> RevisionCompareOut:
    """같은 규격서의 **두 판을 견준다** — 더해진 시험 · 없어진 시험 · 조건이 바뀐 시험.

    개정이 오면 딸린 수십 건 중 **무엇을 다시 봐야 하는지**가 문제다. 「전부 다시」 는 그날
    일을 멈추고 「아무것도 안 봄」 은 바뀐 조건을 놓친다.

    **`/{test_id}` 보다 먼저 선언한다** — 뒤에 두면 id 로 읽혀 404 가 온다.
    """
    return services.compare_revisions(db, user, before, after)


@router.get("/item-proposals", response_model=list[TestItemProposalGroupOut])
def list_item_proposals(
    include_decided: bool = Query(default=False),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[TestItemProposalGroupOut]:
    """시험 항목 제안 — **같은 말끼리 모아서.** 건수가 큰 것이 먼저.

    축(`test_item`)이 closed 라 기계는 값을 못 더한다. 그래서 「문서에 이런 말이 있었는데
    축에 없다」 를 여기에 쌓고, 관리자가 한 번 정하면 그 말을 낸 시험들에 함께 걸린다.

    **`/{test_id}` 보다 먼저 선언한다** — 뒤에 두면 id 로 읽혀 404 가 온다.
    """
    return proposal_service.groups(db, include_decided=include_decided)


@router.post("/item-proposals", response_model=TestItemProposalOut, status_code=201)
def add_item_proposal(
    payload: TestItemProposalRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> TestItemProposalOut:
    """축에 맞는 값이 없다는 것을 남긴다. 그 시험을 고칠 수 있는 사람이면 된다(기계도).

    **같은 말을 두 번 내도 거절하지 않는다** — 적재를 다시 돌리는 일이 흔하고, 그때 409 가
    오면 부른 쪽은 그 줄을 실패로 세어 사람에게 없는 문제를 보고한다.
    """
    row = proposal_service.add(db, user, payload.model_dump())
    return proposal_service._out(db, row)


@router.post("/item-proposals/decide")
def decide_item_proposal(
    payload: TestItemProposalDecision,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """제안 한 묶음을 정한다 — **시스템 관리자만.** 정한 값이 그 말을 낸 시험들에
    한꺼번에 걸린다."""
    return proposal_service.decide(db, user, payload.model_dump())


@router.get("/{test_id}", response_model=ReliabilityTestOut)
def read_reliability_test(
    test_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ReliabilityTestOut:
    return services.test_out(db, user, services.get(db, test_id))


@router.get("/{test_id}/equipment", response_model=CapabilityOut)
def read_capability(
    test_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> CapabilityOut:
    """**이 시험을 돌릴 수 있는 장비.** 조건 속성(`kind="condition"`)을 그대로 검색 조건으로
    옮겨 시험 항목마다 장비를 판정한다 — 판정 규칙은 장비 찾기와 같은 것 하나다.

    범위 속성 하나는 물음 둘이 된다(위로 얼마까지 · 아래로 얼마까지). 단위를 축의 SI 로
    못 바꾸는 조건은 빼고 `skipped` 에 이유를 적는다 — 조용히 빼면 조건을 다 본 것처럼
    「가능」 으로 읽힌다.

    부서로 좁히지 않는다. 옆 부서에 있으면 빌리러 가는 것이 이 시스템의 쓸모다.
    """
    return capability_service.capability(db, user, services.get(db, test_id))


@router.patch("/{test_id}", response_model=ReliabilityTestOut)
def update_reliability_test(
    test_id: uuid.UUID,
    payload: ReliabilityTestUpdateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ReliabilityTestOut:
    """부분 수정. 안 보낸 칸은 그대로, `test_item_term_ids` 는 보내면 통째로 바뀐다."""
    row = services.update(db, user, test_id, payload.model_dump(exclude_unset=True))
    return services.test_out(db, user, row)


@router.post("/{test_id}/confirm", response_model=ReliabilityTestOut)
def confirm_reliability_test(
    test_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ReliabilityTestOut:
    """**후보를 확인했다** — 사람이 내용을 읽고 맞다고 한 것. 그 부서의 관리자 또는 시스템
    관리자만, 그리고 **사람 세션만**(기계 자격은 403). AI 가 스스로 확인할 수 있으면 후보라는
    상태에 아무 뜻이 없다.

    누가 언제 확인했는지가 줄과 감사에 남는다.
    """
    return services.test_out(db, user, services.confirm(db, user, test_id))


@router.post("/{test_id}/reject", status_code=204)
def reject_reliability_test(
    test_id: uuid.UUID,
    payload: ReliabilityRejectRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    """AI 가 올린 후보를 **아니라고 한다.** 사람만, 후보만, 사유와 함께.

    줄은 지우기와 같은 자리로 가지만 감사에 **다른 action 과 사유**가 남는다 — 지우기는
    「이제 안 하는 시험」 이고 반려는 「애초에 틀린 줄」 이다.
    """
    services.reject(db, user, test_id, payload.reason)


@router.post("/batch", response_model=ReliabilityBatchOut, status_code=207)
def create_reliability_tests(
    payload: ReliabilityBatchRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ReliabilityBatchOut:
    """문서 하나에서 뽑은 시험들을 **한 번에** 올린다 — 줄마다 결과가 온다.

    **207 로 답한다.** 201 은 「만들었다」, 400 은 「못 만들었다」 인데 이 답은 둘 다다 —
    스무 줄 중 열여덟이 들어가고 둘이 막힐 수 있고, 그 둘을 201 뒤에 숨기면 부른 쪽이
    안 본다.

    **`/{test_id}` 보다 먼저 선언한다** — 뒤에 두면 `batch` 가 id 로 읽혀 404 가 온다.
    """
    return ReliabilityBatchOut(**services.create_many(db, user, payload.model_dump()))


@router.post("/bulk", response_model=ReliabilityBulkOut)
def bulk_reliability_tests(
    payload: ReliabilityBulkRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ReliabilityBulkOut:
    """여러 줄을 한 번에 — 확인 · 반려 · 지우기.

    **`/{test_id}` 보다 먼저 선언한다** — 뒤에 두면 `bulk` 가 id 로 읽혀 404 가 온다.
    """
    return ReliabilityBulkOut(
        **services.bulk(
            db, user, ids=payload.ids, action=payload.action, reason=payload.reason
        )
    )


@router.post("/{test_id}/reopen", response_model=ReliabilityTestOut)
def reopen_reliability_test(
    test_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ReliabilityTestOut:
    """확정을 풀어 **다시 후보로.** 그 순간부터 AI 가 다시 채울 수 있으므로, 누가 그 문을
    열었는지가 감사에 남는다. 확인한 사람·시각은 안 지운다."""
    return services.test_out(db, user, services.reopen(db, user, test_id))


@router.delete("/{test_id}", status_code=204)
def delete_reliability_test(
    test_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    """지우지 않고 `deleted_at` 만 채운다. 감사 기록에 남는다."""
    services.delete(db, user, test_id)


@router.get("/{test_id}/item-proposals", response_model=list[TestItemProposalOut])
def test_item_proposals(
    test_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[TestItemProposalOut]:
    """이 시험이 낸 제안 — **왜 시험 항목이 비었는지가 여기 있다.**"""
    services.get(db, test_id)
    return proposal_service.of_test(db, test_id)


@router.post("/{test_id}/reviewed-revision", status_code=204)
def mark_reviewed(
    test_id: uuid.UUID,
    revision_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> None:
    """이 시험을 **어느 개정까지 봤다**고 적는다. 비우면 표를 도로 붙인다.

    규격서가 개정되어도 확정은 그대로 두므로(수십 건이 한꺼번에 내려가면 그날 일이 멈춘다),
    「아직 안 봤다」 는 표를 떼는 것이 사람이 하는 일이다. **기계는 못 한다** — 기계가
    「봤다」 고 적으면 사람의 확인이 이름만 남는다.
    """
    from app.modules.documents import services as documents

    documents.mark_reviewed(db, user, test_id, revision_id)


@router.get("/{test_id}/value-history", response_model=list[AttributeValueOut])
def value_history(
    test_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[AttributeValueOut]:
    """이 시험의 **판별 값 전부** — 지금 값과 과거 판이 함께.

    시험은 한 줄이고 판은 값에 붙는다(0046). 목록·카드는 지금 값만 보여 주므로, 「개정
    14에서는 얼마였나」 를 보려면 이 자리가 필요하다. 줄마다 `document_revision_label` 과
    `is_current` 가 온다 — 같은 자리의 값들이 판 순서로 늘어선다.
    """
    services.get(db, test_id)
    rows = attributes.values_of(
        db, target="reliability_test", object_ids=[test_id], include_past=True
    )
    return rows.get(test_id, [])

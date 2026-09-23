"""기준정보 라우터.

**읽기는 누구나 한다.** 이 값을 매일 드롭다운에서 고르는 것은 멤버다 — 못 보면
찾는 값이 없을 때 "아직 없다" 인지 "이름이 다르다" 인지 구별할 수 없다. 고치는
것은 관리자다.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.accounts.models import User
from app.modules.vocabulary import services
from app.modules.vocabulary.schemas import (
    AliasCreateRequest,
    ConditionKeyCreateRequest,
    ConditionKeyOut,
    ConditionKeyUpdateRequest,
    ReferenceGroupOut,
    ReferenceReassignRequest,
    SpecDefinitionCreateRequest,
    SpecDefinitionOut,
    SpecDefinitionUpdateRequest,
    SpecGroupCreateRequest,
    SpecGroupOut,
    SpecGroupUpdateRequest,
    TermCreateRequest,
    TermMergeRequest,
    TermOut,
    TermUpdateRequest,
    VocabularyCreateRequest,
    VocabularyOut,
    VocabularyUpdateRequest,
)
from app.shared.auth import current_user, require_system_admin

router = APIRouter(prefix="/vocabularies", tags=["vocabulary"])


@router.get("", response_model=list[VocabularyOut])
def list_vocabularies(
    _: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[VocabularyOut]:
    return services.list_vocabularies(db)


@router.post("", response_model=VocabularyOut, status_code=201)
def create_vocabulary(
    payload: VocabularyCreateRequest,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> VocabularyOut:
    """축 하나를 새로 세운다. **만들기 전에 목록을 본다** — 비슷한 축이 둘로 갈리면
    값도 둘로 갈리고, 합치는 길이 없다(값 병합은 축을 가로질러 못 한다)."""
    body = payload.model_dump()
    body["attribute_schema"] = [one.model_dump() for one in payload.attribute_schema]
    row = services.create_vocabulary(db, payload=body)
    return services.vocabulary_out(db, row)


@router.patch("/{slug}", response_model=VocabularyOut)
def update_vocabulary(
    slug: str,
    payload: VocabularyUpdateRequest,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> VocabularyOut:
    """축의 이름·설명·정책·속성 칸. **축을 만들거나 slug 를 바꾸는 것은 여기 없다** —
    축은 코드가 걸어야 뜻이 있어서, 화면에서 만든 축은 아무 화면도 안 쓴다."""
    changes = payload.model_dump(exclude_unset=True)
    if "attribute_schema" in changes and changes["attribute_schema"] is not None:
        changes["attribute_schema"] = [
            one.model_dump(exclude_none=True) for one in payload.attribute_schema or []
        ]
    return services.vocabulary_out(
        db, services.update_vocabulary(db, slug=slug, changes=changes)
    )


@router.get("/{slug}/terms", response_model=list[TermOut])
def list_terms(
    slug: str,
    q: str | None = Query(default=None, max_length=200),
    include_deprecated: bool = Query(default=False),
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[TermOut]:
    return services.list_terms(db, slug=slug, query=q, include_deprecated=include_deprecated)


@router.post("/{slug}/terms", response_model=TermOut, status_code=201)
def create_term(
    slug: str,
    payload: TermCreateRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> TermOut:
    """값 하나를 더한다.

    **open 축은 누구나 더한다.** 승인 대기를 두면 피커가 멈추고, 그러면 사람은
    시스템 밖에서 일한다. 드리프트는 사후 병합으로 푼다.
    """
    term = services.create_term(
        db,
        slug=slug,
        value=payload.value,
        code=payload.code,
        parent_term_id=payload.parent_term_id,
        attributes=payload.attributes,
        actor=user,
        is_admin=user.is_system_admin,
    )
    return services.term_out(db, term)


@router.patch("/terms/{term_id}", response_model=TermOut)
def update_term(
    term_id: uuid.UUID,
    payload: TermUpdateRequest,
    admin: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> TermOut:
    term = services.update_term(
        db,
        term_id=term_id,
        value=payload.value,
        code=payload.code,
        parent_term_id=payload.parent_term_id,
        status=payload.status,
        attributes=payload.attributes,
        actor=admin,
    )
    return services.term_out(db, term)


@router.post("/terms/{term_id}/aliases", response_model=TermOut, status_code=201)
def add_alias(
    term_id: uuid.UUID,
    payload: AliasCreateRequest,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> TermOut:
    term = services.add_alias(db, term_id=term_id, value=payload.value)
    return services.term_out(db, term)


@router.delete("/terms/{term_id}/aliases", response_model=TermOut)
def remove_alias(
    term_id: uuid.UUID,
    value: str = Query(min_length=1, max_length=200),
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> TermOut:
    """표기 하나를 뗀다. 값으로 고른다 — 표기에는 id 를 안 내보낸다."""
    term = services.remove_alias(db, term_id=term_id, value=value)
    return services.term_out(db, term)


@router.get("/terms/{term_id}/references", response_model=list[ReferenceGroupOut])
def term_references(
    term_id: uuid.UUID,
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[ReferenceGroupOut]:
    """이 값을 가리키는 것 전부 — 쓰임 수의 **내역**이다. 합치거나 폐기하기 전에 본다."""
    return services.term_references(db, term_id)


@router.delete("/terms/{term_id}/references/{kind}/{row_id}", status_code=204)
def detach_reference(
    term_id: uuid.UUID,
    kind: str,
    row_id: uuid.UUID,
    admin: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> None:
    """줄 하나를 뗀다 — 연결 줄이면 지우고, 비워도 되는 칸이면 비운다."""
    services.detach_reference(db, term_id=term_id, kind_key=kind, row_id=row_id, actor=admin)


@router.post("/terms/{term_id}/references/{kind}/{row_id}/reassign", status_code=204)
def reassign_reference(
    term_id: uuid.UUID,
    kind: str,
    row_id: uuid.UUID,
    payload: ReferenceReassignRequest,
    admin: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> None:
    """줄 하나를 같은 축의 다른 값으로 옮긴다."""
    services.reassign_reference(
        db,
        term_id=term_id,
        kind_key=kind,
        row_id=row_id,
        target_term_id=payload.target_term_id,
        actor=admin,
    )


@router.post("/terms/{term_id}/merge", response_model=TermOut)
def merge_term(
    term_id: uuid.UUID,
    payload: TermMergeRequest,
    admin: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> TermOut:
    """이 값을 다른 값으로 합친다. 원본 이름은 별칭으로 남는다."""
    target = services.merge_terms(
        db, source_id=term_id, target_id=payload.target_term_id, actor=admin
    )
    return services.term_out(db, target)


# --- 조건 정의 ---------------------------------------------------------------
#
# 기준정보 축과 **같은 화면에 산다.** 둘 다 "고르는 값의 뜻을 정하는 자리" 이고,
# 메뉴에 따로 세우면 사람이 어느 쪽에 무엇이 있는지 매번 헷갈린다.

conditions_router = APIRouter(prefix="/condition-keys", tags=["vocabulary"])


@conditions_router.get("", response_model=list[ConditionKeyOut])
def list_conditions(
    include_inactive: bool = Query(default=False),
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[ConditionKeyOut]:
    return services.list_conditions(db, include_inactive=include_inactive)


@conditions_router.post("", response_model=ConditionKeyOut, status_code=201)
def create_condition(
    payload: ConditionKeyCreateRequest,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> ConditionKeyOut:
    row = services.create_condition(db, payload=payload.model_dump())
    return services.condition_out(db, row)


@conditions_router.patch("/{condition_id}", response_model=ConditionKeyOut)
def update_condition(
    condition_id: uuid.UUID,
    payload: ConditionKeyUpdateRequest,
    admin: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> ConditionKeyOut:
    row = services.update_condition(
        db,
        condition_id=condition_id,
        changes=payload.model_dump(exclude_unset=True),
        actor=admin,
    )
    return services.condition_out(db, row)


# --- 사양 정의 ---------------------------------------------------------------
#
# 조건 정의와 같은 화면에 산다. **읽기는 누구나 한다** — 모델에 사양을 채우는
# 사람이 어떤 칸이 있는지 봐야 하고, 없는 칸을 만들어 달라고 말할 수 있어야 한다.

spec_groups_router = APIRouter(prefix="/spec-groups", tags=["specs"])


@spec_groups_router.get("", response_model=list[SpecGroupOut])
def list_spec_groups(
    _: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[SpecGroupOut]:
    return services.list_spec_groups(db)


@spec_groups_router.post("", response_model=SpecGroupOut, status_code=201)
def create_spec_group(
    payload: SpecGroupCreateRequest,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> SpecGroupOut:
    row = services.create_spec_group(db, payload=payload.model_dump())
    return services.group_out(db, row)


@spec_groups_router.patch("/{group_id}", response_model=SpecGroupOut)
def update_spec_group(
    group_id: uuid.UUID,
    payload: SpecGroupUpdateRequest,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> SpecGroupOut:
    row = services.update_spec_group(
        db, group_id=group_id, changes=payload.model_dump(exclude_unset=True)
    )
    return services.group_out(db, row)


@spec_groups_router.delete("/{group_id}", status_code=204)
def delete_spec_group(
    group_id: uuid.UUID,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> None:
    services.delete_spec_group(db, group_id)


spec_definitions_router = APIRouter(prefix="/spec-definitions", tags=["specs"])


@spec_definitions_router.get("", response_model=list[SpecDefinitionOut])
def list_spec_definitions(
    include_inactive: bool = Query(default=False),
    group_id: uuid.UUID | None = Query(default=None),
    category_term_id: uuid.UUID | None = Query(default=None),
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[SpecDefinitionOut]:
    # 분류로 거르면 **공통도 함께 온다.** 안 그러면 전원·무게가 어느 장비
    # 화면에도 안 뜬다.
    return services.list_spec_definitions(
        db,
        include_inactive=include_inactive,
        group_id=group_id,
        category_term_id=category_term_id,
    )


@spec_definitions_router.post("", response_model=SpecDefinitionOut, status_code=201)
def create_spec_definition(
    payload: SpecDefinitionCreateRequest,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> SpecDefinitionOut:
    row = services.create_spec_definition(db, payload=payload.model_dump())
    return services.definition_out(db, row)


@spec_definitions_router.patch("/{definition_id}", response_model=SpecDefinitionOut)
def update_spec_definition(
    definition_id: uuid.UUID,
    payload: SpecDefinitionUpdateRequest,
    admin: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> SpecDefinitionOut:
    row = services.update_spec_definition(
        db,
        definition_id=definition_id,
        changes=payload.model_dump(exclude_unset=True),
        actor=admin,
    )
    return services.definition_out(db, row)


@spec_definitions_router.delete("/{definition_id}", status_code=204)
def delete_spec_definition(
    definition_id: uuid.UUID,
    _: User = Depends(require_system_admin),
    db: Session = Depends(get_db),
) -> None:
    services.delete_spec_definition(db, definition_id)

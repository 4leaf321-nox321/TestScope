"""기준정보 로직 — 값을 만들고, 고치고, 합친다.

## 만들 때 별칭까지 뒤진다

중복은 사후에 합치는 것보다 **애초에 안 생기게 하는 것**이 싸다. UTM 을 등록하려는
사람에게 "만능재료시험기가 이미 있습니다" 라고 말해 주는 자리가 여기다.

## 문은 하나다

2026-09-13 에 1,010줄을 넷으로 갈랐다 — `terms`(축·값·별칭·합치기) · `conditions`(조건
정의) · `spec_definitions`(사양 그룹·정의) · `usage`(쓰임·떼기·옮기기). 라우터는 전부
`services.<이름>` 으로 쓰므로 여기서 그 이름들을 그대로 다시 내보낸다. 새 함수는 네 모듈
중 하나에 적고 여기 `__all__` 에 한 줄 더한다.
"""

from __future__ import annotations

from app.modules.vocabulary.conditions import (
    _condition_usage,
    condition_out,
    create_condition,
    get_condition,
    list_conditions,
    update_condition,
)
from app.modules.vocabulary.spec_definitions import (
    _definition_categories,
    _definition_count,
    _definition_usage,
    _set_definition_categories,
    create_spec_definition,
    create_spec_group,
    definition_out,
    delete_spec_definition,
    delete_spec_group,
    get_spec_definition,
    get_spec_group,
    group_out,
    list_spec_definitions,
    list_spec_groups,
    update_spec_definition,
    update_spec_group,
)
from app.modules.vocabulary.terms import (
    _aliases_of,
    _find_by_key,
    _repoint_references,
    _require_free_code,
    _term_count,
    _twin_exists,
    _usage_of,
    add_alias,
    create_term,
    get_term,
    get_vocabulary,
    list_terms,
    list_vocabularies,
    merge_terms,
    remove_alias,
    term_out,
    update_term,
    update_vocabulary,
    vocabulary_out,
)
from app.modules.vocabulary.usage import (
    _reference_row,
    detach_reference,
    reassign_reference,
    term_references,
)

__all__ = [
    "_aliases_of",
    "_condition_usage",
    "_definition_categories",
    "_definition_count",
    "_definition_usage",
    "_find_by_key",
    "_reference_row",
    "_repoint_references",
    "_require_free_code",
    "_set_definition_categories",
    "_term_count",
    "_twin_exists",
    "_usage_of",
    "add_alias",
    "condition_out",
    "create_condition",
    "create_spec_definition",
    "create_spec_group",
    "create_term",
    "definition_out",
    "delete_spec_definition",
    "delete_spec_group",
    "detach_reference",
    "get_condition",
    "get_spec_definition",
    "get_spec_group",
    "get_term",
    "get_vocabulary",
    "group_out",
    "list_conditions",
    "list_spec_definitions",
    "list_spec_groups",
    "list_terms",
    "list_vocabularies",
    "merge_terms",
    "reassign_reference",
    "remove_alias",
    "term_out",
    "term_references",
    "update_condition",
    "update_spec_definition",
    "update_spec_group",
    "update_term",
    "update_vocabulary",
    "vocabulary_out",
]

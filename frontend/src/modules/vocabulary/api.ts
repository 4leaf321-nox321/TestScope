/** 기준정보·조건 정의 API. 여러 화면이 피커로 쓴다. */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type Vocabulary = components['schemas']['VocabularyOut']
export type Term = components['schemas']['TermOut']
export type ConditionKey = components['schemas']['ConditionKeyOut']
export type SpecGroup = components['schemas']['SpecGroupOut']
export type SpecDefinition = components['schemas']['SpecDefinitionOut']

export const vocabularyApi = {
  list: () => api.get<Vocabulary[]>('/vocabularies'),
  terms: (slug: string, query?: string) =>
    api.get<Term[]>(
      `/vocabularies/${slug}/terms${query ? `?q=${encodeURIComponent(query)}` : ''}`,
    ),
  createTerm: (slug: string, body: { value: string; code?: string | null }) =>
    api.post<Term>(`/vocabularies/${slug}/terms`, body),
  updateTerm: (termId: string, body: Record<string, unknown>) =>
    api.patch<Term>(`/vocabularies/terms/${termId}`, body),
  addAlias: (termId: string, value: string) =>
    api.post<Term>(`/vocabularies/terms/${termId}/aliases`, { value }),
  mergeTerm: (termId: string, targetTermId: string) =>
    api.post<Term>(`/vocabularies/terms/${termId}/merge`, { target_term_id: targetTermId }),

  conditions: (includeInactive = false) =>
    api.get<ConditionKey[]>(`/condition-keys${includeInactive ? '?include_inactive=true' : ''}`),
  createCondition: (body: Record<string, unknown>) =>
    api.post<ConditionKey>('/condition-keys', body),
  updateCondition: (id: string, body: Record<string, unknown>) =>
    api.patch<ConditionKey>(`/condition-keys/${id}`, body),

  // 사양 정의는 조건 정의와 **같은 성격**이다 — 둘 다 값이 아니라 칸의 계약이다.
  // 다른 것은 쓰임뿐이다: 조건은 검색이 묻는 일곱 축, 사양은 사양서의 수백 칸.
  specGroups: () => api.get<SpecGroup[]>('/spec-groups'),
  /** 분류를 주면 그 분류의 사양과 **공통 사양이 함께** 온다. */
  specDefinitions: (
    options: { includeInactive?: boolean; categoryTermId?: string | null } = {},
  ) => {
    const search = new URLSearchParams()
    if (options.includeInactive) search.set('include_inactive', 'true')
    if (options.categoryTermId) search.set('category_term_id', options.categoryTermId)
    const query = search.toString()
    return api.get<SpecDefinition[]>(`/spec-definitions${query ? `?${query}` : ''}`)
  },
  createSpecDefinition: (body: Record<string, unknown>) =>
    api.post<SpecDefinition>('/spec-definitions', body),
  updateSpecDefinition: (id: string, body: Record<string, unknown>) =>
    api.patch<SpecDefinition>(`/spec-definitions/${id}`, body),
}

/**
 * 코드가 거는 축 이름.
 *
 * 문자열을 화면마다 적으면 오타 하나가 **조용히 빈 목록**이 된다 — 서버는 404 를
 * 내지만 피커는 그것을 "값이 없다" 로 그린다.
 */
export const AXIS = {
  testItem: 'test_item',
  equipmentCategory: 'equipment_category',
  manufacturer: 'manufacturer',
  site: 'site',
  standardBody: 'standard_body',
} as const

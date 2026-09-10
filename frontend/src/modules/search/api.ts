/**
 * 장비 찾기 API.
 *
 * 값은 **조건 정의의 저장 단위로 보낸다**(ConditionKey.si_unit). 화면이 다른
 * 단위로 받으면 여기 오기 전에 바꾼다 — 환산을 두 곳에서 하면 언젠가 한쪽만
 * 고쳐지고, 그때 검색이 조용히 세 자릿수 틀린다.
 */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type ConditionQuery = components['schemas']['ConditionQuery']
export type SearchRequest = components['schemas']['SearchRequest']
export type ConditionMatch = components['schemas']['ConditionMatch']
export type SearchHit = components['schemas']['SearchHit']
export type SearchResponse = components['schemas']['SearchResponse']

export const searchApi = {
  test_items: (body: SearchRequest) => api.post<SearchResponse>('/search/test_items', body),
  /** 규격 하나가 요구하는 조건을 검색 물음으로 바꿔 받는다. */
  methodConditions: (methodId: string) =>
    api.get<ConditionQuery[]>(`/search/method-conditions/${methodId}`),
}

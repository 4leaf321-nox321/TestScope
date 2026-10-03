/**
 * 장비 찾기 API.
 *
 * 값은 **그 축의 단위로 보낸다**(ConditionKey.unit — display_unit, 없으면 si_unit).
 * 화면은 그 단위의 숫자를 그대로 보내고 환산하지 않는다 — 장비 조건도 같은 단위로
 * 담겨 있어서, 여기서 si_unit 으로 바꾸면 낙하 높이 152 cm 가 1.52 cm 가 된다.
 */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type ConditionQuery = components['schemas']['ConditionQuery']
export type SearchRequest = components['schemas']['SearchRequest']
export type ConditionMatch = components['schemas']['ConditionMatch']
export type SearchHit = components['schemas']['SearchHit']
export type SearchResponse = components['schemas']['SearchResponse']
export type CatalogSearchResponse = components['schemas']['CatalogSearchResponse']
export type CatalogHit = components['schemas']['CatalogHit']

export const searchApi = {
  test_items: (body: SearchRequest) => api.post<SearchResponse>('/search/test-items', body),
  /** 같은 물음을 카탈로그에 — 「이 시험을 하려면 어떤 기종이 되나 / 사야 하나」. */
  catalog: (body: SearchRequest) => api.post<CatalogSearchResponse>('/search/catalog', body),
  /** 규격 하나가 요구하는 조건을 검색 물음으로 바꿔 받는다. */
  methodConditions: (methodId: string) =>
    api.get<ConditionQuery[]>(`/search/method-conditions/${methodId}`),
}

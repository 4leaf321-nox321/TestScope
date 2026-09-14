/** 시험 항목 카탈로그 API — 사슬의 가운데(물성 ⇄ 시험 항목 → 규격 → 계열/기종 → 보유). */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type TestItemCatalogRow = components['schemas']['TestItemCatalogRow']
export type TestItemCatalog = components['schemas']['TestItemCatalogOut']

export const testItemCatalogApi = {
  /** 96 줄 전부 — 줄마다 사슬 전체의 수. 서버가 한 번에 센다.
   *  `workspace` 를 주면 보유 장비를 그 부서 것만 센다 — 부서 하나의 신뢰성 시험 현황. */
  list: (workspace?: string) =>
    api.get<TestItemCatalogRow[]>(
      workspace ? `/test-items?workspace=${encodeURIComponent(workspace)}` : '/test-items',
    ),
  read: (id: string) => api.get<TestItemCatalog>(`/test-items/${id}`),
  /** 검색축을 통째로 바꾼다. */
  setConditionKeys: (id: string, conditionKeyIds: string[]) =>
    api.put<void>(`/test-items/${id}/condition-keys`, { condition_key_ids: conditionKeyIds }),
}

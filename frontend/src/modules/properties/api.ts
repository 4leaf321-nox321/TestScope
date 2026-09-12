/** 물성 ↔ 시험 항목 API. */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type Property = components['schemas']['PropertyOut']
export type TestItemProperty = components['schemas']['TestItemPropertyOut']
export type LinkBulkResult = components['schemas']['LinkBulkResult']

export const propertyApi = {
  list: (params: { q?: string; domain?: string; linkedOnly?: boolean } = {}) => {
    const search = new URLSearchParams()
    if (params.q) search.set('q', params.q)
    if (params.domain) search.set('domain', params.domain)
    if (params.linkedOnly) search.set('include_unlinked', 'false')
    const query = search.toString()
    return api.get<Property[]>(`/properties${query ? `?${query}` : ''}`)
  },
  links: (params: { testItem?: string; property?: string } = {}) => {
    const search = new URLSearchParams()
    if (params.testItem) search.set('test_item', params.testItem)
    if (params.property) search.set('property', params.property)
    const query = search.toString()
    return api.get<TestItemProperty[]>(`/test-item-properties${query ? `?${query}` : ''}`)
  },
  link: (body: {
    test_item_term_id: string
    property_term_id: string
    note?: string | null
  }) => api.post<TestItemProperty>('/test-item-properties', body),
  update: (id: string, body: { status?: string; note?: string | null }) =>
    api.patch<TestItemProperty>(`/test-item-properties/${id}`, body),
  /** 제안 여럿을 한 번에 확인하거나 되돌린다. 한 줄씩 누르게 두면 아무도 끝내지 못한다. */
  bulk: (linkIds: string[], status: 'confirmed' | 'suggested') =>
    api.patch<LinkBulkResult>('/test-item-properties/bulk', {
      link_ids: linkIds,
      status,
    }),
  unlink: (id: string) => api.delete<void>(`/test-item-properties/${id}`),
}

/** MaterialTwin 키의 앞 토막 → 사람이 읽는 말. 화면이 이것으로 묶는다. */
export const DOMAIN_LABEL: Record<string, string> = {
  mechanical: '기계',
  thermal: '열',
  electrical: '전기',
  optical: '광학',
  chemical: '화학',
  physical: '물리',
  rheological: '유변',
  structure: '구조',
  interface: '계면·접착',
  surface: '표면',
  magnetic: '자기',
  acoustic: '음향',
}

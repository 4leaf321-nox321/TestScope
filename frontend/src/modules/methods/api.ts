/** 시험법 API. */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type TestMethod = components['schemas']['MethodOut']
export type Requirement = components['schemas']['RequirementOut']
type MethodPage = components['schemas']['Page_MethodOut_']

export const methodApi = {
  list: (params: {
    q?: string
    testItem?: string
    /** `none` 이면 요구 조건이 안 적힌 규격만. 홈의 「남은 일」 이 이걸로 온다. */
    requirement?: string
    includeSuperseded?: boolean
  }) => {
    const search = new URLSearchParams()
    if (params.q) search.set('q', params.q)
    if (params.testItem) search.set('test_item', params.testItem)
    if (params.requirement) search.set('requirement', params.requirement)
    if (params.includeSuperseded) search.set('include_superseded', 'true')
    const query = search.toString()
    return api.get<MethodPage>(`/methods${query ? `?${query}` : ''}`)
  },
  read: (id: string) => api.get<TestMethod>(`/methods/${id}`),
  create: (body: Record<string, unknown>) => api.post<TestMethod>('/methods', body),
  update: (id: string, body: Record<string, unknown>) =>
    api.patch<TestMethod>(`/methods/${id}`, body),
  remove: (id: string) => api.delete<void>(`/methods/${id}`),
  putRequirement: (methodId: string, body: Record<string, unknown>) =>
    api.put<Requirement>(`/methods/${methodId}/requirements`, body),
  removeRequirement: (methodId: string, requirementId: string) =>
    api.delete<void>(`/methods/${methodId}/requirements/${requirementId}`),
}

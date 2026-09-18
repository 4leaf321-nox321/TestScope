/** 시험법 API. */

import { api, downloadFile } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type TestMethod = components['schemas']['MethodOut']
export type Requirement = components['schemas']['RequirementOut']
export type RequirementImportResult = components['schemas']['RequirementImportResult']
export type RequirementImportRow = components['schemas']['RequirementImportRow']
type MethodPage = components['schemas']['Page_MethodOut_']

export const methodApi = {
  list: (params: {
    q?: string
    /** 시험 항목 값 id, 또는 `none` — 어느 시험의 규격인지 안 정해진 것만. */
    testItem?: string
    /** `none` 이면 요구 조건이 안 적힌 규격만. 홈의 「남은 일」 이 이걸로 온다. */
    requirement?: string
    /** `none` 이면 어느 계열의 시험 항목에도 안 이어진 규격만. */
    cited?: string
    /** `owned` 면 보유 장비의 시험 항목이 실제로 가리키는 규격만 — 요구 조건은 여기부터. */
    used?: string
    includeSuperseded?: boolean
    /** 속성 값으로 거른다 — `키>=값` 꼴, 여러 개면 **모두** 만족해야 한다. */
    attrs?: string[]
  }) => {
    const search = new URLSearchParams()
    if (params.q) search.set('q', params.q)
    if (params.testItem) search.set('test_item', params.testItem)
    if (params.requirement) search.set('requirement', params.requirement)
    if (params.cited) search.set('cited', params.cited)
    if (params.used) search.set('used', params.used)
    if (params.includeSuperseded) search.set('include_superseded', 'true')
    for (const one of params.attrs ?? []) search.append('attr', one)
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
  /** 규격서를 보고 적은 요구 조건 표를 통째로. 장비 대장 반입과 같은 두 걸음이다. */
  importRequirements: (text: string, dryRun: boolean) =>
    api.post<RequirementImportResult>(
      `/methods/requirements/import?dry_run=${dryRun ? 'true' : 'false'}`,
      { text },
    ),
  requirementTemplate: () =>
    downloadFile('/methods/requirements/import/template', 'testscope-요구조건.csv'),
}

/** 신뢰성 시험 API — 부서가 제품 개발·검증을 위해 수행하는 시험. 「시험 항목」 과 다른 층이다. */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'
import type { AttributeValueIn } from '@/modules/attributes/api'

export type ReliabilityTest = components['schemas']['ReliabilityTestOut']
export type ReliabilityTestItem = components['schemas']['ReliabilityTestItemOut']
export type ReliabilityTestWrite = {
  name: string
  purpose: string
  test_item_term_ids: string[]
  /** 항목 값. 보내면 통째로 바뀐다. `definition_id` 없이 `new_label` 이면 초안이 생긴다. */
  attributes: AttributeValueIn[]
}

export const reliabilityApi = {
  /** 한 부서의 신뢰성 시험 전부. 시험마다 쓰는 시험 항목과 그 항목이 되는 이 부서 장비 수. */
  list: (workspace: string) =>
    api.get<ReliabilityTest[]>(
      `/reliability-tests?workspace=${encodeURIComponent(workspace)}`,
    ),
  /** 전사 전부 — 부서 순. 「누가 무슨 시험을 하나」 를 가로질러 본다. */
  listAll: () => api.get<ReliabilityTest[]>('/reliability-tests'),
  read: (id: string) => api.get<ReliabilityTest>(`/reliability-tests/${id}`),
  create: (workspace: string, body: ReliabilityTestWrite) =>
    api.post<ReliabilityTest>('/reliability-tests', { workspace_slug: workspace, ...body }),
  /** 부분 수정. `test_item_term_ids` 는 보내면 통째로 바뀐다. */
  update: (id: string, body: Partial<ReliabilityTestWrite>) =>
    api.patch<ReliabilityTest>(`/reliability-tests/${id}`, body),
  remove: (id: string) => api.delete<void>(`/reliability-tests/${id}`),
}

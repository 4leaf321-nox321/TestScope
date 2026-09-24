/** 신뢰성 시험 API — 부서가 제품 개발·검증을 위해 수행하는 시험. 「시험 항목」 과 다른 층이다. */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'
import type { AttributeValueIn } from '@/modules/attributes/api'

export type ReliabilityTest = components['schemas']['ReliabilityTestOut']
export type Capability = components['schemas']['CapabilityOut']
export type ReliabilityTestItem = components['schemas']['ReliabilityTestItemOut']
export type ReliabilityTestWrite = {
  name: string
  purpose: string
  test_item_term_ids: string[]
  /** 항목 값. 보내면 통째로 바뀐다. `definition_id` 없이 `new_label` 이면 초안이 생긴다. */
  attributes: AttributeValueIn[]
}

/** `candidate` = AI 가 올리고 아직 사람이 확인 안 한 것. `confirmed` = 사람이 보증한 것. */
export type ReliabilityStatus = 'candidate' | 'confirmed'

export const reliabilityApi = {
  /** 한 부서의 신뢰성 시험 전부 — **후보까지.** 검토하는 자리가 부서 화면이라 후보가 먼저
   *  온다. 시험마다 쓰는 시험 항목과 그 항목이 되는 이 부서 장비 수. */
  list: (workspace: string) =>
    api.get<ReliabilityTest[]>(
      `/reliability-tests?workspace=${encodeURIComponent(workspace)}`,
    ),
  /** 전사 전부 — 부서 순. 「누가 무슨 시험을 하나」 를 가로질러 본다.
   *  `attrs` 는 속성 값 조건(`키>=값`) — 여러 개면 **모두** 만족해야 한다. */
  listAll: (attrs: string[] = [], withCandidates = false) => {
    const search = new URLSearchParams()
    for (const one of attrs) search.append('attr', one)
    // **기본은 확정된 것만.** 이 표는 「저 부서가 무슨 시험을 하나」 에 답하는데, 확인 안
    // 된 후보는 아직 그 답이 아니다 — 옆 부서 사람은 배지를 안 보고 읽는다.
    if (withCandidates) search.append('status', 'all')
    const query = search.toString()
    return api.get<ReliabilityTest[]>(`/reliability-tests${query ? `?${query}` : ''}`)
  },
  /** **이 시험을 돌릴 수 있는 장비.** 조건 속성이 그대로 검색 조건이 된다 — 판정 규칙은
   *  장비 찾기와 같은 것 하나다. 범위 하나는 물음 둘(위로·아래로). */
  capability: (id: string) => api.get<Capability>(`/reliability-tests/${id}/equipment`),
  read: (id: string) => api.get<ReliabilityTest>(`/reliability-tests/${id}`),
  create: (workspace: string, body: ReliabilityTestWrite) =>
    api.post<ReliabilityTest>('/reliability-tests', { workspace_slug: workspace, ...body }),
  /** 부분 수정. `test_item_term_ids` 는 보내면 통째로 바뀐다. */
  update: (id: string, body: Partial<ReliabilityTestWrite>) =>
    api.patch<ReliabilityTest>(`/reliability-tests/${id}`, body),
  /** **후보를 확인했다** — 사람이 내용을 읽고 맞다고 한 것. 기계 자격으로는 못 한다. */
  confirm: (id: string) => api.post<ReliabilityTest>(`/reliability-tests/${id}/confirm`, {}),
  /** 확정을 풀어 다시 후보로. 그 순간부터 AI 가 다시 채울 수 있다 — 감사에 남는다. */
  reopen: (id: string) => api.post<ReliabilityTest>(`/reliability-tests/${id}/reopen`, {}),
  remove: (id: string) => api.delete<void>(`/reliability-tests/${id}`),
}

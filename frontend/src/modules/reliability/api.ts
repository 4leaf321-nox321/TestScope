/** 신뢰성 시험 API — **사업부**가 제품 개발·검증을 위해 수행하는 시험. 「시험 항목」 과 다른 층이다. */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'
import type { AttributeValueIn } from '@/modules/attributes/api'

export type ReliabilityTest = components['schemas']['ReliabilityTestOut']
export type Capability = components['schemas']['CapabilityOut']
export type ReliabilityTestItem = components['schemas']['ReliabilityTestItemOut']
export type Division = components['schemas']['DivisionOut']
export type BulkResult = components['schemas']['ReliabilityBulkOut']
/** 여럿에게 한 번에 할 수 있는 일. */
export type BulkAction = 'confirm' | 'reject' | 'delete'
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
  /** 사업부 목록 — 줄마다 **내가 올릴 수 있는지**(`can_register`)가 온다. 사이드바가
   *  이것으로 서고, 등록 창이 고를 것을 이것으로 좁힌다. */
  divisions: () => api.get<Division[]>('/reliability-tests/divisions'),
  /** 한 사업부의 신뢰성 시험 전부 — **후보까지.** 검토하는 자리가 사업부 화면이라 후보가
   *  먼저 온다. 시험마다 쓰는 시험 항목과 그 항목이 되는 이 사업부 장비 수. */
  list: (division: string) =>
    api.get<ReliabilityTest[]>(`/reliability-tests?division=${encodeURIComponent(division)}`),
  /** 전사 전부 — 사업부 순. 「누가 무슨 시험을 하나」 를 가로질러 본다.
   *  `attrs` 는 속성 값 조건(`키>=값`) — 여러 개면 **모두** 만족해야 한다. */
  listAll: (attrs: string[] = [], withCandidates = false) => {
    const search = new URLSearchParams()
    for (const one of attrs) search.append('attr', one)
    // **기본은 확정된 것만.** 이 표는 「저 사업부가 무슨 시험을 하나」 에 답하는데, 확인 안
    // 된 후보는 아직 그 답이 아니다 — 옆 사업부 사람은 배지를 안 보고 읽는다.
    if (withCandidates) search.append('status', 'all')
    const query = search.toString()
    return api.get<ReliabilityTest[]>(`/reliability-tests${query ? `?${query}` : ''}`)
  },
  /** **한 규격서에서 올라온 시험들** — 후보까지, 확정된 것까지.
   *
   *  AI 가 규격서 한 권에서 스무 건을 뽑아 올린다. 그 스무 줄은 **같은 실수를 함께 한다**
   *  (한 번에 읽은 것이다) — 한 건씩 흩어 놓고 보면 그 결이 안 보이고, 같은 오답을 스무
   *  번 통과시킨다. 그래서 문서 단위로 모아 본다. */
  byDocument: (documentId: string) =>
    api.get<ReliabilityTest[]>(
      `/reliability-tests?status=all&document=${encodeURIComponent(documentId)}`,
    ),
  /** **이 시험을 돌릴 수 있는 장비.** 조건 속성이 그대로 검색 조건이 된다 — 판정 규칙은
   *  장비 찾기와 같은 것 하나다. 범위 하나는 물음 둘(위로·아래로). */
  capability: (id: string) => api.get<Capability>(`/reliability-tests/${id}/equipment`),
  read: (id: string) => api.get<ReliabilityTest>(`/reliability-tests/${id}`),
  create: (division: string, body: ReliabilityTestWrite) =>
    api.post<ReliabilityTest>('/reliability-tests', { division_code: division, ...body }),
  /** 부분 수정. `test_item_term_ids` 는 보내면 통째로 바뀐다. */
  update: (id: string, body: Partial<ReliabilityTestWrite>) =>
    api.patch<ReliabilityTest>(`/reliability-tests/${id}`, body),
  /** **후보를 확인했다** — 사람이 내용을 읽고 맞다고 한 것. 기계 자격으로는 못 한다. */
  confirm: (id: string) => api.post<ReliabilityTest>(`/reliability-tests/${id}/confirm`, {}),
  /** **후보를 아니라고 한다** — 사람만, 후보만. 사유는 필수다: 없으면 AI 가 무엇을
   *  자주 틀리는지 셀 수 없고, 같은 것을 또 올려도 아무도 모른다. */
  reject: (id: string, reason: string) =>
    api.post<void>(`/reliability-tests/${id}/reject`, { reason }),
  /** **여러 줄을 한 번에** — 확인 · 반려 · 지우기. AI 가 몇천 건을 올리므로 줄마다 창을
   *  여는 것은 사람이 할 수 있는 일이 아니다. 줄마다 결과가 온다(안 된 줄은 왜까지). */
  bulk: (ids: string[], action: BulkAction, reason?: string) =>
    api.post<BulkResult>('/reliability-tests/bulk', { ids, action, reason }),
  /** 확정을 풀어 다시 후보로. 그 순간부터 AI 가 다시 채울 수 있다 — 감사에 남는다. */
  reopen: (id: string) => api.post<ReliabilityTest>(`/reliability-tests/${id}/reopen`, {}),
  remove: (id: string) => api.delete<void>(`/reliability-tests/${id}`),
}

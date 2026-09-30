/** 신뢰성 시험 API — **사업부**가 제품 개발·검증을 위해 수행하는 시험. 「시험 항목」 과 다른 층이다. */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'
import type { AttributeValueIn } from '@/modules/attributes/api'

export type ReliabilityTest = components['schemas']['ReliabilityTestOut']
export type Capability = components['schemas']['CapabilityOut']
export type ReliabilityTestItem = components['schemas']['ReliabilityTestItemOut']
export type Division = components['schemas']['DivisionOut']
export type BulkResult = components['schemas']['ReliabilityBulkOut']
export type RevisionCompare = components['schemas']['RevisionCompareOut']
export type AttributeValueRow = components['schemas']['AttributeValueOut']
export type SiblingTest = components['schemas']['SiblingTestOut']
export type TestItemProposal = components['schemas']['TestItemProposalOut']
export type TestItemProposalGroup = components['schemas']['TestItemProposalGroupOut']
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
  /** **아직 저장 안 한 조건**으로 장비를 센다 — 적으면서 보는 자리.
   *
   *  지금은 저장한 뒤 따로 열어야 보여서, 「95 °C 로 올리면 돌릴 장비가 0대」 를 저장하고
   *  나서 안다. 단위 환산은 서버가 한다. */
  capabilityPreview: (termIds: string[], attributes: AttributeValueIn[]) =>
    api.post<Capability>('/reliability-tests/capability-preview', {
      test_item_term_ids: termIds,
      attributes,
    }),
  /** 이름이 같은 다른 시험 — 적용군·규격서·판 중 무엇으로 갈렸는지 함께. */
  siblings: (division: string, name: string, exclude: string | null) => {
    const search = new URLSearchParams({ division, name })
    if (exclude) search.set('exclude', exclude)
    return api.get<SiblingTest[]>(`/reliability-tests/siblings?${search}`)
  },
  /** 이 시험의 **판별 값 전부** — 지금 값과 과거 판이 함께.
   *
   *  시험은 한 줄이고 판은 값에 붙는다. 카드는 지금 값만 보여 주므로, 「개정 14에서는
   *  얼마였나」 를 보려면 이 자리가 필요하다. */
  valueHistory: (id: string) =>
    api.get<AttributeValueRow[]>(`/reliability-tests/${id}/value-history`),
  /** 같은 규격서의 **두 판을 견준다** — 더해진 시험 · 없어진 시험 · 조건이 바뀐 시험.
   *
   *  개정이 오면 딸린 수십 건 중 **무엇을 다시 봐야 하는지**가 문제다. 「전부 다시」 는
   *  그날 일을 멈추고 「아무것도 안 봄」 은 바뀐 조건을 놓친다. */
  compareRevisions: (before: string, after: string) =>
    api.get<RevisionCompare>(
      `/reliability-tests/revision-compare?before=${encodeURIComponent(before)}&after=${encodeURIComponent(after)}`,
    ),
  /** 이 시험이 낸 **시험 항목 제안** — 축에 맞는 값이 없어 남긴 것.
   *
   *  시험 항목 축은 닫혀 있어 AI 가 값을 못 더한다(검색의 첫 축이라 오타 하나가 값이 되면
   *  아무도 못 찾는다). 그래서 지금까지는 그냥 비웠고, **왜 비었는지가 아무 데도 안 남았다.** */
  itemProposals: (id: string) =>
    api.get<TestItemProposal[]>(`/reliability-tests/${id}/item-proposals`),
  /** 같은 말끼리 모은 제안 목록 — 건수가 큰 것이 먼저. 관리자가 한 번 정하면 그 말을
   *  낸 시험 전부에 걸린다. */
  proposalGroups: () => api.get<TestItemProposalGroup[]>('/reliability-tests/item-proposals'),
  /** 제안 한 묶음을 정한다 — **시스템 관리자만.** */
  decideProposal: (body: {
    normalized: string
    term_id?: string | null
    new_value?: string | null
  }) => api.post<Record<string, unknown>>('/reliability-tests/item-proposals/decide', body),
  /** 이 시험을 **어느 개정까지 봤다**고 적는다. 비우면 표를 도로 붙인다. 사람만 한다. */
  markReviewed: (id: string, revisionId: string | null) =>
    api.post<void>(
      `/reliability-tests/${id}/reviewed-revision${
        revisionId ? `?revision_id=${encodeURIComponent(revisionId)}` : ''
      }`,
      {},
    ),
  /** 확정을 풀어 다시 후보로. 그 순간부터 AI 가 다시 채울 수 있다 — 감사에 남는다. */
  reopen: (id: string) => api.post<ReliabilityTest>(`/reliability-tests/${id}/reopen`, {}),
  remove: (id: string) => api.delete<void>(`/reliability-tests/${id}`),
}

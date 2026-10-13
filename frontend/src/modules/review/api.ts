/** 검토함 API — 후보와 근거를 보고, 도메인 전문가가 고른다. 시스템 관리자 전용. */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type ReviewQueue = components['schemas']['QueueOut']
export type ReviewProposal = components['schemas']['ProposalOut']
export type ReviewCandidate = components['schemas']['CandidateOut']
type ProposalPage = components['schemas']['ProposalPage']
export type BulkDecideResult = components['schemas']['BulkDecideResult']
export type ChoicePreview = components['schemas']['ChoicePreviewOut']

/** 보류 사유 — 서버 `SKIP_REASONS` 와 같은 키. */
export const SKIP_REASONS = [
  ['evidence', '근거 부족'],
  ['expert', '도메인 전문가 확인 필요'],
  ['source', '원문(규격서·사양서) 확인 필요'],
  ['no_answer', '후보에 맞는 답 없음'],
  ['other', '기타'],
] as const
export type SkipReason = (typeof SKIP_REASONS)[number][0]

export const reviewApi = {
  queues: () => api.get<ReviewQueue[]>('/review'),
  /** `votes: 'mcp'` 면 MCP 로 낸 의견이 있는 줄만. */
  list: (
    queue: string,
    params: { status?: string; votes?: 'mcp'; limit?: number; offset?: number } = {},
  ) => {
    const search = new URLSearchParams()
    if (params.status) search.set('status', params.status)
    if (params.votes) search.set('votes', params.votes)
    if (params.limit) search.set('limit', String(params.limit))
    if (params.offset) search.set('offset', String(params.offset))
    const query = search.toString()
    return api.get<ProposalPage>(`/review/${queue}${query ? `?${query}` : ''}`)
  },
  /** `addToCiting` 은 규격의 시험 항목 물음 전용 — 고른 시험 항목이 없어 안 이어지는 인용
   *  계열에 그 시험 항목을 더해 잇는다. */
  decide: (queue: string, id: string, choice: string[], note?: string, addToCiting = false) =>
    api.post<ReviewProposal>(`/review/${queue}/${id}/decide`, {
      choice,
      note: note || null,
      add_to_citing: addToCiting,
    }),
  /** 확정 **전에** 이어질 계열 · 안 이어질 계열 · 후보 밖 항목 — 규격의 시험 항목 물음 전용. */
  preview: (queue: string, id: string, choice: string[]) => {
    const search = new URLSearchParams()
    for (const one of choice) search.append('choice', one)
    return api.get<ChoicePreview>(`/review/${queue}/${id}/preview?${search.toString()}`)
  },
  /**
   * 고른 줄들을 **각자의 추천대로** 확정한다 — 줄마다 결과.
   *
   * 추천이 없거나 추천과 다른 의견이 있는 줄은 서버가 **확정하지 않고** 이유와 함께 돌려준다.
   */
  decideRecommended: (queue: string, ids: string[], note?: string) =>
    api.post<BulkDecideResult>(`/review/${queue}/decide-recommended`, {
      ids,
      note: note || null,
    }),
  /**
   * 고른 줄들을 **MCP 로 낸 의견대로** 확정한다 — 줄마다 결과.
   *
   * MCP 의견이 없거나 갈리거나, 사람 의견이 다른 줄은 서버가 확정하지 않고 이유와 함께 돌려준다.
   */
  decideByMcpVotes: (queue: string, ids: string[], note?: string) =>
    api.post<BulkDecideResult>(`/review/${queue}/decide-mcp-votes`, {
      ids,
      note: note || null,
    }),
  /** 보류(보류된 줄이면 해제). 사유와 메모가 남아 보류 목록에 보인다. */
  skip: (queue: string, id: string, reason?: SkipReason, note?: string) =>
    api.post<ReviewProposal>(`/review/${queue}/${id}/skip`, {
      reason: reason ?? null,
      note: note || null,
    }),
  /** 정한 것을 다시 연다. 이미 일어난 일은 안 되돌린다 — 그건 원래 화면에서. */
  reopen: (queue: string, id: string) =>
    api.post<ReviewProposal>(`/review/${queue}/${id}/reopen`),
  /** 의견 — 로그인한 누구나. 확정이 아니라 데이터는 안 바뀐다. 다시 내면 바뀐다. */
  vote: (queue: string, id: string, choice: string[], note?: string) =>
    api.post<ReviewProposal>(`/review/${queue}/${id}/vote`, { choice, note: note || null }),
  withdrawVote: (queue: string, id: string) =>
    api.delete<ReviewProposal>(`/review/${queue}/${id}/vote`),
  refresh: () => api.post<{ open: Record<string, number> }>('/review/refresh'),
}

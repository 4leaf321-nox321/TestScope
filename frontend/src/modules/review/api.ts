/** 검토함 API — 후보와 근거를 보고, 도메인 전문가가 고른다. 시스템 관리자 전용. */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type ReviewQueue = components['schemas']['QueueOut']
export type ReviewProposal = components['schemas']['ProposalOut']
export type ReviewCandidate = components['schemas']['CandidateOut']
type ProposalPage = components['schemas']['ProposalPage']

export const reviewApi = {
  queues: () => api.get<ReviewQueue[]>('/review'),
  list: (queue: string, params: { status?: string; limit?: number; offset?: number } = {}) => {
    const search = new URLSearchParams()
    if (params.status) search.set('status', params.status)
    if (params.limit) search.set('limit', String(params.limit))
    if (params.offset) search.set('offset', String(params.offset))
    const query = search.toString()
    return api.get<ProposalPage>(`/review/${queue}${query ? `?${query}` : ''}`)
  },
  decide: (queue: string, id: string, choice: string[], note?: string) =>
    api.post<ReviewProposal>(`/review/${queue}/${id}/decide`, { choice, note: note || null }),
  skip: (queue: string, id: string) => api.post<ReviewProposal>(`/review/${queue}/${id}/skip`),
  refresh: () => api.post<{ open: Record<string, number> }>('/review/refresh'),
}

/** VOC API — 게시판이고 절차다. */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type VocItem = components['schemas']['VocItemOut']
export type VocDetail = components['schemas']['VocDetailOut']
export type VocEvent = components['schemas']['VocEventOut']

/** 상태 코드 → 한국어. **서버가 `status_label` 을 주지만** 단추 이름은 화면이 짓는다. */
export const VOC_STATUS_LABELS: Record<string, string> = {
  open: '등록',
  accepted: '접수',
  in_progress: '처리 중',
  resolved: '해결',
  closed: '종료',
  rejected: '반려',
}

export const vocApi = {
  /** 기본은 **아직 끝나지 않은 것.** `status: 'all'` 이면 전부. */
  list: (params: { status?: string; mine?: boolean; limit?: number; offset?: number }) => {
    const search = new URLSearchParams()
    if (params.status) search.set('status', params.status)
    if (params.mine) search.set('mine', 'true')
    search.set('limit', String(params.limit ?? 50))
    search.set('offset', String(params.offset ?? 0))
    return api.get<{ items: VocItem[]; total: number; limit: number; offset: number }>(
      `/voc?${search}`,
    )
  },
  get: (id: string) => api.get<VocDetail>(`/voc/${id}`),
  create: (body: { title: string; body: string; page_path?: string | null }) =>
    api.post<VocDetail>('/voc', body),
  /** 상태를 옮기거나(다른 상태), 말을 보탠다(지금 상태 그대로). */
  move: (id: string, body: { to_status: string; note?: string | null }) =>
    api.post<VocDetail>(`/voc/${id}/move`, body),
}

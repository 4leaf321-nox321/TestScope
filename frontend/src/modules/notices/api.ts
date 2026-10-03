/** 공지 API. */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type Notice = components['schemas']['NoticeOut']

export const noticeApi = {
  /** 초안은 시스템 관리자가 `includeDrafts` 로 물을 때만 온다 — 서버가 가른다. */
  list: (includeDrafts = false) =>
    api.get<Notice[]>(`/notices${includeDrafts ? '?include_drafts=true' : ''}`),
  /** 읽지 않은 팝업. 앱 껍데기가 띄운다. */
  popup: () => api.get<Notice[]>('/notices/popup'),
  /** `publish: false` 면 초안으로 둔다. */
  create: (body: Record<string, unknown>) => api.post<Notice>('/notices', body),
  /** 고치기 — 게시 여부는 안 바꾼다. */
  update: (id: string, body: Record<string, unknown>) =>
    api.patch<Notice>(`/notices/${id}`, body),
  /** 초안을 게시한다. 이미 게시된 것은 409. */
  publish: (id: string) => api.post<Notice>(`/notices/${id}/publish`),
  markRead: (id: string) => api.post<Notice>(`/notices/${id}/read`),
  remove: (id: string) => api.delete<void>(`/notices/${id}`),
}

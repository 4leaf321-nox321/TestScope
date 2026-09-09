/** 공지 API. */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type Notice = components['schemas']['NoticeOut']

export const noticeApi = {
  list: () => api.get<Notice[]>('/notices'),
  /** 읽지 않은 팝업. 앱 껍데기가 띄운다. */
  popup: () => api.get<Notice[]>('/notices/popup'),
  create: (body: Record<string, unknown>) => api.post<Notice>('/notices', body),
  markRead: (id: string) => api.post<Notice>(`/notices/${id}/read`),
  remove: (id: string) => api.delete<void>(`/notices/${id}`),
}

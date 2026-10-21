/** 기준정보 허브(StandardPlatform) 수신 — 연계 설정 · 현황 · 이력(시스템 관리자), 받은 데이터(누구나). */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type HubConnection = components['schemas']['HubConnectionOut']
export type HubType = components['schemas']['HubTypeOut']
export type HubCheck = components['schemas']['HubCheckOut']
export type HubStatus = components['schemas']['HubStatusOut']
export type HubTypeStatus = components['schemas']['HubTypeStatusOut']
export type HubRun = components['schemas']['HubRunOut']
export type HubPublicType = components['schemas']['HubPublicTypeOut']
export type HubItem = components['schemas']['HubItemOut']
export type HubItemDetail = components['schemas']['HubItemDetailOut']
type HubItemPage = components['schemas']['HubItemPage']

export type HubConnectionWrite = {
  base_url: string
  /** 비우면 그대로. 평문은 다시 안 보인다. */
  token?: string | null
  clear_token?: boolean
  ca_bundle?: string | null
  /** `null` 이면 공개 타입 전부(새 타입도 저절로). */
  selected_types: string[] | null
  nightly_at: string
  enabled: boolean
}

export const hubApi = {
  connection: () => api.get<HubConnection>('/hub/connection'),
  saveConnection: (body: HubConnectionWrite) =>
    api.put<HubConnection>('/hub/connection', body),
  check: () => api.post<HubCheck>('/hub/check'),
  catalogSeen: () => api.post<void>('/hub/catalog-seen'),
  status: () => api.get<HubStatus>('/hub/status'),
  /** 수동 실행 — 워커가 받는다. `full` 이면 전량 수신과 부재 대조. */
  run: (full: boolean) => api.post<{ job_id: string; full: boolean }>('/hub/run', { full }),
  runs: (limit = 30) => api.get<HubRun[]>(`/hub/runs?limit=${limit}`),
  types: () => api.get<HubPublicType[]>('/hub/types'),
  items: (type: string, params: { q?: string; state?: string; offset?: number } = {}) => {
    const search = new URLSearchParams()
    if (params.q) search.set('q', params.q)
    if (params.state) search.set('state', params.state)
    if (params.offset) search.set('offset', String(params.offset))
    search.set('limit', '50')
    return api.get<HubItemPage>(`/hub/types/${encodeURIComponent(type)}/items?${search}`)
  },
  item: (type: string, key: string) =>
    api.get<HubItemDetail>(
      `/hub/types/${encodeURIComponent(type)}/items/${encodeURIComponent(key)}`,
    ),
}

/** 받은 객체의 상태 — 화면이 쓰는 이름. */
export const ITEM_STATE: Record<string, string> = {
  active: '사용',
  deprecated: '사용 중지',
  deleted: '삭제',
  hidden: '숨김(조회 범위 밖)',
  merged: '병합',
  absent: '부재(허브에서 사라짐)',
}

/** 실행 방식 · 결과 — 화면이 쓰는 이름. */
export const RUN_TRIGGER: Record<string, string> = {
  schedule: '야간 자동',
  reconcile: '주간 전량 대조',
  manual: '수동',
}
export const RUN_STATUS: Record<string, string> = {
  running: '실행 중',
  ok: '정상',
  partial: '일부 실패',
  failed: '실패',
}

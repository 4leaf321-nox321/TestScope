/** 계정 관리 API — 시스템 관리자 전용. */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type Account = components['schemas']['AccountOut']
export type AccountSummary = components['schemas']['AccountSummaryOut']
export type TemporaryPassword = components['schemas']['TemporaryPasswordResponse']
export type Membership = components['schemas']['MembershipOut']

export const accountApi = {
  summary: () => api.get<AccountSummary>('/accounts/summary'),
  list: (status?: string) =>
    api.get<Account[]>(`/accounts${status ? `?status=${status}` : ''}`),
  create: (body: Record<string, unknown>) => api.post<TemporaryPassword>('/accounts', body),
  approve: (id: string, body: { workspace_slug?: string | null; role?: string }) =>
    api.post<Account>(`/accounts/${id}/approve`, body),
  reject: (id: string, note: string) => api.post<Account>(`/accounts/${id}/reject`, { note }),
  suspend: (id: string) => api.post<Account>(`/accounts/${id}/suspend`),
  activate: (id: string) => api.post<Account>(`/accounts/${id}/activate`),
  /**
   * 지금 소속 — **역할까지.** 목록(`Account.memberships`)은 slug 만 준다.
   *
   * 그것만 보고 창을 채우면 역할을 모르는 채로 되보내게 되고, 그러면 **부서 관리자가
   * 조용히 멤버로 내려앉는다** — 그 사람은 어제 하던 일을 오늘 못 하면서 왜인지도 모른다.
   */
  memberships: (id: string) => api.get<Membership[]>(`/accounts/${id}/memberships`),
  /**
   * 소속을 **한 번에** 정한다 — 준 목록이 곧 소속이다(있던 것은 지운다).
   *
   * 떼기와 붙이기를 따로 부르지 않는 이유: 부서를 옮기는 일은 두 걸음인데, 두 번에
   * 나누면 그 사이에 아무 데도 안 속한 사람이 남고 두 번째가 실패하면 그대로 굳는다.
   */
  setMemberships: (id: string, items: { workspace_slug: string; role: string }[]) =>
    api.put<Account>(`/accounts/${id}/memberships`, { items }),
  setHome: (id: string, workspaceSlug: string) =>
    api.post<Account>(`/accounts/${id}/home-workspace`, { workspace_slug: workspaceSlug }),
  setSystemAdmin: (id: string, grant: boolean) =>
    api.post<Account>(`/accounts/${id}/system-admin`, { is_system_admin: grant }),
  resetPassword: (id: string) => api.post<TemporaryPassword>(`/accounts/${id}/reset-password`),
  remove: (id: string) => api.delete<Account>(`/accounts/${id}`),
}

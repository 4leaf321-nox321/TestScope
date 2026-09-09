/** 계정 관리 API — 시스템 관리자 전용. */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type Account = components['schemas']['AccountOut']
export type AccountSummary = components['schemas']['AccountSummaryOut']
export type TemporaryPassword = components['schemas']['TemporaryPasswordResponse']

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
  setHome: (id: string, workspaceSlug: string) =>
    api.post<Account>(`/accounts/${id}/home-workspace`, { workspace_slug: workspaceSlug }),
  setSystemAdmin: (id: string, grant: boolean) =>
    api.post<Account>(`/accounts/${id}/system-admin`, { is_system_admin: grant }),
  resetPassword: (id: string) => api.post<TemporaryPassword>(`/accounts/${id}/reset-password`),
  remove: (id: string) => api.delete<Account>(`/accounts/${id}`),
}

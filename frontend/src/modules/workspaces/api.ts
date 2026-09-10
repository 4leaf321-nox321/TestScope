/** 부서 API. */

import { api, downloadFile } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type Workspace = components['schemas']['WorkspaceOut']
export type Member = components['schemas']['MemberOut']
export type WorkspaceReference = components['schemas']['WorkspaceReferenceOut']
export type WorkspaceOption = components['schemas']['WorkspaceOption']

export const workspaceApi = {
  /**
   * 부서 정보를 CSV 로 내려받는다 — **ReportArchive 와 같은 형식.**
   *
   * 평범한 `<a href>` 로는 안 된다. access 토큰은 메모리에만 있어서 브라우저가
   * 스스로 여는 주소에는 안 실리고, 그러면 새 탭에서 401 이 나는데 **화면에는
   * 아무 표시도 안 뜬다.**
   */
  exportCsv: () => downloadFile('/workspaces/export.csv', '부서정보.csv'),

  options: () => api.get<WorkspaceOption[]>('/workspaces/options'),
  list: (all = false) => api.get<Workspace[]>(`/workspaces${all ? '?all=true' : ''}`),
  create: (body: { slug: string; name: string; parent_slug?: string | null }) =>
    api.post<Workspace>('/workspaces', body),
  update: (slug: string, body: Record<string, unknown>) =>
    api.patch<Workspace>(`/workspaces/${slug}`, body),
  move: (slug: string, parentSlug: string | null) =>
    api.post<Workspace>(`/workspaces/${slug}/move`, { parent_slug: parentSlug }),
  reorder: (slug: string, direction: 'up' | 'down') =>
    api.post<Workspace>(`/workspaces/${slug}/reorder`, { direction }),
  /** **누르기 전에 무엇이 딸려 있는지 보여 준다.** */
  references: (slug: string) =>
    api.get<WorkspaceReference[]>(`/workspaces/${slug}/references`),
  remove: (slug: string) => api.delete<void>(`/workspaces/${slug}`),

  members: (slug: string) => api.get<Member[]>(`/workspaces/${slug}/members`),
  addMember: (slug: string, email: string, role: string) =>
    api.post<Member>(`/workspaces/${slug}/members`, { email, role }),
  setRole: (slug: string, userId: string, role: string) =>
    api.patch<Member>(`/workspaces/${slug}/members/${userId}`, { role }),
  removeMember: (slug: string, userId: string) =>
    api.delete<void>(`/workspaces/${slug}/members/${userId}`),
}

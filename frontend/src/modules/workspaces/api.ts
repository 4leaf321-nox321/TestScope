/** 부서 API. */

import { api, downloadFile } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type Workspace = components['schemas']['WorkspaceOut']
export type Member = components['schemas']['MemberOut']
export type WorkspaceReference = components['schemas']['WorkspaceReferenceOut']
export type WorkspaceReassign = components['schemas']['WorkspaceReassignOut']
export type WorkspaceOption = components['schemas']['WorkspaceOption']
export type WorkspaceImportResult = components['schemas']['WorkspaceImportResult']
export type WorkspaceImportRow = components['schemas']['WorkspaceImportRowOut']

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
  /**
   * ReportArchive 「부서 정보 내보내기」 를 **붙여넣은 글자**로 들인다. 파일이 아닌 이유는 장비
   * 반입과 같다(DRM). `dryRun` 이면 무엇이 만들어질지만 — 미리보기와 적용이 같은 판정이다.
   */
  importText: (text: string, updateExisting: boolean, dryRun: boolean) =>
    api.post<WorkspaceImportResult>(
      `/workspaces/import?dry_run=${dryRun ? 'true' : 'false'}`,
      {
        text,
        update_existing: updateExisting,
      },
    ),
  /** 사이드바 「신뢰성 시험」 아래에 설 부서들 — 소속과 무관하게 누구나 본다. */
  reliabilityListed: () => api.get<WorkspaceOption[]>('/workspaces/reliability-listed'),
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
  /**
   * 이 부서를 저 부서로 합치면 무엇이 옮겨지고 무엇이 겹치나 — **고르는 순간 본다.**
   *
   * `clashes` 가 있으면 그대로는 못 옮긴다(같은 이름이 둘이 된다). 값까지 오므로
   * 화면이 「무엇을 고쳐야 하는지」 를 그대로 보일 수 있다.
   */
  reassignPreview: (slug: string, to: string) =>
    api.get<WorkspaceReassign>(
      `/workspaces/${slug}/reassign-preview?to=${encodeURIComponent(to)}`,
    ),
  /**
   * 부서를 지운다. `reassignTo` 를 주면 가진 것을 그 부서로 **한 걸음에** 옮기고 지운다.
   *
   * 옮기기와 지우기를 두 번에 나누지 않는 이유: 그 사이에 반쯤 옮겨진 부서가 남고,
   * 그때 무엇이 어디 있는지 아무도 모른다.
   */
  remove: (slug: string, reassignTo?: string | null) =>
    api.delete<void>(
      reassignTo
        ? `/workspaces/${slug}?reassign_to=${encodeURIComponent(reassignTo)}`
        : `/workspaces/${slug}`,
    ),

  members: (slug: string) => api.get<Member[]>(`/workspaces/${slug}/members`),
  addMember: (slug: string, email: string, role: string) =>
    api.post<Member>(`/workspaces/${slug}/members`, { email, role }),
  setRole: (slug: string, userId: string, role: string) =>
    api.patch<Member>(`/workspaces/${slug}/members/${userId}`, { role }),
  removeMember: (slug: string, userId: string) =>
    api.delete<void>(`/workspaces/${slug}/members/${userId}`),
}

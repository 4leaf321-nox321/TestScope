/**
 * 사내 규격서 API — **부서가 만든 시험 문서.**
 *
 * 공개 규격(`/methods`, ASTM·ISO·KS 601건)과 **다른 표다.** 출처도 권한도 개정 주기도
 * 다르고, 한 목록에 섞으면 「우리가 인용하는 공개 규격」 을 세는 숫자가 전부 틀어진다.
 *
 * 파일은 첨부로 붙는다(`target="spec_document"`) — 원본과 개정본이 함께.
 */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type SpecDocument = components['schemas']['SpecDocumentOut']
export type SpecDocumentWrite = {
  code: string
  title: string
  revision: string | null
  note: string | null
}

export const specDocumentApi = {
  /** 전사 전부(부서 순) 또는 한 부서 것. 읽기는 로그인한 누구나 —
   *  옆 부서가 무슨 기준으로 시험하는지 보는 것이 이 플랫폼의 물음이다. */
  list: (params: { workspace?: string; q?: string } = {}) => {
    const search = new URLSearchParams()
    if (params.workspace) search.set('workspace', params.workspace)
    if (params.q) search.set('q', params.q)
    const query = search.toString()
    return api.get<SpecDocument[]>(`/spec-documents${query ? `?${query}` : ''}`)
  },
  read: (id: string) => api.get<SpecDocument>(`/spec-documents/${id}`),
  create: (workspace: string, body: SpecDocumentWrite) =>
    api.post<SpecDocument>('/spec-documents', { workspace_slug: workspace, ...body }),
  /** 부분 수정. **판(`revision`)을 고치는 것이 개정이다** — 줄을 새로 만들지 않아서
   *  걸어 둔 신뢰성 시험의 링크가 안 끊긴다. */
  update: (id: string, body: Partial<SpecDocumentWrite>) =>
    api.patch<SpecDocument>(`/spec-documents/${id}`, body),
  /** 걸려 있는 시험이 있으면 409 — 지우고 나면 그 시험이 무엇을 따랐는지 알 수 없다. */
  remove: (id: string) => api.delete<void>(`/spec-documents/${id}`),
}

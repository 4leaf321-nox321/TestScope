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
export type SpecDocumentRevision = components['schemas']['SpecDocumentRevisionOut']
export type SpecDocumentWrite = {
  /** **번호는 없을 수 있다** — 번호 안 붙은 사내 문서가 실제로 있다. */
  code: string | null
  title: string
  revision: string | null
  /** 본 자리 — 「12-18」. */
  pages: string | null
  /** 발췌인가. 전문을 안 본 채 옮긴 것은 그렇게 보여야 한다. */
  is_excerpt: boolean
  /** 원본이 있는 사내 경로·URL. 파일을 못 올리는 문서가 있다. */
  source_path: string | null
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
  /** 개정 이력 — 나중 판이 먼저. 최신판 줄에 **아직 안 본 시험 수**가 함께 온다. */
  revisions: (id: string) =>
    api.get<SpecDocumentRevision[]>(`/spec-documents/${id}/revisions`),
  /** 개정 한 줄을 쌓는다. **딸린 시험은 확정인 채로 두고** 「아직 안 봤다」 표만 붙는다 —
   *  수십 건이 한꺼번에 후보로 내려가면 그날 일이 멈추고, 멈춘 일은 미뤄진다. */
  addRevision: (
    id: string,
    body: { label: string; issued_on?: string | null; summary?: string | null },
  ) => api.post<SpecDocumentRevision>(`/spec-documents/${id}/revisions`, body),
  /** 걸려 있는 시험이 있으면 409 — 지우고 나면 그 시험이 무엇을 따랐는지 알 수 없다. */
  remove: (id: string) => api.delete<void>(`/spec-documents/${id}`),
}

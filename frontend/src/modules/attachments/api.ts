/**
 * 첨부 — **파일은 한 벌, 붙는 자리는 여럿.**
 *
 * 올리는 것은 multipart 라 `api.post`(JSON)를 못 쓴다. 한 번에 한 장씩 보낸다 — 여러 장을
 * 한 요청에 담으면 열째에서 막혔을 때 앞의 아홉이 들어갔는지 사람이 알 수 없다.
 */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type Attachment = components['schemas']['AttachmentOut']

/** 첨부를 붙일 수 있는 대상. 속성(`AttributeTarget`)과 같은 말을 쓴다.
 *
 *  `method` 는 **규격서 원문**이다 — 사내 규격서도 여기 붙는다. 여러 신뢰성 시험이
 *  한 문서를 인용하므로 시험마다 복사하지 않고 규격에 두고 「참조 규격」 으로 가리킨다. */
export type AttachmentTarget = 'reliability_test' | 'method' | 'spec_document'

export const attachmentApi = {
  list: (target: AttachmentTarget, objectId: string) =>
    api.get<Attachment[]>(
      `/attachments?${new URLSearchParams({ target, object_id: objectId })}`,
    ),

  upload: async (
    target: AttachmentTarget,
    objectId: string,
    file: File,
    options: { definitionId?: string | null; caption?: string } = {},
  ): Promise<Attachment> => {
    const form = new FormData()
    form.append('target', target)
    form.append('object_id', objectId)
    form.append('file', file)
    if (options.definitionId) form.append('definition_id', options.definitionId)
    form.append('caption', options.caption ?? '')
    return api.upload<Attachment>('/attachments', form)
  },

  update: (id: string, body: { caption?: string; definition_id?: string | null }) =>
    api.patch<Attachment>(`/attachments/${id}`, body),

  remove: (id: string) => api.delete(`/attachments/${id}`),
}

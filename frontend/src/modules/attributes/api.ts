/**
 * 항목 정의 API — 신뢰성 시험(뒤에는 보유 장비)에 붙는 칸을 열이 아니라 **행**으로 둔다.
 *
 * 정의는 초안(draft)과 정식(standard). 초안은 값을 적는 사람이 새 이름을 쓰면 서버가 만든다 —
 * 여기서 만드는 것은 시스템 관리자가 미리 준비하는 정의다. 값은 붙는 대상의 API 가 함께 받는다.
 */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type AttributeDefinition = components['schemas']['AttributeDefinitionOut']
export type AttributeValue = components['schemas']['AttributeValueOut']
export type AttributeValueIn = components['schemas']['AttributeValueIn']
export type AttributeTarget = 'reliability_test' | 'equipment' | 'series' | 'method'

export const attributeApi = {
  /** 한 대상의 항목 정의 — 정식이 먼저, 초안이 뒤. `value_count` 가 그 항목으로 적힌 값의 수. */
  definitions: (target: AttributeTarget, includeInactive = false) =>
    api.get<AttributeDefinition[]>(
      `/attribute-definitions?target=${target}${includeInactive ? '&include_inactive=true' : ''}`,
    ),
  create: (body: Record<string, unknown>) =>
    api.post<AttributeDefinition>('/attribute-definitions', body),
  /** 정식으로 올리기는 `{ status: 'standard' }` 하나. 종류는 값이 없을 때만 바뀐다. */
  update: (id: string, body: Record<string, unknown>) =>
    api.patch<AttributeDefinition>(`/attribute-definitions/${id}`, body),
  /** **값이 0건인 항목만** 지워진다(오타 초안). 값이 있으면 409 — 끄거나 합친다. */
  remove: (id: string) => api.delete<void>(`/attribute-definitions/${id}`),
  /** 이름만 다른 항목을 `targetId` 로. 값이 옮겨 가고 이 항목은 꺼진다. */
  merge: (id: string, targetId: string) =>
    api.post<AttributeDefinition>(`/attribute-definitions/${id}/merge`, {
      target_id: targetId,
    }),
}

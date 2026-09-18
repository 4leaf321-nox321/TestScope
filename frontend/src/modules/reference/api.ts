/** 기준정보 허브 — 객체 종류마다 저장 방식·건수·고정 칸·관리자 정의 칸을 한 표로. */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type ObjectKind = components['schemas']['ObjectKindOut']

export const referenceApi = {
  overview: () => api.get<ObjectKind[]>('/reference/overview'),
}

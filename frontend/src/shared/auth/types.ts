/**
 * 인증 관련 타입 — **생성된 스키마에서 뽑아 쓴다.**
 *
 * 손으로 적은 타입은 반드시 서버와 어긋나고, 어긋난 날 화면은 아무 말도 안 하고
 * undefined 를 그린다. 그래서 여기는 이름만 붙이고 모양은 서버가 정한다.
 *
 *     cd backend  ; python scripts/export_openapi.py
 *     cd frontend ; npm run api:types
 */

import type { components } from '@/shared/api/schema'

export type WorkspaceMembership = components['schemas']['WorkspaceMembershipOut']
export type CurrentUser = components['schemas']['UserOut']
export type LoginResponse = components['schemas']['LoginResponse']

/**
 * 이 설치가 어느 버전인가.
 *
 * **서버가 정본이다.** 화면 번들에 버전을 박아 넣으면 그것은 빌드된 버전이지 지금
 * 도는 서버가 아니다 — 배포가 반쯤 끝난 상태에서 둘이 갈리고, 그때 화면이
 * 거짓말을 한다. 답이 틀린 것은 못 답하는 것보다 나쁘다.
 */

import { api } from '@/shared/api/client'

export interface Health {
  status: string
  /** v0.1.0 처럼. 어디서도 못 찾으면 unknown — 개발 경로에서 돈다는 뜻이다. */
  version: string
}

/** 어디서도 못 찾았을 때 서버가 주는 값. **화면은 이것을 안 보여 준다.** */
export const UNKNOWN_VERSION = 'unknown'

export const systemApi = {
  health: () => api.get<Health>('/health'),
}

/**
 * 표의 줄을 눌러 여는 자리 — **링크·단추 위에서는 안 연다.**
 *
 * 줄 전체를 누를 수 있게 하면 편하지만, 그 줄 안에는 대개 다른 데로 가는 링크가 함께 있다
 * (시험 항목 링크 · 부서 이름 · 「수행 가능 장비」 단추). 그것을 누른 사람은 거기로 가려던
 * 것이지 줄을 연 것이 아니다. 구별하지 않으면 **누를 때마다 엉뚱한 창이 뜬다.**
 *
 * 모듈 둘 이상이 쓰므로 여기 둔다 — 한쪽에 두고 다른 쪽이 가져다 쓰면, 그 모듈을 지울 때
 * 관계없는 화면이 같이 깨진다.
 */

import type { MouseEvent } from 'react'

const INTERACTIVE = 'a, button, input, select, textarea, label, [role="button"]'

export function isPlainRowClick(event: MouseEvent<HTMLElement>): boolean {
  const target = event.target as HTMLElement | null
  // **판정 못 하면 아무 일도 안 한다.** `!target?.closest(…)` 로 적으면 target 이 없을 때
  // 참이 되어, 무엇을 눌렀는지 모르는 채로 창을 연다.
  if (target === null || typeof target.closest !== 'function') return false
  return target.closest(INTERACTIVE) === null
}

/**
 * 사이드바가 화면 목록의 정본이다 — **라우터와 어긋나면 여기서 잡는다.**
 *
 * 메뉴에 있는데 라우트가 없으면 눌렀을 때 「없는 페이지」 가 뜬다. 그것은 고장으로
 * 읽히는데, 실제로는 둘 중 한쪽만 고친 것이다.
 */

import { describe, expect, it } from 'vitest'

import { NAV_GROUPS, canSee, itemHref, pendingItems, visibleGroups } from './navigation'

const MEMBER = { isSystemAdmin: false, isAnyManager: false }
const MANAGER = { isSystemAdmin: false, isAnyManager: true }
const ADMIN = { isSystemAdmin: true, isAnyManager: true }

describe('권한별 메뉴', () => {
  it('멤버에게는 관리 메뉴가 안 보인다', () => {
    const labels = visibleGroups(MEMBER).flatMap((group) =>
      group.items.map((one) => one.label),
    )
    expect(labels).toContain('장비 찾기')
    expect(labels).toContain('보유 장비')
    // **눌러야 403 을 아는 메뉴는 "할 수 있는 일" 을 알려 주지 못한다.**
    expect(labels).not.toContain('계정')
    expect(labels).not.toContain('부서 멤버')
  })

  it('부서 관리자는 내 부서 메뉴까지 본다', () => {
    const labels = visibleGroups(MANAGER).flatMap((group) =>
      group.items.map((one) => one.label),
    )
    expect(labels).toContain('부서 멤버')
    expect(labels).toContain('변경 이력')
    expect(labels).not.toContain('계정')
  })

  it('시스템 관리자는 전부 본다', () => {
    const labels = visibleGroups(ADMIN).flatMap((group) => group.items.map((one) => one.label))
    expect(labels).toContain('계정')
    expect(labels).toContain('부서 정보')
    expect(labels).toContain('서버')
  })

  it('빈 그룹은 제목까지 사라진다', () => {
    // 제목만 남으면 「뭔가 안 나온다」 로 읽힌다.
    const titles = visibleGroups(MEMBER).map((group) => group.title)
    expect(titles).not.toContain('관리')
    expect(titles).not.toContain('내 부서')
  })

  it('audience 가 없으면 누구나 본다', () => {
    expect(canSee(undefined, MEMBER)).toBe(true)
    expect(canSee('manager', MEMBER)).toBe(false)
    expect(canSee('manager', ADMIN)).toBe(true)
  })
})

describe('경로', () => {
  it('부서 스코프 항목은 slug 를 받아 푼다', () => {
    const home = NAV_GROUPS[0].items[0]
    expect(itemHref(home, 'metal-lab')).toBe('/w/metal-lab')
  })

  it('모든 항목이 갈 곳을 갖는다', () => {
    // to 도 resolve 도 없으면 눌렀을 때 루트로 튄다 — 아무 일도 안 한 것처럼 보인다.
    for (const item of NAV_GROUPS.flatMap((group) => group.items)) {
      expect(item.to ?? item.resolve).toBeDefined()
    }
  })

  it('미구현 항목은 단계를 밝힌다', () => {
    // 빈 화면으로 두면 "고장난 것" 처럼 보인다. 언제 오는지 적어 두면 상태를 안다.
    for (const item of pendingItems()) {
      expect(item.phase).toBeTruthy()
    }
  })
})

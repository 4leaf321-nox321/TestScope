/**
 * 줄을 눌러 여는 자리 — **링크·단추 위에서는 안 연다.**
 *
 * 이 판정이 화면 시험으로는 잘 안 잡힌다: 줄 안의 링크가 마침 줄과 같은 곳으로 가면
 * 가드를 빼도 시험이 통과한다(실측 2026-09-24, 보유 장비 목록). 그래서 판정 자체를 여기서
 * 본다 — 이 함수가 틀리면 신뢰성 시험 목록에서 「인장」 을 누른 사람이 엉뚱한 창을 받는다.
 */

import { describe, expect, it } from 'vitest'

import { isPlainRowClick } from './rowClick'

/** `event.target` 만 보는 함수라, 진짜 DOM 조각이면 충분하다. */
function clickOn(html: string, pick: string) {
  const host = document.createElement('table')
  host.innerHTML = `<tbody><tr>${html}</tr></tbody>`
  const target = host.querySelector(pick)
  expect(target).not.toBeNull()
  return isPlainRowClick({ target } as unknown as Parameters<typeof isPlainRowClick>[0])
}

describe('줄 클릭', () => {
  it('글자 위에서는 연다', () => {
    expect(clickOn('<td><span>만능재료시험기</span></td>', 'span')).toBe(true)
  })

  it('링크 위에서는 안 연다 — 그 사람은 거기로 가려던 것이다', () => {
    expect(clickOn('<td><a href="/x">인장</a></td>', 'a')).toBe(false)
  })

  it('링크 **안의** 글자에서도 안 연다', () => {
    expect(clickOn('<td><a href="/x"><span>인장</span></a></td>', 'span')).toBe(false)
  })

  it('단추·입력칸·선택칸 위에서는 안 연다', () => {
    expect(clickOn('<td><button>수행 가능 장비</button></td>', 'button')).toBe(false)
    expect(clickOn('<td><input placeholder="자산번호" /></td>', 'input')).toBe(false)
    expect(clickOn('<td><select></select></td>', 'select')).toBe(false)
    expect(clickOn('<td><textarea></textarea></td>', 'textarea')).toBe(false)
  })

  it('role="button" 도 단추다 — 라이브러리가 div 로 만든 것들', () => {
    expect(clickOn('<td><div role="button">고르기</div></td>', 'div[role]')).toBe(false)
  })

  it('target 이 없으면 안 연다 — 판정 못 할 때는 아무 일도 안 한다', () => {
    expect(
      isPlainRowClick({ target: null } as unknown as Parameters<typeof isPlainRowClick>[0]),
    ).toBe(false)
  })
})

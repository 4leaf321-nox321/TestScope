/**
 * 크게 보기의 폭 — **원본이 작아도 키우되, 뭉개질 만큼은 안 키운다.**
 *
 * `max-w-full` 만 두면 `<img>` 는 원본 크기로 선다. 560 px 짜리 프로파일은 크게 보기를
 * 눌러도 560 px 그대로라 「눌렀는데 그대로인데」 가 된다(실측 2026-09-24).
 */

import { describe, expect, it } from 'vitest'

import { widthOf } from './ImageLightbox'

describe('크게 보기 폭', () => {
  it('원본의 두 배까지 키운다 — 작은 그림도 커진다', () => {
    // 560x320 온습도 프로파일: 1120px 까지.
    expect(widthOf({ w: 560, h: 320 })).toContain('1120px')
  })

  it('화면을 넘지 않는다 — 가로도 세로도', () => {
    const made = widthOf({ w: 4000, h: 3000 })
    expect(made).toContain('88vw')
    // 세로로도 묶는다: 74vh 에 가로세로비를 곱한 값이 상한 중 하나다.
    expect(made).toContain('74vh')
  })

  it('아직 못 읽었으면 폭을 정하지 않는다 — 클래스의 상한만 쓴다', () => {
    expect(widthOf(null)).toBeUndefined()
    // 0 으로 나누지 않는다.
    expect(widthOf({ w: 0, h: 0 })).toBeUndefined()
  })
})

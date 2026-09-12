/**
 * 단위 환산 — **자릿수를 사람이 세지 않게.**
 *
 * 카탈로그는 「4,000 cP」 로 적고 우리 정의는 Pa·s 다. 머리로 곱하다 0 을 하나 빠뜨리면
 * 검색이 그 틀린 값으로 자신 있게 답한다.
 */

import { describe, expect, it } from 'vitest'

import { convertValue, isError, normalizeUnit } from '@/shared/units'

describe('단위 환산', () => {
  it('단위를 안 적으면 그 칸의 단위로 본다', () => {
    expect(convertValue('4000', 'cP')).toEqual({ value: 4000 })
    expect(convertValue('  ', 'cP')).toBeNull()
  })

  it('점도 cP 를 Pa·s 로 바꾼다', () => {
    const got = convertValue('4000 cP', 'Pa·s')
    expect(got).toMatchObject({ value: 4 })
    expect((got as { note: string }).note).toContain('4 Pa·s')
    // 1.6B cP — 0 을 세는 자리다.
    expect(convertValue('1600000000cP', 'Pa·s')).toMatchObject({ value: 1600000 })
  })

  it('표기가 흔들려도 같은 단위로 본다', () => {
    expect(normalizeUnit('°C')).toBe(normalizeUnit('degC'))
    expect(normalizeUnit('µm')).toBe(normalizeUnit('um'))
    expect(normalizeUnit('N·m')).toBe(normalizeUnit('Nm'))
    expect(convertValue('20 kN', 'N')).toMatchObject({ value: 20000 })
  })

  it('온도는 곱셈이 아니라 자리 옮김이다', () => {
    // 배율표에 섞으면 0 °C 가 0 K 가 된다.
    expect(convertValue('300 K', 'degC')).toMatchObject({ value: 26.85 })
    expect(convertValue('0 degC', 'K')).toMatchObject({ value: 273.15 })
  })

  it('모르는 단위는 거절한다', () => {
    const got = convertValue('10 Hoge', 'kN')
    expect(isError(got)).toBe(true)
    expect((got as { error: string }).error).toContain('모르는 단위')
  })

  it('재는 것이 다르면 거절한다', () => {
    // 조용히 숫자만 취하면 하중 칸에 온도가 들어간다.
    const got = convertValue('20 degC', 'kN')
    expect(isError(got)).toBe(true)
  })

  it('동점도(cSt)는 점도가 아니라고 말한다', () => {
    // 밀도를 알아야 Pa·s 가 된다 — 아는 척하면 틀린 값이 들어간다.
    expect(isError(convertValue('10 cSt', 'Pa·s'))).toBe(true)
  })
})

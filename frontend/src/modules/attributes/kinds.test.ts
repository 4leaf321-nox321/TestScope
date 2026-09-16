/**
 * 친 글자에서 종류 알아맞히기 — **`85℃` 가 문장으로 저장되면 나중에 「80 이상」 을 못 묻는다.**
 */

import { describe, expect, it } from 'vitest'

import { detect, normalizeUnitInput } from '@/modules/attributes/kinds'

describe('종류 알아맞히기', () => {
  it('수치와 단위를 가른다', () => {
    expect(detect('85℃')).toEqual({ kind: 'number', numValue: 85, unit: '℃' })
    expect(detect('5 개')).toEqual({ kind: 'number', numValue: 5, unit: '개' })
    expect(detect('12.5')).toEqual({ kind: 'number', numValue: 12.5, unit: '' })
    expect(detect('-40 degC')).toEqual({ kind: 'number', numValue: -40, unit: 'degC' })
  })

  it('구간은 ~ 로 가르고, 음수가 앞에 와도 읽는다', () => {
    expect(detect('-40~125 ℃')).toEqual({ kind: 'range', numMin: -40, numMax: 125, unit: '℃' })
    expect(detect('85 ~ 85 %')).toEqual({ kind: 'range', numMin: 85, numMax: 85, unit: '%' })
    // 하이픈만 있으면 음수 둘인지 구간인지 사람도 모른다 — 구간으로 읽지 않는다.
    expect(detect('-40-125').kind).toBe('text')
  })

  it('날짜는 날짜로', () => {
    expect(detect('2026-3-1')).toEqual({ kind: 'date', text: '2026-03-01' })
    expect(detect('2026.03.01').kind).toBe('date')
  })

  it('그 밖은 문장 — 숫자로 시작해도 글이 길면 문장이다', () => {
    expect(detect('외관 이상 없음').kind).toBe('text')
    expect(detect('5개 이상 준비하여 시험 전 24시간 방치').kind).toBe('text')
    expect(detect('')).toEqual({ kind: 'text', text: '' })
  })

  it('단위 표기를 서버가 아는 꼴로', () => {
    expect(normalizeUnitInput('℃')).toBe('degC')
    expect(normalizeUnitInput('°C')).toBe('degC')
    expect(normalizeUnitInput('kN')).toBe('kN')
  })
})

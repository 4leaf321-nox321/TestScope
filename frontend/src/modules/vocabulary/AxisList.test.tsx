/**
 * 축 목록 — **접히지 않는다**는 것이 요점이다.
 *
 * 드롭다운이었을 때는 지금 고른 축 말고는 아무것도 화면에 없었다. 여기서 지키는
 * 것 셋: 축이 전부 한꺼번에 보인다 · 값 수가 함께 보인다 · 지금 고른 것이
 * 무엇인지 표시가 남는다.
 */

import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'

import { AxisList } from '@/modules/vocabulary/AxisList'
import type { Vocabulary } from '@/modules/vocabulary/api'

const AXES = [
  { slug: 'test_item', label: '시험 항목', term_count: 87, description: '무엇을 재는가' },
  { slug: 'manufacturer', label: '제조사', term_count: 0, description: null },
] as unknown as Vocabulary[]

describe('AxisList', () => {
  it('축을 펼쳐 두고 값 수를 함께 보여 준다', () => {
    render(<AxisList axes={AXES} current="test_item" onSelect={() => {}} />)

    // 고르지 않은 축도 보인다 — 이것이 드롭다운과 다른 점 전부다.
    expect(screen.getByText('시험 항목')).toBeTruthy()
    expect(screen.getByText('제조사')).toBeTruthy()

    // 빈 축과 채워진 축이 같아 보이면 어디를 채울지 알 수 없다.
    expect(screen.getByText('87')).toBeTruthy()
    expect(screen.getByText('0')).toBeTruthy()
  })

  it('고른 축에 표시가 남고, 누르면 그 슬러그를 준다', () => {
    const onSelect = vi.fn()
    render(<AxisList axes={AXES} current="test_item" onSelect={onSelect} />)

    const chosen = screen.getByText('시험 항목').closest('button')
    expect(chosen?.getAttribute('aria-current')).toBe('true')

    const other = screen.getByText('제조사').closest('button')
    expect(other?.getAttribute('aria-current')).toBe(null)

    fireEvent.click(other!)
    expect(onSelect).toHaveBeenCalledWith('manufacturer')
  })
})

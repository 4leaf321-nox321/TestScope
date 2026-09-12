/**
 * 시험 항목 카탈로그 — **0 이 곧 공백이고, 공백을 골라 볼 수 있다.**
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const rows = [
  {
    id: 't1',
    value: '인장',
    code: 'tensile',
    aliases: ['Tensile'],
    properties_total: 5,
    properties_confirmed: 0,
    methods_total: 12,
    methods_with_requirements: 2,
    series_count: 42,
    model_count: 190,
    equipment_count: 7,
    condition_keys: ['하중 용량', '시험 온도'],
  },
  {
    id: 't2',
    value: '절연저항',
    code: 'insulation_resistance',
    aliases: [],
    properties_total: 0,
    properties_confirmed: 0,
    methods_total: 4,
    methods_with_requirements: 0,
    series_count: 6,
    model_count: 18,
    equipment_count: 0,
    condition_keys: [],
  },
]

vi.mock('@/shared/api/client', () => ({
  api: { get: vi.fn(async () => rows) },
  ApiError: class extends Error {},
}))

import TestItemsCatalogPage from '@/modules/test_items/TestItemsCatalogPage'

async function open(url = '/catalog/test-items') {
  await act(async () => {
    render(
      <MemoryRouter initialEntries={[url]}>
        <TestItemsCatalogPage />
      </MemoryRouter>,
    )
  })
}

beforeEach(() => {})

describe('시험 항목 카탈로그', () => {
  it('한 줄에 사슬 전체의 수를 보인다', async () => {
    await open()
    expect(screen.getByText('인장')).toBeTruthy()
    expect(screen.getByText('(확인 0)')).toBeTruthy()
    expect(screen.getByText('42 / 190')).toBeTruthy()
    expect(screen.getByText('하중 용량 · 시험 온도')).toBeTruthy()
  })

  it('공백을 세고, 골라 보인다', async () => {
    await open()
    // 각각 다른 사람의 할 일이라 따로 센다.
    expect(screen.getByText('물성 없음 1')).toBeTruthy()
    expect(screen.getByText('보유 장비 없음 1')).toBeTruthy()
    expect(screen.getByText('검색축 없음 1')).toBeTruthy()
    await act(async () => {
      fireEvent.click(screen.getByText('물성 없음 1'))
    })
    expect(screen.queryByText('인장')).toBeNull()
    expect(screen.getByText('절연저항')).toBeTruthy()
  })

  it('홈 링크로 거르기가 주소로 온다', async () => {
    await open('/catalog/test-items?gap=equipment')
    expect(screen.queryByText('인장')).toBeNull()
    expect(screen.getByText('절연저항')).toBeTruthy()
  })
})

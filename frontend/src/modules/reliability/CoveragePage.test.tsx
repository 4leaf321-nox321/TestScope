/**
 * 수행 가능 현황 — **급한 시험이 위에, 병목 항목의 수가 보이고, 상태로 거른다.**
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const fetched: string[] = []

function item(value: string, ready: number, extra: Record<string, number> = {}) {
  return {
    term_id: `t-${value}`,
    value,
    ready,
    in_division: ready,
    soon: 0,
    check: 0,
    expired: 0,
    ...extra,
  }
}

const board = {
  computed_at: '2026-10-16T01:00:00Z',
  horizon_days: 60,
  counts: { none: 1, check: 0, single: 1, soon: 0, no_items: 0, ok: 1 },
  rows: [
    {
      test_id: 'r1',
      name: '열충격 500cy',
      division_code: 'mx',
      division_name: 'MX',
      state: 'none',
      bottleneck: '열충격',
      ready: 0,
      items: [item('열충격', 0, { expired: 1 })],
      conditions_asked: 2,
      skipped_conditions: 0,
    },
    {
      test_id: 'r2',
      name: '고온고습 1000h',
      division_code: 'mx',
      division_name: 'MX',
      state: 'single',
      bottleneck: '항온항습',
      ready: 1,
      items: [item('항온항습', 1), item('외관', 4)],
      conditions_asked: 4,
      skipped_conditions: 1,
    },
    {
      test_id: 'r3',
      name: '인장 상온',
      division_code: 'mx',
      division_name: 'MX',
      state: 'ok',
      bottleneck: '인장',
      ready: 5,
      items: [item('인장', 5)],
      conditions_asked: 0,
      skipped_conditions: 0,
    },
  ],
}

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (url: string) => {
      fetched.push(url)
      if (url === '/reliability-tests/divisions')
        return [
          { code: 'mx', name: 'MX', can_register: true },
          { code: 'vd', name: 'VD', can_register: false },
        ]
      if (url.startsWith('/reliability-tests/coverage')) return board
      if (url === '/reliability-tests/r2/equipment')
        return { test_id: 'r2', conditions_asked: 4, skipped: [], items: [], sets: [] }
      if (url === '/reliability-tests/r2') return { id: 'r2', name: '고온고습 1000h' }
      return []
    }),
  },
  ApiError: class extends Error {},
}))

import CoveragePage from '@/modules/reliability/CoveragePage'

async function open(path = '/reliability-tests/coverage') {
  await act(async () => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/reliability-tests/coverage" element={<CoveragePage />} />
        </Routes>
      </MemoryRouter>,
    )
  })
}

beforeEach(() => {
  fetched.length = 0
})

describe('수행 가능 현황', () => {
  it('시험마다 상태와 병목 항목의 수를 보여 준다', async () => {
    await open()
    const rows = screen.getAllByRole('row').slice(1)
    expect(within(rows[0]).getByText('불가')).toBeTruthy()
    expect(within(rows[0]).getByText('열충격 500cy')).toBeTruthy()
    // 항목이 여럿이면 전부 적고, 수는 병목(항온항습 1대)의 것이다.
    expect(within(rows[1]).getByText('1대뿐')).toBeTruthy()
    expect(within(rows[1]).getByText(/항온항습 1대 · 외관 4대/)).toBeTruthy()
    expect(within(rows[1]).getByText(/뺀 조건 1개/)).toBeTruthy()
    expect(screen.getByRole('button', { name: '불가 1' })).toBeTruthy()
  })

  it('상태로 거르고, 사업부를 고르면 그 사업부로 다시 묻는다', async () => {
    await open()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '여유 1' }))
    })
    expect(screen.queryByText('열충격 500cy')).toBeNull()
    expect(screen.getByText('인장 상온')).toBeTruthy()

    await act(async () => {
      fireEvent.change(screen.getByLabelText('사업부'), { target: { value: 'vd' } })
    })
    expect(fetched).toContain('/reliability-tests/coverage?division=vd')
  })

  it('장비 보기는 되는 장비 창을 연다', async () => {
    await open()
    const row = screen.getAllByRole('row')[2]
    await act(async () => {
      fireEvent.click(within(row).getByRole('button', { name: '장비 보기' }))
    })
    expect(fetched).toContain('/reliability-tests/r2')
    expect(fetched).toContain('/reliability-tests/r2/equipment')
  })
})

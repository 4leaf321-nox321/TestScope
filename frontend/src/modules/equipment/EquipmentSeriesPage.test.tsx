/**
 * 장비 계열 목록 — **열마다 거르고, 거르는 것은 서버다.**
 *
 * 이 목록은 전에 한 쪽(200줄)을 통째로 받아 놓고 쪽 넘김이 없었다. 198건이라 그때는
 * 다 보였지만, 200을 넘는 순간 나머지가 조용히 사라지고 그 사실은 화면 어디에도
 * 안 남는다 — 못 찾은 사람은 없다고 결론 내리고 계열을 새로 만든다.
 *
 * 여기서 지키는 것 — 거르기가 서버로 간다 · 열마다 따로 친다 · 0 건이 되어도 거르는
 * 줄은 남는다.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/** 계열 한 줄. */
function series(over: Record<string, unknown> = {}) {
  return {
    id: 's1',
    name: '6800',
    name_ko: null,
    maker: '한국시험기',
    brand: null,
    category: '만능재료시험기',
    kind: 'main',
    status: 'active',
    model_count: 4,
    unit_count: 0,
    operational_count: 0,
    test_item_count: 2,
    ...over,
  }
}

let items: ReturnType<typeof series>[] = []

/** 나간 주소. **거르기가 서버로 갔는지**는 이것으로만 안다. */
const calls: string[] = []

function lastList(): string {
  const rows = calls.filter((one) => one.startsWith('/equipment-series?'))
  return rows[rows.length - 1] ?? ''
}

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (url: string) => {
      calls.push(url)
      if (url.startsWith('/equipment-series/filter-options')) {
        return {
          makers: [{ value: 'm1', label: '한국시험기', count: 12 }],
          categories: [{ value: 'c1', label: '만능재료시험기', count: 9 }],
          kinds: [
            { value: 'main', label: '본체', count: 186 },
            { value: 'accessory', label: '부속', count: 9 },
          ],
          statuses: [{ value: 'active', label: '현행', count: 198 }],
          series: [],
        }
      }
      if (url.startsWith('/equipment-series')) {
        return { items, total: items.length, limit: 50, offset: 0 }
      }
      return []
    }),
    post: vi.fn(),
  },
  ApiError: class extends Error {},
}))

vi.mock('@/shared/auth/AuthContext', () => ({
  useAuth: () => ({ user: { memberships: [], is_system_admin: false } }),
}))

import EquipmentSeriesPage from '@/modules/equipment/EquipmentSeriesPage'

async function open(url = '/catalog/equipment-series') {
  await act(async () => {
    render(
      <MemoryRouter initialEntries={[url]}>
        <EquipmentSeriesPage />
      </MemoryRouter>,
    )
  })
}

beforeEach(() => {
  items = [series()]
  calls.length = 0
})

describe('계열 목록의 열별 거르기', () => {
  it('열마다 거르는 칸이 머리글 아래에 있다', async () => {
    await open()
    // 위에 모아 두면 「이 목록이 왜 짧지」 를 사람이 되짚어야 한다.
    expect(screen.getByPlaceholderText('계열명')).toBeTruthy()
    expect(screen.getByText('제조사 전체')).toBeTruthy()
    expect(screen.getByText('분류 전체')).toBeTruthy()
    expect(screen.getByText('기종 전체')).toBeTruthy()
    expect(screen.getByText('시험 항목 전체')).toBeTruthy()
    expect(screen.getByText('보유 전체')).toBeTruthy()
    expect(screen.getByText('상태 전체')).toBeTruthy()
  })

  it('고를 수 있는 값을 서버에서 받아 온다', async () => {
    await open()
    // 기준정보 전체가 아니라 **카탈로그에 쓰인 값만** — 제조사 축 수백 종 중
    // 계열이 가리키는 것은 79종이다.
    expect(calls.some((one) => one.startsWith('/equipment-series/filter-options'))).toBe(true)
  })

  it('기본은 본체만 본다', async () => {
    await open()
    // 챔버와 시험기가 한 줄씩 섞이면 「우리가 무슨 장비를 가졌나」 가 안 보인다.
    expect(lastList()).toContain('kind=main')
  })

  it('「남은 일」 에서 왔으면 종류로 좁히지 않는다', async () => {
    await open('/catalog/equipment-series?owned=1&test_item=none')
    // 부속 계열도 시험 항목이 빌 수 있다. 좁히면 홈이 센 수와 여기 줄 수가 어긋나고,
    // 그때 사람은 둘 다 안 믿는다.
    expect(lastList()).not.toContain('kind=')
    expect(lastList()).toContain('test_item=none')
    expect(lastList()).toContain('owned=true')
  })

  it('쪽 넘김이 있다', async () => {
    await open()
    // 상한까지 받아 놓고 쪽 넘김을 안 달면 나머지가 조용히 사라진다.
    expect(lastList()).toContain('limit=50')
  })

  it('걸러서 0 건이 되어도 거르는 줄은 남는다', async () => {
    items = []
    await open('/catalog/equipment-series?test_item=none')
    expect(screen.getByPlaceholderText('계열명')).toBeTruthy()
    expect(screen.getByText(/필터에 맞는 계열이 없습니다/)).toBeTruthy()
  })
})

/**
 * 물성 항목 — **제안과 확인을 다르게 그리고, 이어진 것이 없는 물성도 보인다.**
 *
 * 첫 채움은 기계가 했다. 그것이 확인된 것과 같은 얼굴이면 아무도 되짚지 않고, 「굽힘으로
 * 인장강도」 같은 오답이 확인된 것과 나란히 앉는다. 그리고 연결 없는 물성을 숨기면 「우리는
 * 이 물성을 못 잰다」 와 「아직 아무도 안 이었다」 가 같아진다.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

function link(over: Record<string, unknown> = {}) {
  return {
    id: 'l1',
    test_item_term_id: 't1',
    test_item: '인장',
    property_term_id: 'p1',
    property: '인장강도(UTS)',
    property_code: 'mechanical.tensile_strength',
    status: 'suggested',
    source: 'materialtwin',
    note: null,
    confirmed_at: null,
    created_at: '2026-09-12T00:00:00Z',
    ...over,
  }
}

let properties: Record<string, unknown>[] = []
const calls: { method: string; url: string; body?: unknown }[] = []
let admin = false

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (url: string) => {
      calls.push({ method: 'GET', url })
      if (url.startsWith('/properties')) return properties
      if (url.includes('/terms'))
        return [{ id: 't9', value: 'DMA (동적기계)', usage_count: 1 }]
      return []
    }),
    post: vi.fn(async (url: string, body: unknown) => {
      calls.push({ method: 'POST', url, body })
      return link({ id: 'l9', test_item_term_id: 't9', status: 'confirmed', source: 'manual' })
    }),
    patch: vi.fn(async (url: string, body: unknown) => {
      calls.push({ method: 'PATCH', url, body })
      return link({ status: 'confirmed' })
    }),
    delete: vi.fn(async (url: string) => {
      calls.push({ method: 'DELETE', url })
    }),
  },
  ApiError: class extends Error {},
}))

vi.mock('@/shared/auth/AuthContext', () => ({
  useAuth: () => ({ user: { memberships: [], is_system_admin: admin } }),
}))

import PropertiesPage from '@/modules/properties/PropertiesPage'

async function open() {
  await act(async () => {
    render(
      <MemoryRouter>
        <PropertiesPage />
      </MemoryRouter>,
    )
  })
}

beforeEach(() => {
  calls.length = 0
  admin = false
  properties = [
    {
      id: 'p1',
      value: '인장강도(UTS)',
      code: 'mechanical.tensile_strength',
      domain: 'mechanical',
      symbol: 'Rm',
      si_unit: 'Pa',
      aliases: ['UTS'],
      links: [
        link(),
        link({
          id: 'l2',
          test_item_term_id: 't2',
          test_item: '고속 인장',
          status: 'confirmed',
        }),
      ],
    },
    {
      id: 'p2',
      value: '밴드갭',
      code: 'electrical.band_gap',
      domain: 'electrical',
      symbol: null,
      si_unit: 'eV',
      aliases: [],
      links: [],
    },
  ]
})

describe('물성 항목', () => {
  it('제안은 점선으로, 확인은 또렷하게 선다', async () => {
    await open()
    const suggested = screen.getByText('인장').closest('span')
    const confirmed = screen.getByText('고속 인장').closest('span')
    expect(suggested?.className).toContain('border-dashed')
    expect(confirmed?.className).not.toContain('border-dashed')
    // 제안이 몇 개 남았는지 머리에서 센다 — 확인이 할 일이라는 것을 화면이 말한다.
    expect(screen.getByText(/확인 안 한 제안 1/)).toBeTruthy()
  })

  it('이어진 것이 없는 물성도 보이고 그렇다고 말한다', async () => {
    await open()
    expect(screen.getByText('밴드갭')).toBeTruthy()
    expect(screen.getByText(/이어진 시험 없음/)).toBeTruthy()
    // 도메인별로 묶인다 — 「기계」 와 「전기」 가 한 표에 섞이지 않는다.
    expect(screen.getByText('기계')).toBeTruthy()
    expect(screen.getByText('전기')).toBeTruthy()
  })

  it('「시험이 이어진 것만」 은 서버로 간다', async () => {
    await open()
    await act(async () => {
      fireEvent.click(screen.getByLabelText('시험이 이어진 것만'))
    })
    expect(calls.some((one) => one.url.includes('include_unlinked=false'))).toBe(true)
  })

  it('멤버에게는 확인·지우기 단추가 없다', async () => {
    await open()
    expect(screen.queryByLabelText('인장 연결 확인')).toBeNull()
    expect(screen.queryByText('시험 잇기')).toBeNull()
  })

  it('관리자는 제안을 확인하고, 시험을 잇고, 지운다', async () => {
    admin = true
    await open()
    await act(async () => {
      fireEvent.click(screen.getByLabelText('인장 연결 확인'))
    })
    expect(calls.find((one) => one.method === 'PATCH')).toEqual({
      method: 'PATCH',
      url: '/test-item-properties/l1',
      body: { status: 'confirmed' },
    })

    await act(async () => {
      fireEvent.click(screen.getAllByText('시험 잇기')[1])
    })
    // 피커가 뜬다 — 87종을 <Select> 에 펼치지 않는다.
    expect(screen.getByText('시험 항목')).toBeTruthy()

    await act(async () => {
      fireEvent.click(screen.getByLabelText('고속 인장 연결 지우기'))
    })
    expect(calls.find((one) => one.method === 'DELETE')?.url).toBe('/test-item-properties/l2')
  })
})

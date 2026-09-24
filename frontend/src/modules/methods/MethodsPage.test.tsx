/**
 * 시험법 목록·상세 — **못 하는 시험과 끊긴 연결을 가른다.**
 *
 * 시험법 464 중 287 이 「가능 장비 없음」 으로 서 있었다. 그중 172 는 카탈로그가 인용했는데
 * 어느 시험의 규격인지 안 정해져 못 이어진 것이었다 — 못 하는 시험이 아니라 끊긴 연결인데
 * 화면이 그 둘을 구별하지 못했다.
 *
 * 여기서 지키는 것 — 홈의 링크(`?test_item=none`)가 서버 거르기로 간다 · 목록이 「인용
 * 계열」 과 「미정」 을 따로 말한다 · 상세에 시험 항목을 정하는 자리가 있다.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

function method(over: Record<string, unknown> = {}) {
  return {
    id: 'm1',
    code: 'ASTM E8',
    edition: null,
    title: 'Tension Testing of Metallic Materials',
    status: 'active',
    // **목록이다**(N:M) — 규격 하나가 시험 항목 여럿을 덮는다.
    test_items: [],
    body: 'ASTM',
    superseded_by_code: null,
    summary: null,
    workspace_slug: null,
    equipment_count: 0,
    series_count: 0,
    pending_series_count: 3,
    cited_series: [
      { series_id: 's1', series_name: '6800', test_item: null, pending: true },
      { series_id: 's2', series_name: 'AG-X', test_item: '인장', pending: false },
    ],
    requirements: [],
    created_at: '2026-09-01T00:00:00Z',
    can_edit: true,
    ...over,
  }
}

const calls: { method: string; url: string; body?: unknown }[] = []

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (url: string) => {
      calls.push({ method: 'get', url })
      if (url.startsWith('/methods/')) return method()
      if (url.startsWith('/methods')) {
        return { items: [method()], total: 1, limit: 50, offset: 0 }
      }
      if (url.includes('/terms')) return [{ id: 't1', value: '인장', aliases: [] }]
      return []
    }),
    patch: vi.fn(async (url: string, body: unknown) => {
      calls.push({ method: 'patch', url, body })
      return method({
        test_items: [{ term_id: 't1', value: '인장' }],
        pending_series_count: 0,
      })
    }),
    post: vi.fn(),
  },
  ApiError: class extends Error {},
}))

vi.mock('@/shared/auth/AuthContext', () => ({
  useAuth: () => ({ user: { memberships: [], is_system_admin: true } }),
}))

import MethodDetailPage from '@/modules/methods/MethodDetailPage'
import MethodsPage from '@/modules/methods/MethodsPage'

async function open(url: string) {
  await act(async () => {
    render(
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/methods" element={<MethodsPage />} />
          <Route path="/methods/:id" element={<MethodDetailPage />} />
        </Routes>
      </MemoryRouter>,
    )
  })
}

beforeEach(() => {
  calls.length = 0
})

describe('시험법 목록', () => {
  it('홈의 「남은 일」 링크가 서버 거르기로 간다', async () => {
    await open('/methods?test_item=none')
    // 세는 조건과 거르는 조건이 같아야 그 줄을 눌러 온 사람이 같은 목록을 본다.
    const list = calls.find((one) => one.url.startsWith('/methods?'))
    expect(list?.url).toContain('test_item=none')
    expect(screen.getByText('시험 항목 미지정 규격만')).toBeTruthy()
  })

  it('인용 계열과 항목 미정을 따로 말한다', async () => {
    await open('/methods')
    // 「0」 만 보면 카탈로그에 없는 것으로 읽힌다 — 미정 3 이 있으면 끊긴 연결이다.
    expect(screen.getByText('(미정 3)')).toBeTruthy()
    expect(screen.getByText('안 정해짐')).toBeTruthy()
  })
})

describe('시험법 상세', () => {
  it('인용한 계열을 미정과 이어진 것으로 나눠 보인다', async () => {
    await open('/methods/m1')
    expect(screen.getByText('6800')).toBeTruthy()
    expect(screen.getByText('시험 항목 미지정')).toBeTruthy()
    expect(screen.getByText('AG-X')).toBeTruthy()
  })

  it('시험 항목을 정하는 자리가 있고, 고르기 전에는 못 누른다', async () => {
    await open('/methods/m1')
    expect(screen.getByText('이 규격이 어느 시험의 것인지 정해 주십시오.')).toBeTruthy()
    const button = screen.getByText('적용 규격으로 지정')
    // 고르기 전에는 못 누른다.
    expect((button as HTMLButtonElement).disabled).toBe(true)
  })
})

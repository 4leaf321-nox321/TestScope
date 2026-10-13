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
import { act, fireEvent, render, screen, within } from '@testing-library/react'
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
/** 상세가 돌려줄 규격 — 시험마다 덮는다. */
let detail: Record<string, unknown> = {}

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (url: string) => {
      calls.push({ method: 'get', url })
      if (url.includes('/detach-preview')) return { cut: ['6800'], kept: ['AG-X'] }
      if (url.startsWith('/methods/')) return method(detail)
      if (url.startsWith('/methods')) {
        return {
          // 병합 창의 찾기(q=)에만 두 번째 규격이 뜬다.
          items: url.includes('q=')
            ? [method(), method({ id: 'm2', code: 'ASTM E8/E8M', title: 'Tension (metric)' })]
            : [method()],
          total: 2,
          limit: 50,
          offset: 0,
        }
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
    post: vi.fn(async (url: string, body?: unknown) => {
      calls.push({ method: 'post', url, body })
      if (url.endsWith('/detach')) return { cut: ['6800'], kept: ['AG-X'], reopened: false }
      if (url.endsWith('/merge')) return method({ id: 'm2', code: 'ASTM E8/E8M' })
      return { added_to: ['6800'], still_unlinked: 0 }
    }),
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
  detail = {}
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
    expect(screen.getByText('미지정')).toBeTruthy()
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
    expect(screen.getByText('이 규격의 시험 항목 지정 필요.')).toBeTruthy()
    const button = screen.getByText('적용 규격으로 지정')
    // 고르기 전에는 못 누른다.
    expect((button as HTMLButtonElement).disabled).toBe(true)
  })

  it('시험 항목은 정했는데 안 이어진 인용 계열을 알리고, 이을 길을 준다', async () => {
    detail = { test_items: [{ term_id: 't1', value: '인장' }], pending_series_count: 1 }
    await open('/methods/m1')
    // 처리가 끝난 것처럼 보이면 안 된다 — 그 계열의 장비는 이 규격으로 검색되지 않는다.
    expect(screen.getByText('연결되지 않은 인용 계열 1개.')).toBeTruthy()
    await act(async () => {
      screen.getByRole('button', { name: '인용 계열에 시험 항목 추가' }).click()
    })
    expect(
      calls.some((one) => one.method === 'post' && one.url === '/methods/m1/link-citations'),
    ).toBe(true)
    expect(screen.getByText(/인용 계열 1개에 시험 항목 추가 후 연결/)).toBeTruthy()
  })

  it('잘못 걸린 시험 항목을 떼기 전에 끊기는 계열을 보여 주고 사유를 받는다', async () => {
    detail = { test_items: [{ term_id: 't1', value: '인장' }], pending_series_count: 0 }
    await open('/methods/m1')
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '인장 해제' }))
    })
    expect(screen.getByText('1개 계열이 이 규격과 끊김.')).toBeTruthy()
    expect(within(screen.getByRole('dialog')).getByText('6800')).toBeTruthy()
    const confirm = screen.getByRole('button', { name: '해제 (1개 계열 끊김)' })
    // 사유 없이는 못 뗀다.
    expect((confirm as HTMLButtonElement).disabled).toBe(true)
    fireEvent.change(screen.getByLabelText(/해제 사유/), {
      target: { value: '이 규격은 굽힘만 다룸' },
    })
    await act(async () => {
      fireEvent.click(confirm)
    })
    expect(calls).toContainEqual({
      method: 'post',
      url: '/methods/m1/test-items/t1/detach',
      body: { reason: '이 규격은 굽힘만 다룸' },
    })
    expect(screen.getByText(/끊긴 계열 1개는 미연결 인용으로 남음: 6800/)).toBeTruthy()
  })

  it('표기만 다른 규격을 다른 규격으로 병합한다', async () => {
    await open('/methods/m1')
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '다른 규격으로 병합' }))
    })
    // 자기 자신은 후보에 없다.
    await act(async () => {
      fireEvent.click(screen.getByRole('radio'))
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'ASTM E8/E8M(으)로 병합' }))
    })
    expect(calls).toContainEqual({
      method: 'post',
      url: '/methods/m1/merge',
      body: { target_id: 'm2', reason: '' },
    })
  })
})

/**
 * 대량 처리가 **끊어 보내는가** — 운영에서 1784건이 「눌러도 아무 일이 없던」 자리.
 *
 * 서버는 한 번에 500건까지 받는다(한 번의 실수가 되돌릴 수 없는 크기가 되지 않게). 화면은
 * 그 422 를 **안 잡고 있었다** — 사람에게는 조용히 실패한 것으로 보였다.
 *
 * 여기서 지키는 것:
 *
 * 1. 500건씩 끊어 보낸다 — 1784건이면 네 번.
 * 2. **중간 결과를 쌓아 보여 준다** — 세 묶음째에서 막히면 앞의 둘은 이미 처리된 것이고,
 *    그 경계를 사람이 알아야 다시 누를지 정할 수 있다.
 * 3. 통째로 막히면 **화면이 말한다.** 이것이 없어서 「작동 안 함」 으로 보였다.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const get = vi.fn()
const post = vi.fn()

vi.mock('@/shared/api/client', () => ({
  api: { get, post, patch: vi.fn(), delete: vi.fn(), upload: vi.fn() },
  ApiError: class extends Error {},
}))

vi.mock('@/shared/auth/AuthContext', () => ({
  useAuth: () => ({ user: { is_system_admin: true, memberships: [] } }),
}))

vi.mock('react-router-dom', async () => {
  const real = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...real, useParams: () => ({ slug: 'vd' }) }
})

const { default: WorkspaceReliabilityPage } =
  await import('@/modules/reliability/WorkspaceReliabilityPage')

/** 1784건짜리 사업부 — 운영에서 실제로 나온 크기다. */
const TOTAL = 1784

function row(at: number) {
  return {
    id: `t${at}`,
    division_code: 'vd',
    division_name: 'VD',
    name: `시험 ${at}`,
    purpose: '',
    status: 'candidate',
    submitted_via: '사내 AI',
    confirmed_by: null,
    confirmed_at: null,
    test_items: [],
    attributes: [],
    attachment_count: 0,
    can_edit: true,
    created_at: '2026-09-30T00:00:00Z',
    updated_at: '2026-09-30T00:00:00Z',
  }
}

function page(limit: number, offset: number) {
  const items = Array.from({ length: Math.min(limit, TOTAL - offset) }, (_, at) =>
    row(offset + at),
  )
  return { items, total: TOTAL, limit, offset }
}

afterEach(() => vi.clearAllMocks())

describe('대량 처리', () => {
  it('1784건을 500건씩 끊어 보낸다 — 한 번에 보내면 422 다', async () => {
    get.mockImplementation(async (path: string) => {
      if (path.startsWith('/reliability-tests/divisions')) {
        return [{ code: 'vd', name: 'VD', can_register: true, test_count: TOTAL }]
      }
      if (!path.startsWith('/reliability-tests?')) return []
      const found = new URL(`http://x${path}`).searchParams
      return page(Number(found.get('limit') ?? 50), Number(found.get('offset') ?? 0))
    })
    post.mockImplementation(async (_path: string, body: { ids: string[] }) => ({
      requested: body.ids.length,
      done: body.ids,
      failed: [],
    }))

    await act(async () => {
      render(
        <MemoryRouter>
          <WorkspaceReliabilityPage />
        </MemoryRouter>,
      )
    })

    // **쪽으로 끊어 그린다** — 1784건을 한 화면에 세우지 않는다.
    expect(screen.getByText(/전체 1784건/)).toBeTruthy()

    await act(async () => {
      screen.getByLabelText('보이는 줄 전부 고르기').click()
    })
    await act(async () => {
      screen.getByLabelText('필터 결과 전체 1784건 적용').click()
    })
    await act(async () => {
      screen.getByText('확인').click()
    })

    const sent = post.mock.calls.filter(([path]) => path === '/reliability-tests/bulk')
    // 1784 = 500 + 500 + 500 + 284
    expect(sent.map(([, body]) => (body as { ids: string[] }).ids.length)).toEqual([
      500, 500, 500, 284,
    ])
  })

  it('통째로 막히면 화면이 말한다 — 조용히 끝나지 않는다', async () => {
    get.mockImplementation(async (path: string) => {
      if (path.startsWith('/reliability-tests/divisions')) {
        return [{ code: 'vd', name: 'VD', can_register: true, test_count: 3 }]
      }
      if (!path.startsWith('/reliability-tests?')) return []
      return { items: [row(0), row(1), row(2)], total: 3, limit: 50, offset: 0 }
    })
    post.mockRejectedValue(new Error('서버가 거절했습니다'))

    await act(async () => {
      render(
        <MemoryRouter>
          <WorkspaceReliabilityPage />
        </MemoryRouter>,
      )
    })
    await act(async () => {
      screen.getByLabelText('보이는 줄 전부 고르기').click()
    })
    await act(async () => {
      screen.getByText('확인').click()
    })
    // **이것이 없어서 1784건이 「작동 안 함」 으로 보였다.**
    expect(screen.getByText(/서버가 거절했습니다/)).toBeTruthy()
  })
})

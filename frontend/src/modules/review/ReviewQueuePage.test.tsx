/**
 * 검토함 — **추천은 자동으로 골라지지 않고, 근거가 옆에 붙고, 고른 줄은 사라진다.**
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const posted: { url: string; body: unknown }[] = []

const proposal = {
  id: 'p1',
  queue: 'method_test_items',
  subject_key: 'astm d3580',
  subject_id: 'm1',
  subject_label: 'ASTM D3580',
  context: '인용: Unholtz-Dickie 진동 시험기',
  link: '/methods/m1',
  candidates: [
    {
      code: 'vibration_sine_random',
      label: '정현·랜덤 진동',
      recommended: true,
      reason: '규격 제목이 Vibration Testing',
    },
    { code: 'mechanical_shock', label: '기계적 충격', recommended: false, reason: null },
  ],
  payload: {},
  status: 'open',
  choice: null,
  followed: null,
  note: null,
  decided_by: null,
  decided_at: null,
  votes: [
    {
      user_id: 'u2',
      user: '이OO',
      choice: ['mechanical_shock'],
      note: null,
      at: '2026-09-13T00:00:00Z',
    },
  ],
  my_vote: null,
}

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (url: string) => {
      if (url === '/review')
        return [
          {
            key: 'method_test_items',
            label: '규격의 시험 항목',
            description: '어느 시험의 것인지',
            multi: false,
            open: 1,
            decided: 0,
            skipped: 0,
          },
        ]
      if (url.startsWith('/review/method_test_items')) return { items: [proposal], total: 1 }
      if (url.startsWith('/vocabularies/test_item/terms'))
        return [{ id: 't9', value: '굽힘', code: 'flexure', usage_count: 0 }]
      return []
    }),
    post: vi.fn(async (url: string, body: unknown) => {
      posted.push({ url, body })
      return { ...proposal, status: 'decided' }
    }),
  },
  ApiError: class extends Error {},
}))

// 관리자로 본다 — 확정 단추가 있어야 「자동으로 골라지지 않는다」 를 볼 수 있다.
vi.mock('@/shared/auth/AuthContext', () => ({
  useAuth: () => ({ user: { memberships: [], is_system_admin: true } }),
}))

import ReviewQueuePage from '@/modules/review/ReviewQueuePage'

async function open() {
  await act(async () => {
    render(
      <MemoryRouter initialEntries={['/admin/review/method_test_items']}>
        <Routes>
          <Route path="/admin/review/:queue" element={<ReviewQueuePage />} />
        </Routes>
      </MemoryRouter>,
    )
  })
}

beforeEach(() => {
  posted.length = 0
})

describe('검토함 물음 화면', () => {
  it('추천은 근거와 함께 보이되 자동으로 골라지지 않는다', async () => {
    await open()
    expect(screen.getByText('ASTM D3580')).toBeTruthy()
    expect(screen.getByText('추천')).toBeTruthy()
    expect(screen.getByText('규격 제목이 Vibration Testing')).toBeTruthy()
    // 추천(진동)은 자동으로 안 골라진다. 골라져 있는 것은 사람의 의견(충격)이다.
    expect((screen.getByLabelText(/정현·랜덤 진동/) as HTMLInputElement).checked).toBe(false)
    expect((screen.getByLabelText(/기계적 충격/) as HTMLInputElement).checked).toBe(true)
    // 의견이 하나뿐이면 그것이 다수라 미리 골라진다 — 다만 추천이 아니라 사람의 의견이다.
    expect(screen.getByText('다수 의견으로 미리 골라 두었습니다.')).toBeTruthy()
    expect(screen.getByText('이OO')).toBeTruthy()
  })

  it('의견은 줄을 남기고 갱신되며, 확정만 줄을 보낸다', async () => {
    await open()
    await act(async () => {
      fireEvent.click(screen.getByLabelText(/정현·랜덤 진동/))
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '의견 내기' }))
    })
    expect(posted[0]).toEqual({
      url: '/review/method_test_items/p1/vote',
      body: { choice: ['vibration_sine_random'], note: null },
    })
    // 의견을 냈어도 줄은 그대로 있다.
    expect(screen.getByText('ASTM D3580')).toBeTruthy()
  })

  it('고르면 서버에 보내고 줄이 사라진다', async () => {
    await open()
    await act(async () => {
      fireEvent.click(screen.getByLabelText(/기계적 충격/))
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '확정' }))
    })
    expect(posted).toEqual([
      {
        url: '/review/method_test_items/p1/decide',
        body: { choice: ['mechanical_shock'], note: null },
      },
    ])
    expect(screen.queryByText('ASTM D3580')).toBeNull()
  })

  it('건너뛰기는 결정이 아니다', async () => {
    await open()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '건너뛰기' }))
    })
    expect(posted[0].url).toBe('/review/method_test_items/p1/skip')
  })
})

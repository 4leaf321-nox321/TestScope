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
    const radios = screen.getAllByRole('radio') as HTMLInputElement[]
    expect(radios.every((one) => !one.checked)).toBe(true)
    // 고르기 전에는 정할 수 없다 — 빈 결정이 「해당 없음」 으로 들어가면 안 된다.
    expect(
      (screen.getByRole('button', { name: '이걸로 정함' }) as HTMLButtonElement).disabled,
    ).toBe(true)
  })

  it('고르면 서버에 보내고 줄이 사라진다', async () => {
    await open()
    await act(async () => {
      fireEvent.click(screen.getByLabelText(/기계적 충격/))
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '이걸로 정함' }))
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

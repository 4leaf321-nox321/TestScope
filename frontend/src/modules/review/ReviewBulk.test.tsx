/**
 * 검토함 — **합의된 줄만 골라서, 각자의 추천대로 한꺼번에.**
 *
 * 하나씩 열어 「추천」 을 누르는 일이 고됐다(2026-10-03). 덜어 주는 것은 「훑어 확정」 쪽이고,
 * 갈린 줄은 여전히 사람이 열어 본다.
 *
 * 여기서 지키는 것:
 *
 * 1. **추천이 없는 줄 · 추천과 다른 의견이 있는 줄은 고를 수 없다** — 칸이 꺼지고 **왜인지**
 *    가 올라 있다. 숨기면 「이 줄은 왜 안 골라지지」 를 되짚어야 한다.
 * 2. 「추천 있는 줄 고르기」 는 **고를 수 있는 줄만** 고른다.
 * 3. 한 번 더 묻고 나서 보낸다 — 확정하면 바로 적용되고 되돌리지 않는다.
 * 4. 정해진 줄은 목록에서 빠지고, **서버가 돌려보낸 줄은 이유와 함께** 남는다.
 * 5. 관리자가 아니면 고르는 칸이 없다.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

/** 이번 시험의 사람. 관리자가 아니면 고르는 칸이 없다. */
let admin = true
const posted: { url: string; body: unknown }[] = []
/** 서버가 일괄 확정에 돌려줄 것. 시험마다 정한다. */
let answer: { requested: number; done: string[]; failed: unknown[] } = {
  requested: 0,
  done: [],
  failed: [],
}

function proposal(id: string, label: string, over: Record<string, unknown> = {}) {
  return {
    id,
    queue: 'method_test_items',
    subject_key: id,
    subject_id: `m-${id}`,
    subject_label: label,
    context: null,
    link: null,
    candidates: [
      { code: 'tensile', label: '인장', recommended: true, reason: '제목이 Tensile' },
      { code: 'shock', label: '충격', recommended: false, reason: null },
    ],
    payload: {},
    status: 'open',
    choice: null,
    followed: null,
    note: null,
    decided_by: null,
    decided_at: null,
    votes: [],
    my_vote: null,
    ...over,
  }
}

/** 합의 · 추천 없음 · 다른 의견 · **같은 의견**. */
const ROWS = [
  proposal('p-ok', 'ASTM 합의'),
  proposal('p-bare', 'ASTM 추천없음', {
    candidates: [{ code: 'tensile', label: '인장', recommended: false, reason: null }],
  }),
  proposal('p-dissent', 'ASTM 다른의견', {
    votes: [{ user_id: 'u2', user: '이OO', choice: ['shock'], note: null, at: '2026-10-01' }],
  }),
  proposal('p-agree', 'ASTM 같은의견', {
    votes: [
      { user_id: 'u3', user: '박OO', choice: ['tensile'], note: null, at: '2026-10-01' },
    ],
  }),
]

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
            open: 4,
            decided: 0,
            skipped: 0,
          },
        ]
      if (url.startsWith('/review/method_test_items'))
        return { items: ROWS, total: ROWS.length }
      return []
    }),
    post: vi.fn(async (url: string, body: unknown) => {
      posted.push({ url, body })
      return answer
    }),
  },
  ApiError: class extends Error {},
}))

vi.mock('@/shared/auth/AuthContext', () => ({
  useAuth: () => ({ user: { memberships: [], is_system_admin: admin } }),
}))

const { default: ReviewQueuePage, bulkBlock } =
  await import('@/modules/review/ReviewQueuePage')

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

const box = (label: string) => screen.getByLabelText(`${label} 고르기`) as HTMLInputElement

beforeEach(() => {
  admin = true
  posted.length = 0
  answer = { requested: 0, done: [], failed: [] }
})

describe('검토함 — 추천대로 한꺼번에', () => {
  it('합의된 줄만 고를 수 있고, 못 고르는 줄은 왜인지 말한다', async () => {
    await open()
    expect(box('ASTM 합의').disabled).toBe(false)
    // 추천과 **같은** 의견은 막지 않는다 — 합의다.
    expect(box('ASTM 같은의견').disabled).toBe(false)

    expect(box('ASTM 추천없음').disabled).toBe(true)
    expect(box('ASTM 추천없음').title).toMatch(/추천이 없는/)
    expect(box('ASTM 다른의견').disabled).toBe(true)
    expect(box('ASTM 다른의견').title).toMatch(/다른 의견이 1건/)
  })

  it('「추천 있는 줄 고르기」 는 고를 수 있는 줄만 고른다', async () => {
    await open()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /추천 있는 줄 고르기 \(2\)/ }))
    })
    expect(box('ASTM 합의').checked).toBe(true)
    expect(box('ASTM 같은의견').checked).toBe(true)
    expect(box('ASTM 추천없음').checked).toBe(false)
    expect(box('ASTM 다른의견').checked).toBe(false)
  })

  it('한 번 더 묻고 나서 보내고, 정한 줄은 빠지고 돌아온 줄은 이유와 함께 남는다', async () => {
    answer = {
      requested: 2,
      done: ['p-ok'],
      // 그사이 누가 다른 의견을 냈다 — 서버가 돌려보낸다.
      failed: [
        { id: 'p-agree', code: 'TSC-REVIEW-0015', message: '추천과 다른 의견이 1건 있습니다' },
      ],
    }
    await open()
    await act(async () => {
      fireEvent.click(box('ASTM 합의'))
      fireEvent.click(box('ASTM 같은의견'))
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '고른 2건 추천대로 확정' }))
    })
    // **아직 안 보냈다** — 한 번 더 묻는다.
    expect(posted).toEqual([])
    expect(screen.getByText(/각자의 추천대로/)).toBeTruthy()

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '2건 확정' }))
    })
    expect(posted).toEqual([
      {
        url: '/review/method_test_items/decide-recommended',
        body: { ids: ['p-ok', 'p-agree'], note: null },
      },
    ])
    // 정한 줄은 빠지고,
    expect(screen.queryByText('ASTM 합의')).toBeNull()
    // 돌아온 줄은 **이유와 함께** 남는다.
    expect(screen.getByText('1건은 확정하지 않았습니다')).toBeTruthy()
    expect(screen.getByText(/추천과 다른 의견이 1건 있습니다/)).toBeTruthy()
  })

  it('관리자가 아니면 고르는 칸이 없다', async () => {
    admin = false
    await open()
    expect(screen.queryByLabelText('ASTM 합의 고르기')).toBeNull()
    expect(screen.queryByRole('button', { name: /추천 있는 줄 고르기/ })).toBeNull()
  })
})

describe('bulkBlock — 서버와 같은 판단', () => {
  it('추천이 여럿이면 의견이 그 묶음과 같아야 합의다', () => {
    const many = proposal('p-many', '여럿', {
      candidates: [
        { code: 'a', label: 'A', recommended: true, reason: null },
        { code: 'b', label: 'B', recommended: true, reason: null },
      ],
      votes: [{ user_id: 'u', user: 'u', choice: ['b', 'a'], note: null, at: '' }],
    })
    // 순서가 달라도 같은 묶음이면 합의다.
    expect(bulkBlock(many as never)).toBeNull()
    // 하나만 골랐으면 다른 의견이다.
    const partial = {
      ...many,
      votes: [{ user_id: 'u', user: 'u', choice: ['a'], note: null, at: '' }],
    }
    expect(bulkBlock(partial as never)).toMatch(/다른 의견/)
  })
})

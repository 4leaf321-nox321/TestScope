/**
 * 검토함 — **추천은 자동으로 골라지지 않고, 근거가 옆에 붙고, 고른 줄은 사라진다.**
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const posted: { url: string; body: unknown }[] = []
const fetched: string[] = []
/** 확정 전 미리보기가 돌려줄 「안 이어질 인용 계열」. 시험마다 바꾼다. */
let unlinked: string[] = []
/** 목록이 돌려줄 줄 — 시험마다 바꾼다(없으면 기본 줄). */
let listed: unknown[] | null = null

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

const freeSpec = {
  ...proposal,
  id: 'f1',
  queue: 'free_spec_definitions',
  subject_key: 'stroke|mm',
  subject_label: '스트로크 (stroke · mm)',
  candidates: [
    { code: 'promote', label: '정식 사양 정의로 승격', recommended: true, reason: null },
    { code: 'keep', label: '기종 고유 사양으로 유지', recommended: false, reason: null },
  ],
  votes: [],
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
      fetched.push(url)
      if (url.startsWith('/review/free_spec_definitions/f1/preview'))
        return {
          linked: [],
          unlinked: [],
          off_candidates: [],
          kind: 'range',
          movable: ['A-100: min 0 · max 152'],
          unmovable: ['B-200: 약 300'],
        }
      if (url.startsWith('/review/free_spec_definitions'))
        return { items: listed ?? [freeSpec], total: 1 }
      if (url.startsWith('/review/method_test_items/p1/preview'))
        return {
          linked: [],
          unlinked,
          off_candidates: url.includes('flexure') ? ['굽힘'] : [],
        }
      if (url.startsWith('/review/method_test_items'))
        return { items: listed ?? [proposal], total: 1 }
      if (url.startsWith('/vocabularies/test_item/terms'))
        return [{ id: 't9', value: '굽힘', code: 'flexure', usage_count: 0 }]
      return []
    }),
    post: vi.fn(async (url: string, body: unknown) => {
      posted.push({ url, body })
      if (url.endsWith('decide-mcp-votes')) return { requested: 1, done: ['p1'], failed: [] }
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

async function open(path = '/admin/review/method_test_items') {
  await act(async () => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/admin/review/:queue" element={<ReviewQueuePage />} />
        </Routes>
      </MemoryRouter>,
    )
  })
}

beforeEach(() => {
  posted.length = 0
  fetched.length = 0
  unlinked = []
  listed = null
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
    expect(screen.getByText('다수 의견으로 미리 선택됨.')).toBeTruthy()
    expect(screen.getByText('이OO')).toBeTruthy()
  })

  it('의견은 줄을 남기고 갱신되며, 확정만 줄을 보낸다', async () => {
    await open()
    await act(async () => {
      fireEvent.click(screen.getByLabelText(/정현·랜덤 진동/))
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '의견 제출' }))
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
        body: { choice: ['mechanical_shock'], note: null, add_to_citing: false },
      },
    ])
    expect(screen.queryByText('ASTM D3580')).toBeNull()
  })

  it('안 이어질 인용 계열이 있으면 확정 전에 묻고, 인용 계열에 더하는 길을 준다', async () => {
    unlinked = ['Unholtz-Dickie 진동 시험기']
    await open()
    // 후보가 무엇인지 화면이 말한다 — 인용 계열이 이미 하는 시험.
    expect(
      screen.getByText(/후보: 이 규격을 인용한 계열이 이미 수행하는 시험 항목/),
    ).toBeTruthy()
    await act(async () => {
      fireEvent.click(screen.getByLabelText(/기계적 충격/))
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '확정' }))
    })
    // **바로 보내지 않는다.** 안 이어질 계열을 보여 주고 묻는다.
    expect(posted).toEqual([])
    expect(screen.getByText('연결되지 않는 인용 계열 있음')).toBeTruthy()
    expect(screen.getByText('Unholtz-Dickie 진동 시험기')).toBeTruthy()
    await act(async () => {
      fireEvent.click(
        screen.getByRole('button', { name: '인용 계열에 시험 항목 추가 후 확정' }),
      )
    })
    expect(posted).toEqual([
      {
        url: '/review/method_test_items/p1/decide',
        body: { choice: ['mechanical_shock'], note: null, add_to_citing: true },
      },
    ])
  })

  it('보류는 결정이 아니고, 사유와 메모가 남는다', async () => {
    await open()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '보류' }))
    })
    // 바로 보내지 않는다 — 사유를 고른다.
    expect(posted).toEqual([])
    fireEvent.change(screen.getByLabelText('보류 사유'), { target: { value: 'expert' } })
    fireEvent.change(screen.getByLabelText('보류 메모'), {
      target: { value: '진동 담당 확인' },
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '보류 확정' }))
    })
    expect(posted).toEqual([
      {
        url: '/review/method_test_items/p1/skip',
        body: { reason: 'expert', note: '진동 담당 확인' },
      },
    ])
  })

  it('보류 목록에 사유 · 메모 · 누가가 보인다', async () => {
    listed = [
      {
        ...proposal,
        status: 'skipped',
        skip_reason: 'source',
        skip_reason_label: '원문(규격서·사양서) 확인 필요',
        skipped_by: '박OO(MCP)',
        skipped_at: '2026-10-13T00:00:00Z',
        note: '규격서 4절 확인',
      },
    ]
    await open('/admin/review/method_test_items?status=skipped')
    expect(screen.getByText(/보류: 원문\(규격서·사양서\) 확인 필요/)).toBeTruthy()
    expect(screen.getByText(/박OO\(MCP\)/)).toBeTruthy()
    expect(screen.getByText('메모: 규격서 4절 확인')).toBeTruthy()
    expect(screen.getByRole('button', { name: '보류 해제' })).toBeTruthy()
  })

  it('MCP 의견만 모아 보고 MCP 의견대로 한꺼번에 확정한다', async () => {
    listed = [
      {
        ...proposal,
        votes: [
          {
            user_id: 'u3',
            user: '김OO(MCP)',
            choice: ['vibration_sine_random'],
            note: null,
            at: '2026-10-13T00:00:00Z',
            mcp: true,
          },
        ],
      },
    ]
    await open('/admin/review/method_test_items?votes=mcp')
    expect(fetched.some((url) => url.includes('votes=mcp'))).toBe(true)
    // 의견 수 옆에 MCP 몇 건인지.
    expect(screen.getByText(/의견 1 · MCP 1/)).toBeTruthy()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /MCP 의견 일치 줄 고르기/ }))
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '고른 1건 MCP 의견대로 확정' }))
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '1건 확정' }))
    })
    expect(posted).toEqual([
      { url: '/review/method_test_items/decide-mcp-votes', body: { ids: ['p1'], note: null } },
    ])
  })

  it('후보 밖에서 고른 것은 결정 줄에 이름으로 보인다', async () => {
    listed = [
      {
        ...proposal,
        status: 'decided',
        choice: ['custom_001'],
        decided_by: '박OO',
        decided_at: '2026-10-13T00:00:00Z',
        payload: { choice_labels: { custom_001: '열충격 후 굽힘' } },
        votes: [],
      },
    ]
    await open('/admin/review/method_test_items?status=decided')
    expect(screen.getByText('열충격 후 굽힘')).toBeTruthy()
    expect(screen.queryByText('custom_001')).toBeNull()
  })

  it('경고가 붙은 후보는 경고를 보여 준다', async () => {
    listed = [
      {
        ...proposal,
        candidates: [
          {
            code: 'battery_abuse',
            label: '배터리 남용',
            recommended: false,
            reason: '제조사 문장 2',
            warning: '분류와 맞지 않음: 나노인덴터의 다른 계열에 없는 시험',
          },
        ],
      },
    ]
    await open()
    expect(
      screen.getByText('분류와 맞지 않음: 나노인덴터의 다른 계열에 없는 시험'),
    ).toBeTruthy()
  })

  it('사양 정의 승격은 확정 전에 옮기지 못하는 값을 보여 준다', async () => {
    await open('/admin/review/free_spec_definitions')
    await act(async () => {
      fireEvent.click(screen.getByLabelText(/정식 사양 정의로 승격/))
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '확정' }))
    })
    expect(posted).toEqual([])
    expect(screen.getByText('정식 칸으로 옮기지 못하는 값 있음')).toBeTruthy()
    expect(screen.getByText('B-200: 약 300')).toBeTruthy()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '옮길 수 있는 값만 옮기고 승격' }))
    })
    expect(posted).toEqual([
      {
        url: '/review/free_spec_definitions/f1/decide',
        body: { choice: ['promote'], note: null, add_to_citing: false },
      },
    ])
  })
})

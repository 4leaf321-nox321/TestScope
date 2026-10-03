/**
 * VOC 한 건 — **단추는 서버가 말한 것만 선다.**
 *
 * 화면이 권한을 다시 계산하면 서버와 갈라지고, 그때 사람은 눌리는 단추가 403 을 돌려주는
 * 것을 본다 — 그 403 은 고장으로 읽힌다. 그래서 `can_move` 를 그대로 단추로 만든다.
 *
 * 여기서 지키는 것:
 *
 * 1. 흐름이 **시간 순으로** 그려진다 — 등록·상태 변경·댓글이 한 줄씩.
 * 2. 단추는 `can_move` 뿐이다. 하나도 없으면 **왜 없는지** 말한다.
 * 3. 말이 필요한 단추(`note_required`)는 **적기 전에는 안 눌린다** — 눌러서 400 을 받고
 *    알게 하지 않는다.
 * 4. 「말 보태기」 는 **지금 상태를 그대로** 보낸다. 그것이 댓글이다.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const get = vi.fn()
const post = vi.fn()

vi.mock('@/shared/api/client', () => ({
  api: { get, post, patch: vi.fn(), delete: vi.fn(), upload: vi.fn() },
  ApiError: class extends Error {},
}))

const { default: VocDetailPage } = await import('@/modules/voc/VocDetailPage')

const ITEM = {
  id: 'v-1',
  seq: 12,
  title: '장비 수정에서 저장이 안 됩니다',
  body: '저장을 누르면 아무 일도 안 일어납니다.',
  status: 'open',
  status_label: '등록',
  created_by_name: '제보자',
  created_at: '2026-10-01T00:00:00Z',
  status_at: '2026-10-01T00:00:00Z',
  comment_count: 1,
  page_path: '/equipment',
  events: [
    {
      id: 'e-1',
      at: '2026-10-01T00:00:00Z',
      by_name: '제보자',
      from_status: null,
      to_status: 'open',
      note: null,
    },
    {
      id: 'e-2',
      at: '2026-10-01T01:00:00Z',
      by_name: '옆사람',
      from_status: 'open',
      to_status: 'open',
      note: '저도 같은 증상입니다',
    },
  ],
  can_move: ['accepted', 'resolved'],
  note_required: ['resolved'],
}

async function show(over: Partial<typeof ITEM> & { can_attach?: boolean } = {}) {
  // 첨부 목록도 GET 이다 — 한 값으로 다 답하면 첨부 칸이 VOC 한 건을 목록으로 읽는다.
  get.mockImplementation(async (url: string) =>
    url.startsWith('/attachments') ? [] : { ...ITEM, can_attach: false, ...over },
  )
  post.mockResolvedValue({ ...ITEM, ...over })
  await act(async () => {
    render(
      <MemoryRouter initialEntries={['/voc/v-1']}>
        <Routes>
          <Route path="/voc/:id" element={<VocDetailPage />} />
        </Routes>
      </MemoryRouter>,
    )
  })
}

afterEach(() => vi.clearAllMocks())

describe('VOC 한 건', () => {
  it('자료는 붙일 수 있는 사람에게만 올리는 단추가 선다 — 서버가 말해 준다', async () => {
    await show({ can_attach: true })
    expect(screen.getByText(/화면 갈무리 · 자료 첨부/)).toBeTruthy()
    expect(get).toHaveBeenCalledWith('/attachments?target=voc&object_id=v-1')
  })

  it('붙일 수 없고 붙은 것도 없으면 첨부 칸을 안 그린다', async () => {
    await show({ can_attach: false })
    expect(screen.queryByText(/화면 갈무리 · 자료 첨부/)).toBeNull()
  })

  it('흐름이 시간 순으로 그려진다 — 등록도 한 줄이다', async () => {
    await show()
    expect(screen.getByText(/최초 등록/)).toBeTruthy()
    expect(screen.getByText(/· 의견 추가/)).toBeTruthy()
    expect(screen.getByText('저도 같은 증상입니다')).toBeTruthy()
  })

  it('단추는 can_move 뿐이다', async () => {
    await show()
    expect(screen.getByRole('button', { name: '접수' })).toBeTruthy()
    // 서버가 안 준 상태는 단추가 없다 — 있으면 눌러서 403 을 받는다.
    expect(screen.queryByRole('button', { name: '반려' })).toBeNull()
    expect(screen.queryByRole('button', { name: '종료' })).toBeNull()
  })

  it('옮길 데가 없으면 왜 없는지 말한다 — 빈 자리는 고장으로 읽힌다', async () => {
    await show({ can_move: [], note_required: [] })
    expect(screen.getByText(/상태 변경은/)).toBeTruthy()
  })

  it('말이 필요한 단추는 적기 전에는 안 눌린다', async () => {
    await show()
    // 「해결 *」 — 별표가 그 사실을 말한다.
    const resolve = screen.getByRole('button', { name: /해결/ })
    expect(resolve).toBeDisabled()

    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText(/조치 내용/), {
        target: { value: '권한 검사를 고쳤습니다' },
      })
    })
    expect(screen.getByRole('button', { name: /해결/ })).not.toBeDisabled()
  })

  it('「말 보태기」 는 지금 상태를 그대로 보낸다 — 그것이 댓글이다', async () => {
    await show()
    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText(/조치 내용/), {
        target: { value: '저도 그렇습니다' },
      })
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '의견 추가' }))
    })
    expect(post).toHaveBeenCalledWith('/voc/v-1/move', {
      to_status: 'open',
      note: '저도 그렇습니다',
    })
  })
})

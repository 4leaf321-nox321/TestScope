/**
 * 공지 화면 — **초안을 남기고, 게시는 따로 누른다.**
 *
 * 여기서 지키는 것 — 관리자는 초안까지 묻는다 · 「임시저장」 은 초안으로 보낸다 · 초안 줄의
 * 「게시」 가 게시 길을 부른다 · 관리자가 아니면 쓰는 자리가 없다.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'

const get = vi.fn()
const post = vi.fn()

vi.mock('@/shared/api/client', () => ({
  api: { get, post, patch: vi.fn(), delete: vi.fn() },
  ApiError: class extends Error {},
}))

/** 이번 시험의 사람 — 부를 때마다 이 값을 읽는다. */
let admin = true
vi.mock('@/shared/auth/AuthContext', () => ({
  useAuth: () => ({ user: { memberships: [], is_system_admin: admin } }),
}))

const { default: NoticesPage } = await import('@/modules/notices/NoticesPage')

const DRAFT = {
  id: 'n-1',
  title: '점검 안내',
  body: '토요일 오전 서버를 내립니다.',
  level: 'info',
  is_popup: true,
  published_at: null,
  expires_at: null,
  author_name: '관리자',
  read: false,
  created_at: '2026-10-03T00:00:00Z',
}

async function show() {
  get.mockResolvedValue([{ ...DRAFT }])
  post.mockResolvedValue({ ...DRAFT, published_at: '2026-10-03T01:00:00Z' })
  await act(async () => {
    render(<NoticesPage />)
  })
}

beforeEach(() => {
  get.mockReset()
  post.mockReset()
  admin = true
})

describe('공지', () => {
  it('관리자는 초안까지 묻고, 초안 줄에서 따로 게시한다', async () => {
    await show()
    expect(get).toHaveBeenCalledWith('/notices?include_drafts=true')
    expect(screen.getByText('초안')).toBeTruthy()

    // 초안 줄의 「게시」 — 쓰는 칸의 「게시」 와 다른 단추다.
    const buttons = screen.getAllByRole('button', { name: '게시' })
    await act(async () => {
      fireEvent.click(buttons[buttons.length - 1])
    })
    expect(post).toHaveBeenCalledWith('/notices/n-1/publish')
  })

  it('「임시저장」 은 초안으로 보낸다', async () => {
    await show()
    fireEvent.change(screen.getByPlaceholderText('제목'), { target: { value: '새 공지' } })
    fireEvent.change(screen.getByPlaceholderText('내용'), { target: { value: '본문' } })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '임시저장' }))
    })
    expect(post).toHaveBeenCalledWith('/notices', {
      title: '새 공지',
      body: '본문',
      is_popup: false,
      publish: false,
    })
  })

  it('관리자가 아니면 쓰는 자리도 초안 묻기도 없다', async () => {
    admin = false
    await show()
    expect(get).toHaveBeenCalledWith('/notices')
    expect(screen.queryByRole('button', { name: '임시저장' })).toBeNull()
    expect(screen.queryByRole('button', { name: '고치기' })).toBeNull()
  })
})

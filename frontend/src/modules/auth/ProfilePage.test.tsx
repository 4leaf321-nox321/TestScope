/**
 * 액세스 토큰 발급 — **화면이 범위를 고르게 한다.**
 *
 * 화면이 이름만 보내던 때가 있었다. 서버는 안 주면 `["read"]` 로 보므로(설계대로다)
 * 무엇을 적든 **읽기 전용만 나왔고**, 그 토큰으로 MCP 쓰기 도구를 부르면 403 이 왔다.
 * 그 403 은 「권한이 없다」 로 읽혀서 사람은 관리자를 찾아갔다 — 실제로는 제가 발급한
 * 토큰이 좁았던 것이다(2026-09-29).
 *
 * 그래서 여기서 지키는 것:
 *
 * 1. 아무것도 안 고르면 **읽기 전용**으로 간다 — 기본이 전권이면 아무도 안 좁힌다.
 * 2. 고른 쓰기 범위가 **읽기와 함께** 간다 — 쓰기만 준 토큰은 만들기 전에 찾아보는
 *    일(resolve)이 막혀 쓸모가 없다.
 * 3. 목록에 **범위가 보인다** — 폐기할지 판단할 근거가 이름과 이것뿐이다.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'

const get = vi.fn()
const post = vi.fn(async (_path: string, _body?: unknown) => ({ token: 'tsp_평문한번' }))

vi.mock('@/shared/api/client', () => ({
  api: {
    get: (path: string) => get(path),
    post: (path: string, body?: unknown) => post(path, body),
    patch: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
  downloadFile: vi.fn(),
  ApiError: class extends Error {},
}))

vi.mock('@/shared/auth/AuthContext', () => ({
  useAuth: () => ({
    user: { display_name: '한 사람', email: 'one@testscope.local' },
    reload: vi.fn(),
  }),
}))

const { default: ProfilePage } = await import('@/modules/auth/ProfilePage')

function serve(scopes: string[]) {
  get.mockImplementation(async () => [
    {
      id: 't1',
      name: '내 MCP',
      prefix: 'tsp_abc',
      scopes,
      created_at: '2026-09-29T00:00:00Z',
      expires_at: null,
      last_used_at: null,
      revoked_at: null,
    },
  ])
}

async function open() {
  await act(async () => {
    render(<ProfilePage />)
  })
}

async function issue(name: string) {
  const input = screen.getByPlaceholderText('토큰 용도') as HTMLInputElement
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      'value',
    )?.set
    setter?.call(input, name)
    input.dispatchEvent(new Event('input', { bubbles: true }))
  })
  await act(async () => {
    screen.getByRole('button', { name: '발급' }).click()
  })
}

afterEach(() => vi.clearAllMocks())

describe('토큰 발급', () => {
  it('아무것도 안 고르면 읽기 전용으로 간다', async () => {
    serve(['read'])
    await open()
    await issue('읽기용')
    expect(post).toHaveBeenCalledWith('/auth/tokens', {
      name: '읽기용',
      scopes: ['read'],
    })
  })

  it('고른 쓰기 범위가 읽기와 함께 간다', async () => {
    serve(['read'])
    await open()
    await act(async () => {
      screen.getByRole('checkbox', { name: /카탈로그 쓰기/ }).click()
    })
    await issue('카탈로그 채우기')
    expect(post).toHaveBeenCalledWith('/auth/tokens', {
      name: '카탈로그 채우기',
      scopes: ['read', 'catalog:write'],
    })
  })

  it('둘 다 고르면 둘 다 간다', async () => {
    serve(['read'])
    await open()
    await act(async () => {
      screen.getByRole('checkbox', { name: /카탈로그 쓰기/ }).click()
      screen.getByRole('checkbox', { name: /장비·시험 쓰기/ }).click()
    })
    await issue('전부')
    expect(post.mock.calls[0][1]).toEqual({
      name: '전부',
      scopes: ['read', 'catalog:write', 'equipment:write'],
    })
  })
})

describe('토큰 목록', () => {
  it('읽기만 있으면 「읽기 전용」 이라고 적는다', async () => {
    serve(['read'])
    await open()
    expect(screen.getByText('읽기 전용')).toBeTruthy()
  })

  it('쓰기가 있으면 무엇을 쓸 수 있는지 적는다', async () => {
    serve(['read', 'catalog:write', 'equipment:write'])
    await open()
    expect(screen.getByText('카탈로그 쓰기 · 장비·시험 쓰기')).toBeTruthy()
  })
})

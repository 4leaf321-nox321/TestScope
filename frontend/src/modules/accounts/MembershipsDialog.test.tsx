/**
 * 소속 바꾸기 창 — **역할을 잃지 않는다.**
 *
 * 계정 목록은 소속을 slug 로만 준다. 그것만 보고 창을 채우면 역할을 모르는 채로 되보내게
 * 되고, 그러면 **부서 관리자가 조용히 멤버로 내려앉는다** — 그 사람은 어제 하던 일을 오늘
 * 못 하면서 왜인지도 모른다. 실제로 그렇게 만들었다가 잡았다(2026-09-28).
 *
 * 그래서 창은 역할까지 따로 받아 오고, **다 받기 전에는 저장을 막는다** — 빈 목록을
 * 보내면 소속을 통째로 지우는 것이 된다.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'

const get = vi.fn()
const put = vi.fn(async (_path: string, _body?: unknown) => ({}))

vi.mock('@/shared/api/client', () => ({
  api: {
    get: (path: string) => get(path),
    post: vi.fn(),
    patch: vi.fn(),
    put: (path: string, body?: unknown) => put(path, body),
    delete: vi.fn(),
  },
  downloadFile: vi.fn(),
  ApiError: class extends Error {},
}))

const { MembershipsDialog } = await import('@/modules/accounts/MembershipsDialog')

const ACCOUNT = {
  id: 'u1',
  display_name: '한 사람',
  memberships: ['lab', 'qa'],
} as never

function serve(mine: { workspace_slug: string; workspace_name: string; role: string }[]) {
  get.mockImplementation(async (path: string) =>
    path.includes('/memberships')
      ? mine
      : [
          { slug: 'lab', name: '신뢰성팀' },
          { slug: 'qa', name: '품질팀' },
          { slug: 'new', name: '새팀' },
        ],
  )
}

async function open() {
  await act(async () => {
    render(<MembershipsDialog account={ACCOUNT} onClose={() => {}} onSaved={() => {}} />)
  })
}

afterEach(() => vi.clearAllMocks())

describe('소속 바꾸기 창', () => {
  it('역할을 읽어 와 그대로 되보낸다 — 관리자가 멤버로 내려앉으면 안 된다', async () => {
    serve([
      { workspace_slug: 'lab', workspace_name: '신뢰성팀', role: 'manager' },
      { workspace_slug: 'qa', workspace_name: '품질팀', role: 'member' },
    ])
    await open()
    // 부서 이름으로 보인다 — slug 는 사람이 쓰는 말이 아니다.
    expect(screen.getByText('신뢰성팀')).toBeTruthy()

    await act(async () => {
      screen.getByRole('button', { name: '저장' }).click()
    })
    expect(put).toHaveBeenCalledWith('/accounts/u1/memberships', {
      items: [
        { workspace_slug: 'lab', role: 'manager' },
        { workspace_slug: 'qa', role: 'member' },
      ],
    })
  })

  it('하나 빼고 저장하면 나머지는 역할까지 그대로 간다', async () => {
    serve([
      { workspace_slug: 'lab', workspace_name: '신뢰성팀', role: 'manager' },
      { workspace_slug: 'qa', workspace_name: '품질팀', role: 'member' },
    ])
    await open()
    await act(async () => {
      screen.getByRole('button', { name: 'qa 빼기' }).click()
    })
    await act(async () => {
      screen.getByRole('button', { name: '저장' }).click()
    })
    expect(put).toHaveBeenCalledWith('/accounts/u1/memberships', {
      items: [{ workspace_slug: 'lab', role: 'manager' }],
    })
  })

  it('다 못 읽었으면 저장이 안 눌린다 — 빈 목록은 소속을 통째로 지운다', async () => {
    // 영영 안 오는 응답.
    get.mockImplementation(() => new Promise(() => {}))
    await open()
    const button = screen.getByRole('button', { name: '저장' }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    expect(screen.getByText(/읽는 중/)).toBeTruthy()
  })
})

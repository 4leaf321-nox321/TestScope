/**
 * 시스템 관리자 임명 — **화면이 시키는 일을 화면에서 할 수 있어야 한다.**
 *
 * 이 화면은 관리자가 하나뿐이면 「한 명 더 지정해 두십시오」 라고 띄운다. 그런데 지정할
 * 자리가 없었다 — 서버에는 `POST /accounts/{id}/system-admin` 이 있고 API 클라이언트에도
 * `setSystemAdmin` 이 있는데 아무도 부르지 않았다(2026-09-29). 읽은 사람은 서버 콘솔을
 * 찾아보다 그만둔다.
 *
 * 여기서 지키는 것:
 *
 * 1. 지정·해제 단추가 **있고**, 누르면 그 계정에 대해 불린다.
 * 2. 권한을 넓히는 쪽은 **한 번 묻는다** — 취소하면 아무 일도 안 일어난다.
 * 3. **마지막 한 명은 해제를 못 누른다.** 서버도 거절하지만, 눌러 보고 오류를 읽는 것과
 *    못 누르는 것은 다르다 — 그 계정이 잠기면 복구가 서버 콘솔뿐이다.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const setSystemAdmin = vi.fn(async (_id: string, _grant: boolean) => ({}))
const list = vi.fn()
const summary = vi.fn()

vi.mock('@/modules/accounts/api', () => ({
  accountApi: {
    summary: () => summary(),
    list: () => list(),
    approve: vi.fn(),
    reject: vi.fn(),
    suspend: vi.fn(),
    activate: vi.fn(),
    resetPassword: vi.fn(),
    setSystemAdmin: (id: string, grant: boolean) => setSystemAdmin(id, grant),
  },
}))

// 소속 창은 이 시험이 보려는 것이 아니다 — 제 API 를 또 부르므로 갈아 끼운다.
vi.mock('@/modules/accounts/MembershipsDialog', () => ({
  MembershipsDialog: () => null,
}))

const { default: AccountsAdminPage } = await import('@/modules/accounts/AccountsAdminPage')

function account(over: Record<string, unknown> = {}) {
  return {
    id: 'u1',
    email: 'one@testscope.local',
    display_name: '한 사람',
    status: 'active',
    is_system_admin: false,
    memberships: ['lab'],
    requested_workspace_slug: null,
    created_at: '2026-09-29T00:00:00Z',
    decided_at: null,
    ...over,
  }
}

async function show(rows: ReturnType<typeof account>[], admins: number) {
  list.mockResolvedValue(rows)
  summary.mockResolvedValue({ active_system_admins: admins })
  await act(async () => {
    render(
      <MemoryRouter>
        <AccountsAdminPage />
      </MemoryRouter>,
    )
  })
}

afterEach(() => {
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

describe('시스템 관리자 임명', () => {
  it('지정 단추를 누르면 그 계정에 대해 불린다', async () => {
    vi.stubGlobal('confirm', () => true)
    await show([account()], 2)
    await act(async () => {
      screen.getByRole('button', { name: '관리자 지정' }).click()
    })
    expect(setSystemAdmin).toHaveBeenCalledWith('u1', true)
  })

  it('묻는 말에 아니오면 아무 일도 안 일어난다', async () => {
    vi.stubGlobal('confirm', () => false)
    await show([account()], 2)
    await act(async () => {
      screen.getByRole('button', { name: '관리자 지정' }).click()
    })
    expect(setSystemAdmin).not.toHaveBeenCalled()
  })

  it('이미 관리자면 해제로 보이고, 해제로 불린다', async () => {
    vi.stubGlobal('confirm', () => true)
    await show([account({ is_system_admin: true })], 2)
    await act(async () => {
      screen.getByRole('button', { name: '관리자 해제' }).click()
    })
    expect(setSystemAdmin).toHaveBeenCalledWith('u1', false)
  })

  it('**마지막 한 명은 해제를 못 누른다** — 잠기면 복구가 서버 콘솔뿐이다', async () => {
    await show([account({ is_system_admin: true })], 1)
    const button = screen.getByRole('button', { name: '관리자 해제' }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    expect(button.getAttribute('title')).toContain('마지막 시스템 관리자')
  })

  it('승인 대기 계정에는 안 보인다 — 먼저 승인이다', async () => {
    await show([account({ status: 'pending' })], 2)
    expect(screen.queryByRole('button', { name: '관리자 지정' })).toBeNull()
    expect(screen.getByRole('button', { name: '승인' })).toBeTruthy()
  })
})

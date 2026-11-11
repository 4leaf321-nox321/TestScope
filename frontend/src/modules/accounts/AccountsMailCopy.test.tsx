/**
 * 메일 주소 복사 — **여러 사람에게 한 번에 메일을 쓰려고.** 사내 배포는 평문 http 다.
 *
 * 여기서 지키는 것:
 *
 * 1. 고른 계정의 주소가 `; ` 로 이어져 클립보드에 간다 — Outlook 의 받는 사람 칸이 그대로
 *    가른다.
 * 2. **평문 http 에서도 간다.** 표준 API(`navigator.clipboard`)가 없어 옛 길(`execCommand`)로
 *    가는데, 그 길은 사용자가 **누른 그 순간**에만 허락된다 — 누르는 동안에 불려야 한다.
 * 3. 메일 형식이 아닌 아이디(`admin`)는 빼고, **뺐다고 말한다.**
 * 4. 브라우저가 막으면 손으로 복사할 칸이 뜬다 — 조용히 실패하면 사람은 복사된 줄 알고
 *    클립보드에 남아 있던 옛 글자를 붙인다.
 * 5. 51번째 계정도 고를 수 있다 — 서버는 한 번에 50명(기본)·100명(상한)까지만 준다.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const list = vi.fn()

vi.mock('@/modules/accounts/api', () => ({
  accountApi: {
    summary: async () => ({ active_system_admins: 2, pending: 0 }),
    list: (...args: unknown[]) => list(...args),
    approve: vi.fn(),
    reject: vi.fn(),
    suspend: vi.fn(),
    activate: vi.fn(),
    resetPassword: vi.fn(),
    setSystemAdmin: vi.fn(),
  },
}))

vi.mock('@/modules/accounts/MembershipsDialog', () => ({
  MembershipsDialog: () => null,
}))

const { default: AccountsAdminPage } = await import('@/modules/accounts/AccountsAdminPage')

function account(id: string, email: string) {
  return {
    id,
    email,
    display_name: id,
    status: 'active',
    is_system_admin: false,
    memberships: ['lab'],
    requested_workspace_slug: null,
    created_at: '2026-11-11T00:00:00Z',
    decided_at: null,
  }
}

/** 복사로 간 글자. 옛 길은 화면 밖 칸에 글자를 담아 고른 뒤 `copy` 를 부른다. */
let copiedText: string[] = []
let allowCopy = true

beforeEach(() => {
  // **여기가 사내 배포다** — 평문 http 라 보안 문맥이 아니다.
  Object.defineProperty(window, 'isSecureContext', { value: false, configurable: true })
  copiedText = []
  allowCopy = true
  document.execCommand = vi.fn((command: string) => {
    if (command === 'copy') {
      const box = document.querySelector<HTMLTextAreaElement>('textarea[readonly]')
      copiedText.push(box?.value ?? '')
    }
    return allowCopy
  }) as unknown as typeof document.execCommand
})

afterEach(() => {
  vi.clearAllMocks()
})

async function show(rows: ReturnType<typeof account>[]) {
  list.mockResolvedValue(rows)
  await act(async () => {
    render(
      <MemoryRouter>
        <AccountsAdminPage />
      </MemoryRouter>,
    )
  })
}

async function tick(name: string) {
  await act(async () => {
    screen.getByRole('checkbox', { name }).click()
  })
}

async function copy() {
  await act(async () => {
    screen.getByRole('button', { name: /메일 주소 복사/ }).click()
  })
}

describe('메일 주소 복사', () => {
  it('고른 계정의 주소를 「; 」 로 이어 복사한다', async () => {
    await show([
      account('u1', 'one@corp.local'),
      account('u2', 'two@corp.local'),
      account('u3', 'three@corp.local'),
    ])
    await tick('one@corp.local 선택')
    await tick('three@corp.local 선택')
    await copy()
    expect(copiedText).toEqual(['one@corp.local; three@corp.local'])
    expect(screen.getByText(/메일 주소 2개 복사함/)).toBeTruthy()
  })

  it('**누르는 그 순간에 복사한다** — 평문 http 의 옛 길은 한 박자 늦으면 거절된다', async () => {
    await show([account('u1', 'one@corp.local')])
    await tick('one@corp.local 선택')
    // act 를 기다리지 않는다 — 누른 동안(같은 이벤트 안)에 이미 불렸어야 한다.
    act(() => {
      screen.getByRole('button', { name: /메일 주소 복사/ }).click()
    })
    expect(document.execCommand).toHaveBeenCalledWith('copy')
    expect(copiedText).toEqual(['one@corp.local'])
    await act(async () => {})
  })

  it('전체 선택은 전부를 고른다', async () => {
    await show([account('u1', 'one@corp.local'), account('u2', 'two@corp.local')])
    await tick('전체 선택')
    await copy()
    expect(copiedText).toEqual(['one@corp.local; two@corp.local'])
  })

  it('메일 형식이 아닌 아이디는 빼고, 뺐다고 말한다', async () => {
    await show([account('u1', 'admin'), account('u2', 'two@corp.local')])
    await tick('전체 선택')
    await copy()
    expect(copiedText).toEqual(['two@corp.local'])
    expect(screen.getByText(/메일 형식이 아닌 아이디 1개 제외: admin/)).toBeTruthy()
  })

  it('고른 것이 모두 메일 형식이 아니면 복사하지 않고 그렇게 말한다', async () => {
    await show([account('u1', 'admin')])
    await tick('admin 선택')
    await copy()
    expect(document.execCommand).not.toHaveBeenCalled()
    expect(screen.getByText(/복사할 메일 주소 없음.*admin/)).toBeTruthy()
  })

  it('브라우저가 막으면 손으로 복사할 칸이 뜬다', async () => {
    allowCopy = false
    await show([account('u1', 'one@corp.local'), account('u2', 'two@corp.local')])
    await tick('전체 선택')
    await copy()
    expect(screen.getByText(/브라우저가 복사를 막음/)).toBeTruthy()
    const box = screen.getByRole('textbox', {
      name: '복사할 메일 주소',
    }) as HTMLTextAreaElement
    expect(box.value).toBe('one@corp.local; two@corp.local')
  })

  it('고른 것이 없으면 단추가 꺼져 있다', async () => {
    await show([account('u1', 'one@corp.local')])
    const button = screen.getByRole('button', { name: /메일 주소 복사/ }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
  })

  it('51번째 계정도 나온다 — 쪽을 끝까지 받는다', async () => {
    const first = Array.from({ length: 100 }, (_, index) =>
      account(`u${index}`, `p${index}@corp.local`),
    )
    list
      .mockResolvedValueOnce(first)
      .mockResolvedValueOnce([account('u100', 'last@corp.local')])
    await act(async () => {
      render(
        <MemoryRouter>
          <AccountsAdminPage />
        </MemoryRouter>,
      )
    })
    expect(list).toHaveBeenNthCalledWith(1, undefined, 100, 0)
    expect(list).toHaveBeenNthCalledWith(2, undefined, 100, 100)
    expect(screen.getByRole('checkbox', { name: 'last@corp.local 선택' })).toBeTruthy()
  })
})

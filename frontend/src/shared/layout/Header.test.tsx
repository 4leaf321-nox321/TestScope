/**
 * 상단 바의 부서 — **고를 것이 없으면 고르는 물건을 두지 않는다.**
 *
 * 그리고 이것이 바꾸는 것은 부서 홈과 부서 멤버 **둘뿐**이다. 상단에 있으니 「지금 이 부서
 * 안에 있다」 로 읽히기 쉬운데(다른 시스템의 맥락 전환기가 그렇다), 장비·시험 목록은 부서와
 * 무관하게 전부 보인다 — 목록이 걸러지는 줄 알고 보면 「우리 부서 장비가 왜 이렇게 많지」 가
 * 된다. 그래서 무엇이 바뀌는지 적어 둔다.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const user = vi.fn()

vi.mock('@/shared/auth/AuthContext', () => ({
  useAuth: () => ({ user: user(), logout: vi.fn() }),
}))

vi.mock('@/shared/layout/NotificationBell', () => ({
  NotificationBell: () => null,
}))

vi.mock('@/shared/layout/SidePanel', () => ({
  useLeftPanel: () => ({ has: false, open: vi.fn() }),
}))

// 테마는 이 시험이 보려는 것이 아니다 — 공급자를 감싸는 대신 갈아 끼운다.
vi.mock('@/shared/theme/ThemeProvider', () => ({
  useTheme: () => ({ theme: 'light', toggle: vi.fn(), setTheme: vi.fn() }),
}))

const { Header } = await import('@/shared/layout/Header')

function member(slug: string, path: string) {
  return { slug, name: path, path, role: 'member' }
}

async function show(memberships: ReturnType<typeof member>[]) {
  user.mockReturnValue({
    display_name: '한 사람',
    email: 'one@testscope.local',
    memberships,
    is_system_admin: false,
  })
  await act(async () => {
    render(
      <MemoryRouter>
        <Header onToggleSidebar={() => {}} workspaceSlug={memberships[0]?.slug ?? 'hq'} />
      </MemoryRouter>,
    )
  })
}

afterEach(() => vi.clearAllMocks())

describe('상단 바의 부서', () => {
  it('소속이 하나면 이름만 — 고를 것이 없다', async () => {
    await show([member('lab', '연구소 / 신뢰성팀')])
    expect(screen.getByText('연구소 / 신뢰성팀')).toBeTruthy()
    expect(screen.queryByLabelText('부서 홈·멤버를 볼 부서')).toBeNull()
  })

  it('둘 이상이면 고를 수 있고, **무엇이 바뀌는지** 적혀 있다', async () => {
    await show([member('lab', '연구소 / 신뢰성팀'), member('qa', '품질본부 / 품질팀')])
    const picker = screen.getByLabelText('부서 홈·멤버를 볼 부서')
    expect(picker).toBeTruthy()
    // 상단에 있으면 「이 부서 안에 있다」 로 읽힌다 — 그렇지 않다고 말해 둔다.
    expect(picker.getAttribute('title')).toContain('부서 홈과 부서 멤버')
    expect(picker.getAttribute('title')).toContain('장비·시험 목록은 부서와 무관')
  })

  it('소속이 없으면 그렇게 말한다', async () => {
    await show([])
    expect(screen.getByText('소속된 부서가 없습니다')).toBeTruthy()
  })
})

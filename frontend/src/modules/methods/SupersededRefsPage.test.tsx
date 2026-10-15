/**
 * 대체된 규격을 가리키는 곳 — **옛 판마다 묶이고, 새 판과 고칠 화면으로 간다.**
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const fetched: string[] = []

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (url: string) => {
      fetched.push(url)
      return [
        {
          kind: 'reliability_test',
          target_id: 'r1',
          target_label: '인장 상온',
          owner: 'MX',
          owner_id: 'd1',
          detail: '참조 규격',
          link: '/reliability-tests/mx?name=%EC%9D%B8%EC%9E%A5',
          method_id: 'm-old',
          method_label: 'ASTM D638 2014',
          successor_id: 'm-new',
          successor_label: 'ASTM D638 2022',
        },
        {
          kind: 'equipment',
          target_id: 'e1',
          target_label: 'UTM-01 만능시험기',
          owner: '시험팀',
          owner_id: 'w1',
          detail: '인장',
          link: '/equipment/e1',
          method_id: 'm-old',
          method_label: 'ASTM D638 2014',
          successor_id: 'm-new',
          successor_label: 'ASTM D638 2022',
        },
      ]
    }),
  },
  ApiError: class extends Error {},
}))

vi.mock('@/shared/auth/AuthContext', () => ({
  useAuth: () => ({ user: { memberships: [], is_system_admin: false } }),
}))

import SupersededRefsPage from '@/modules/methods/SupersededRefsPage'

beforeEach(() => {
  fetched.length = 0
})

describe('대체된 규격을 가리키는 곳', () => {
  it('옛 판마다 묶고 새 판과 고칠 화면으로 잇는다', async () => {
    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/methods/superseded-refs']}>
          <Routes>
            <Route path="/methods/superseded-refs" element={<SupersededRefsPage />} />
          </Routes>
        </MemoryRouter>,
      )
    })
    expect(screen.getByRole('link', { name: 'ASTM D638 2014' }).getAttribute('href')).toBe(
      '/methods/m-old',
    )
    expect(screen.getByRole('link', { name: 'ASTM D638 2022' }).getAttribute('href')).toBe(
      '/methods/m-new',
    )
    expect(screen.getByText('2곳')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'UTM-01 만능시험기' }).getAttribute('href')).toBe(
      '/equipment/e1',
    )
    expect(fetched).toEqual(['/methods/superseded-refs'])

    // 시스템 관리자가 아니면 기본은 내 소속 — 체크하면 전부.
    await act(async () => {
      fireEvent.click(screen.getByLabelText('다른 부서 것도 보기'))
    })
    expect(fetched).toContain('/methods/superseded-refs?all=true')
  })
})

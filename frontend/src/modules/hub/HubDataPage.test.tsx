/**
 * 허브 기준정보 — **타입마다 받은 객체를 보고, 참조는 이름으로, 관계까지 연다.**
 */

import { describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const fetched: string[] = []

const item = {
  key: 'SM-X100',
  label: 'SM-X100',
  status: 'active',
  state: 'active',
  merged_into: null,
  previous_keys: ['SM-X100A'],
  properties: { task: 'T-0012', series: 'X1' },
  references: { 'T-0012': '과제 12' },
  hub_updated_at: '2026-10-21T00:00:00.000000Z',
  received_at: '2026-10-21T00:00:00Z',
  term_id: 't1',
}

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (url: string) => {
      fetched.push(url)
      if (url === '/hub/types')
        return [
          {
            slug: 'plm_model',
            label: '개발모델',
            axis_slug: 'hub_plm_model',
            active: 1,
            total: 1,
            last_received_at: null,
          },
        ]
      if (url.startsWith('/hub/types/plm_model/items/'))
        return {
          ...item,
          outgoing: [
            {
              src: 'SM-X100',
              relation: 'plm_derived_from',
              dst: 'SM-X090',
              dst_type: 'plm_model',
              dst_label: 'SM-X090',
              deleted: false,
            },
          ],
          incoming: [],
        }
      if (url.startsWith('/hub/types/plm_model/items')) return { items: [item], total: 1 }
      return []
    }),
  },
  ApiError: class extends Error {},
}))

import HubDataPage from '@/modules/hub/HubDataPage'

describe('허브 기준정보', () => {
  it('받은 객체를 보이고 참조를 이름으로 풀고 관계를 연다', async () => {
    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/hub']}>
          <HubDataPage />
        </MemoryRouter>,
      )
    })
    expect(fetched.some((url) => url.startsWith('/hub/types/plm_model/items?'))).toBe(true)
    expect(screen.getByText(/task: 과제 12 \(T-0012\)/)).toBeTruthy()
    await act(async () => {
      // 식별자와 이름이 같은 객체 — 식별자 칸(첫 칸)을 누른다.
      fireEvent.click(screen.getAllByText('SM-X100', { selector: 'td' })[0])
    })
    expect(screen.getByText(/plm_derived_from → SM-X090/)).toBeTruthy()
    expect(screen.getByText('SM-X100A')).toBeTruthy()
  })
})

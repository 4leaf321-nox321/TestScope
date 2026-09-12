/**
 * 상세 옆 목록 — **뒤로 가지 않고 옆 것으로 건너뛴다.**
 *
 * 실사용에서 나왔다: 기종을 하나 열면 옆 기종을 보는 길이 브라우저 뒤로 가기뿐이었다.
 *
 * 여기서 지키는 것 — 거르기는 서버가 한다 · 지금 보는 줄이 표시된다 · 거르기가 그 줄을
 * 밀어내면 그렇다고 말한다(안 그러면 「목록에 없다」 로 읽힌다).
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const calls: string[] = []
let items = [
  { id: 'm1', name: 'DV3T LV', series_name: 'Brookfield DV3T', maker: 'Brookfield' },
  { id: 'm2', name: 'DV3T RV', series_name: 'Brookfield DV3T', maker: 'Brookfield' },
]

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (url: string) => {
      calls.push(url)
      return { items, total: items.length, limit: 50, offset: 0 }
    }),
  },
  ApiError: class extends Error {},
}))

import { LeftPanelHost, LeftPanelProvider } from '@/shared/layout/SidePanel'
import { RecordListPanel } from '@/modules/equipment/RecordListPanel'

async function open(currentId: string) {
  await act(async () => {
    render(
      <MemoryRouter>
        <LeftPanelProvider>
          <LeftPanelHost />
          <RecordListPanel kind="model" currentId={currentId} />
        </LeftPanelProvider>
      </MemoryRouter>,
    )
  })
  // 글자마다 요청하지 않으려고 250ms 기다린다 — 그 시간을 넘긴다.
  await act(async () => {
    vi.advanceTimersByTime(300)
  })
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  calls.length = 0
  items = [
    { id: 'm1', name: 'DV3T LV', series_name: 'Brookfield DV3T', maker: 'Brookfield' },
    { id: 'm2', name: 'DV3T RV', series_name: 'Brookfield DV3T', maker: 'Brookfield' },
  ]
})

describe('상세 옆 목록', () => {
  it('옆 것으로 건너뛸 링크를 준다', async () => {
    await open('m1')
    const link = screen.getByText('DV3T RV').closest('a')
    expect(link?.getAttribute('href')).toBe('/catalog/equipment-models/m2')
  })

  it('지금 보는 줄을 표시한다', async () => {
    await open('m1')
    const here = screen.getByText('DV3T LV').closest('a')
    // 자기 자리를 못 찾으면 옆 것으로 옮겨 갈 수가 없다.
    expect(here?.getAttribute('aria-current')).toBe('page')
  })

  it('찾기는 서버로 간다', async () => {
    await open('m1')
    await act(async () => {
      fireEvent.change(screen.getByLabelText('장비 기종 찾기'), { target: { value: 'RV' } })
    })
    await act(async () => {
      vi.advanceTimersByTime(300)
    })
    // 받아 놓고 화면에서 거르면 50건을 넘는 순간 뒤엣것이 없는 것처럼 보인다.
    expect(calls.some((one) => one.includes('q=RV'))).toBe(true)
  })

  it('거르기가 지금 보는 것을 밀어내면 그렇다고 말한다', async () => {
    await open('m9')
    expect(screen.getByText(/이 거르기에 안 걸립니다/)).toBeTruthy()
  })
})

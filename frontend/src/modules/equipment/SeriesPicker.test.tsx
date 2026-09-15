/**
 * 계열 피커 — **서버가 거르고, 잘린 것을 말한다.**
 *
 * 계열 265개를 200개씩 받아 Select 에 넣으면 65개가 조용히 안 보인다. 타이핑이 서버로
 * 가는지, 그리고 상한을 넘으면 「N건 중 M건」 이라고 말하는지를 본다.
 */

import { describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'

const calls: string[] = []

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (url: string) => {
      calls.push(url)
      return {
        items: [
          {
            id: 's1',
            name: '6800 Series',
            name_ko: '인스트론 6800 시리즈',
            maker: 'Instron',
            category: '만능재료시험기',
            kind: 'main',
            model_count: 10,
          },
        ],
        total: 265,
        limit: 50,
        offset: 0,
      }
    }),
  },
  ApiError: class extends Error {},
}))

import { SeriesPicker } from '@/modules/equipment/SeriesPicker'

describe('계열 피커', () => {
  it('타이핑이 서버로 가고, 잘린 만큼을 말한다', async () => {
    const onChange = vi.fn()
    render(<SeriesPicker value="" onChange={onChange} />)
    await act(async () => {
      screen.getByRole('button', { name: /계열 선택/ }).click()
    })
    // 줄에는 무엇으로 구별하는지가 보인다 — 이름만으로는 본체와 부속 계열이 안 갈린다.
    expect(screen.getByText('Instron · 만능재료시험기 · 본체')).toBeTruthy()
    expect(screen.getByText('기종 10')).toBeTruthy()
    // **잘렸으면 말한다.** 안 말하면 「카탈로그에 없구나」 가 된다.
    expect(screen.getByText('265건 중 1건. 더 자세히 입력하세요.')).toBeTruthy()

    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('계열명·한글명 또는 제조사'), {
        target: { value: '6800' },
      })
      await new Promise((resolve) => setTimeout(resolve, 300))
    })
    expect(calls.some((url) => url.includes('q=6800'))).toBe(true)

    await act(async () => {
      screen.getByText('인스트론 6800 시리즈').click()
    })
    expect(onChange).toHaveBeenCalledWith('s1', expect.objectContaining({ id: 's1' }))
  })
})

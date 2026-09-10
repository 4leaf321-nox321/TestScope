/**
 * 장비 찾기의 **시험 항목 고르기.**
 *
 * 87종을 드롭다운에 접어 두면 두 가지를 잃는다: 찾기 어렵고, 무엇보다 **무엇을 물을
 * 수 있는지 자체를 모른다.** 이 화면에 처음 온 사람에게 그 목록이 곧 「이 시스템에
 * 무엇을 물을 수 있나」 다.
 *
 * 여기서 지키는 것 셋 — 다 보인다 · 다시 누르면 풀린다 · 칠 수도 있다.
 */

import { describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const ITEMS = [
  { id: 't1', value: '인장', usage_count: 42 },
  { id: 't2', value: '압축', usage_count: 7 },
  // 쓰이는 데가 없는 항목. **지우지 않는다** — 카탈로그에 없을 뿐이다.
  { id: 't3', value: '마모', usage_count: 0 },
]

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (url: string) => {
      if (url.includes('/condition-keys')) return []
      if (url.includes('/terms')) return ITEMS
      return []
    }),
    post: vi.fn(),
  },
  ApiError: class extends Error {},
}))

import SearchPage from '@/modules/search/SearchPage'

async function open() {
  await act(async () => {
    render(
      <MemoryRouter>
        <SearchPage />
      </MemoryRouter>,
    )
  })
}

function chip(label: string): HTMLButtonElement {
  return screen.getByRole('button', { name: label }) as HTMLButtonElement
}

describe('시험 항목 고르기', () => {
  it('항목이 전부 펼쳐진다', async () => {
    await open()
    for (const one of ITEMS) {
      expect(chip(one.value)).toBeTruthy()
    }
    // 「전체」 도 고를 수 있는 하나다 — 고른 것을 지우는 자리가 눈에 보여야 한다.
    expect(chip('전체')).toBeTruthy()
  })

  it('다시 누르면 풀린다', async () => {
    await open()
    const picked = chip('인장')
    await act(async () => picked.click())
    expect(chip('인장').className).toContain('bg-primary')

    await act(async () => chip('인장').click())
    // 풀렸으면 「전체」 가 다시 골라진 상태다.
    expect(chip('인장').className).not.toContain('bg-primary')
    expect(chip('전체').className).toContain('bg-primary')
  })

  it('쓰이는 항목이 앞에 온다', async () => {
    await open()
    const labels = screen
      .getAllByRole('button')
      .map((one) => one.textContent ?? '')
      .filter((one) => ITEMS.some((item) => item.value === one))
    expect(labels).toEqual(['인장', '압축', '마모'])
  })
})

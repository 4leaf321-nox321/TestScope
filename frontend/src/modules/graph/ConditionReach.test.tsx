/**
 * 조건 축의 쓰임 — **온톨로지와 검색 사이의 다리.**
 *
 * 그래프는 「어느 축을 거는가」 까지 답한다. 「값이 얼마인가」 는 검색이 답하는데, 그
 * 경계가 화면 어디에도 없어서 읽는 사람은 여기서 막히고 이 플랫폼이 그걸 못 한다고 읽었다.
 *
 * 여기서 지키는 것:
 *
 * 1. 몇 건이고 어디까지 쓰이나를 말한다.
 * 2. **구간을 안 나눈다** — 임의 경계는 없는 것보다 나쁘다.
 * 3. 좁히는 자리로 **넘긴다**(`attr` 은 축 id 가 아니라 칸의 key 를 받는다).
 * 4. 조용히 빼지 않는다 — 단위를 못 바꿔 범위에서 빠진 수를 말한다.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const get = vi.fn()

vi.mock('@/shared/api/client', () => ({
  api: { get, post: vi.fn(), patch: vi.fn(), delete: vi.fn(), upload: vi.fn() },
  ApiError: class extends Error {},
}))

const { ConditionReach } = await import('@/modules/graph/ConditionReach')

function answer(over: Record<string, unknown> = {}) {
  return {
    condition_key_id: 'c1',
    label: '시험 온도',
    display_unit: 'degC',
    definitions: [{ id: 'd1', key: 'reliability_temperature', label: '시험 온도' }],
    test_count: 14,
    valued_count: 11,
    unconvertible_count: 0,
    low: -55,
    high: 150,
    ...over,
  }
}

async function show(body: Record<string, unknown>) {
  get.mockResolvedValue(body)
  await act(async () => {
    render(
      <MemoryRouter>
        <ConditionReach nodeId="condition_key:c1" />
      </MemoryRouter>,
    )
  })
}

afterEach(() => vi.clearAllMocks())

describe('조건 축의 쓰임', () => {
  it('노드 id 에서 uuid 만 떼어 부른다', async () => {
    await show(answer())
    expect(get).toHaveBeenCalledWith('/condition-keys/c1/reach')
  })

  it('몇 건이고 어디까지인지 말하고, 구간은 안 나눈다', async () => {
    await show(answer())
    expect(screen.getByText('14건')).toBeTruthy()
    expect(screen.getByText(/-55 ~ 150 degC/)).toBeTruthy()
    // **칸만 꺼내 놓고 안 채운 것**이 보여야 「이만큼 쓰인다」 로 안 읽힌다.
    expect(screen.getByText(/3건은 칸만 있고 값이 없습니다/)).toBeTruthy()
    // 구간은 없다 — 있으면 읽는 사람이 그 경계에 뜻이 있다고 믿는다.
    expect(screen.queryByText(/이하/)).toBeNull()
  })

  it('값으로 좁히는 자리로 넘긴다 — 축 id 가 아니라 칸의 key 로', async () => {
    await show(answer())
    const link = screen.getByRole('link', { name: /값으로 좁히기/ })
    expect(link.getAttribute('href')).toBe('/reliability-tests?attr=reliability_temperature*')
  })

  it('단위를 못 바꿔 빠진 것을 말한다 — 조용히 빼지 않는다', async () => {
    await show(answer({ unconvertible_count: 2 }))
    expect(screen.getByText(/빠진 시험 2건/)).toBeTruthy()
  })

  it('적는 칸이 없으면 그 사실만 말한다', async () => {
    await show(
      answer({ definitions: [], test_count: 0, valued_count: 0, low: null, high: null }),
    )
    expect(screen.getByText(/적는 칸이 아직 없습니다/)).toBeTruthy()
    expect(screen.queryByRole('link', { name: /값으로 좁히기/ })).toBeNull()
  })

  it('아직 아무도 안 걸었으면 0 으로 선다 — 「없다」 가 아니다', async () => {
    await show(answer({ test_count: 0, valued_count: 0, low: null, high: null }))
    // 두 줄(거는 시험 · 값이 적힌 것)이 다 0 이다.
    expect(screen.getAllByText('0건').length).toBe(2)
    expect(screen.queryByText(/적힌 값의 범위/)).toBeNull()
  })
})

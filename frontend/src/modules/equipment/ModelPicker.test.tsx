/**
 * 기종 피커 — **크기가 안 변한다.**
 *
 * 줄 수나 모드에 따라 창이 뛰면 누르려던 줄이 손가락 아래에서 옮겨 간다. 머리 줄과
 * 목록과 바닥 줄의 키를 못 박아 두는 이유가 그것이다.
 */

import { describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (url: string) => {
      if (url.startsWith('/equipment-series')) {
        return {
          items: [
            {
              id: 's1',
              name: '6800 Series',
              name_ko: '인스트론 6800 시리즈',
              maker: 'Instron',
              category: '만능재료시험기',
              model_count: 10,
            },
          ],
          total: 1,
          limit: 50,
          offset: 0,
        }
      }
      return {
        items: [
          {
            id: 'm1',
            name: '68FM-300',
            series_id: 's1',
            series_name: '6800 Series',
            maker: 'Instron',
            form_factor: 'floor',
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      }
    }),
  },
  ApiError: class extends Error {},
}))

import { ModelPicker } from '@/modules/equipment/ModelPicker'

async function openPicker() {
  render(<ModelPicker value="" onChange={() => {}} />)
  await act(async () => {
    screen.getByRole('button', { name: /카탈로그에서 찾기/ }).click()
  })
  return document.querySelector('[data-slot="popover-content"]') as HTMLElement
}

/** 키를 정하는 세 줄. **셋 다 못 박혀 있어야** 창이 안 뛴다. */
function shape(root: ParentNode) {
  return {
    head: root.querySelector('.h-11') !== null,
    list: root.querySelector('ul.h-72') !== null,
    foot: root.querySelector('p.h-9') !== null,
  }
}

describe('기종 피커', () => {
  it('두 모드에서 창의 뼈대가 같다', async () => {
    const content = await openPicker()
    expect(shape(content)).toEqual({ head: true, list: true, foot: true })

    // 「계열부터 고르기」 로 바꿔도 같은 뼈대여야 한다 — 여기서 키가 바뀌면
    // 모드를 오갈 때마다 창이 뛴다.
    await act(async () => {
      screen.getByRole('button', { name: '계열부터 선택' }).click()
    })
    expect(shape(content)).toEqual({ head: true, list: true, foot: true })
  })

  it('계열로 좁혀도 뼈대가 같고, 무엇으로 좁혔는지 보인다', async () => {
    const content = await openPicker()
    await act(async () => {
      screen.getByRole('button', { name: '계열부터 선택' }).click()
    })
    await act(async () => {
      screen.getByRole('button', { name: /인스트론 6800 시리즈/ }).click()
    })

    expect(shape(content)).toEqual({ head: true, list: true, foot: true })
    // **무엇으로 좁혔는지 보이고 한 번에 풀린다** — 안 보이면 목록이 짧은 것을
    // 「카탈로그에 없다」 로 읽는다.
    expect(screen.getByRole('button', { name: /해제/ })).toBeInTheDocument()
  })
})

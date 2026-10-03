/**
 * 카탈로그 기종 등록 요청 — **못 고르는 쪽에 말할 자리.**
 *
 * 장비를 등록할 때 카탈로그에 기종이 없으면 비워 두게 되어 있다. 그 안내는 맞지만(비슷한
 * 기종을 고르면 그 장비의 하중·온도가 남의 것이 된다), 비워 둔 다음에 **왜 비었는지가
 * 아무 데도 안 남았다.**
 *
 * 여기서 지키는 것:
 *
 * 1. 등록 창에서 **장비를 만든 뒤에** 요청이 간다 — 요청은 그 장비에 붙는 것이라 id 가
 *    있어야 한다.
 * 2. 모델명을 안 적으면 **켤 수 없다** — 무엇을 세워 달라는 것인지가 요청의 전부다.
 * 3. 기종을 고른 장비에는 안 보낸다 — 카탈로그에 있는 것을 또 세워 달라고 하는 셈이다.
 * 4. 검토 화면은 같은 기종을 **한 줄로** 세우고, 세우면 요청한 장비 전부가 이어진다.
 * 5. 계열을 안 고르면 「세우기」 가 안 눌린다 — 기종은 계열 아래에만 선다(ADR 0006).
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const get = vi.fn()
const post = vi.fn()
const patch = vi.fn()

vi.mock('@/shared/api/client', () => ({
  api: { get, post, patch, delete: vi.fn(), upload: vi.fn() },
  ApiError: class extends Error {},
}))

vi.mock('@/shared/auth/AuthContext', () => ({
  useAuth: () => ({ user: { is_system_admin: true, memberships: [] } }),
}))

const { EquipmentDialog } = await import('@/modules/equipment/EquipmentDialog')
const { default: ModelProposalsPage } = await import('@/modules/equipment/ModelProposalsPage')

const TERM = { id: 'term-1', value: '만능시험기', code: null, status: 'active' }

function base(path: string): unknown {
  if (path.startsWith('/vocabularies')) return [TERM]
  if (path.startsWith('/workspaces')) {
    return [{ slug: 'lab', name: '분석팀', id: 'ws-1', parent_id: null }]
  }
  if (path.startsWith('/attribute-definitions')) return []
  return []
}

afterEach(() => vi.clearAllMocks())

describe('등록 창의 기종 등록 요청', () => {
  async function open() {
    get.mockImplementation(async (path: string) => base(path))
    post.mockResolvedValue({ id: 'eq-1' })
    await act(async () => {
      render(
        <MemoryRouter>
          <EquipmentDialog open onClose={() => undefined} onSaved={() => undefined} />
        </MemoryRouter>,
      )
    })
  }

  function type(label: string, value: string) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } })
  }

  it('모델명을 적어야 켤 수 있다 — 무엇을 세워 달라는 것인지가 요청의 전부다', async () => {
    await open()
    const box = screen.getByRole('checkbox', { name: /카탈로그 기종 등록 요청/ })
    expect((box as HTMLInputElement).disabled).toBe(true)
    await act(async () => {
      type('모델명', '68FM-300')
    })
    expect((box as HTMLInputElement).disabled).toBe(false)
  })

  it('장비를 만든 다음에 요청이 간다 — 요청은 그 장비에 붙는다', async () => {
    await open()
    await act(async () => {
      type('자산번호', 'EQ-1')
      type('장비 이름', '만능기')
      type('설치 위치', '3동')
      type('제조사', 'Instron')
      type('모델명', '68FM-300')
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('checkbox', { name: /카탈로그 기종 등록 요청/ }))
    })
    await act(async () => {
      type('기종 등록 요청 사유', '6800 시리즈는 있는데 이 모델만 없음')
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '등록' }))
    })

    const calls = post.mock.calls.map(([path]) => String(path))
    // **순서가 중요하다** — 장비가 먼저 만들어져야 그 id 에 요청을 붙일 수 있다.
    expect(calls[0]).toBe('/equipment')
    expect(calls[1]).toBe('/equipment/eq-1/model-proposals')
    expect(post.mock.calls[1][1]).toEqual({
      model_text: '68FM-300',
      maker_text: 'Instron',
      note: '6800 시리즈는 있는데 이 모델만 없음',
    })
  })

  it('안 켜면 안 보낸다', async () => {
    await open()
    await act(async () => {
      type('자산번호', 'EQ-2')
      type('장비 이름', '만능기')
      type('설치 위치', '3동')
      type('모델명', '자작-1호')
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '등록' }))
    })
    expect(post.mock.calls.map(([path]) => String(path))).toEqual(['/equipment'])
  })
})

describe('기종 등록 요청 검토', () => {
  const GROUP = {
    normalized: 'instron68fm300',
    text: 'Instron 68FM-300',
    count: 2,
    proposals: [
      {
        id: 'p1',
        maker_text: 'Instron',
        model_text: '68FM-300',
        text: 'Instron 68FM-300',
        note: '6800 시리즈는 있는데 이 모델만 없음',
        status: 'open',
        equipment_id: 'eq-1',
        equipment_asset_no: 'EQ-1',
        equipment_name: '만능기',
        model_id: null,
        model_name: null,
        submitted_via: null,
        created_at: '2026-09-30T00:00:00Z',
      },
      {
        id: 'p2',
        maker_text: 'instron',
        model_text: '68fm-300',
        text: 'instron 68fm-300',
        note: null,
        status: 'open',
        equipment_id: 'eq-2',
        equipment_asset_no: 'EQ-2',
        equipment_name: '만능기2',
        model_id: null,
        model_name: null,
        submitted_via: null,
        created_at: '2026-09-30T00:00:00Z',
      },
    ],
  }

  async function show() {
    get.mockImplementation(async (path: string) => {
      if (path.startsWith('/equipment-models/proposals')) return [GROUP]
      if (path.startsWith('/equipment-series')) {
        return {
          items: [{ id: 's-1', name: '6800 시리즈', maker: 'Instron' }],
          total: 1,
          limit: 200,
          offset: 0,
        }
      }
      return []
    })
    post.mockResolvedValue({ status: 'created', decided: 2, linked: 2, failed: [] })
    await act(async () => {
      render(
        <MemoryRouter>
          <ModelProposalsPage />
        </MemoryRouter>,
      )
    })
  }

  it('같은 기종이 한 줄로 서고 요청한 장비가 함께 보인다', async () => {
    await show()
    expect(screen.getByText('Instron 68FM-300')).toBeTruthy()
    expect(screen.getByText(/장비 2대가 요청했습니다/)).toBeTruthy()
    // 표기가 갈린 줄은 **원문을 그대로** 보여 준다 — 판단하는 사람이 라벨을 봐야 한다.
    expect(screen.getByText(/「instron 68fm-300」 로 적힘/)).toBeTruthy()
    expect(screen.getByText(/6800 시리즈는 있는데 이 모델만 없음/)).toBeTruthy()
  })

  it('계열을 안 고르면 세울 수 없다 — 기종은 계열 아래에만 선다', async () => {
    await show()
    const button = screen.getByRole('button', { name: '카탈로그에 세우기' })
    expect((button as HTMLButtonElement).disabled).toBe(true)
  })

  it('계열을 고르고 세우면 그 묶음이 한 번에 정해진다', async () => {
    await show()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '어느 계열에' }))
    })
    await act(async () => {
      screen.getAllByText('6800 시리즈')[0].click()
    })
    await act(async () => {
      fireEvent.change(screen.getByLabelText('Instron 68FM-300 기종 이름'), {
        target: { value: '68FM-300' },
      })
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '카탈로그에 세우기' }))
    })
    expect(post).toHaveBeenCalledWith('/equipment-models/proposals/decide', {
      normalized: 'instron68fm300',
      series_id: 's-1',
      name: '68FM-300',
    })
  })

  it('「아니오」 는 계열 없이도 눌린다 — 자작 장비는 카탈로그에 올릴 것이 아니다', async () => {
    await show()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '아니오' }))
    })
    // 「아니오」 는 **말해서** 보낸다 — 빈 본문을 거절로 읽으면 인자를 빠뜨린 호출이 조용히
    // 요청을 닫는다(서버는 이제 그것을 400 으로 막는다).
    expect(post).toHaveBeenCalledWith('/equipment-models/proposals/decide', {
      normalized: 'instron68fm300',
      reject: true,
    })
  })
})

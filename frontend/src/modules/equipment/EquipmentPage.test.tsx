/**
 * 보유 장비 목록 — **거르기가 실제로 서버로 간다.**
 *
 * 화면이 한 쪽을 받아 놓고 스스로 거르면, 상한을 넘는 순간 나머지가 조용히 빠지고
 * 목록은 「그 조건에 맞는 장비가 이것뿐」 이라고 거짓말한다. 그래서 거르는 자리는
 * 서버여야 하고, 그 사실은 **호출에 실려 나가는 것**으로만 확인할 수 있다.
 *
 * 여기서 지키는 것 셋 — 주소의 거르기를 읽는다 · 열마다 따로 친다 · 서버가 거른다.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

const calls: string[] = []
/** 걸러서 0 건이 된 상황을 만든다. */
let empty = false

/** 한 대라도 있어야 표가 그려진다 — 한 대도 없는 회사는 거르기를 볼 일이 없다. */
const ONE = {
  id: 'e1',
  asset_no: 'A-001',
  name: '만능시험기',
  category: '만능재료시험기',
  model_name: null,
  series_name: null,
  catalog_linked: true,
  workspace_name: '시험팀',
  shared_use: false,
  site: '본사',
  location: '1동',
  status: 'operational',
  test_items: ['인장'],
  calibration_required: false,
  calibration_missing: false,
  calibration_due_on: null,
  calibration_due_estimated: false,
}

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (url: string) => {
      calls.push(url)
      if (url.startsWith('/equipment/filter-options')) {
        return {
          categories: [{ value: 'c1', label: '만능재료시험기', count: 2 }],
          workspaces: [{ value: 'team', label: '시험팀', count: 2 }],
          sites: [{ value: 's1', label: '본사', count: 2 }],
          statuses: [{ value: 'operational', label: 'operational', count: 2 }],
          test_items: [{ value: 'i1', label: '인장', count: 1 }],
        }
      }
      if (url.startsWith('/equipment')) {
        return empty
          ? { items: [], total: 0, limit: 50, offset: 0 }
          : { items: [ONE], total: 1, limit: 50, offset: 0 }
      }
      return []
    }),
    post: vi.fn(),
  },
  ApiError: class extends Error {},
}))

vi.mock('@/shared/auth/AuthContext', () => ({
  useAuth: () => ({ user: { memberships: [], is_system_admin: false } }),
}))

import EquipmentPage from '@/modules/equipment/EquipmentPage'

async function open(url = '/equipment') {
  calls.length = 0
  await act(async () => {
    render(
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/equipment" element={<EquipmentPage />} />
          {/* 줄을 눌러 상세로 가는지 보려면 갈 곳이 있어야 한다. */}
          <Route path="/equipment/:id" element={<p>상세 화면</p>} />
        </Routes>
      </MemoryRouter>,
    )
  })
}

/** 목록을 부른 마지막 주소. 거르기가 **서버로 갔는지**는 이것으로만 안다. */
function lastList(): string {
  const list = calls.filter((one) => one.startsWith('/equipment?') || one === '/equipment')
  return list[list.length - 1] ?? ''
}

beforeEach(() => {
  calls.length = 0
  empty = false
})

describe('보유 장비 목록', () => {
  it('주소에 실려 온 거르기를 읽는다', async () => {
    // 홈의 「남은 일」 이 이 주소로 온다. 안 읽으면 눌러도 전체 목록이 뜬다.
    await open('/equipment?calibration=missing')
    expect(lastList()).toContain('calibration=missing')
  })

  it('카탈로그에 안 이어진 장비도 주소로 거른다', async () => {
    // 기종은 반입 창에서 못 만든다(전사 공용·시스템 관리자). 그래서 비워 두는데,
    // 그 장비를 되찾는 길이 없으면 대장에만 있고 아무도 못 찾는다.
    await open('/equipment?catalog=unlinked')
    expect(lastList()).toContain('catalog=unlinked')
  })

  it('시험 항목이 없는 장비도 주소로 거른다', async () => {
    await open('/equipment?test_item=none')
    expect(lastList()).toContain('test_item=none')
  })

  it('자산번호와 이름을 각자 친다', async () => {
    await open()
    const assetNo = screen.getByPlaceholderText('자산번호') as HTMLInputElement
    const name = screen.getByPlaceholderText('이름') as HTMLInputElement
    expect(assetNo).toBeTruthy()
    expect(name).toBeTruthy()
    // 한 칸으로 합치면 번호를 치는 사람이 이름에 걸린 줄을 함께 보게 된다.
    expect(assetNo).not.toBe(name)
  })

  it('걸러서 0 건이 되어도 거르는 줄은 남는다', async () => {
    // 머리글째 사라지면 방금 건 조건이 화면에서 없어지고, 무엇을 풀어야 할지가
    // 안 보인다 — 사람은 그때 시스템에 장비가 없다고 읽는다.
    empty = true
    await open('/equipment?calibration=missing')
    expect(screen.getByPlaceholderText('자산번호')).toBeTruthy()
    expect(screen.getByText(/필터에 맞는 장비가 없습니다/)).toBeTruthy()
  })

  it('고를 수 있는 값을 서버에서 받아 온다', async () => {
    await open()
    // 온톨로지 전체가 아니라 **목록에 있는 값만** — 골라도 0 건인 선택지가 섞이면
    // 사람은 거르기를 안 믿는다.
    expect(calls.some((one) => one.startsWith('/equipment/filter-options'))).toBe(true)
  })

  it('줄 아무 데나 누르면 상세로 간다 — 자산번호를 누른 것과 같다', async () => {
    /**
     * 열이 여덟인데 눌리는 것은 글자 두 개(자산번호·이름)뿐이라 과녁이 너무 작았다.
     * 신뢰성 시험 목록과 같은 규칙으로 맞춘다.
     */
    await open()
    // 링크가 아닌 칸 — 분류 글자.
    await act(async () => {
      fireEvent.click(screen.getByText('만능재료시험기'))
    })
    expect(screen.getByText('상세 화면')).toBeTruthy()
  })
})

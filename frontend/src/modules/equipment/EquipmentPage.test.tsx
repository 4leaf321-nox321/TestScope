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
/**
 * 이번 테스트가 보는 상태. **`ONE` 을 직접 고치지 않는다** — 그 객체는 이미 그려진 화면이
 * 들고 있고, 디바운스로 다시 그려지는 순간 바뀐 값을 읽는다. 한 테스트에서 두 번 그리면
 * 같은 글자가 둘이 되어 `getByText` 가 「여럿입니다」 로 떨어진다(CI 에서 그렇게 떨어졌다,
 * 2026-10-02). 부를 때마다 새 줄을 만든다.
 */
let status = 'operational'
/** 카탈로그에 이어졌나와 모델 글자 — 미연결 표시를 보는 시험만 바꾼다. */
let catalog: {
  model_name: string | null
  series_name: string | null
  catalog_linked: boolean
} = { model_name: null, series_name: null, catalog_linked: true }

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
  status_reason: null as string | null,
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
          : { items: [{ ...ONE, status, ...catalog }], total: 1, limit: 50, offset: 0 }
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

/** 그 일이 일어날 때까지 — 디바운스를 고정 시간으로 재면 느린 기계에서 떨어진다. */
async function waited(until: () => boolean, tries = 40): Promise<void> {
  for (let at = 0; at < tries; at += 1) {
    if (until()) return
    await act(async () => {
      await new Promise((done) => setTimeout(done, 25))
    })
  }
}

/** 목록을 부른 마지막 주소. 거르기가 **서버로 갔는지**는 이것으로만 안다. */
function lastList(): string {
  const list = calls.filter((one) => one.startsWith('/equipment?') || one === '/equipment')
  return list[list.length - 1] ?? ''
}

beforeEach(() => {
  calls.length = 0
  empty = false
  status = 'operational'
  catalog = { model_name: null, series_name: null, catalog_linked: true }
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
    expect(screen.getByText(/필터에 맞는 장비 없음/)).toBeTruthy()
  })

  it('거르는 줄의 칸 수가 머리글과 같다 — 어긋나면 열이 통째로 밀린다', async () => {
    /**
     * 거르기는 머리글 **바로 아래 줄**이고, 칸이 자리로 맞춰진다. 열을 하나 더하면서
     * 그 줄에 칸을 안 더하면 모든 거르기가 한 칸씩 밀려서, 「상태」 칸에 친 글자가
     * 「위치」 로 나간다 — 화면은 멀쩡해 보이고 결과만 틀린다.
     */
    await open()
    const rows = document.querySelectorAll('thead tr')
    expect(rows.length).toBe(2)
    expect(rows[1].children.length).toBe(rows[0].children.length)
  })

  it('상태 근거를 서버로 보낸다', async () => {
    await open()
    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('근거에 든 글자'), {
        target: { value: '제어보드' },
      })
    })
    // **고정 시간을 안 기다린다.** 화면은 250ms 쉬고 묻는데, 그보다 조금 긴 시간을 재면
    // 느린 기계에서 아슬아슬하게 떨어진다 — 걸릴 때까지 본다.
    await waited(() =>
      lastList().includes('status_reason=%EC%A0%9C%EC%96%B4%EB%B3%B4%EB%93%9C'),
    )
    expect(lastList()).toContain('status_reason=%EC%A0%9C%EC%96%B4%EB%B3%B4%EB%93%9C')
  })

  it('「근거 미입력」 을 물을 자리가 있고 주소로도 온다', async () => {
    /**
     * 「폐기인데 왜 버렸는지가 없다」 가 상태 근거 칸을 만든 이유다. 서버는 `none` 을
     * 받는데 화면에 글자 입력만 있어서 **눌러서 물을 수 없었다**(2026-10-02).
     *
     * 고르는 칸 자체는 Radix 라 jsdom 에서 눌러 볼 수 없다 — 여기서는 **그 칸이 있는지**와
     * **주소에 실려 오면 서버로 가는지**를 본다(홈이나 링크로 들어오는 길이 그쪽이다).
     */
    await open()
    expect(screen.getByText('근거 전체')).toBeTruthy()
    expect(screen.getByPlaceholderText('근거에 든 글자')).toBeTruthy()
  })

  it('주소의 「근거 미입력」 이 서버로 가고 글자 칸은 숨는다', async () => {
    await open('/equipment?status_reason=none')
    expect(lastList()).toContain('status_reason=none')
    // **둘을 함께 걸 수 있다고 읽히면 안 된다** — 서버는 하나만 받는다.
    expect(screen.queryByPlaceholderText('근거에 든 글자')).toBeNull()
  })

  it('가동에는 「미입력」 을 안 칠한다 — 이유를 물을 것이 없다', async () => {
    // 전부에 칠하면 그 표시가 아무 뜻도 없어진다.
    await open()
    expect(screen.queryByText('미입력')).toBeNull()
  })

  it('모델 글자가 있어도 미연결이면 같은 색으로 단다', async () => {
    // 글자가 있으면 사람은 이어진 줄로 읽는다 — 그 글자는 검색이 안 본다. 회색으로 붙이면
    // 더 속이는 쪽이 덜 눈에 띈다.
    catalog = { model_name: '68FM-300', series_name: null, catalog_linked: false }
    await open()
    const mark = screen.getByText(/카탈로그 미연결/)
    expect(mark.className).toContain('text-amber-600')
  })

  it('모델 글자가 없어도 미연결이면 같은 색이다', async () => {
    catalog = { model_name: null, series_name: null, catalog_linked: false }
    await open()
    expect(screen.getByText('카탈로그 미연결').className).toContain('text-amber-600')
  })

  it('폐기인데 근거가 없으면 칠한다', async () => {
    // 반년 뒤 「그 장비 어디 갔냐」 에 답할 수 없다.
    //
    // **한 테스트에 한 번만 그린다.** 두 번 그리면 먼저 그린 화면이 DOM 에 남아 같은 글자가
    // 둘이 되고, 그러면 `getByText` 가 「여럿입니다」 로 떨어진다.
    status = 'retired'
    await open()
    expect(screen.getByText('미입력')).toBeTruthy()
  })

  it('표를 화면에 가둔다 — 열이 열이면 가로 막대에 닿을 수 없다', async () => {
    /**
     * 안 가두면 가로 스크롤 막대가 표 **맨 아래**에 붙어서, 오른쪽 열을 보려면 먼저 세로로
     * 끝까지 내려가야 한다. 신뢰성 표에서 고친 자리인데(0.39.0) 그 뒤 이 표에 상태 근거·
     * 담당자 두 열이 붙어 열이 열이 되도록 안 걸려 있었다(2026-10-02).
     */
    await open()
    const box = document.querySelector('[data-slot="table-container"]')
    expect(box?.className).toContain('overflow-y-auto')
    // 머리글이 `thead` 째로 붙으므로 **거르는 줄도 함께 붙는다.**
    expect(box?.className).toContain('[&>table>thead]:sticky')
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

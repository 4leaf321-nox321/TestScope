/**
 * 장비 기종 목록 — **대표 사양이 기종을 가른다.**
 *
 * 한 계열에 기종이 열일곱까지 있고, 제조사·계열·시험 항목은 형제끼리 전부 같다.
 * 그 열일곱을 가르는 것은 **수치**뿐이라, 그 칸이 틀리면 목록은 「고를 수 없는 표」 가
 * 된다.
 *
 * 여기서 지키는 것 셋 — 값이 없으면 라벨도 안 그린다 · 「사양 없음」 과 「사양 몇 칸」 을
 * 구별한다 · 「제한 없음」 을 0 으로 그리지 않는다.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/** 기종 한 줄. 대표 사양만 갈아 끼우며 쓴다. */
function model(over: Record<string, unknown>) {
  return {
    id: 'm1',
    name: '68FM-300',
    series_id: 's1',
    series_name: '68FM',
    category: '만능재료시험기',
    maker: '한국시험기',
    status: 'active',
    unit_count: 0,
    operational_count: 0,
    test_items: [],
    spec_count: 0,
    headline_specs: [],
    ...over,
  }
}

/** 사양 한 칸. 종류마다 읽는 자리가 다르다. */
function spec(over: Record<string, unknown>) {
  return {
    definition_id: 'd1',
    label: '하중 용량',
    kind: 'number',
    si_unit: 'N',
    display_unit: 'kN',
    num_value: null,
    num_min: null,
    num_max: null,
    text_value: null,
    bool_value: null,
    ...over,
  }
}

let items: ReturnType<typeof model>[] = []

/** 나간 주소. **거르기가 서버로 갔는지**는 이것으로만 안다. */
const calls: string[] = []

function lastList(): string {
  const rows = calls.filter((one) => one.startsWith('/equipment-models?'))
  return rows[rows.length - 1] ?? ''
}

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (url: string) => {
      calls.push(url)
      if (url.startsWith('/equipment-models/filter-options')) {
        return {
          makers: [{ value: 'm1', label: '한국시험기', count: 3 }],
          categories: [{ value: 'c1', label: '만능재료시험기', count: 3 }],
          kinds: [],
          statuses: [{ value: 'active', label: '현행', count: 3 }],
          series: [{ value: 's1', label: '68FM', count: 3 }],
        }
      }
      if (url.startsWith('/equipment-models')) {
        return { items, total: items.length, limit: 50, offset: 0 }
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

import EquipmentModelsPage from '@/modules/equipment/EquipmentModelsPage'

async function open(url = '/catalog/equipment-models') {
  await act(async () => {
    render(
      <MemoryRouter initialEntries={[url]}>
        <EquipmentModelsPage />
      </MemoryRouter>,
    )
  })
}

beforeEach(() => {
  items = []
  calls.length = 0
})

describe('기종 목록의 대표 사양', () => {
  it('분류가 정한 사양을 값과 단위로 적는다', async () => {
    items = [
      model({
        spec_count: 12,
        headline_specs: [spec({ num_value: 300 })],
      }),
    ]
    await open()
    // 단위는 **실무 단위**로 보인다 — 300000 N 은 라벨의 숫자와 안 맞아서, 사람이
    // 자기가 든 장비를 자기 목록에서 못 알아본다.
    expect(screen.getByText('300 kN')).toBeTruthy()
    expect(screen.getByText(/하중 용량/)).toBeTruthy()
  })

  it('사양이 아예 없는 기종과 대표만 없는 기종을 구별한다', async () => {
    items = [
      model({ id: 'm1', name: '없는것', spec_count: 0 }),
      model({ id: 'm2', name: '대표만없는것', spec_count: 9 }),
    ]
    await open()
    // 앞엣것은 **채워야 할 구멍**이고(홈의 「남은 일」 이 세는 것과 같은 말),
    // 뒤엣것은 사양이 있는데 이 분류에 대표가 안 정해졌을 뿐이다. 둘을 「—」 로
    // 뭉치면 채워야 할 것이 영영 안 채워진다.
    expect(screen.getByText('사양 없음')).toBeTruthy()
    expect(screen.getByText('사양 9칸')).toBeTruthy()
  })

  it('비운 쪽을 0 이 아니라 「제한 없음」 으로 적는다', async () => {
    items = [
      model({
        spec_count: 3,
        headline_specs: [
          spec({ label: '시험 온도', kind: 'range', display_unit: '℃', num_max: 300 }),
        ],
      }),
    ]
    await open()
    // 하한이 0 인 챔버와 하한이 안 적힌 챔버는 정반대다 — 0 으로 그리면 영하까지
    // 되는 장비를 못 찾고, 안 되는 장비를 된다고 답한다.
    expect(screen.getByText('제한 없음 ~ 300 ℃')).toBeTruthy()
  })

  it('시험 항목은 수가 아니라 이름으로 적는다 — 목록은 이름만 받는다', async () => {
    items = [
      model({
        test_items: ['인장', '압축', '굽힘'],
      }),
    ]
    await open()
    // 「3」 은 무슨 시험이 되는지에 아무 답도 못 한다. 다만 **이름만** 온다 —
    // 조건 수치와 인용 규격은 계열이 갖는 값이라 형제 기종끼리 전부 같고,
    // 목록에 실으면 50줄에 52 KB 를 만들어 놓고 안 그린다.
    expect(screen.getByText(/인장 · 압축/)).toBeTruthy()
    expect(screen.getByText(/\+1/)).toBeTruthy()
  })

  it('걸러 온 목록이면 왜 짧은지를 말한다', async () => {
    items = [model({})]
    await open('/catalog/equipment-models?spec=none')
    // 안 말하면 목록이 짧은 것을 오류로 읽는다.
    expect(screen.getByText(/사양이 하나도 안 적힌 기종/)).toBeTruthy()
    expect(screen.getByRole('button', { name: '필터 해제' })).toBeTruthy()
    // **그 거르기가 서버로 갔나.** 화면이 받아 놓고 스스로 거르면 상한을 넘는
    // 순간 나머지가 조용히 빠진다.
    expect(lastList()).toContain('spec=none')
  })

  it('열마다 거르는 칸이 머리글 아래에 있다', async () => {
    items = [model({})]
    await open()
    // 위에 모아 두면 「이 목록이 왜 짧지」 를 사람이 되짚어야 하고, 되짚기는 대개
    // 실패한다. 이름은 **그 열만** 보는 칸이라 `q` 와 따로 있다.
    expect(screen.getByPlaceholderText('기종명')).toBeTruthy()
    expect(screen.getByText('분류 전체')).toBeTruthy()
    expect(screen.getByText('제조사 전체')).toBeTruthy()
    expect(screen.getByText('계열 전체')).toBeTruthy()
  })

  it('고를 수 있는 값을 서버에서 받아 온다', async () => {
    items = [model({})]
    await open()
    // 기준정보 전체가 아니라 **카탈로그에 있는 값만** — 골라도 0 건인 선택지가
    // 섞이면 사람은 거르기를 안 믿는다.
    expect(calls.some((one) => one.startsWith('/equipment-models/filter-options'))).toBe(true)
  })

  it('걸러서 0 건이 되어도 거르는 줄은 남는다', async () => {
    items = []
    await open('/catalog/equipment-models?spec=none')
    expect(screen.getByPlaceholderText('기종명')).toBeTruthy()
    expect(screen.getByText(/필터에 맞는 기종이 없습니다/)).toBeTruthy()
  })
})

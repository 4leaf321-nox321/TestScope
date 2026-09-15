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

const PROPERTIES = [
  {
    id: 'p1',
    value: '인장강도(UTS)',
    code: 'mechanical.tensile_strength',
    domain: 'mechanical',
    symbol: 'Rm',
    si_unit: 'Pa',
    aliases: [],
    links: [
      {
        id: 'l1',
        test_item_term_id: 't1',
        test_item: '인장',
        property_term_id: 'p1',
        property: '인장강도(UTS)',
        property_code: 'mechanical.tensile_strength',
        status: 'suggested',
        source: 'ontology',
        note: null,
        confirmed_at: null,
        created_at: '2026-09-12T00:00:00Z',
      },
    ],
  },
]

const CONDITIONS = [
  {
    id: 'k-force',
    key: 'force',
    label: '하중 용량',
    kind: 'range',
    dimension: 'force',
    si_unit: 'kN',
    display_unit: 'kN',
    choices: [],
    help: null,
    sort_order: 1,
    is_active: true,
  },
  {
    id: 'k-temp',
    key: 'temperature',
    label: '시험 온도',
    kind: 'range',
    dimension: 'temperature',
    si_unit: 'degC',
    display_unit: 'degC',
    choices: [],
    help: null,
    sort_order: 2,
    is_active: true,
  },
  {
    id: 'k-rh',
    key: 'humidity',
    label: '상대 습도',
    kind: 'range',
    dimension: 'ratio',
    si_unit: '%',
    display_unit: '%',
    choices: [],
    help: null,
    sort_order: 3,
    is_active: true,
  },
]

/** 시험 항목마다의 검색축 — 인장은 하중·온도, 압축은 안 정해짐. */
const AXES = [
  {
    id: 't1',
    value: '인장',
    code: 'tensile',
    aliases: [],
    properties_total: 1,
    properties_confirmed: 0,
    methods_total: 0,
    methods_with_requirements: 0,
    series_count: 1,
    model_count: 1,
    equipment_count: 0,
    condition_keys: ['하중 용량', '시험 온도'],
    condition_key_ids: ['k-force', 'k-temp'],
  },
  {
    id: 't2',
    value: '압축',
    code: 'compression',
    aliases: [],
    properties_total: 0,
    properties_confirmed: 0,
    methods_total: 0,
    methods_with_requirements: 0,
    series_count: 0,
    model_count: 0,
    equipment_count: 0,
    condition_keys: [],
    condition_key_ids: [],
  },
]

/** 나간 검색 요청. **물성이 서버로 갔는지**는 이것으로만 안다. */
const posted: unknown[] = []

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (url: string) => {
      if (url.includes('/condition-keys')) return CONDITIONS
      if (url.includes('/terms')) return ITEMS
      if (url.startsWith('/properties')) return PROPERTIES
      if (url.startsWith('/test-items')) return AXES
      return []
    }),
    post: vi.fn(async (url: string, body: unknown) => {
      posted.push({ url, body })
      if (url === '/search/catalog') {
        return {
          hits: [
            {
              series_id: 's1',
              series_name: '5900 Series',
              maker: 'Instron',
              category: '만능재료시험기',
              test_item: '인장',
              methods: ['ISO 6892'],
              note: null,
              models: [
                {
                  model_id: 'm1',
                  model_name: '5982',
                  verdict: 'match',
                  owned_units: 2,
                  conditions: [
                    {
                      condition_key_id: 'k1',
                      condition_label: '하중 용량',
                      display_unit: 'kN',
                      verdict: 'met',
                      asked: '20 kN 이상',
                      condition_range: '제한 없음 ~ 100 kN',
                    },
                  ],
                },
                {
                  model_id: 'm2',
                  model_name: '5942',
                  verdict: 'accessory',
                  owned_units: 0,
                  conditions: [],
                },
              ],
            },
          ],
          total_series: 1,
          total_models: 2,
          unmet_models: 3,
          expanded_test_items: [],
        }
      }
      const asked = body as { test_item_term_id?: string | null }
      if (asked.test_item_term_id === 't2') {
        // 압축: 장비는 하나 있는데 상한이 없어 모른다.
        return {
          hits: [
            {
              equipment_test_item_id: 'e1',
              equipment_id: 'q1',
              asset_no: 'UTM-001',
              equipment_name: '만능시험기',
              status: 'operational',
              workspace_name: '재료시험팀',
              site: '본사',
              location: '1동',
              contact_name: null,
              test_item: '압축',
              method_code: null,
              confidence: 'catalog',
              note: null,
              verdict: 'unknown',
              conditions: [
                {
                  condition_key_id: 'k1',
                  condition_label: '하중 용량',
                  display_unit: 'kN',
                  verdict: 'unknown',
                  asked: '20 kN 이상',
                  condition_range: '0 kN ~ 제한 없음',
                  reason: 'no_max',
                },
              ],
              calibration_due_on: null,
            },
          ],
          total: 1,
          unmet_count: 0,
          unregistered_equipment: 0,
          diagnosis: {
            equipment_with_item: 1,
            catalog_series_with_item: 0,
            unlinked_equipment: 0,
          },
          expanded_test_items: [],
        }
      }
      return {
        hits: [],
        total: 0,
        unmet_count: 0,
        unregistered_equipment: 3,
        // 인장을 하는 장비는 등록된 적이 없고, 카탈로그에는 계열이 12 있다.
        diagnosis: {
          equipment_with_item: 0,
          catalog_series_with_item: 12,
          unlinked_equipment: 5,
        },
        expanded_test_items: ['인장'],
      }
    }),
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

describe('물성으로 묻기', () => {
  it('이어진 것만 고르게 하고, 고른 물성이 서버로 간다', async () => {
    await open()
    // 검색 화면은 **이어진 물성만** 받는다 — 연결 없는 것을 골라 봐야 결과가 늘 빈다.
    const trigger = screen.getByLabelText(/물성으로 묻기/)
    expect(trigger.textContent).toContain('물성 (선택)')

    await act(async () => {
      trigger.click()
    })
    await act(async () => {
      screen.getByText('인장강도(UTS)').click()
    })
    await act(async () => {
      chip('검색').click()
    })
    expect(posted[0]).toMatchObject({
      url: '/search/test-items',
      body: { property_term_id: 'p1', test_item_term_id: null },
    })
    // 무엇으로 펼쳤는지 화면이 말한다 — 0 건일 때 「연결이 없다」 와 「장비가 없다」 를 가른다.
    expect(screen.getByText(/으로 펼쳐/)).toBeTruthy()
  })
})

describe('카탈로그에서 찾기', () => {
  it('같은 물음을 카탈로그에 던지고, 기종마다 판정과 보유 대수가 온다', async () => {
    await open()
    await act(async () => {
      screen.getByRole('tab', { name: '카탈로그에서' }).click()
    })
    // 보유 장비에만 뜻이 있는 손잡이는 사라진다.
    expect(screen.queryByLabelText('점검·고장·폐기 장비도 보기')).toBeNull()
    await act(async () => {
      chip('검색').click()
    })
    expect(posted.at(-1)).toMatchObject({ url: '/search/catalog' })
    expect(screen.getByText('5900 Series')).toBeTruthy()
    expect(screen.getByText('5982')).toBeTruthy()
    // **사기 전에 있는 것을 본다.**
    expect(screen.getByText('보유 2대')).toBeTruthy()
    expect(screen.getByText('부속 있으면')).toBeTruthy()
    expect(screen.getByText(/빠진 기종 3종/)).toBeTruthy()
  })
})

describe('왜 모르는지, 왜 없는지', () => {
  it('빈 결과는 이유 셋을 갈라 말하고 채우러 갈 곳을 준다', async () => {
    await open()
    await act(async () => chip('인장').click())
    await act(async () => chip('검색').click())
    expect(screen.getByText('이 시험을 하는 장비가 등록된 적이 없습니다')).toBeTruthy()
    expect(screen.getByText(/카탈로그에는 이 시험을 하는 계열이/).textContent).toContain(
      '12개',
    )
    expect(screen.getByRole('link', { name: '이어 주기' }).getAttribute('href')).toBe(
      '/equipment?catalog=unlinked',
    )
    expect(screen.getByRole('link', { name: '적으러 가기' }).getAttribute('href')).toBe(
      '/equipment?test_item=none',
    )
  })

  it('모르는 조건은 어느 칸이 비었는지와 채우기 링크를 단다', async () => {
    await open()
    await act(async () => chip('압축').click())
    await act(async () => chip('검색').click())
    expect(screen.getByText(/상한이 없어 「이상」 을 판정할 수 없습니다/)).toBeTruthy()
    expect(screen.getByRole('link', { name: '채우기' }).getAttribute('href')).toBe(
      '/equipment/q1',
    )
  })
})

describe('조건은 시험 항목이 정한다', () => {
  it('시험 항목을 고르면 그 축이 조건 칸에 미리 깔린다', async () => {
    await open()
    await act(async () => chip('인장').click())
    // 인장에 습도를 묻는 것은 뜻이 없다 — 하중·온도만 깔리고 습도는 안 깔린다.
    expect(screen.getByText('하중 용량')).toBeTruthy()
    expect(screen.getByText('시험 온도')).toBeTruthy()
    expect(screen.queryByText('상대 습도')).toBeNull()
  })

  it('축이 안 정해진 항목이면 그렇다고 말하고 정하러 갈 곳을 준다', async () => {
    await open()
    await act(async () => chip('압축').click())
    // 조용히 일곱 개를 다 내면 사람은 뭘 채워야 하는지 모른다.
    expect(screen.getByText(/검색 조건이 아직 안 정해져/)).toBeTruthy()
    expect(screen.getByText('시험 항목에서 정하기').closest('a')?.getAttribute('href')).toBe(
      '/catalog/test-items/t2',
    )
  })
})

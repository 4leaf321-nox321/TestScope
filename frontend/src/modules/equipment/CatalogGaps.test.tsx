/**
 * 카탈로그 보강 — **미연결 장비를 왜 미연결인지로 가른 화면.**
 *
 * 여기서 지키는 것:
 *
 * 1. 사유별 수가 보이고, 사유를 고르면 서버에 그 사유로 묻는다(거르기는 서버가 한다).
 * 2. 같은 기종이 있으면 연결 단추가 있고, **누르면 바로 잇지 않고 확인 창을 띄운다** —
 *    기종을 고르면 그 계열의 시험 항목이 복사되고 조건 판정이 그 사양을 쓴다.
 * 3. 계열만 있으면 그 계열에 기종을 등록한다(계열 + 이름).
 * 4. 모델명이 없는 묶음에는 연결·요청 단추가 없다 — 대조할 열쇠가 없다.
 * 5. 정본에 없는 분류는 표에 표시된다 — 기종을 찾기 전에 분류부터 넣어야 한다.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const get = vi.fn()
const post = vi.fn()

vi.mock('@/shared/api/client', () => ({
  api: { get, post, patch: vi.fn(), delete: vi.fn(), upload: vi.fn() },
  downloadFile: vi.fn(),
  ApiError: class extends Error {},
}))

const { default: CatalogGapsPage } = await import('@/modules/equipment/CatalogGapsPage')

const LABELS = {
  exact: '같은 기종 있음',
  similar: '비슷한 기종 있음',
  series_only: '계열만 있음',
  not_in_catalog: '카탈로그에 없음',
  no_model: '모델명 없음',
  excluded: '카탈로그 대상 아님',
}

function unit(id: string, asset: string) {
  return { id, asset_no: asset, name: '오실로스코프', workspace: '분석팀', category: null }
}

const BODY = {
  units: 4,
  by_case: {
    exact: 1,
    similar: 0,
    series_only: 1,
    not_in_catalog: 1,
    no_model: 1,
    excluded: 0,
  },
  case_labels: LABELS,
  by_category: [
    {
      category: '전자계측장비 > 오실로스코프',
      category_term_id: 'cat-osc',
      in_catalog: false,
      total: 3,
      by_case: {
        exact: 0,
        similar: 0,
        series_only: 1,
        not_in_catalog: 1,
        no_model: 1,
        excluded: 0,
      },
    },
  ],
  groups_total: 4,
  groups: [
    {
      key: 'flirt865',
      case: 'exact',
      case_label: LABELS.exact,
      maker_text: 'FLIR',
      model_text: 'T865',
      maker_known: true,
      count: 1,
      categories: ['광학·디스플레이 측정장비 > 열화상 카메라'],
      departments: ['분석팀'],
      units: [unit('eq-1', 'EQ-001')],
      models: [{ id: 'model-t865', label: 'T865', detail: 'flir · T800 series', score: 1 }],
      series: [],
      open_requests: 0,
    },
    {
      key: 'zwickroellz250allroundline',
      case: 'series_only',
      case_label: LABELS.series_only,
      maker_text: 'ZwickRoell',
      model_text: 'Z250 AllroundLine',
      maker_known: true,
      count: 1,
      categories: [],
      departments: ['분석팀'],
      units: [unit('eq-2', 'EQ-002')],
      models: [],
      series: [{ id: 'series-arl', label: 'AllroundLine', detail: 'zwickroell', score: null }],
      open_requests: 0,
    },
    {
      key: 'keysightdsox3054t',
      case: 'not_in_catalog',
      case_label: LABELS.not_in_catalog,
      maker_text: 'Keysight',
      model_text: 'DSOX3054T',
      maker_known: true,
      count: 1,
      categories: ['전자계측장비 > 오실로스코프'],
      departments: ['분석팀'],
      units: [unit('eq-3', 'EQ-003')],
      models: [],
      series: [],
      open_requests: 0,
    },
    {
      key: 'no_model|전자계측장비 > 오실로스코프|tektronix',
      case: 'no_model',
      case_label: LABELS.no_model,
      maker_text: 'Tektronix',
      model_text: null,
      maker_known: false,
      count: 1,
      categories: ['전자계측장비 > 오실로스코프'],
      departments: ['분석팀'],
      units: [unit('eq-4', 'EQ-004')],
      models: [],
      series: [],
      open_requests: 0,
    },
  ],
}

afterEach(() => vi.clearAllMocks())

async function show() {
  get.mockResolvedValue(BODY)
  post.mockResolvedValue({ status: 'linked', decided: 1, linked: 1, failed: [] })
  await act(async () => {
    render(
      <MemoryRouter>
        <CatalogGapsPage />
      </MemoryRouter>,
    )
  })
}

function card(text: string): HTMLElement {
  const found = screen.getByText(text, { selector: 'span' }).closest('li')
  if (!found) throw new Error(`묶음 없음: ${text}`)
  return found
}

describe('카탈로그 보강', () => {
  it('사유별 수가 보이고, 사유를 고르면 서버에 그 사유로 묻는다', async () => {
    await show()
    expect(screen.getByRole('button', { name: '전체 4대' })).toBeTruthy()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '계열만 있음 1대' }))
    })
    expect(get.mock.calls.at(-1)?.[0]).toBe('/equipment-models/gaps?case=series_only')
    expect(screen.getByText(/계열에 기종 등록\./)).toBeTruthy()
  })

  it('같은 기종 연결은 확인 창을 거친다', async () => {
    await show()
    const exact = card('FLIR T865')
    await act(async () => {
      fireEvent.click(within(exact).getByRole('button', { name: '이 기종에 연결' }))
    })
    // **누르자마자 잇지 않는다** — 확인 창에 무엇이 복사되는지가 적혀 있어야 한다.
    expect(post).not.toHaveBeenCalled()
    expect(screen.getByText(/시험 항목이 장비에 복사/)).toBeTruthy()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '연결' }))
    })
    expect(post).toHaveBeenCalledWith('/equipment-models/gaps/resolve', {
      key: 'flirt865',
      model_id: 'model-t865',
    })
  })

  it('계열만 있으면 그 계열에 기종을 등록한다', async () => {
    await show()
    const family = card('ZwickRoell Z250 AllroundLine')
    await act(async () => {
      fireEvent.click(within(family).getByRole('button', { name: '계열에 기종 등록' }))
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '등록' }))
    })
    expect(post).toHaveBeenCalledWith('/equipment-models/gaps/resolve', {
      key: 'zwickroellz250allroundline',
      series_id: 'series-arl',
      name: 'Z250 AllroundLine',
    })
  })

  it('모델명이 없는 묶음에는 연결·요청 단추가 없다', async () => {
    await show()
    const blank = card('Tektronix (모델명 없음)')
    expect(within(blank).queryByRole('button', { name: '요청으로 올리기' })).toBeNull()
    expect(within(blank).queryByRole('button', { name: '이 기종에 연결' })).toBeNull()
    expect(within(blank).getByText(/모델명 입력 필요/)).toBeTruthy()
  })

  it('정본에 없는 분류가 표에 표시된다', async () => {
    await show()
    expect(screen.getByText('정본에 분류 없음')).toBeTruthy()
  })
})

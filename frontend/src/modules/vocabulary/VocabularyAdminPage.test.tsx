/**
 * 기준정보 편집 — **고칠 수 있는 것이 전부 보여야 화면이 정본이 된다.**
 *
 * 값 편집 창이 이름·코드·상위 값·속성(축이 정한 칸)·표기·병합·폐기를 한 자리에서 내밀고,
 * 축 편집이 이름·설명·정책·속성 칸을 저장한다. prompt 로 묻던 셋에서 여기까지 왔다.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const AXES = [
  {
    id: 'a1',
    slug: 'property',
    label: '물성 항목',
    domain: 'common',
    domain_label: '공통',
    description: '시험으로 얻는 값',
    entry_policy: 'closed',
    parent_slug: null,
    sort_order: 15,
    attribute_schema: [
      { key: 'symbol', label: '기호', kind: 'text', help: 'Rp0.2' },
      { key: 'si_unit', label: 'SI 단위', kind: 'text' },
      { key: 'condition_axes', label: '조건 축', kind: 'list' },
    ],
    term_count: 2,
  },
]

const TERMS = [
  {
    id: 't1',
    vocabulary_slug: 'property',
    value: '항복강도',
    code: 'mechanical.yield_strength',
    parent_term_id: null,
    parent_value: null,
    status: 'active',
    usage_count: 3,
    aliases: ['Rp0.2'],
    attributes: {
      symbol: 'Rp0.2',
      si_unit: 'Pa',
      condition_axes: ['temperature_k'],
      domain: 'mechanical',
    },
    created_at: '2026-09-12T00:00:00Z',
  },
  {
    id: 't2',
    vocabulary_slug: 'property',
    value: '항복 강도 (오타)',
    code: null,
    parent_term_id: null,
    parent_value: null,
    status: 'active',
    usage_count: 0,
    aliases: [],
    attributes: {},
    created_at: '2026-09-12T00:00:00Z',
  },
]

/** 「항복강도」 를 가리키는 것들. 종류마다 떼는 법이 다르다. */
const REFERENCES = [
  {
    key: 'item_property_by_property',
    label: '시험 항목 연결',
    detach: 'delete',
    rows: [{ id: 'l1', label: '인장 → 항복강도', href: '/properties' }],
  },
  {
    key: 'equipment_site',
    label: '장비의 거점',
    detach: 'none',
    rows: [{ id: 'e1', label: 'UTM-001 만능시험기', href: '/equipment/e1' }],
  },
]

const calls: { method: string; url: string; body?: unknown }[] = []

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (url: string) => {
      calls.push({ method: 'GET', url })
      if (url === '/vocabularies') return AXES
      if (url.endsWith('/references')) return REFERENCES
      if (url.includes('/terms')) return TERMS
      return []
    }),
    post: vi.fn(async (url: string, body: unknown) => {
      calls.push({ method: 'POST', url, body })
      return TERMS[0]
    }),
    patch: vi.fn(async (url: string, body: unknown) => {
      calls.push({ method: 'PATCH', url, body })
      return url.startsWith('/vocabularies/property') ? AXES[0] : TERMS[0]
    }),
    delete: vi.fn(async (url: string) => {
      calls.push({ method: 'DELETE', url })
      return { ...TERMS[0], aliases: [] }
    }),
  },
  ApiError: class extends Error {},
}))

import VocabularyAdminPage from '@/modules/vocabulary/VocabularyAdminPage'

async function open() {
  await act(async () => {
    render(
      <MemoryRouter>
        <VocabularyAdminPage />
      </MemoryRouter>,
    )
  })
}

beforeEach(() => {
  calls.length = 0
})

describe('기준정보 편집', () => {
  it('값 편집 창이 축이 정한 속성 칸을 그리고, 저장하면 속성이 통째로 간다', async () => {
    await open()
    await act(async () => {
      fireEvent.click(screen.getByLabelText('항복강도 편집'))
    })
    // 축의 칸 셋. 스키마에 없는 domain 은 「그 밖의 속성」 으로 보인다 — 지우지 않는다.
    expect((screen.getByLabelText(/기호/) as HTMLInputElement).value).toBe('Rp0.2')
    expect((screen.getByLabelText(/조건 축/) as HTMLInputElement).value).toBe('temperature_k')
    expect(screen.getByText('그 밖의 속성')).toBeTruthy()

    fireEvent.change(screen.getByLabelText(/SI 단위/), { target: { value: 'MPa' } })
    fireEvent.change(screen.getByLabelText(/조건 축/), {
      target: { value: 'temperature_k, strain_rate' },
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '저장' }))
    })
    const saved = calls.find(
      (one) => one.method === 'PATCH' && one.url === '/vocabularies/terms/t1',
    )
    expect(saved?.body).toMatchObject({
      value: '항복강도',
      code: 'mechanical.yield_strength',
      attributes: {
        symbol: 'Rp0.2',
        si_unit: 'MPa',
        condition_axes: ['temperature_k', 'strain_rate'],
        domain: 'mechanical',
      },
    })
  })

  it('표기를 떼고, 다른 값으로 합친다', async () => {
    await open()
    await act(async () => {
      fireEvent.click(screen.getByLabelText('항복 강도 (오타) 편집'))
    })
    // 병합 대상 피커 — 자기 자신은 후보에 없다.
    await act(async () => {
      screen.getByRole('button', { name: '합칠 대상' }).click()
    })
    await act(async () => {
      // 표에도 같은 이름이 있다 — 피커 목록의 줄(버튼)만 집는다.
      const rows = screen.getAllByRole('button', { name: /항복강도/ })
      rows.find((one) => one.textContent?.includes('mechanical.yield_strength'))!.click()
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '합치기' }))
    })
    expect(calls.find((one) => one.url === '/vocabularies/terms/t2/merge')?.body).toEqual({
      target_term_id: 't1',
    })
  })

  it('표기 떼기는 값으로 지운다', async () => {
    await open()
    await act(async () => {
      fireEvent.click(screen.getByLabelText('항복강도 편집'))
    })
    await act(async () => {
      fireEvent.click(screen.getByLabelText('표기 Rp0.2 삭제'))
    })
    expect(calls.find((one) => one.method === 'DELETE')?.url).toBe(
      '/vocabularies/terms/t1/aliases?value=Rp0.2',
    )
  })

  it('축의 설명·정책·속성 칸을 저장한다', async () => {
    await open()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /축 고치기/ }))
    })
    fireEvent.change(screen.getByLabelText('설명'), { target: { value: '고친 설명' } })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /칸 추가/ }))
    })
    fireEvent.change(screen.getByLabelText('속성 4 키'), {
      target: { value: 'test_standard' },
    })
    fireEvent.change(screen.getByLabelText('속성 4 이름'), { target: { value: '대표 규격' } })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '축 저장' }))
    })
    const saved = calls.find(
      (one) => one.method === 'PATCH' && one.url === '/vocabularies/property',
    )
    expect(saved?.body).toMatchObject({
      description: '고친 설명',
      entry_policy: 'closed',
      attribute_schema: [
        { key: 'symbol', label: '기호', kind: 'text', help: 'Rp0.2' },
        { key: 'si_unit', label: 'SI 단위', kind: 'text' },
        { key: 'condition_axes', label: '조건 축', kind: 'list' },
        { key: 'test_standard', label: '대표 규격', kind: 'text' },
      ],
    })
  })
})

describe('값의 쓰임', () => {
  it('내역을 종류별로 보이고, 줄마다 떼거나 옮긴다 — 못 떼는 칸은 옮기기만', async () => {
    await open()
    await act(async () => {
      fireEvent.click(screen.getByLabelText('항복강도 편집'))
    })
    expect(screen.getByText('시험 항목 연결')).toBeTruthy()
    expect(screen.getByText('장비의 거점')).toBeTruthy()
    expect(screen.getByText('2건')).toBeTruthy()
    // 갈 수 있는 곳은 링크다.
    expect(screen.getByRole('link', { name: /UTM-001/ }).getAttribute('href')).toBe(
      '/equipment/e1',
    )

    // 비울 수 없는 칸에는 「떼기」 가 없다 — 서버가 말한 대로.
    expect(screen.queryByLabelText('UTM-001 만능시험기 참조 해제')).toBeNull()
    expect(screen.getByLabelText('UTM-001 만능시험기 이동')).toBeTruthy()

    vi.spyOn(window, 'confirm').mockReturnValue(true)
    await act(async () => {
      fireEvent.click(screen.getByLabelText('인장 → 항복강도 참조 해제'))
    })
    expect(calls.find((one) => one.method === 'DELETE')?.url).toBe(
      '/vocabularies/terms/t1/references/item_property_by_property/l1',
    )

    // 옮기기 — 같은 축의 다른 값을 골라 보낸다.
    await act(async () => {
      fireEvent.click(screen.getByLabelText('UTM-001 만능시험기 이동'))
    })
    await act(async () => {
      screen.getByRole('button', { name: '옮길 값' }).click()
    })
    await act(async () => {
      screen.getAllByRole('button', { name: /항복 강도 \(오타\)/ })[0].click()
    })
    await act(async () => {
      fireEvent.click(screen.getAllByRole('button', { name: '이동' }).at(-1)!)
    })
    expect(
      calls.find((one) => one.url.endsWith('/references/equipment_site/e1/reassign'))?.body,
    ).toEqual({ target_term_id: 't2' })
  })
})

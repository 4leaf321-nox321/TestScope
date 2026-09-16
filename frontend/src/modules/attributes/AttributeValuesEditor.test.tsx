/**
 * 속성 값 편집 — **이름은 목록에서 고르고, 없을 때만 새로 적는다.**
 *
 * 여기서 지키는 것 — 정식·초안이 목록에 서고 초안엔 건수가 붙는다 · 새 이름은 초안 줄이 되고
 * 친 글자의 모양으로 종류를 알아맞힌다 · 같은 이름을 새로 치면 새로 만들지 않고 그것을 고른다 ·
 * 빈 줄은 서버로 안 간다.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async () => [
      {
        id: 'd-temp',
        target: 'reliability_test',
        key: 'test_temperature',
        label: '시험 온도',
        kind: 'condition',
        unit: 'degC',
        choices: [],
        condition_key_id: 'ck',
        condition_key_label: '온도',
        vocabulary_id: null,
        vocabulary_slug: null,
        status: 'standard',
        is_required: true,
        help: null,
        sort_order: 0,
        is_active: true,
        merged_into_id: null,
        value_count: 3,
        created_at: '2026-01-01T00:00:00Z',
      },
      {
        id: 'd-sample',
        target: 'reliability_test',
        key: 'draft-abc',
        label: '시료 수',
        kind: 'number',
        unit: '',
        choices: [],
        condition_key_id: null,
        condition_key_label: null,
        vocabulary_id: null,
        vocabulary_slug: null,
        status: 'draft',
        is_required: false,
        help: null,
        sort_order: 0,
        is_active: true,
        merged_into_id: null,
        value_count: 2,
        created_at: '2026-01-01T00:00:00Z',
      },
    ]),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
  ApiError: class extends Error {},
}))

import { AttributeValuesEditor, toPayload } from '@/modules/attributes/AttributeValuesEditor'
import type { AttributeRow } from '@/modules/attributes/AttributeValuesEditor'

let latest: AttributeRow[] = []

function Harness() {
  const [rows, setRows] = useState<AttributeRow[]>([])
  latest = rows
  return <AttributeValuesEditor target="reliability_test" rows={rows} onChange={setRows} />
}

afterEach(() => {
  latest = []
})

describe('속성 값 편집', () => {
  it('필수 정식 항목이 미리 서고, 새 이름은 초안 줄이 되어 종류를 알아맞힌다', async () => {
    await act(async () => {
      render(<Harness />)
    })
    // 필수 항목 「시험 온도」 가 줄로 미리 선다 — 비어 있으면 아래에서 말한다.
    expect(screen.getByLabelText('시험 온도 값')).toBeTruthy()
    expect(screen.getByText(/비어 있는 필수 속성: 시험 온도/)).toBeTruthy()

    // 새 이름 → 초안 줄. 「85℃」 를 치면 수치로 읽는다.
    fireEvent.change(screen.getByLabelText('새 속성 이름'), { target: { value: '습도' } })
    fireEvent.click(screen.getByRole('button', { name: '새 속성' }))
    const input = screen.getByLabelText('습도 값')
    fireEvent.change(input, { target: { value: '85 %' } })
    expect(screen.getByText(/수치로 읽었습니다 · 단위 %/)).toBeTruthy()

    const payload = toPayload(latest)
    // 비어 있는 「시험 온도」 줄은 빠지고 습도만 간다.
    expect(payload).toHaveLength(1)
    expect(payload[0]).toMatchObject({
      definition_id: null,
      new_label: '습도',
      new_kind: 'number',
      num_value: 85,
      unit: '%',
    })
  })

  it('이미 있는 이름을 새로 치면 새로 만들지 않고 그것을 고른다', async () => {
    await act(async () => {
      render(<Harness />)
    })
    fireEvent.change(screen.getByLabelText('새 속성 이름'), { target: { value: '시료 수' } })
    fireEvent.click(screen.getByRole('button', { name: '새 속성' }))
    fireEvent.change(screen.getByLabelText('시료 수 값'), { target: { value: '5' } })
    const payload = toPayload(latest)
    expect(payload).toHaveLength(1)
    expect(payload[0]).toMatchObject({
      definition_id: 'd-sample',
      new_label: null,
      num_value: 5,
    })
    // 초안 표시가 붙는다 — 정식이 아님을 읽는 사람이 알아야 한다.
    expect(screen.getAllByText('초안').length).toBeGreaterThan(0)
  })
})

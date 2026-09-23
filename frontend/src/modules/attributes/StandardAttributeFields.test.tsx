/**
 * 정식 속성을 **그냥 칸으로** — 「속성 추가」 뒤가 아니라 폼의 칸으로.
 *
 * 여기서 지키는 것:
 *
 * 1. 칸이 **갈래로 묶여** 선다. 스물을 한 줄로 세우면 사람은 스크롤만 하다 끝난다.
 * 2. 표에 없는 key 는 「그 밖의 칸」 으로 간다 — 나중에 는 칸도 자리를 잃지 않는다.
 * 3. 구간은 **두 칸**이다. 한 칸에 받으면 글자가 되고, 글자는 장비 판정에 안 실린다.
 * 4. 채운 칸만 서버로 간다.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'

function definition(over: Record<string, unknown>) {
  return {
    id: String(over.key),
    target: 'reliability_test',
    kind: 'text',
    unit: '',
    choices: [],
    condition_key_id: null,
    condition_key_label: null,
    vocabulary_id: null,
    vocabulary_slug: null,
    status: 'standard',
    is_required: false,
    help: null,
    sort_order: 0,
    is_active: true,
    merged_into_id: null,
    value_count: 0,
    created_at: '2026-01-01T00:00:00Z',
    ...over,
  }
}

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async () => [
      definition({ key: 'reliability_type', label: '유형', kind: 'text' }),
      definition({
        key: 'reliability_temperature',
        label: '시험 온도',
        kind: 'condition',
        unit: 'degC',
        condition_key_id: 'ck-temp',
      }),
      definition({ key: 'reliability_procedure', label: '시험 절차' }),
      definition({ key: 'made_up_later', label: '나중에 는 칸' }),
      definition({ key: 'a_draft', label: '초안은 안 보인다', status: 'draft' }),
    ]),
  },
  ApiError: class extends Error {},
}))

const { StandardAttributeFields, toStandardPayload } =
  await import('@/modules/attributes/StandardAttributeFields')
const { attributeApi } = await import('@/modules/attributes/api')
type StandardValue = Awaited<
  ReturnType<typeof import('@/modules/attributes/StandardAttributeFields').fromValues>
>[string]

afterEach(() => vi.clearAllMocks())

function Harness({ onDefs }: { onDefs?: (rows: unknown[]) => void }) {
  const [values, setValues] = useState<Record<string, StandardValue>>({})
  return (
    <StandardAttributeFields
      target="reliability_test"
      values={values}
      onChange={setValues}
      onLoaded={onDefs}
    />
  )
}

describe('정식 속성 칸', () => {
  it('갈래로 묶여 서고, 표에 없는 칸은 그 밖으로 간다', async () => {
    await act(async () => {
      render(<Harness />)
    })

    // 묶음 이름이 선다 — 무엇이 무엇과 한 묶음인지 보인다.
    expect(screen.getByText('무엇을 왜')).toBeTruthy()
    expect(screen.getByText('시험 조건')).toBeTruthy()
    expect(screen.getByText('방법과 판정')).toBeTruthy()
    expect(screen.getByText('그 밖의 칸')).toBeTruthy()

    // 초안은 이 자리에 안 선다 — 여기는 「원래 있는 칸」 이다.
    expect(screen.queryByText('초안은 안 보인다')).toBeNull()

    // **구간은 두 칸이다.**
    expect(screen.getByPlaceholderText('최소')).toBeTruthy()
    expect(screen.getByLabelText('시험 온도 최대')).toBeTruthy()
  })

  it('채운 칸만 서버로 간다', async () => {
    let defs: unknown[] = []
    await act(async () => {
      render(<Harness onDefs={(rows) => (defs = rows)} />)
    })

    const rows = defs as Awaited<ReturnType<typeof attributeApi.definitions>>
    const temperature = rows.find((one) => one.key === 'reliability_temperature')!

    // 아무것도 안 채우면 아무것도 안 간다 — 빈 값은 저장이 아니라 지우기다.
    expect(toStandardPayload(rows, {})).toEqual([])

    const filled = toStandardPayload(rows, {
      [temperature.id]: {
        numValue: null,
        numMin: -40,
        numMax: 85,
        textValue: '',
        termId: null,
        methodId: null,
        pairs: [],
        matrix: [],
      },
    })
    expect(filled).toEqual([
      {
        definition_id: temperature.id,
        new_kind: 'condition',
        num_min: -40,
        num_max: 85,
        unit: 'degC',
      },
    ])
  })

  it('구간에 친 숫자가 상태로 들어간다', async () => {
    await act(async () => {
      render(<Harness />)
    })
    const min = screen.getByPlaceholderText('최소') as HTMLInputElement
    await act(async () => {
      fireEvent.change(min, { target: { value: '-40' } })
    })
    expect((screen.getByPlaceholderText('최소') as HTMLInputElement).value).toBe('-40')
  })
})

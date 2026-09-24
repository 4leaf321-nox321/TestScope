/**
 * 정식 속성을 **그냥 칸으로** — 「속성 추가」 뒤가 아니라 폼의 칸으로.
 *
 * 여기서 지키는 것:
 *
 * 1. 칸이 **갈래로 묶여** 선다. 스물을 한 줄로 세우면 사람은 스크롤만 하다 끝난다.
 * 2. 표에 없는 key 는 「그 밖의 칸」 으로 간다 — 나중에 는 칸도 자리를 잃지 않는다.
 * 3. 시험 조건은 **적은 것만 선다.** 축이 열하나라 전부 세우면 빈 칸으로만 길어진다.
 * 4. 한쪽만 적으면 「이상」·「이하」 다. 숫자로 못 적는 것은 비고에 적고, 그 줄은 판정에 안 쓰인다.
 * 5. 채운 칸만 서버로 간다.
 * 6. **조건 줄에도 이미지가 붙는다.** 온습도 프로파일은 「시험 온도」 의 그림이다.
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
  fetchBlobUrl: vi.fn(async () => 'blob:이미지'),
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

function Harness({
  onDefs,
  attachments,
}: {
  onDefs?: (rows: unknown[]) => void
  attachments?: Parameters<typeof StandardAttributeFields>[0]['attachments']
}) {
  const [values, setValues] = useState<Record<string, StandardValue>>({})
  return (
    <StandardAttributeFields
      target="reliability_test"
      values={values}
      onChange={setValues}
      onLoaded={onDefs}
      attachments={attachments}
    />
  )
}

/** 「시험 온도」 에 붙은 이미지 한 장. 조건 칸의 정의 id 는 key 와 같게 두었다. */
function onTemperature() {
  return {
    objectId: 'r1',
    canEdit: true,
    onChanged: () => {},
    rows: [
      {
        id: 'a1',
        target: 'reliability_test',
        object_id: 'r1',
        definition_id: 'reliability_temperature',
        definition_label: '시험 온도',
        original_name: '온습도-프로파일.png',
        caption: '온습도 프로파일',
        content_type: 'image/png',
        bytes: 2970,
        sort_order: 1,
        url: '/api/attachments/a1/file',
        created_at: '2026-09-24T00:00:00Z',
      },
    ],
  } as Parameters<typeof StandardAttributeFields>[0]['attachments']
}

describe('정식 속성 칸', () => {
  it('갈래로 묶여 서고, 표에 없는 칸은 그 밖으로 간다', async () => {
    await act(async () => {
      render(<Harness />)
    })

    // 묶음 이름이 선다 — 무엇이 무엇과 한 묶음인지 보인다.
    expect(screen.getByText('시험 구분')).toBeTruthy()
    expect(screen.getByText('시험 조건')).toBeTruthy()
    expect(screen.getByText('방법과 판정')).toBeTruthy()
    expect(screen.getByText('기타 항목')).toBeTruthy()

    // 초안은 이 자리에 안 선다 — 여기는 「원래 있는 칸」 이다.
    expect(screen.queryByText('초안은 안 보인다')).toBeNull()

    // **조건은 적은 것만 선다.** 빈 축 열하나를 세워 두지 않는다.
    expect(screen.queryByPlaceholderText('최소')).toBeNull()
    expect(screen.getByText('조건 추가')).toBeTruthy()
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

    const blank = {
      numValue: null,
      numMin: null,
      numMax: null,
      textValue: '',
      termId: null,
      methodId: null,
      documentId: null,
      pairs: [],
      matrix: [],
      note: '',
    }

    // 양쪽 다 적으면 그 사이.
    expect(
      toStandardPayload(rows, { [temperature.id]: { ...blank, numMin: -40, numMax: 85 } }),
    ).toEqual([
      {
        definition_id: temperature.id,
        new_kind: 'condition',
        num_min: -40,
        num_max: 85,
        unit: 'degC',
        note: null,
      },
    ])

    // **한쪽만 적어도 간다** — 「85 이상」 은 최대를 비운 것이다.
    expect(toStandardPayload(rows, { [temperature.id]: { ...blank, numMin: 85 } })).toEqual([
      {
        definition_id: temperature.id,
        new_kind: 'condition',
        num_min: 85,
        num_max: null,
        unit: 'degC',
        note: null,
      },
    ])

    // **숫자가 없어도 비고가 있으면 간다** — 「상온」 처럼 숫자로 못 적는 조건이 있다.
    expect(toStandardPayload(rows, { [temperature.id]: { ...blank, note: '상온' } })).toEqual([
      {
        definition_id: temperature.id,
        new_kind: 'condition',
        num_min: null,
        num_max: null,
        unit: 'degC',
        note: '상온',
      },
    ])
  })

  it('조건을 꺼내 한쪽만 적으면 「이상」 이라고 말해 준다', async () => {
    await act(async () => {
      render(<Harness />)
    })

    // 「조건 추가」 로 꺼낸다.
    await act(async () => {
      fireEvent.click(screen.getByText('조건 추가'))
    })
    await act(async () => {
      fireEvent.click(screen.getByText('시험 온도'))
    })

    const min = screen.getByPlaceholderText('최소') as HTMLInputElement
    await act(async () => {
      fireEvent.change(min, { target: { value: '85' } })
    })
    expect((screen.getByPlaceholderText('최소') as HTMLInputElement).value).toBe('85')
    // **한쪽만 적은 것이 실수인지 뜻인지 사람이 본다.**
    expect(screen.getByText(/85 degC 이상/)).toBeTruthy()
  })

  it('조건 줄에 붙은 이미지가 보인다 — 값이 비어 있어도 줄이 선다', async () => {
    /**
     * 실측(2026-09-24): 이미지 자리가 **조건이 아닌 칸에만** 있었다. 「시험 온도」 에 붙인
     * 온습도 프로파일은 수정 창 어디에도 안 보여서, 붙인 사람은 붙은 줄 알고 고치려는
     * 사람은 없는 줄 알았다.
     *
     * 값이 비어 있을 때도 줄이 서야 한다 — 프로파일 그림만 먼저 받고 램프 시간은 아직
     * 모르는 경우가 실제로 있다. 값으로만 줄을 접으면 그 이미지는 찾을 길이 없다.
     */
    await act(async () => {
      render(<Harness attachments={onTemperature()} />)
    })

    // 값이 없는데도 조건 줄이 서 있다.
    expect(screen.getByPlaceholderText('최소')).toBeTruthy()
    // 그 줄 안에 이미지가 있다.
    expect(screen.getByAltText('온습도 프로파일')).toBeTruthy()
  })

  it('값도 이미지도 없으면 조건 줄은 안 선다 — 빈 축을 세워 두지 않는다', async () => {
    await act(async () => {
      render(<Harness attachments={{ ...onTemperature()!, rows: [] }} />)
    })
    expect(screen.queryByPlaceholderText('최소')).toBeNull()
    expect(screen.getByText('조건 추가')).toBeTruthy()
  })
})

/**
 * 속성이 **열로** 서고, 열마다 걸린다.
 *
 * 여기서 지키는 것:
 *
 * 1. 정의마다 열이 하나 — 값이 한 건도 없는 정의도 선다. **그 열이 있어야 「안 적힌 것」
 *    을 물을 수 있다.**
 * 2. 값이 없는 칸은 「—」 로 적힌다 — 아무것도 안 그리면 열이 밀린 것인지 값이 없는
 *    것인지 구별이 안 된다.
 * 3. 한 정의에 값이 여럿이면(조건 묶음) **한 칸에 함께** 선다. 하나만 그리면 나머지가
 *    조용히 사라진다.
 * 4. 「값 없음」 이 `키!*` 를 만든다 — `키!=` 로는 못 묻는 물음이다(줄 자체가 없으면
 *    어떤 비교도 안 걸린다).
 * 5. 지금 값만 — 과거 판의 값은 이 자리의 답이 아니다.
 * 6. 열을 접으면 머리글도 값 칸도 함께 사라진다.
 */

import { afterEach, describe as suite, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'

import type { AttributeDefinition } from '@/modules/attributes/api'

function definition(over: Partial<AttributeDefinition>): AttributeDefinition {
  return {
    id: 'x',
    target: 'reliability_test',
    key: 'x',
    label: 'X',
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
  } as AttributeDefinition
}

const DEFINITIONS = [
  definition({
    id: 'd-temp',
    key: 'temp_x',
    label: '시험 온도',
    kind: 'condition',
    unit: 'degC',
    value_count: 12,
  }),
  definition({ id: 'd-note', key: 'note_x', label: '비고', kind: 'text', value_count: 2 }),
  // 값이 한 건도 없는 정의 — **이 열이 있어야 「아직 아무도 안 적은 칸」 을 물을 수 있다.**
  definition({ id: 'd-hum', key: 'hum_x', label: '상대 습도', kind: 'condition', unit: '%' }),
]

vi.mock('@/shared/api/client', () => ({
  api: { get: vi.fn(async () => DEFINITIONS) },
  ApiError: class extends Error {},
}))

const { AttributeBodyCells, AttributeColumnPicker, AttributeHeadCells, useAttributeColumns } =
  await import('@/modules/attributes/AttributeColumns')
const { Table, TableBody, TableHeader, TableRow } =
  await import('@/shared/components/ui/table')

const VALUES = [
  { definition_id: 'd-temp', set_label: '주', display: '85 degC', status: 'standard' },
  { definition_id: 'd-temp', set_label: '불량 시', display: '90 degC', status: 'standard' },
  // 과거 판의 값 — 지금 값이 아니다.
  {
    definition_id: 'd-note',
    display: '개정 14의 비고',
    status: 'standard',
    is_current: false,
  },
]

let asked: string[] = []

function Harness() {
  const columns = useAttributeColumns('reliability_test')
  const [value, setValue] = useState<string[]>([])
  asked = value
  return (
    <>
      <AttributeColumnPicker columns={columns} />
      <Table>
        <TableHeader>
          <TableRow>
            <AttributeHeadCells columns={columns.shown} value={value} onChange={setValue} />
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <AttributeBodyCells columns={columns.shown} values={VALUES} />
          </TableRow>
        </TableBody>
      </Table>
    </>
  )
}

async function show() {
  asked = []
  await act(async () => {
    render(<Harness />)
  })
}

afterEach(() => {
  window.localStorage.clear()
  vi.clearAllMocks()
})

suite('속성 열', () => {
  it('정의마다 열이 하나 — 값이 없는 정의도 선다', async () => {
    await show()
    expect(screen.getByText('시험 온도')).toBeTruthy()
    expect(screen.getByText('비고')).toBeTruthy()
    // **값이 0건인 정의도 열로 선다** — 없으면 「안 적힌 것」 을 물을 자리가 없다.
    expect(screen.getByText('상대 습도')).toBeTruthy()
  })

  it('묶음이 둘이면 한 칸에 둘 다 — 하나만 그리면 나머지가 사라진다', async () => {
    await show()
    expect(screen.getByText('85 degC')).toBeTruthy()
    expect(screen.getByText('90 degC')).toBeTruthy()
    expect(screen.getByText('주')).toBeTruthy()
    expect(screen.getByText('불량 시')).toBeTruthy()
  })

  it('지금 값만 — 과거 판은 카드 안에서 본다', async () => {
    await show()
    expect(screen.queryByText('개정 14의 비고')).toBeNull()
    // 지금 값이 없으니 그 칸은 비었다고 **적힌다**.
    expect(screen.getAllByText('—').length).toBe(2)
  })

  it('「값 없음」 은 `!*` 다 — `!=` 로는 못 묻는다', async () => {
    await show()
    await act(async () => {
      fireEvent.click(screen.getByLabelText('상대 습도 거르기'))
    })
    await act(async () => {
      fireEvent.change(screen.getByLabelText('상대 습도 연산'), { target: { value: '!*' } })
    })
    await act(async () => {
      fireEvent.click(screen.getByText('거르기'))
    })
    // **`!=` 가 아니다.** `!=` 는 *적혀 있는데* 그 값이 아닌 것이고, 안 적힌 줄은 어떤
    // 비교에도 안 걸린다 — 그래서 이 물음에는 제 연산이 필요하다.
    expect(asked).toEqual(['hum_x!*'])
  })

  it('값이 있는 조건은 그 열의 키로 만들어진다', async () => {
    await show()
    await act(async () => {
      fireEvent.click(screen.getByLabelText('시험 온도 거르기'))
    })
    await act(async () => {
      fireEvent.change(screen.getByLabelText('시험 온도 연산'), { target: { value: '>=' } })
    })
    const box = screen.getByPlaceholderText('degC')
    await act(async () => {
      fireEvent.change(box, { target: { value: '100' } })
    })
    await act(async () => {
      fireEvent.click(screen.getByText('거르기'))
    })
    expect(asked).toEqual(['temp_x>=100'])
  })

  it('빈 값으로는 안 걸린다 — 누른 사람이 400 을 받지 않는다', async () => {
    await show()
    await act(async () => {
      fireEvent.click(screen.getByLabelText('비고 거르기'))
    })
    await act(async () => {
      fireEvent.click(screen.getByText('거르기'))
    })
    expect(asked).toEqual([])
  })

  it('열을 접으면 머리글도 값 칸도 함께 사라진다', async () => {
    await show()
    await act(async () => {
      fireEvent.click(screen.getByText(/속성 열 3\/3/))
    })
    await act(async () => {
      // 목록의 「시험 온도」 체크칸 — 머리글의 것과 이름이 같으므로 창 안의 것을 집는다.
      fireEvent.click(screen.getAllByRole('checkbox')[0])
    })
    expect(screen.queryByText('85 degC')).toBeNull()
    expect(screen.getByText(/속성 열 2\/3/)).toBeTruthy()
  })
})

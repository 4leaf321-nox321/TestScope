/**
 * 속성으로 거르기 — **건 조건이 사람 말로 보이고, 뺄 수 있어야 한다.**
 *
 * 여기서 지키는 것 — 조건 글자(`temp_x>=100`)가 속성 이름·단위·우리말 연산으로 읽힌다 ·
 * 모르는 키는 글자 그대로 보여 준다(빈칸으로 삼키지 않는다) · 빼기가 그 조건만 뺀다 ·
 * 여러 조건이 「모두 만족」 이라고 적힌다.
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe as suite, expect, it, vi } from 'vitest'

import type { AttributeDefinition } from '@/modules/attributes/api'

const DEFINITIONS: Partial<AttributeDefinition>[] = [
  {
    id: '1',
    key: 'temp_x',
    label: '시험 온도',
    kind: 'condition',
    unit: 'degC',
    status: 'standard',
    is_active: true,
  },
  {
    id: '2',
    key: 'use_x',
    label: '장비 용도',
    kind: 'text',
    unit: '',
    status: 'draft',
    is_active: true,
  },
]

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (path: string) =>
      path.includes('/diagnose')
        ? [
            {
              key: 'temp_x',
              label: '시험 온도',
              status: 'standard',
              with_value: 0,
              unconvertible: 0,
              matched: 0,
              hint: '「시험 온도」 에 값이 적힌 것이 없습니다 — 조건이 아니라 적힌 값이 없는 것입니다.',
            },
          ]
        : DEFINITIONS,
    ),
  },
  ApiError: class extends Error {},
}))

import { AttributeFilterBar, describe } from '@/modules/attributes/AttributeFilterBar'

suite('속성 거르기 칸', () => {
  it('건 조건을 사람 말로 보이고 하나씩 뺀다', async () => {
    const onChange = vi.fn()
    render(
      <AttributeFilterBar
        target="reliability_test"
        value={['temp_x>=100', 'use_x~고온']}
        onChange={onChange}
      />,
    )

    await waitFor(() => expect(screen.getByText('시험 온도 100 degC 이상')).toBeTruthy())
    expect(screen.getByText('장비 용도 고온 포함')).toBeTruthy()
    // 여러 조건은 **모두** 만족해야 한다 — 「또는」 으로 읽으면 결과 수를 오해한다.
    expect(screen.getByText('모두 만족하는 것만')).toBeTruthy()

    await userEvent.click(screen.getByRole('button', { name: '시험 온도 100 degC 이상 빼기' }))
    expect(onChange).toHaveBeenCalledWith(['use_x~고온'])
  })

  it('0건이면 조건마다 왜 비었는지가 뜬다 — 빈 표는 「없다」 로 읽힌다', async () => {
    render(
      <AttributeFilterBar
        target="reliability_test"
        value={['temp_x>=100']}
        onChange={() => undefined}
        empty
      />,
    )
    await waitFor(() => expect(screen.getByText(/값이 적힌 것이 없습니다/)).toBeTruthy())
  })

  it('모르는 키는 삼키지 않고 글자 그대로 보여 준다', () => {
    // 빈칸으로 두면 주소를 받아 연 사람이 「조건 없음」 으로 읽는다. key 는 영문·숫자뿐이라
    // (서버가 그 꼴만 받는다) 모르는 키도 그 이름 그대로 선다.
    expect(describe('gone_x>=3', [])).toBe('gone_x 3 이상')
    expect(describe('말이 안 되는 것', [])).toBe('말이 안 되는 것')
    expect(describe('book_x*', [])).toBe('book_x 값이 있다')
  })
})

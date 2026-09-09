/**
 * 검색형 고르기 — **목록이 길어지면 드롭다운으로는 못 찾는다.**
 *
 * 여기서 지키는 것 넷: 쳐서 좁혀진다 · 「상세」 로 전부 훑는다 · 이미 있는 것은
 * 고르기 전에 보인다 · 창을 닫으면 검색어가 남지 않는다.
 */

import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { act, render, screen } from '@testing-library/react'

import { SearchablePicker } from '@/shared/components/SearchablePicker'
import type { PickerOption } from '@/shared/components/SearchablePicker'

const OPTIONS: PickerOption[] = [
  { id: 'a', label: '인장', detail: '기계' },
  { id: 'b', label: '압축', detail: '기계' },
  { id: 'c', label: '충격', detail: '기계', badge: '이미 있음', disabled: true },
  { id: 'd', label: '경도', detail: '표면' },
]

function Harness() {
  const [value, setValue] = useState('')
  return (
    <>
      <SearchablePicker
        options={OPTIONS}
        value={value}
        onChange={setValue}
        placeholder="시험 항목"
        detailTitle="시험 항목"
      />
      <p data-testid="picked">{value}</p>
    </>
  )
}

function type(box: HTMLElement, text: string) {
  act(() => {
    const setter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      'value',
    )?.set
    setter?.call(box, text)
    box.dispatchEvent(new Event('input', { bubbles: true }))
  })
}

describe('검색형 고르기', () => {
  it('쳐서 좁히고 고르면 값이 들어간다', async () => {
    render(<Harness />)
    await act(async () => {
      screen.getByRole('button', { name: '시험 항목' }).click()
    })
    // 열자마자 전부 보인다 — 무엇이 있는지 모르는 사람이 먼저다.
    expect(screen.getAllByText('인장').length).toBeGreaterThan(0)

    type(screen.getByPlaceholderText(/이름의 일부/), '경도')
    expect(screen.queryByText('인장')).toBeNull()

    await act(async () => {
      screen.getByText('경도').click()
    })
    expect(screen.getByTestId('picked').textContent).toBe('d')
  })

  it('이미 있는 것은 고르기 전에 보이고 못 고른다', async () => {
    render(<Harness />)
    await act(async () => {
      screen.getByRole('button', { name: '시험 항목' }).click()
    })
    // **눌러 보고 409 를 받는 것은 답이지만, 답을 받으려고 누르게 하는 것은
    // 화면의 일이 아니다.**
    expect(screen.getByText('이미 있음')).toBeInTheDocument()
    const row = screen.getByText('충격').closest('button')
    expect(row).toBeDisabled()
  })

  it('「상세」 는 전부 훑는 자리다', async () => {
    render(<Harness />)
    await act(async () => {
      screen.getByRole('button', { name: /시험 항목 전체 보기/ }).click()
    })
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    // 4개 중 4개 — 큰 창은 거르지 않고 시작한다.
    expect(screen.getAllByText(/4개 중 4개/).length).toBeGreaterThan(0)

    await act(async () => {
      screen.getAllByText('압축')[0].click()
    })
    expect(screen.getByTestId('picked').textContent).toBe('b')
    // 고르면 닫힌다 — 고른 뒤에도 열려 있으면 「됐나」 를 화면이 안 말해 준다.
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('닫으면 검색어가 남지 않는다', async () => {
    render(<Harness />)
    const trigger = screen.getByRole('button', { name: '시험 항목' })
    await act(async () => trigger.click())
    type(screen.getByPlaceholderText(/이름의 일부/), '경도')
    await act(async () => trigger.click())
    await act(async () => trigger.click())
    // 지난 검색이 남아 있으면 짧은 목록을 「없다」 로 읽는다.
    expect((screen.getByPlaceholderText(/이름의 일부/) as HTMLInputElement).value).toBe('')
  })
})

/**
 * 이름마다 숫자가 붙는 칸 — 「A등급 4 · B등급 4」.
 *
 * 여기서 지키는 것:
 *
 * 1. 이름과 숫자를 **갈라 받는다.** 한 칸으로 받으면 글자가 되고, 글자는 기계가 못 읽는다.
 * 2. 빈 줄 하나가 먼저 서 있다 — 「추가」 부터 누르게 하지 않는다.
 * 3. 매트릭스는 사양마다 그 짝이 한 벌이다.
 */

import { useState } from 'react'
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { beforeEach, describe, expect, it } from 'vitest'

import { MatrixEditor, PairsEditor } from '@/modules/attributes/PairsEditor'
import type { MatrixRow, Pair } from '@/modules/attributes/kinds'

let container: HTMLDivElement

beforeEach(() => {
  container = document.createElement('div')
  document.body.appendChild(container)
})

function field(label: string): HTMLInputElement {
  const found = container.querySelector<HTMLInputElement>(`[aria-label="${label}"]`)
  if (!found) throw new Error(`못 찾음: ${label}`)
  return found
}

function type(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    'value',
  )?.set
  setter?.call(input, value)
  input.dispatchEvent(new Event('input', { bubbles: true }))
}

/** 값을 들고 있는 감싸개 — 실제 폼이 쓰는 모양 그대로. */
function PairsHarness({ onChange }: { onChange: (rows: Pair[]) => void }) {
  const [rows, setRows] = useState<Pair[]>([])
  return (
    <PairsEditor
      rows={rows}
      unit="개"
      onChange={(next) => {
        setRows(next)
        onChange(next)
      }}
    />
  )
}

function MatrixHarness({ onChange }: { onChange: (rows: MatrixRow[]) => void }) {
  const [rows, setRows] = useState<MatrixRow[]>([])
  return (
    <MatrixEditor
      rows={rows}
      unit="개"
      onChange={(next) => {
        setRows(next)
        onChange(next)
      }}
    />
  )
}

describe('이름별 수량', () => {
  it('이름과 숫자를 갈라 받는다', () => {
    let rows: Pair[] = []
    act(() => {
      createRoot(container).render(<PairsHarness onChange={(next) => (rows = next)} />)
    })

    act(() => type(field('등급·단계 이름 1'), 'A등급'))
    expect(rows).toEqual([{ label: 'A등급', value: null }])

    act(() => type(field('A등급 수량'), '4'))
    expect(rows).toEqual([{ label: 'A등급', value: 4 }])

    // 단위는 칸의 것이라 줄마다 안 적는다.
    expect(container.textContent).toContain('개')
  })
})

describe('사양별 수량', () => {
  it('사양 한 줄에 그 사양의 짝들이 붙는다', () => {
    let rows: MatrixRow[] = []
    act(() => {
      createRoot(container).render(<MatrixHarness onChange={(next) => (rows = next)} />)
    })

    act(() => type(field('사양 1'), '사양 A'))
    expect(rows).toEqual([{ label: '사양 A', entries: [{ label: '', value: null }] }])

    act(() => type(field('등급·단계 이름 1'), 'A등급'))
    expect(rows[0].entries).toEqual([{ label: 'A등급', value: null }])
  })
})

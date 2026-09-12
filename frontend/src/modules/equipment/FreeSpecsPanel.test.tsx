/**
 * 이 기종만의 사양 — **정의 없이 값을 보이고, 여럿이 되면 올리라고 말한다.**
 *
 * 여기서 지키는 것 — 원본 키 그대로인 이름은 그렇게 보인다(사람이 아직 안 읽었다) ·
 * 다른 기종에도 같은 키가 있으면 말한다 · 「정의로 세우기」 는 사람이 이름·종류를 정하는
 * 창을 연다.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'

const calls: { method: string; url: string; body?: unknown }[] = []

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (url: string) => {
      calls.push({ method: 'GET', url })
      if (url.startsWith('/spec-groups'))
        return [{ id: 'g1', slug: 'range', label: '시험 범위' }]
      return []
    }),
    post: vi.fn(async (url: string, body: unknown) => {
      calls.push({ method: 'POST', url, body })
      return { definition_id: 'd1', moved: 3, left: 1 }
    }),
    put: vi.fn(),
    delete: vi.fn(),
  },
  ApiError: class extends Error {},
}))

import { FreeSpecsPanel } from '@/modules/equipment/FreeSpecsPanel'

const rows = [
  {
    id: 'f1',
    label: 'stroke_mm_pk_pk',
    value_text: '152',
    unit: 'mm',
    note: null,
    source_key: 'stroke_mm_pk_pk',
    origin: 'catalog',
    source_id: null,
    source_page: null,
    same_key_models: 5,
  },
  {
    id: 'f2',
    label: '제어 방식',
    value_text: 'PID · 서보',
    unit: null,
    note: null,
    source_key: 'control',
    origin: 'catalog',
    source_id: null,
    source_page: null,
    same_key_models: 0,
  },
]

beforeEach(() => {
  calls.length = 0
})

describe('이 기종만의 사양', () => {
  it('값을 보이고, 같은 키가 다른 기종에도 있으면 말한다', () => {
    render(<FreeSpecsPanel modelId="m1" rows={rows} canEdit onChanged={() => {}} />)
    expect(screen.getByText('152')).toBeTruthy()
    expect(screen.getByText('PID · 서보')).toBeTruthy()
    // 여러 기종이 공유하는 값은 비교할 수 있어야 한다 — 정의의 자리다.
    expect(screen.getByText('다른 기종 5개도')).toBeTruthy()
  })

  it('정의로 세우기 창은 이름·키·종류를 사람이 정하게 한다', async () => {
    render(<FreeSpecsPanel modelId="m1" rows={rows} canEdit onChanged={() => {}} />)
    await act(async () => {
      fireEvent.click(screen.getByLabelText('stroke_mm_pk_pk 정의로 세우기'))
    })
    // 키 후보는 단위 꼬리를 뗀 것 — 사람이 고친다.
    expect((screen.getByLabelText(/^키/) as HTMLInputElement).value).toBe('stroke_mm_pk_pk')
    expect(screen.getByText(/다른 기종 5개의 값도 함께 옮기기/)).toBeTruthy()
    // 그룹을 안 고르면 못 누른다 — 정의는 어딘가에 속해야 한다.
    expect(
      (screen.getByText('정의로 세우기', { selector: 'button' }) as HTMLButtonElement)
        .disabled,
    ).toBe(true)
  })

  it('고칠 수 없으면 단추가 없다', () => {
    render(<FreeSpecsPanel modelId="m1" rows={rows} canEdit={false} onChanged={() => {}} />)
    expect(screen.queryByLabelText('stroke_mm_pk_pk 정의로 세우기')).toBeNull()
  })
})

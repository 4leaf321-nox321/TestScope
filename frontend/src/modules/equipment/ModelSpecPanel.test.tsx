/**
 * 기종 사양표 — **누가 넣었는지 보인다.**
 *
 * AI 가 넣은 값은 AI 가 replace 없이 고치고, 사람이 고치면 다시 잠긴다(0051). 어느 값이
 * 열려 있는지가 화면에 안 보이면, 사람은 자기가 고친 값이 왜 안 덮였는지(또는 왜 덮였는지)를
 * 알 수 없다.
 */

import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

function value(id: string, extra: Record<string, unknown>) {
  return {
    id,
    definition_id: `def-${id}`,
    key: `key_${id}`,
    label: `사양 ${id}`,
    kind: 'number',
    si_unit: 'kg',
    display_unit: 'kg',
    choices: [],
    sort_order: 0,
    is_active: true,
    condition_key_id: null,
    axis_unit_mismatch: false,
    applies: true,
    num_value: 30,
    num_min: null,
    num_max: null,
    text_value: null,
    bool_value: null,
    note: null,
    requires_accessory: false,
    source_id: null,
    source_path: null,
    source_page: null,
    updated_at: '2026-10-03T00:00:00Z',
    ...extra,
  }
}

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (url: string) => {
      if (url.startsWith('/equipment-models/m1/specs'))
        return {
          model_id: 'm1',
          groups: [
            {
              group_id: 'g1',
              slug: 'general',
              label: '일반',
              items: [
                value('a', {
                  origin: 'agent',
                  updated_via: 'Claude 백필',
                  updated_by_name: '홍길동',
                }),
                value('b', { origin: 'manual', updated_by_name: '김철수' }),
                value('c', { origin: null }),
              ],
            },
          ],
        }
      if (url.startsWith('/spec-sources')) return { items: [], total: 0 }
      return []
    }),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
  ApiError: class extends Error {},
}))

import { ModelSpecPanel } from '@/modules/equipment/ModelSpecPanel'

describe('ModelSpecPanel', () => {
  it('AI 가 넣은 값에만 표를 달고, 누가 넣었는지는 마우스를 올리면 보인다', async () => {
    render(
      <ModelSpecPanel modelId="m1" categoryTermId={null} canEdit={false} onSaved={() => {}} />,
    )
    await screen.findByText('사양 a')

    // 표는 AI 가 넣은 줄 하나뿐이다 — 사람 값·기록 전 값에 달면 표가 뜻을 잃는다.
    const marks = screen.getAllByText('AI')
    expect(marks).toHaveLength(1)
    expect(marks[0].getAttribute('title')).toContain('입력: Claude 백필 (홍길동)')

    const values = screen.getAllByText('30 kg')
    expect(values[1].getAttribute('title')).toBe('입력: 김철수')
    // 기록 전에 적힌 값은 말하지 않는다 — 모르는 것을 「사람」 이라고 적으면 거짓말이다.
    expect(values[2].getAttribute('title')).toBeNull()
  })
})

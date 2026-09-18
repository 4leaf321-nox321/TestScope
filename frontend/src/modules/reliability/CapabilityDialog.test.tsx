/**
 * 「이 시험, 어느 장비로 돌리나」 — **0대의 이유를 가른다.**
 *
 * 여기서 지키는 것 — 물은 조건 수를 말한다 · 못 옮겨 뺀 조건을 조용히 삼키지 않는다 ·
 * 장비 줄에 부서·위치·담당자·판정이 있다(찾은 다음에 연락할 사람이 없으면 검색은 절반이다) ·
 * 0대일 때 「조건이 안 맞아서」 와 「그 항목이 적힌 장비가 없어서」 를 다른 말로 답한다.
 */

import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe as suite, expect, it, vi } from 'vitest'

import type { Capability, ReliabilityTest } from '@/modules/reliability/api'

const ANSWER: Capability = {
  test_id: 't1',
  conditions_asked: 2,
  skipped: [{ label: '측정 주기', reason: '단위 「쇼어」 를 온도의 degC 로 못 바꿉니다.' }],
  items: [
    {
      term_id: 'i1',
      value: '고온인장',
      total: 1,
      unmet_count: 2,
      hits: [
        {
          equipment_test_item_id: 'e1',
          equipment_id: 'q1',
          asset_no: 'EQ-1',
          equipment_name: '광역 챔버',
          status: 'in_use',
          workspace_name: '신뢰성팀',
          site: '수원',
          location: '3동 201호',
          contact_name: '박용진',
          test_item: '고온인장',
          method_code: null,
          confidence: 'verified',
          note: null,
          verdict: 'match',
          conditions: [
            {
              condition_key_id: 'c1',
              condition_label: '온도',
              display_unit: 'degC',
              verdict: 'met',
              asked: '125 degC 이상',
              condition_range: '-40 ~ 150 degC',
              reason: null,
            },
          ],
          calibration_due_on: null,
        },
      ],
    },
    { term_id: 'i2', value: '경도', total: 0, unmet_count: 3, hits: [] },
    { term_id: 'i3', value: '염수분무', total: 0, unmet_count: 0, hits: [] },
  ],
}

vi.mock('@/shared/api/client', () => ({
  api: { get: vi.fn(async () => ANSWER) },
  ApiError: class extends Error {},
}))

import { CapabilityDialog } from '@/modules/reliability/CapabilityDialog'

const TEST = { id: 't1', name: '열충격' } as ReliabilityTest

suite('가능한 장비', () => {
  it('물은 조건과 뺀 조건을 말하고, 장비 줄에 연락할 곳을 담는다', async () => {
    render(
      <MemoryRouter>
        <CapabilityDialog test={TEST} onClose={() => undefined} />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText(/조건 2개로 물었습니다/)).toBeTruthy())
    // 뺀 조건은 **조용히 빠지지 않는다** — 다 본 것처럼 읽히면 「가능」 이 거짓이 된다.
    expect(screen.getByText(/측정 주기 — 단위 「쇼어」/)).toBeTruthy()

    expect(screen.getByText('광역 챔버')).toBeTruthy()
    expect(screen.getByText('신뢰성팀')).toBeTruthy()
    expect(screen.getByText('수원 · 3동 201호')).toBeTruthy()
    expect(screen.getByText('박용진')).toBeTruthy()
    expect(screen.getByText('가능')).toBeTruthy()
    expect(screen.getByText(/온도 125 degC 이상/)).toBeTruthy()
    expect(screen.getByText(/조건이 안 맞아 빠진 장비 2대/)).toBeTruthy()
  })

  it('0대의 이유를 가른다 — 조건이 안 맞는 것과 적힌 장비가 없는 것', async () => {
    render(
      <MemoryRouter>
        <CapabilityDialog test={TEST} onClose={() => undefined} />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('경도')).toBeTruthy())
    expect(screen.getByText(/이 조건을 못 맞춥니다/)).toBeTruthy()
    expect(screen.getByText(/이 시험 항목이 적힌 장비가 없습니다/)).toBeTruthy()
  })
})

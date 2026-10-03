/**
 * 보유 장비 표 — **머리글 · 거르기 줄 · 본문이 같은 열에 선다.**
 *
 * 세 줄을 손으로 맞추게 되어 있어서 어긋났다(2026-10-03). 두 겹이었다:
 *
 * 1. 고르기 체크박스 열이 있을 때(부서 관리자) 거르기 줄에 **빈 앞칸이 없어서** 거르기
 *    칸이 전부 한 칸씩 왼쪽으로 밀렸다 — 자산번호 거르기가 체크박스 밑에, 거점 거르기가
 *    「보유」 밑에 섰다. 그래서 「거점이 없는 것 같다」 로 보고됐다.
 * 2. 거르기 줄은 `상태 → 시험 항목 → 상태 근거 → 담당자` 였고 머리글은 `상태 → 상태 근거 →
 *    담당자 → 시험 항목` 이었다. 상태 근거 칸에는 「머리글과 수가 같아야 열이 안 밀린다」 는
 *    주석까지 있었다 — **주석은 지켜지지 않는다.**
 *
 * 그래서 세 줄의 칸마다 `data-col` 을 달고 여기서 **순서까지** 대조한다. 1 은 관리자일 때만
 * 나므로 두 경우를 다 본다.
 */

import { describe, expect, it, vi } from 'vitest'
import { act, render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/** 이번 시험의 사람. **관리자면 고르기 열이 선다** — 밀림은 그때만 난다. */
let manager = false

const ONE = {
  id: 'e1',
  asset_no: 'A-001',
  name: '만능시험기',
  category: '만능재료시험기',
  model_name: null,
  series_name: null,
  catalog_linked: true,
  workspace_name: '시험팀',
  shared_use: false,
  site: '본사',
  location: '1동',
  status: 'operational',
  status_reason: null,
  contact_name: null,
  test_items: ['인장'],
  calibration_required: false,
  calibration_missing: false,
  calibration_due_on: null,
  calibration_due_estimated: false,
}

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (url: string) => {
      if (url.startsWith('/equipment/filter-options')) {
        return {
          categories: [],
          workspaces: [],
          sites: [{ value: 's1', label: '본사', count: 1 }],
          statuses: [{ value: 'operational', label: 'operational', count: 1 }],
          test_items: [],
        }
      }
      if (url.startsWith('/equipment')) {
        return { items: [{ ...ONE }], total: 1, limit: 50, offset: 0 }
      }
      return []
    }),
    post: vi.fn(),
  },
  ApiError: class extends Error {},
}))

vi.mock('@/shared/auth/AuthContext', () => ({
  useAuth: () => ({
    user: {
      is_system_admin: false,
      memberships: manager ? [{ slug: 'team', role: 'manager' }] : [],
    },
  }),
}))

const { default: EquipmentPage } = await import('@/modules/equipment/EquipmentPage')

/** 세 줄의 열 이름표 — 머리글 · 거르기 · 첫 본문 줄. */
async function columns(): Promise<{ head: string[]; filter: string[]; body: string[] }> {
  await act(async () => {
    render(
      <MemoryRouter initialEntries={['/equipment']}>
        <EquipmentPage />
      </MemoryRouter>,
    )
  })
  const rows = document.querySelectorAll('thead tr')
  const keys = (row: Element | null | undefined) =>
    [...(row?.children ?? [])].map((cell) => cell.getAttribute('data-col') ?? '(이름표 없음)')
  return {
    head: keys(rows[0]),
    filter: keys(rows[1]),
    body: keys(document.querySelector('tbody tr')),
  }
}

describe('보유 장비 표의 열', () => {
  it('관리자가 아니면 — 세 줄이 같은 순서다', async () => {
    manager = false
    const { head, filter, body } = await columns()
    expect(head[0]).toBe('asset_no')
    expect(filter).toEqual(head)
    expect(body).toEqual(head)
  })

  it('관리자면 고르기 열이 서고, 거르기 줄도 그 자리를 비운다', async () => {
    manager = true
    const { head, filter, body } = await columns()
    expect(head[0]).toBe('pick')
    // **이 단정이 이 시험의 이유다** — 빈 앞칸이 없으면 거르기가 전부 한 칸 밀린다.
    expect(filter).toEqual(head)
    expect(body).toEqual(head)
  })

  it('거점이 머리글에 이름으로 보인다 — 「위치」 만 적으면 거점이 없는 줄 안다', async () => {
    manager = false
    await columns()
    const site = document.querySelector('thead th[data-col="site"]')
    expect(site?.textContent).toContain('거점')
  })
})

/**
 * 보유 장비 등록·수정 — **한 벌이다.**
 *
 * 여기서 지키는 것:
 *
 * 1. 수정으로 열면 **지금 값이 채워져 있다.** 빈 칸에서 시작하면 안 건드린 칸이 지워진다.
 * 2. **자산번호는 못 고친다** — 서버가 안 받고(`EquipmentUpdateRequest`), 이 장비를
 *    가리키는 이름이라 바꾸면 밖에 나간 문서·라벨과 어긋난다.
 * 3. 저장은 `PATCH` 다. `POST` 로 가면 **같은 장비가 하나 더 생긴다.**
 * 4. 등록으로 열면 `POST` 이고 자산번호를 싣는다.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'

const post = vi.fn(async () => ({ id: 'e1' }))
const patch = vi.fn(async () => ({ id: 'e1' }))

/** 거점·분류·기종·속성 정의 — 창이 열리면서 부르는 것들. */
const get = vi.fn(async (path: string) => {
  if (path.includes('/vocabularies/site/terms')) {
    return [{ id: 'site-1', value: '본사', aliases: [], status: 'active' }]
  }
  if (path.includes('/vocabularies/equipment_category/terms')) {
    return [{ id: 'cat-1', value: '만능재료시험기', aliases: [], status: 'active' }]
  }
  if (path.includes('attribute-definitions')) return []
  if (path.includes('/vocabularies/')) return []
  return { items: [], total: 0 }
})

vi.mock('@/shared/api/client', () => ({
  api: { get: (p: string) => get(p), post, patch, delete: vi.fn() },
  ApiError: class extends Error {},
}))

vi.mock('@/shared/auth/AuthContext', () => ({
  useAuth: () => ({
    user: { memberships: [{ slug: '시험팀', role: 'manager' }], is_system_admin: true },
  }),
}))

const { EquipmentDialog } = await import('@/modules/equipment/EquipmentDialog')
const { equipmentApi } = await import('@/modules/equipment/api')
type Equipment = Awaited<ReturnType<typeof equipmentApi.read>>

function one(over: Partial<Equipment> = {}): Equipment {
  return {
    id: 'e1',
    asset_no: 'UTM-001',
    name: '만능재료시험기 300kN',
    dept_asset_no: 'D-7',
    model_id: null,
    model_name: null,
    series_id: null,
    series_name: null,
    category: '만능재료시험기',
    category_group: null,
    manufacturer: 'Instron',
    catalog_linked: false,
    serial_no: 'SN-9',
    workspace_slug: '시험팀',
    workspace_name: '시험팀',
    shared_use: false,
    site: '본사',
    location: '3동 105호',
    status: 'operational',
    acquired_on: '2020-03-01',
    manufactured_year: 2019,
    retired_on: null,
    contact_name: null,
    note: '펌웨어 2.1',
    test_item_count: 0,
    test_items: [],
    calibration_required: true,
    calibration_interval_months: 12,
    calibration_due_on: null,
    calibration_due_estimated: false,
    calibration_missing: false,
    spec_override_count: 0,
    attributes: [],
    created_at: '2026-01-01T00:00:00Z',
    can_edit: true,
    ...over,
  } as Equipment
}

async function show(editing: Equipment | null) {
  await act(async () => {
    render(<EquipmentDialog open editing={editing} onClose={() => {}} onSaved={() => {}} />)
  })
}

function field(label: string): HTMLInputElement {
  return screen.getByLabelText(label) as HTMLInputElement
}

afterEach(() => vi.clearAllMocks())

describe('보유 장비 수정', () => {
  it('지금 값이 채워진 채로 열린다', async () => {
    await show(one())
    expect(screen.getByText('보유 장비 수정')).toBeTruthy()
    expect(field('자산번호').value).toBe('UTM-001')
    expect(field('장비 이름').value).toBe('만능재료시험기 300kN')
    expect(field('부서관리번호').value).toBe('D-7')
    expect(field('설치 위치').value).toBe('3동 105호')
    expect(field('비고').value).toBe('펌웨어 2.1')
  })

  it('자산번호는 못 고친다 — 그래도 보인다', async () => {
    await show(one())
    // 숨기지 않는다: 어느 장비를 고치는 중인지가 보여야 한다.
    expect(field('자산번호').disabled).toBe(true)
  })

  it('저장하면 PATCH 이고 자산번호는 안 싣는다', async () => {
    await show(one())
    await act(async () => {
      screen.getByRole('button', { name: '저장' }).click()
    })
    expect(post).not.toHaveBeenCalled()
    expect(patch).toHaveBeenCalledTimes(1)
    const [path, body] = patch.mock.calls[0] as unknown as [string, Record<string, unknown>]
    expect(path).toBe('/equipment/e1')
    // **서버가 안 받는 칸이다.** 실어 보내면 422 가 난다.
    expect(body).not.toHaveProperty('asset_no')
    expect(body.location).toBe('3동 105호')
    expect(body.note).toBe('펌웨어 2.1')
  })

  it('등록으로 열면 POST 이고 자산번호를 싣는다', async () => {
    await show(null)
    expect(screen.getByText('장비 등록')).toBeTruthy()
    expect(field('자산번호').disabled).toBe(false)
    expect(field('자산번호').value).toBe('')
  })
})

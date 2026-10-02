/**
 * 사업부 화면에서 **속성으로 거르기** — 그리고 거른 것이 대량 처리까지 따라간다.
 *
 * 여기서 지키는 것:
 *
 * 1. **거르기는 서버가 한다.** 한 쪽을 받아 놓고 화면에서 거르면 쉰 줄만 뒤지고, 그러고도
 *    표는 「조건에 맞는 것이 이것뿐」 이라고 적는다.
 * 2. 조건은 **주소에 실린다** — 좁혀 놓은 화면을 링크로 건넬 수 있어야 한다.
 * 3. 「이 조건의 전체 N건에 적용」 이 **그 조건의 N건**이다. 조건을 안 들고 가면 스무
 *    건이라고 적어 놓고 사업부의 1784건을 전부 확인한다.
 * 4. **속성 아닌 열도 걸린다** — 이름 · 목적 · 시험 항목 · 보유 장비. 화면이 열로 보여
 *    주는 것은 열로 거를 수 있어야 한다.
 * 5. **지난 판은 일부러 펼친다** — 판마다 줄이 서므로(0049) 기본은 최신판만이고, 「과거 판
 *    포함」 이 있어야 지난 판을 볼 길이 있다.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const get = vi.fn()
const post = vi.fn(async (_path: string, body: { ids: string[] }) => ({
  requested: body.ids.length,
  done: body.ids,
  failed: [],
}))

vi.mock('@/shared/api/client', () => ({
  api: { get, post, patch: vi.fn(), delete: vi.fn(), upload: vi.fn() },
  ApiError: class extends Error {},
}))

vi.mock('@/shared/auth/AuthContext', () => ({
  useAuth: () => ({ user: { is_system_admin: true, memberships: [] } }),
}))

vi.mock('react-router-dom', async () => {
  const real = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...real, useParams: () => ({ slug: 'vd' }) }
})

const { default: WorkspaceReliabilityPage } =
  await import('@/modules/reliability/WorkspaceReliabilityPage')

/** 조건에 맞는 줄 수 — 한 쪽(50)을 넘어야 「전체에 적용」 이 뜬다. */
const MATCHED = 120

function row(at: number) {
  return {
    id: `t${at}`,
    division_code: 'vd',
    division_name: 'VD',
    name: `시험 ${at}`,
    purpose: '',
    status: 'candidate',
    submitted_via: '사내 AI',
    confirmed_by: null,
    confirmed_at: null,
    test_items: [],
    attributes: [],
    attachment_count: 0,
    can_edit: true,
    created_at: '2026-09-30T00:00:00Z',
    updated_at: '2026-09-30T00:00:00Z',
  }
}

/** 신뢰성 시험 목록을 부른 주소들 — 물음표 뒤를 사람이 읽는 꼴로. */
function listed(): string[] {
  return get.mock.calls
    .map(([path]) => String(path))
    .filter((path) => path.startsWith('/reliability-tests?'))
    .map(decodeURIComponent)
}

async function show(search: string) {
  get.mockImplementation(async (path: string) => {
    if (path.startsWith('/reliability-tests/divisions')) {
      return [{ code: 'vd', name: 'VD', can_register: true, test_count: 1784 }]
    }
    if (!path.startsWith('/reliability-tests?')) return []
    const found = new URL(`http://x${path}`).searchParams
    const limit = Number(found.get('limit') ?? 50)
    const offset = Number(found.get('offset') ?? 0)
    // **서버가 좁혀서 준다** — 조건이 걸리면 전체도 그 수다.
    const narrowed =
      found.getAll('attr').length > 0 ||
      ['name', 'purpose', 'test_item', 'equipment'].some((key) => found.get(key))
    const total = narrowed ? MATCHED : 1784
    const items = Array.from(
      { length: Math.max(0, Math.min(limit, total - offset)) },
      (_, at) => row(offset + at),
    )
    return { items, total, limit, offset }
  })
  await act(async () => {
    render(
      <MemoryRouter initialEntries={[`/reliability-tests/vd${search}`]}>
        <WorkspaceReliabilityPage />
      </MemoryRouter>,
    )
  })
}

afterEach(() => vi.clearAllMocks())

describe('사업부 화면의 속성 조건', () => {
  it('주소의 조건을 서버로 보낸다 — 화면 안에서 거르지 않는다', async () => {
    await show('?attr=hum_x!*')
    // 「값이 없는 것」 은 **서버만** 셀 수 있다: 줄 자체가 없는 것이라 받은 줄을 아무리
    // 뒤져도 안 나온다.
    expect(listed().some((path) => path.includes('attr=hum_x!*'))).toBe(true)
    expect(screen.getByText(/필터 적용됨/)).toBeTruthy()
  })

  it('「전체에 적용」 이 그 조건의 전체다 — 사업부 전부가 아니다', async () => {
    await show('?attr=hum_x!*')
    await act(async () => {
      screen.getByLabelText('보이는 줄 전부 고르기').click()
    })
    await act(async () => {
      screen.getByLabelText(`필터 결과 전체 ${MATCHED}건 적용`).click()
    })
    await act(async () => {
      screen.getByText('확인').click()
    })

    // id 를 그러모을 때도 **같은 조건**이라야 한다 — 안 그러면 120건이라고 적어 놓고
    // 1784건을 확인한다.
    const gathered = listed().filter((path) => path.includes('limit=200'))
    expect(gathered.length).toBeGreaterThan(0)
    expect(gathered.every((path) => path.includes('attr=hum_x!*'))).toBe(true)

    const sent = post.mock.calls.filter(([path]) => path === '/reliability-tests/bulk')
    const many = sent.reduce(
      (sum, [, body]) => sum + (body as { ids: string[] }).ids.length,
      0,
    )
    expect(many).toBe(MATCHED)
  })

  it('머리글의 깔때기가 열마다 조건을 만든다', async () => {
    await show('')
    // 「목적을 안 적은 줄」 — AI 가 올린 줄은 목적이 비어 있는 경우가 많다.
    await act(async () => {
      fireEvent.click(screen.getByLabelText('목적 필터'))
    })
    await act(async () => {
      fireEvent.click(screen.getByLabelText(/목적 미입력/))
    })
    expect(listed().some((path) => path.includes('purpose=none'))).toBe(true)

    // 「돌릴 장비 없음」 은 「미지정」 과 **다른 물음**이다 — 앞은 항목을 이었는데 그
    // 항목이 되는 장비가 없는 것이고, 뒤는 항목을 아직 안 이은 것이다.
    await act(async () => {
      fireEvent.click(screen.getByLabelText('적용 시험 항목 · 보유 장비 필터'))
    })
    await act(async () => {
      fireEvent.click(screen.getByLabelText(/보유 장비 없음/))
    })
    const last = listed().at(-1) ?? ''
    expect(last).toContain('equipment=none')
    // 앞서 건 조건도 함께 간다 — 여럿이면 모두 만족해야 한다.
    expect(last).toContain('purpose=none')
  })

  it('걸린 조건은 칩으로 서고, 칩에서 풀린다', async () => {
    await show('?purpose=none&equipment=none')
    expect(screen.getByText('목적 미입력')).toBeTruthy()
    expect(screen.getByText('보유 장비 없음')).toBeTruthy()
    await act(async () => {
      fireEvent.click(screen.getByLabelText('목적 미입력 필터 해제'))
    })
    const last = listed().at(-1) ?? ''
    expect(last).not.toContain('purpose=none')
    expect(last).toContain('equipment=none')
  })

  it('열 조건도 대량 처리가 들고 간다 — 「전체 N건」 이 그 조건의 N건이다', async () => {
    await show('?purpose=none')
    await act(async () => {
      screen.getByLabelText('보이는 줄 전부 고르기').click()
    })
    await act(async () => {
      screen.getByLabelText(`필터 결과 전체 ${MATCHED}건 적용`).click()
    })
    await act(async () => {
      screen.getByText('확인').click()
    })
    const gathered = listed().filter((path) => path.includes('limit=200'))
    expect(gathered.length).toBeGreaterThan(0)
    expect(gathered.every((path) => path.includes('purpose=none'))).toBe(true)
  })

  it('「과거 판 포함」 이 서버로 간다 — 없으면 지난 판을 볼 길이 없다', async () => {
    await show('')
    expect(listed().some((path) => path.includes('include_superseded'))).toBe(false)
    await act(async () => {
      fireEvent.click(screen.getByLabelText('과거 판 포함'))
    })
    expect(listed().at(-1)).toContain('include_superseded=true')
  })

  it('0건이어도 표와 머리글은 남는다 — 필터를 풀 자리가 있어야 한다', async () => {
    get.mockImplementation(async (path: string) => {
      if (path.startsWith('/reliability-tests/divisions')) {
        return [{ code: 'vd', name: 'VD', can_register: true, test_count: 1784 }]
      }
      if (!path.startsWith('/reliability-tests?')) return []
      return { items: [], total: 0, limit: 50, offset: 0 }
    })
    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/reliability-tests/vd?attr=hum_x%3E%3D100']}>
          <WorkspaceReliabilityPage />
        </MemoryRouter>,
      )
    })
    // **해야 할 일이 다르다** — 「등록하십시오」 를 읽은 사람은 이미 있는 것을 또 만든다.
    expect(screen.getByText(/필터 조건에 해당하는 신뢰성 시험이 없습니다/)).toBeTruthy()
    // **표는 남는다** — 머리글이 사라지면 어느 열에 무엇이 걸렸는지 볼 수도 풀 수도 없다.
    expect(screen.getByLabelText('목적 필터')).toBeTruthy()
  })
})

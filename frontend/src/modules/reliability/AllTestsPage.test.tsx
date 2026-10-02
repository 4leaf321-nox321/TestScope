/**
 * 전사 신뢰성 목록 — **판마다 줄이 서는데 지난 판을 볼 길이 있나.**
 *
 * 0.42.0 에서 판을 줄의 자리로 올리고 「최신판만 보이기」 를 넣었는데, 「과거 판 포함」 체크를
 * **사업부 화면에만** 두었다. 그래서 전사 목록은 최신판만 보여 주고 지난 판을 볼 길이 아예
 * 없었다 — 서버는 `include_superseded` 를 받는데 그 화면이 안 보냈다(2026-10-02).
 *
 * 여기서 지키는 것:
 *
 * 1. 기본은 **최신판만** — 안 가리면 목록이 판 수만큼 부푼다.
 * 2. 「과거 판 포함」 이 **서버로 간다.** 화면 안에서 거르면 쪽을 넘은 줄은 영영 안 걸린다.
 * 3. 체크가 바뀌면 **첫 쪽으로** — 세 번째 쪽을 보다 펼치면 빈 화면이 뜬다.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const get = vi.fn()

vi.mock('@/shared/api/client', () => ({
  api: { get, post: vi.fn(), patch: vi.fn(), delete: vi.fn(), upload: vi.fn() },
  ApiError: class extends Error {},
}))

const { default: ReliabilityTestsPage } =
  await import('@/modules/reliability/ReliabilityTestsPage')

/** 쪽을 넘을 만큼 — 체크가 첫 쪽으로 되돌리는지 보려면 다음 쪽이 있어야 한다. */
const TOTAL = 120

function row(at: number) {
  return {
    id: `t${at}`,
    division_code: 'mx',
    division_name: 'MX',
    name: `열충격 ${at}`,
    purpose: '',
    status: 'confirmed',
    submitted_via: null,
    confirmed_by: null,
    confirmed_at: null,
    document_revision_id: null,
    document_revision_label: at % 2 === 0 ? '18' : '14',
    test_items: [],
    attributes: [],
    attachment_count: 0,
    can_edit: false,
    created_at: '2026-10-01T00:00:00Z',
    updated_at: '2026-10-01T00:00:00Z',
  }
}

/** 목록을 부른 주소들 — 사람이 읽는 꼴로. */
function listed(): string[] {
  return get.mock.calls
    .map(([path]) => String(path))
    .filter((path) => path.startsWith('/reliability-tests?'))
    .map(decodeURIComponent)
}

async function show() {
  get.mockImplementation(async (path: string) => {
    if (!path.startsWith('/reliability-tests?')) return []
    const found = new URL(`http://x${path}`).searchParams
    const limit = Number(found.get('limit') ?? 50)
    const offset = Number(found.get('offset') ?? 0)
    const items = Array.from(
      { length: Math.max(0, Math.min(limit, TOTAL - offset)) },
      (_, at) => row(offset + at),
    )
    return { items, total: TOTAL, limit, offset }
  })
  await act(async () => {
    render(
      <MemoryRouter>
        <ReliabilityTestsPage />
      </MemoryRouter>,
    )
  })
}

afterEach(() => vi.clearAllMocks())

describe('전사 신뢰성 목록', () => {
  it('기본은 최신판만 — 지난 판을 안 싣는다', async () => {
    await show()
    expect(listed().length).toBeGreaterThan(0)
    expect(listed().every((path) => !path.includes('include_superseded'))).toBe(true)
  })

  it('「과거 판 포함」 이 서버로 간다 — 없으면 지난 판을 볼 길이 없다', async () => {
    await show()
    await act(async () => {
      fireEvent.click(screen.getByLabelText('과거 판 포함'))
    })
    // **서버가 가린다.** 화면 안에서 거르면 쪽을 넘은 줄은 영영 안 걸린다.
    expect(listed().at(-1)).toContain('include_superseded=true')
  })

  it('펼치면 첫 쪽으로 — 세 번째 쪽을 보다 펼치면 빈 화면이 뜬다', async () => {
    await show()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /다음/ }))
    })
    expect(listed().at(-1)).toContain('offset=50')
    await act(async () => {
      fireEvent.click(screen.getByLabelText('과거 판 포함'))
    })
    expect(listed().at(-1)).toContain('offset=0')
  })
})

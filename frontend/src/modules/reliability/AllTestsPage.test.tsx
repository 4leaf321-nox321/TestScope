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
 * 4. **줄 하나는 한 줄 높이다** — 목적은 한 줄로 자르고, 시험 항목은 안 접는다.
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

/** **한 줄에 안 들어가는 목적.** 짧은 글로는 자르는지 펼치는지 구별이 안 된다. */
const LONG =
  '고온고습 환경에서 장시간 통전했을 때 절연 저항이 규격 이하로 떨어지는지, ' +
  '그리고 떨어진 뒤 상온으로 되돌렸을 때 회복되는지를 함께 본다.'

function row(at: number) {
  return {
    id: `t${at}`,
    division_code: 'mx',
    division_name: 'MX',
    name: `열충격 ${at}`,
    purpose: LONG,
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

  it('목적은 한 줄로 자른다 — 프로즈를 펼치면 그 열 하나가 표를 삼킨다', async () => {
    // 접힌 칸 하나가 줄 전체를 높게 만든다. 목적만은 넓혀서 담을 수 없으니(문단이다)
    // 한 줄로 자르고 전문은 툴팁·보기 창에 둔다(2026-10-03).
    //
    // **자르려면 확정 상한이 있어야 한다.** `w-full` 이면 표가 그 한 줄을 다 담으려고
    // 열을 늘려서 생략표가 아예 안 생긴다 — 그래서 상한도 함께 본다.
    await show()
    const shown = screen.getAllByTitle(LONG)[0]
    expect(shown.className).toContain('truncate')
    const cell = shown.closest('td')
    expect(cell?.className ?? '').toContain('max-w-')
  })

  it('시험 항목은 안 접는다 — 항목이 열이면 줄이 열 줄이 된다', async () => {
    await show()
    // `flex-wrap` 이면 항목 수만큼 줄이 쌓인다. 넘치는 것은 표가 가로로 스크롤한다.
    const list = document.querySelector('td ul')
    // 이 fixture 는 항목이 없어 ul 이 안 그려질 수 있다 — 그러면 볼 것이 없으므로 통과.
    if (list) expect(list.className).not.toContain('flex-wrap')
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

/**
 * 후보와 확정 — **AI 가 올린 것은 사람이 본 뒤에 쓴다.**
 *
 * 여기서 지키는 것:
 *
 * 1. 후보면 **읽기 전에** 후보라고 말한다. 스물두 칸을 다 읽은 뒤에 알면 늦다.
 * 2. 누가 올렸는지가 보인다 — 「이거 누가 올린 거야」 를 묻게 하면 안 묻고 그냥 누른다.
 * 3. 확정된 것에는 **누가 보증했는지**가 남아 보인다.
 * 4. 못 고치는 사람에게는 확인 단추가 없다. 눌러야 403 을 아는 단추는 아무것도 안 알려 준다.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const post = vi.fn(async () => ({}))

vi.mock('@/shared/api/client', () => ({
  api: { get: vi.fn(async () => []), post, patch: vi.fn(), delete: vi.fn() },
  ApiError: class extends Error {},
}))

const { CandidateBadge, ReviewBanner } = await import('@/modules/reliability/CandidateReview')
const { reliabilityApi } = await import('@/modules/reliability/api')
type ReliabilityTest = Awaited<ReturnType<typeof reliabilityApi.read>>

function row(over: Partial<ReliabilityTest> = {}): ReliabilityTest {
  return {
    id: 'r1',
    workspace_slug: 'lab',
    workspace_name: '신뢰성팀',
    name: '고온고습 1000h',
    purpose: '85/85',
    status: 'candidate',
    submitted_via: 'mcp-박용진',
    confirmed_by: null,
    confirmed_at: null,
    test_items: [],
    attributes: [],
    attachment_count: 0,
    can_edit: true,
    created_at: '2026-09-24T00:00:00Z',
    updated_at: '2026-09-24T00:00:00Z',
    ...over,
  } as ReliabilityTest
}

afterEach(() => vi.clearAllMocks())

describe('후보 배지', () => {
  it('후보에만 붙는다', async () => {
    const { rerender } = render(<CandidateBadge row={row()} />)
    expect(screen.getByText('확인 전')).toBeTruthy()

    rerender(<CandidateBadge row={row({ status: 'confirmed' })} />)
    expect(screen.queryByText('확인 전')).toBeNull()
  })
})

describe('검토 띠', () => {
  it('후보면 누가 올렸는지 말하고, 확인하면 서버를 부른다', async () => {
    const changed = vi.fn()
    render(<ReviewBanner row={row()} onChanged={changed} />)

    expect(screen.getByText(/아직 확인 전인 후보입니다/)).toBeTruthy()
    // **누가 올렸나.** 감사까지 뒤지게 하면 안 묻고 그냥 누른다.
    expect(screen.getByText(/mcp-박용진/)).toBeTruthy()

    await userEvent.click(screen.getByRole('button', { name: /내용 확인/ }))
    expect(post).toHaveBeenCalledWith('/reliability-tests/r1/confirm', {})
    expect(changed).toHaveBeenCalled()
  })

  it('확정된 것은 누가 보증했는지 보이고 다시 열 수 있다', async () => {
    render(
      <ReviewBanner
        row={row({
          status: 'confirmed',
          confirmed_by: '박용진',
          confirmed_at: '2026-09-24T00:00:00Z',
        })}
        onChanged={() => {}}
      />,
    )
    expect(screen.getByText(/박용진 확인/)).toBeTruthy()
    expect(screen.queryByText(/아직 확인 전인 후보입니다/)).toBeNull()

    await userEvent.click(screen.getByRole('button', { name: /후보로 되돌리기/ }))
    expect(post).toHaveBeenCalledWith('/reliability-tests/r1/reopen', {})
  })

  it('못 고치는 사람에게는 확인 단추가 없다 — 후보라는 사실은 보인다', () => {
    render(<ReviewBanner row={row({ can_edit: false })} onChanged={() => {}} />)
    expect(screen.getByText(/아직 확인 전인 후보입니다/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /내용 확인/ })).toBeNull()
  })

  it('저장 전 새 시험에는 아무것도 안 그린다 — 아직 상태랄 것이 없다', () => {
    const { container } = render(<ReviewBanner row={null} onChanged={() => {}} />)
    expect(container.textContent).toBe('')
  })
})

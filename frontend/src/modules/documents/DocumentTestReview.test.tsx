/**
 * 문서 단위 검토 — **한 문서에서 나온 줄은 함께 읽힌다.**
 *
 * AI 가 규격서 한 권에서 시험 스무 건을 뽑아 올린다. 그 스무 줄은 같은 실수를 함께 한다 —
 * 한 번에 읽고 한 번에 옮겨 적은 것이다. 한 건씩 흩어 놓고 보면 그 결이 안 보이고, 사람은
 * 같은 오답을 스무 번 통과시킨다.
 *
 * 여기서 지키는 것:
 *
 * 1. 그 문서의 줄만 부른다(`document=<id>`), **후보까지**(`status=all`).
 * 2. **고칠 수 있는 줄만 골라진다** — 남의 사업부 줄이 골라지면 「12건 실패」 가 온다.
 * 3. 한 번에 확인·반려·지우기. 반려는 **사유를 받는다.**
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const get = vi.fn()
const post = vi.fn(async () => ({ requested: 2, done: ['t1', 't2'], failed: [] }))

vi.mock('@/shared/api/client', () => ({
  api: { get, post, patch: vi.fn(), delete: vi.fn(), upload: vi.fn() },
  ApiError: class extends Error {},
}))

const { DocumentTestReview } = await import('@/modules/documents/DocumentTestReview')

function test_(id: string, over: Record<string, unknown> = {}) {
  return {
    id,
    name: `시험 ${id}`,
    division_code: 'vd',
    division_name: 'VD',
    status: 'candidate',
    submitted_via: '사내 AI',
    can_edit: true,
    attributes: [],
    test_items: [],
    ...over,
  }
}

async function show(rows: unknown[]) {
  // 목록은 쪽으로 온다 — 1784건을 한 화면에 그리면 브라우저가 멎는다(0.38.0).
  get.mockResolvedValue({ items: rows, total: rows.length, limit: 50, offset: 0 })
  await act(async () => {
    render(
      <MemoryRouter>
        <DocumentTestReview documentId="doc-1" />
      </MemoryRouter>,
    )
  })
}

afterEach(() => vi.clearAllMocks())

describe('문서 단위 검토', () => {
  it('그 문서의 줄만, 후보까지 부른다', async () => {
    await show([test_('t1'), test_('t2')])
    const [called] = get.mock.calls[0] as [string]
    expect(called).toContain('document=doc-1')
    // **후보를 안 부르면 검토할 것이 안 보인다** — 전사 목록의 기본은 확정된 것만이다.
    expect(called).toContain('status=all')
    expect(screen.getByText(/이 규격서에서 올라온 시험 2건/)).toBeTruthy()
    expect(screen.getByText(/확인 전 2건/)).toBeTruthy()
  })

  it('한 번에 확인한다 — 스무 건에 창을 스무 번 열지 않는다', async () => {
    await show([test_('t1'), test_('t2')])
    await act(async () => {
      fireEvent.click(screen.getByLabelText('이 문서의 시험 전부 고르기'))
    })
    expect(screen.getByText('2건 선택')).toBeTruthy()
    await act(async () => {
      fireEvent.click(screen.getByText('확인'))
    })
    expect(post).toHaveBeenCalledWith('/reliability-tests/bulk', {
      ids: ['t1', 't2'],
      action: 'confirm',
      reason: undefined,
    })
  })

  it('반려는 사유를 받는다 — 없으면 안 보낸다', async () => {
    await show([test_('t1')])
    await act(async () => {
      fireEvent.click(screen.getByLabelText('이 문서의 시험 전부 고르기'))
    })
    const ask = vi.spyOn(window, 'prompt').mockReturnValue('  ')
    await act(async () => {
      fireEvent.click(screen.getByText('반려'))
    })
    // **빈 사유로는 안 간다** — 받아 둬야 AI 가 무엇을 자주 틀리는지 셀 수 있다.
    expect(post).not.toHaveBeenCalled()

    ask.mockReturnValue('조건 단위가 틀렸습니다')
    await act(async () => {
      fireEvent.click(screen.getByText('반려'))
    })
    expect(post).toHaveBeenCalledWith('/reliability-tests/bulk', {
      ids: ['t1'],
      action: 'reject',
      reason: '조건 단위가 틀렸습니다',
    })
    ask.mockRestore()
  })

  it('고칠 수 없는 줄은 안 골라진다', async () => {
    await show([test_('t1'), test_('t2', { can_edit: false, division_name: 'MX' })])
    await act(async () => {
      fireEvent.click(screen.getByLabelText('이 문서의 시험 전부 고르기'))
    })
    // 남의 사업부 줄이 함께 골라지면 누른 사람은 「1건 실패」 를 받고 왜인지 세어 본다.
    expect(screen.getByText('1건 선택')).toBeTruthy()
    expect((screen.getByLabelText('시험 t2 고르기') as HTMLInputElement).disabled).toBe(true)
  })

  it('걸린 시험이 없으면 아무것도 안 그린다 — 빈 자리가 창을 늘리지 않는다', async () => {
    await show([])
    expect(screen.queryByText(/이 규격서에서 올라온 시험/)).toBeNull()
  })

  it('다시 후보로도 사유를 받는다 — 확정을 푸는 일이다', async () => {
    await show([test_('t1', { status: 'confirmed' })])
    await act(async () => {
      fireEvent.click(screen.getByLabelText('이 문서의 시험 전부 고르기'))
    })
    const ask = vi.spyOn(window, 'prompt').mockReturnValue('')
    await act(async () => {
      fireEvent.click(screen.getByText('다시 후보로'))
    })
    // **빈 사유로는 안 간다** — 서른 건이 한꺼번에 풀리면 왜인지가 남아야 한다.
    expect(post).not.toHaveBeenCalled()

    ask.mockReturnValue('기타 조건의 원문을 다시 옮기려고')
    await act(async () => {
      fireEvent.click(screen.getByText('다시 후보로'))
    })
    expect(post).toHaveBeenCalledWith('/reliability-tests/bulk', {
      ids: ['t1'],
      action: 'reopen',
      reason: '기타 조건의 원문을 다시 옮기려고',
    })
    ask.mockRestore()
  })

  it('막히면 화면이 말한다 — 조용히 끝나지 않는다', async () => {
    /**
     * 사업부 목록에서 1784건이 「눌러도 아무 일이 없던」 것과 같은 자리다 — `catch` 가
     * 없으면 403·409 가 예외로 사라지고, 사람에게는 아무 일도 안 일어난 것으로 보인다.
     */
    await show([test_('t1')])
    await act(async () => {
      fireEvent.click(screen.getByLabelText('이 문서의 시험 전부 고르기'))
    })
    post.mockRejectedValueOnce(new Error('남의 사업부입니다'))
    await act(async () => {
      fireEvent.click(screen.getByText('확인'))
    })
    expect(screen.getByText(/남의 사업부입니다/)).toBeTruthy()
  })
})

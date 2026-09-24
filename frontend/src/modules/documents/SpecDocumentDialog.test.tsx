/**
 * 사내 규격서 등록 — **문서와 파일을 한 걸음에.**
 *
 * 첨부는 대상 id 를 요구해서 문서 줄이 먼저 있어야 한다. 그 두 걸음을 사람에게 시키면
 * 「만들고 → 다시 열고 → 올리기」 가 되고, 그러면 대개 만들기까지만 하고 파일은 안
 * 올라온다 — 번호만 있는 문서가 남는다.
 *
 * 여기서 지키는 것:
 *
 * 1. 저장하면 **만들고 이어서 올린다.** 사람은 한 번만 누른다.
 * 2. 올리기가 막히면 **창을 닫지 않고 어느 파일이 안 갔는지 말한다** — 문서는 이미
 *    만들어졌으므로, 조용히 닫으면 사람은 파일이 갔는지 모른 채 나간다.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'

const post = vi.fn(async () => ({ id: 'doc-1' }))
const patch = vi.fn(async () => ({ id: 'doc-1' }))
const upload = vi.fn(async () => ({ id: 'a1' }))

vi.mock('@/shared/api/client', () => ({
  api: { get: vi.fn(async () => []), post, patch, delete: vi.fn(), upload },
  ApiError: class extends Error {},
}))

vi.mock('@/shared/auth/AuthContext', () => ({
  useAuth: () => ({
    user: { memberships: [{ slug: 'lab', name: '시험팀', role: 'manager' }] },
  }),
}))

const { SpecDocumentDialog } = await import('@/modules/documents/SpecDocumentDialog')

function pdf(name: string) {
  return new File([new Uint8Array([1, 2, 3])], name, { type: 'application/pdf' })
}

async function open(onSaved = vi.fn()) {
  await act(async () => {
    render(<SpecDocumentDialog open onClose={() => {}} onSaved={onSaved} />)
  })
  return onSaved
}

async function fill() {
  fireEvent.change(screen.getByLabelText('문서 번호'), { target: { value: 'MX-REL-012' } })
  fireEvent.change(screen.getByLabelText('제목'), { target: { value: '환경 시험 표준' } })
}

function choose(...files: File[]) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement
  fireEvent.change(input, { target: { files } })
}

afterEach(() => vi.clearAllMocks())

describe('사내 규격서 등록', () => {
  it('저장하면 문서를 만들고 이어서 파일을 올린다', async () => {
    const saved = await open()
    await act(async () => fill())
    await act(async () => choose(pdf('MX-REL-012_Rev1.pdf'), pdf('국문.pdf')))

    // 고른 파일이 보인다 — 무엇을 올릴지 누르기 전에 알아야 한다.
    expect(screen.getByText('MX-REL-012_Rev1.pdf')).toBeTruthy()
    expect(screen.getByText('국문.pdf')).toBeTruthy()

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '등록' }))
    })

    expect(post).toHaveBeenCalledTimes(1)
    // **한 장씩 보낸다** — 하나가 막혀도 나머지는 들어간다.
    expect(upload).toHaveBeenCalledTimes(2)
    expect(saved).toHaveBeenCalled()
  })

  it('파일을 안 고르면 문서만 만든다', async () => {
    const saved = await open()
    await act(async () => fill())
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '등록' }))
    })
    expect(post).toHaveBeenCalledTimes(1)
    expect(upload).not.toHaveBeenCalled()
    expect(saved).toHaveBeenCalled()
  })

  it('올리기가 막히면 창을 안 닫고 어느 파일인지 말한다', async () => {
    /** 문서는 이미 만들어졌다 — 조용히 닫으면 사람은 파일이 갔는지 모른 채 나간다. */
    upload.mockRejectedValueOnce(new Error('422'))
    const saved = await open()
    await act(async () => fill())
    await act(async () => choose(pdf('너무큰.pdf')))

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '등록' }))
    })

    expect(post).toHaveBeenCalledTimes(1)
    expect(saved).not.toHaveBeenCalled()
    expect(screen.getByText(/너무큰\.pdf/)).toBeTruthy()
    expect(screen.getByText(/문서는 저장됐지만/)).toBeTruthy()
  })

  it('고른 파일을 다시 뺄 수 있다', async () => {
    await open()
    await act(async () => choose(pdf('잘못골랐다.pdf')))
    expect(screen.getByText('잘못골랐다.pdf')).toBeTruthy()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '잘못골랐다.pdf 빼기' }))
    })
    expect(screen.queryByText('잘못골랐다.pdf')).toBeNull()
  })
})

/**
 * 부서 정보 가져오기 — **미리보기 없이 만들지 않는다.**
 *
 * 여기서 지키는 것 — 붙여넣으면 먼저 dry_run 으로 계획을 받는다 · 계획을 본 뒤에야 적용이
 * 가고 그때 dry_run=false 다 · 만들 것이 0 이면 적용 단추가 안 산다 · 결과 뒤 목록을 다시 읽는다.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'

const calls: { path: string; body: unknown }[] = []
let answer: unknown = null

vi.mock('@/shared/api/client', () => ({
  api: {
    post: vi.fn(async (path: string, body: unknown) => {
      calls.push({ path, body })
      return answer
    }),
    get: vi.fn(async () => []),
  },
  downloadFile: vi.fn(async () => undefined),
  ApiError: class extends Error {},
}))

import { ImportWorkspacesDialog } from '@/modules/workspaces/ImportWorkspacesDialog'

const PLAN = {
  rows: [
    {
      line: 2,
      slug: 'rnd',
      name: '개발본부',
      parent_slug: null,
      action: 'create',
      reason: '',
    },
    {
      line: 3,
      slug: 'tf-x',
      name: '신제품 TF',
      parent_slug: 'rnd',
      action: 'skip_kind',
      reason: '한시 조직(TF)·개인 공간은 조직도가 아니라 들이지 않습니다.',
    },
  ],
  created: 1,
  updated: 0,
  skipped: 1,
  errors: 0,
  dry_run: true,
}

afterEach(() => {
  calls.length = 0
  answer = null
})

describe('부서 정보 가져오기', () => {
  it('붙여넣기 → 미리보기(dry_run) → 적용(dry_run=false) 순서로 간다', async () => {
    const onDone = vi.fn()
    answer = PLAN
    render(<ImportWorkspacesDialog open onClose={() => undefined} onDone={onDone} />)

    // 비어 있으면 미리보기도 못 누른다.
    const preview = screen.getByRole('button', { name: '미리보기' }) as HTMLButtonElement
    expect(preview.disabled).toBe(true)

    fireEvent.change(screen.getByLabelText('부서 정보 CSV'), {
      target: { value: 'slug,name,parent_slug,kind\nrnd,개발본부,,org\n' },
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '미리보기' }))
    })
    expect(calls[0].path).toBe('/workspaces/import?dry_run=true')
    expect(screen.getByText('개발본부')).toBeTruthy()
    expect(screen.getByText('대상 아님')).toBeTruthy()
    expect(onDone).not.toHaveBeenCalled()

    answer = { ...PLAN, dry_run: false }
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '1개 가져오기' }))
    })
    expect(calls[1].path).toBe('/workspaces/import?dry_run=false')
    expect(onDone).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: '닫기' })).toBeTruthy()
  })

  it('만들 것이 없으면 적용 단추가 안 산다', async () => {
    answer = { ...PLAN, rows: [PLAN.rows[1]], created: 0, skipped: 1 }
    render(<ImportWorkspacesDialog open onClose={() => undefined} onDone={() => undefined} />)
    fireEvent.change(screen.getByLabelText('부서 정보 CSV'), {
      target: { value: 'slug,name,parent_slug,kind\ntf-x,신제품 TF,rnd,tf\n' },
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '미리보기' }))
    })
    const apply = screen.getByRole('button', {
      name: '가져올 것이 없습니다',
    }) as HTMLButtonElement
    expect(apply.disabled).toBe(true)
  })
})

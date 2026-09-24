/**
 * 부서 지우기 — **누르기 전에 무엇이 딸려 있는지 보인다.**
 *
 * 여기서 지키는 것:
 *
 * 1. 가진 것을 **세어서 보인다.** 지우고 나서 「장비 12대가 사라졌다」 를 알면 늦는다.
 * 2. 막는 것이 있는데 옮길 곳을 안 정했으면 **단추가 안 눌린다.**
 * 3. 옮기면 이름이 겹칠 수 있다 — 그때도 막고, **무엇이 겹치는지 값을 보인다.**
 * 4. 가진 것이 없으면 그냥 지운다.
 *
 * 대상 고르기(Radix Select)는 브라우저 밖에서 누르기가 어렵다 — 그래서 그 **판정만**
 * 순수 함수(`removalState`)로 떼어 두고 여기서 직접 본다.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'

const get = vi.fn()
const remove = vi.fn(async (_path: string) => undefined)

vi.mock('@/shared/api/client', () => ({
  api: {
    get: (path: string) => get(path),
    post: vi.fn(),
    patch: vi.fn(),
    delete: (path: string) => remove(path),
  },
  downloadFile: vi.fn(),
  ApiError: class extends Error {},
}))

const { DeleteWorkspaceDialog, removalState, NONE } =
  await import('@/modules/workspaces/DeleteWorkspaceDialog')

type Reference = { table: string; label: string; count: number; blocks_delete: boolean }

const TEAM = { id: 'w1', slug: 'gone', name: '없어질팀' } as never
const OTHER = { id: 'w2', slug: 'stays', name: '남을팀' } as never

async function open(references: Reference[]) {
  get.mockImplementation(async (path: string) =>
    path.includes('references') ? references : [],
  )
  await act(async () => {
    render(
      <DeleteWorkspaceDialog
        target={TEAM}
        all={[TEAM, OTHER]}
        onClose={() => {}}
        onDeleted={() => {}}
      />,
    )
  })
}

afterEach(() => vi.clearAllMocks())

describe('부서 지우기 창', () => {
  it('가진 것을 세어서 보인다', async () => {
    await open([
      { table: 'equipment', label: '장비', count: 12, blocks_delete: true },
      { table: 'test_methods', label: '사내 시험법', count: 3, blocks_delete: false },
    ])
    expect(screen.getByText('장비')).toBeTruthy()
    expect(screen.getByText(/12건/)).toBeTruthy()
    expect(screen.getByText(/3건/)).toBeTruthy()
  })

  it('막는 것이 있으면 옮길 곳을 정하기 전까지 안 눌린다', async () => {
    await open([{ table: 'equipment', label: '장비', count: 12, blocks_delete: true }])
    const button = screen.getByRole('button', { name: /지우기/ }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    expect(screen.getByText(/옮길 곳을 정해야/)).toBeTruthy()
  })

  it('가진 것이 없으면 그냥 지운다', async () => {
    await open([])
    expect(screen.getByText(/그냥 지울 수 있습니다/)).toBeTruthy()
    const button = screen.getByRole('button', { name: /지우기/ }) as HTMLButtonElement
    expect(button.disabled).toBe(false)

    await act(async () => button.click())
    // **이관 없이는 주소에 대상이 안 붙는다** — 빈 값을 보내면 서버가 404 를 찾는다.
    expect(remove).toHaveBeenCalledWith('/workspaces/gone')
  })
})

describe('지울 수 있나 (판정)', () => {
  const blocking: Reference[] = [
    { table: 'equipment', label: '장비', count: 12, blocks_delete: true },
  ]

  it('옮기지 않을 때는 막는 것이 하나라도 있으면 못 지운다', () => {
    expect(removalState({ to: NONE, references: blocking, clashes: [] }).blocked).toBe(true)
    expect(removalState({ to: NONE, references: [], clashes: [] }).blocked).toBe(false)
  })

  it('막지 않는 참조는 지우기를 막지 않는다 — 옮겨 갈 필요가 없다', () => {
    const soft: Reference[] = [
      { table: 'test_methods', label: '사내 시험법', count: 3, blocks_delete: false },
    ]
    expect(removalState({ to: NONE, references: soft, clashes: [] }).blocked).toBe(false)
  })

  it('옮길 때는 이름이 겹치면 못 지운다 — 옮긴 순간 같은 이름이 둘이 된다', () => {
    const moving = { to: 'stays', references: blocking }
    expect(removalState({ ...moving, clashes: [] }).blocked).toBe(false)
    expect(removalState({ ...moving, clashes: [{ values: ['고온고습'] }] }).blocked).toBe(true)
  })

  it('단추의 말이 무엇을 하는지 말한다', () => {
    expect(removalState({ to: NONE, references: [], clashes: [] }).label).toBe('지우기')
    expect(removalState({ to: 'stays', references: [], clashes: [] }).label).toBe(
      '옮기고 지우기',
    )
  })
})

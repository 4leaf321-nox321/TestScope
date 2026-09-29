/**
 * 여럿 고르기 — **안 보이는 것은 고른 것에서 빠진다.**
 *
 * 이것 하나가 조용히 틀리면 사고가 된다: 거르기를 좁혔는데 고른 것이 남아 있으면, 사람은
 * 열 줄을 보면서 「500건 지우기」 를 누르고, 누른 뒤에도 자기가 무엇을 지웠는지 모른다.
 *
 * 머리 체크박스의 **반쯤 찬 모양**도 여기서 지킨다 — 「전부 골랐다」 로 읽히면 그대로
 * 지우기를 누른다.
 */

import { describe, expect, it } from 'vitest'
import { act, renderHook } from '@testing-library/react'

import { useSelection } from './useSelection'

describe('여럿 고르기', () => {
  it('골랐다 풀었다 한다', () => {
    const { result } = renderHook(() => useSelection(['a', 'b', 'c']))
    expect(result.current.ids).toEqual([])

    act(() => result.current.toggle('b'))
    expect(result.current.ids).toEqual(['b'])
    expect(result.current.has('b')).toBe(true)

    act(() => result.current.toggle('b'))
    expect(result.current.ids).toEqual([])
  })

  it('목록 순서대로 돌려준다 — 누른 차례가 아니다', () => {
    const { result } = renderHook(() => useSelection(['a', 'b', 'c']))
    act(() => result.current.toggle('c'))
    act(() => result.current.toggle('a'))
    expect(result.current.ids).toEqual(['a', 'c'])
  })

  it('머리 체크박스는 전부 고르고 전부 푼다', () => {
    const { result } = renderHook(() => useSelection(['a', 'b']))
    act(() => result.current.toggleAll())
    expect(result.current.ids).toEqual(['a', 'b'])
    expect(result.current.allPicked).toBe(true)
    expect(result.current.somePicked).toBe(false)

    act(() => result.current.toggleAll())
    expect(result.current.ids).toEqual([])
  })

  it('하나만 고르면 **반쯤 찬 모양** — 「전부」 로 읽히면 안 된다', () => {
    const { result } = renderHook(() => useSelection(['a', 'b']))
    act(() => result.current.toggle('a'))
    expect(result.current.allPicked).toBe(false)
    expect(result.current.somePicked).toBe(true)
  })

  it('빈 목록에서는 「전부 골랐다」 가 아니다', () => {
    const { result } = renderHook(() => useSelection([]))
    expect(result.current.allPicked).toBe(false)
  })

  it('**거르기로 사라진 줄은 고른 것에서 빠진다** — 안 보이는 것을 지우게 되면 안 된다', () => {
    const { result, rerender } = renderHook(({ ids }) => useSelection(ids), {
      initialProps: { ids: ['a', 'b', 'c'] },
    })
    act(() => result.current.toggleAll())
    expect(result.current.ids).toEqual(['a', 'b', 'c'])

    rerender({ ids: ['a'] })
    expect(result.current.ids).toEqual(['a'])
    // 다시 넓혀도 사라진 것은 안 돌아온다 — 고른 적이 있다는 것을 기억하지 않는다.
    rerender({ ids: ['a', 'b', 'c'] })
    expect(result.current.ids).toEqual(['a'])
  })

  it('같은 내용이면 고른 것을 안 흔든다 — 새 배열이 와도 그대로다', () => {
    const { result, rerender } = renderHook(({ ids }) => useSelection(ids), {
      initialProps: { ids: ['a', 'b'] },
    })
    act(() => result.current.toggle('a'))
    rerender({ ids: ['a', 'b'] })
    expect(result.current.ids).toEqual(['a'])
  })
})

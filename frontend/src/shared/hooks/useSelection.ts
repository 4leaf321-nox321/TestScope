/**
 * 목록에서 여럿 고르기.
 *
 * **AI 가 몇천 건을 올린다.** 줄마다 창을 열어 확인을 누르는 것은 사람이 할 수 있는 일이
 * 아니고, 못 하면 후보가 쌓인 채로 아무도 안 본다 — 그러면 확인이라는 단계가 이름만 남는다.
 *
 * 화면마다 이 상태를 다시 쓰면 그때마다 조금씩 달라진다. 특히 **거르기를 바꿨을 때 고른
 * 것이 어떻게 되나** 가 갈린다 — 안 보이는 줄이 골라진 채로 남아 있으면, 사람은 열 줄을
 * 보면서 「500건 지우기」 를 누르게 된다. 여기서는 목록에 **지금 있는 것만** 남긴다.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'

export interface Selection {
  /** 고른 id 들 — 목록에 있는 것만. */
  ids: string[]
  has: (id: string) => boolean
  toggle: (id: string) => void
  /** 지금 보이는 줄 전부를 고르거나, 전부 푼다. */
  toggleAll: () => void
  clear: () => void
  /** 보이는 줄이 전부 골라졌나(빈 목록이면 false). */
  allPicked: boolean
  /** 하나라도 골랐지만 전부는 아닌 상태 — 머리 체크박스가 반쯤 찬 모양이 된다. */
  somePicked: boolean
}

export function useSelection(visibleIds: string[]): Selection {
  const [picked, setPicked] = useState<ReadonlySet<string>>(() => new Set())

  // **안 보이는 것은 고른 것에서 뺀다.** 거르기를 좁혔는데 고른 것이 남아 있으면, 열 줄을
  // 보면서 500건을 지우는 일이 생긴다 — 누른 사람은 자기가 무엇을 지웠는지 모른다.
  const key = visibleIds.join('\u0000')
  useEffect(() => {
    setPicked((before) => {
      const alive = new Set(visibleIds)
      const next = new Set([...before].filter((one) => alive.has(one)))
      return next.size === before.size ? before : next
    })
    // visibleIds 는 매번 새 배열이라 그대로 쓰면 무한히 돈다 — 내용으로 비교한다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  const toggle = useCallback((id: string) => {
    setPicked((before) => {
      const next = new Set(before)
      if (!next.delete(id)) next.add(id)
      return next
    })
  }, [])

  const toggleAll = useCallback(() => {
    setPicked((before) =>
      before.size === visibleIds.length ? new Set() : new Set(visibleIds),
    )
  }, [visibleIds])

  const clear = useCallback(() => setPicked(new Set()), [])

  return useMemo(
    () => ({
      ids: visibleIds.filter((one) => picked.has(one)),
      has: (id: string) => picked.has(id),
      toggle,
      toggleAll,
      clear,
      allPicked: visibleIds.length > 0 && picked.size === visibleIds.length,
      somePicked: picked.size > 0 && picked.size < visibleIds.length,
    }),
    [visibleIds, picked, toggle, toggleAll, clear],
  )
}

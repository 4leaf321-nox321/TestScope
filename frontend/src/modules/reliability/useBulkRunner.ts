/**
 * 여러 줄에 한 번에 — **끊어 보내고, 막히면 말한다.**
 *
 * 화면 두 곳(사업부 목록 · 문서 단위 검토)이 같은 일을 하는데, 같은 코드를 두 벌 두었더니
 * 한쪽만 고쳐졌다: 운영에서 1784건을 골라 눌렀을 때 **422 를 아무도 안 잡아** 사람에게는
 * 「눌러도 아무 일이 없다」 로 보였다(2026-09-30). 세 번째 복사본이 생기기 전에 한 곳으로
 * 묶는다.
 *
 * 두 가지를 지킨다:
 *
 *   * **오백 건씩 끊어 보낸다.** 서버가 한 번에 500건까지 받는다 — 한 번의 실수가 되돌릴
 *     수 없는 크기가 되지 않게 둔 상한이라, 우회하지 않고 나눠 보낸다.
 *   * **중간 결과를 쌓아 보여 준다.** 세 묶음째에서 막히면 앞의 둘은 이미 처리된 것이고,
 *     그 경계를 사람이 알아야 다시 누를지 정할 수 있다.
 */

import { useState } from 'react'

import type { BulkOutcome } from '@/shared/components/BulkBar'
import { CHUNK, reliabilityApi } from '@/modules/reliability/api'
import type { BulkAction } from '@/modules/reliability/api'

export interface BulkRunner {
  busy: boolean
  outcome: BulkOutcome | null
  /** 통째로 막혔을 때 — 줄마다의 실패는 `outcome` 이 말한다. */
  error: Error | null
  /** `ids` 는 목록이거나, 그때 가서 그러모으는 함수다(쪽을 넘어 전부에 걸 때). */
  run: (
    ids: string[] | (() => Promise<string[]>),
    action: BulkAction,
    reason?: string,
  ) => Promise<void>
  reset: () => void
}

export function useBulkRunner(onDone: () => void): BulkRunner {
  const [busy, setBusy] = useState(false)
  const [outcome, setOutcome] = useState<BulkOutcome | null>(null)
  const [error, setError] = useState<Error | null>(null)

  async function run(
    ids: string[] | (() => Promise<string[]>),
    action: BulkAction,
    reason?: string,
  ) {
    setBusy(true)
    setOutcome(null)
    setError(null)
    try {
      const every = typeof ids === 'function' ? await ids() : ids
      const sum: BulkOutcome = { requested: 0, done: [], failed: [] }
      for (let at = 0; at < every.length; at += CHUNK) {
        const got = await reliabilityApi.bulk(every.slice(at, at + CHUNK), action, reason)
        sum.requested += got.requested
        sum.done = [...sum.done, ...got.done]
        sum.failed = [...sum.failed, ...got.failed]
        // 묶음마다 보여 준다 — 네 묶음이 다 끝나기를 기다리면 그동안 화면이 멎은 듯 보인다.
        setOutcome({ ...sum })
      }
      onDone()
    } catch (failed) {
      // **잡지 않으면 조용히 끝난다.** 이것이 1784건이 「작동 안 하는」 것처럼 보인 이유다.
      setError(failed as Error)
    } finally {
      setBusy(false)
    }
  }

  return {
    busy,
    outcome,
    error,
    run,
    reset: () => {
      setOutcome(null)
      setError(null)
    },
  }
}

/**
 * 여럿을 골랐을 때 뜨는 띠.
 *
 * **골랐는데 할 자리가 안 보이면 고른 것이 무슨 뜻인지 알 수 없다.** 그래서 하나라도
 * 고르면 목록 위에 붙어 「몇 건 골랐고 무엇을 할 수 있나」 를 말한다.
 *
 * 결과도 여기서 말한다 — 일괄 처리는 **줄마다 성패가 갈리므로**(남의 사업부 · 이미 지운
 * 줄), 「12건 실패」 만 던지면 다시 누를지 고칠지 알 수 없다.
 */

import type { ReactNode } from 'react'

import { Button } from '@/shared/components/ui/button'

export interface BulkOutcome {
  done: unknown[]
  /** 서버가 주는 모양은 `{id, code, message}` 인데, 생성 타입에서는 문자열 사전이다
   *  (`dict[str, str]`). 읽는 자리에서 없을 수도 있다고 보고 다룬다. */
  failed: Record<string, string>[]
  requested: number
}

interface BulkBarProps {
  count: number
  onClear: () => void
  /** 단추들. 화면마다 할 수 있는 일이 달라서 밖에서 넣는다. */
  children: ReactNode
  busy?: boolean
  outcome?: BulkOutcome | null
}

export function BulkBar({ count, onClear, children, busy, outcome }: BulkBarProps) {
  if (count === 0 && !outcome) return null
  return (
    <div className="bg-muted/60 space-y-2 rounded-md border p-2">
      {count > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium">{count}건 선택</span>
          <div className="flex flex-wrap gap-1">{children}</div>
          <div className="flex-1" />
          <Button variant="ghost" size="sm" onClick={onClear} disabled={busy}>
            선택 해제
          </Button>
        </div>
      )}
      {outcome && (
        <div className="text-sm">
          <p>
            {outcome.requested}건 중 <strong>{outcome.done.length}건</strong> 처리
            {outcome.failed.length > 0 && <> · {outcome.failed.length}건 실패</>}
          </p>
          {/* **왜 안 됐는지 말한다.** 같은 사유가 여럿이면 한 줄로 묶어 센다 — 500건이
              같은 이유로 막혔을 때 500줄을 읽게 하지 않는다. */}
          {outcome.failed.length > 0 && (
            <ul className="text-muted-foreground mt-1 space-y-0.5 text-xs">
              {Object.entries(
                outcome.failed.reduce<Record<string, number>>((into, one) => {
                  const said = one.message || one.code || '알 수 없는 오류'
                  into[said] = (into[said] ?? 0) + 1
                  return into
                }, {}),
              ).map(([message, times]) => (
                <li key={message}>
                  {message} ({times}건)
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

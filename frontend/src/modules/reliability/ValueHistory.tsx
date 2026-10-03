/**
 * 값의 판별 이력 — **화면은 최신판을 보여 주고, 과거 판은 여기서 본다.**
 *
 * 시험은 한 줄이고 판은 값에 붙는다. 카드가 지금 값만 보여 주는 것은 옳지만(85 와 95 가
 * 나란히 서면 어느 것이 조건인지 안 보인다), 그러면 「개정 14에서는 얼마였나」 를 볼 길이
 * 없어진다 — 그 물음이 곧 「이 개정에서 무엇이 바뀌었나」 다.
 *
 * 자리(칸·묶음·차례)마다 판이 늘어서고, 지금 값에 표가 붙는다. **바뀐 자리만 접지 않고
 * 다 보여 주는 이유**: 안 바뀐 것을 확인하는 것도 검토다 — 「이건 그대로구나」 를 못 보면
 * 사람은 원본을 다시 연다.
 */

import { useMemo } from 'react'

import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { useResource } from '@/shared/hooks/useResource'
import { reliabilityApi } from '@/modules/reliability/api'
import type { AttributeValueRow } from '@/modules/reliability/api'

/** 한 자리 — 같은 칸·묶음·차례의 값들이 판마다 늘어선다. */
function slotOf(row: AttributeValueRow): string {
  const step = row.step_order === null ? '' : ` ${row.step_order}번째`
  const inside = [row.set_label, step.trim()].filter(Boolean).join(' ')
  return inside ? `${row.label} (${inside})` : row.label
}

export function ValueHistory({ testId }: { testId: string }) {
  const rows = useResource(() => reliabilityApi.valueHistory(testId), [testId])

  const slots = useMemo(() => {
    const groups = new Map<string, AttributeValueRow[]>()
    for (const one of rows.data ?? []) {
      const key = slotOf(one)
      groups.set(key, [...(groups.get(key) ?? []), one])
    }
    // 판이 하나뿐인 자리는 이력이랄 것이 없다 — 바뀐 자리만 남긴다.
    return [...groups.entries()]
      .filter(([, mine]) => mine.length > 1)
      .sort(([a], [b]) => a.localeCompare(b))
  }, [rows.data])

  if (rows.error) return <ErrorNotice error={rows.error} />
  if (!rows.data) return null
  if (slots.length === 0) {
    return (
      <p className="text-muted-foreground text-xs">
        판별로 달라진 값 없음. 지금 값이 처음 값과 같음.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      <p className="text-muted-foreground text-xs">
        판별로 값이 달라진 항목. <strong>지금 값</strong>은 최신판 값, 아래는 이전 판 값.
      </p>
      <ul className="space-y-2">
        {slots.map(([where, mine]) => (
          <li key={where} className="rounded-md border p-2">
            <p className="text-sm font-medium">{where}</p>
            <ul className="mt-0.5 space-y-0.5 text-sm">
              {mine
                // 지금 값이 맨 위 — 읽는 사람이 찾는 것은 대개 그것이다.
                .slice()
                .sort((a, b) => Number(b.is_current) - Number(a.is_current))
                .map((one) => (
                  <li
                    key={`${one.document_revision_id ?? 'none'}`}
                    className="flex flex-wrap items-baseline gap-2"
                  >
                    <span className="text-muted-foreground w-16 shrink-0 text-xs">
                      {one.document_revision_label ?? '판 없음'}
                    </span>
                    <span className={one.is_current ? 'font-medium' : ''}>
                      {one.display || '—'}
                    </span>
                    {one.is_current && (
                      <span className="text-muted-foreground text-xs">지금 값</span>
                    )}
                    {one.note && (
                      <span className="text-muted-foreground text-xs">{one.note}</span>
                    )}
                  </li>
                ))}
            </ul>
          </li>
        ))}
      </ul>
    </div>
  )
}

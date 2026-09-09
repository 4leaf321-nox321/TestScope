/**
 * 축 고르기 — **드롭다운이 아니라 옆에 펼쳐 둔 목록.**
 *
 * 축은 다섯뿐이라 드롭다운으로도 고를 수는 있다. 문제는 고르는 게 아니라 **보는
 * 것**이다. 접혀 있으면 "규격 제정기관에 값이 몇 개나 있지" 를 알려면 한 번씩
 * 열어 봐야 하고, 그 사이 지금 어디를 보고 있었는지가 화면에서 사라진다.
 *
 * 값 수를 함께 그리는 이유도 같다. 비어 있는 축과 채워진 축이 같아 보이면 어디를
 * 채워야 하는지 알 수 없다.
 */

import type { Vocabulary } from '@/modules/vocabulary/api'
import { cn } from '@/shared/lib/utils'

export function AxisList({
  axes,
  current,
  onSelect,
  className,
}: {
  axes: Vocabulary[]
  current: string | null
  onSelect: (slug: string) => void
  className?: string
}) {
  return (
    <ul className={cn('w-56 shrink-0 space-y-1', className)}>
      {axes.map((axis) => (
        <li key={axis.slug}>
          <button
            type="button"
            onClick={() => onSelect(axis.slug)}
            // 축의 뜻을 title 로 달아 둔다 — 편집 화면에는 설명을 그릴 자리가
            // 없는데, 비슷한 축 둘 중 아무 데나 값을 넣는 사고는 거기서 난다.
            title={axis.description ?? undefined}
            aria-current={axis.slug === current ? 'true' : undefined}
            className={cn(
              'flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm',
              axis.slug === current
                ? 'bg-accent text-accent-foreground font-medium'
                : 'text-muted-foreground hover:bg-accent/60',
            )}
          >
            <span className="truncate">{axis.label}</span>
            <span className="text-xs">{axis.term_count}</span>
          </button>
        </li>
      ))}
    </ul>
  )
}

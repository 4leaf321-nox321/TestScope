/**
 * 축 고르기 — **드롭다운이 아니라 옆에 펼쳐 둔 목록.**
 *
 * 축은 일곱뿐이라 드롭다운으로도 고를 수는 있다. 문제는 고르는 게 아니라 **보는
 * 것**이다. 접혀 있으면 "규격 제정기관에 값이 몇 개나 있지" 를 알려면 한 번씩
 * 열어 봐야 하고, 그 사이 지금 어디를 보고 있었는지가 화면에서 사라진다.
 *
 * 값 수를 함께 그리는 이유도 같다. 비어 있는 축과 채워진 축이 같아 보이면 어디를
 * 채워야 하는지 알 수 없다.
 *
 * ## 어디의 축인지로 묶는다
 *
 * 일곱이 한 줄로 서 있으면 「이게 어디 쓰이는 값이지」 를 알 수 없다. 제조사와 규격
 * 제정기관이 나란히 있으면 장비를 등록하러 온 사람이 제정기관에 회사 이름을 넣고,
 * **그 값은 아무도 안 지운다.**
 *
 * 묶음의 이름은 **서버가 준다**(`domain_label`) — 화면이 사전을 들면 축이 하나 늘 때
 * 여기만 안 고쳐진다.
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
  // 서버가 준 순서를 그대로 쓴다(sort_order). **여기서 다시 정렬하지 않는다** —
  // 두 곳에서 순서를 정하면 축이 하나 늘 때 한쪽만 고쳐진다.
  const groups: { domain: string; label: string; axes: Vocabulary[] }[] = []
  for (const axis of axes) {
    const last = groups.at(-1)
    if (last && last.domain === axis.domain) last.axes.push(axis)
    else groups.push({ domain: axis.domain, label: axis.domain_label, axes: [axis] })
  }

  return (
    <div className={cn('w-56 shrink-0 space-y-4', className)}>
      {groups.map((group) => (
        <div key={group.domain} className="space-y-1">
          <p className="text-muted-foreground px-2 text-xs font-medium">{group.label}</p>
          <ul className="space-y-1">
            {group.axes.map((axis) => (
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
        </div>
      ))}
    </div>
  )
}

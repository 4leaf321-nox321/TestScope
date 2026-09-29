/**
 * 조건 축이 **얼마나, 어디까지** 쓰이나 — 온톨로지와 검색 사이의 다리.
 *
 * 그래프에서 「시험 온도」 를 열면 「이 조건을 거는 시험 14건」 까지는 보이는데 **값이 안
 * 보였다.** 그래서 읽는 사람은 「-40 °C 이하인 시험」 을 물으려다 막히고, 이 플랫폼이
 * 그걸 못 한다고 읽었다 — 실제로는 검색(`attr`)이 답하는 물음인데 그 경계가 화면 어디에도
 * 없었다.
 *
 * **구간을 안 나눈다.** 온도를 「-40 이하 / -40~85 / 85 이상」 으로 가르는 근거가 없고
 * 축마다 다르다(VSWR 과 낙하 높이를 같은 규칙으로 못 나눈다). 임의로 나눈 구간은 없는
 * 것보다 나쁘다 — 읽는 사람이 그 경계에 뜻이 있다고 믿는다. 쓰다 보면 자연스러운 경계가
 * 드러나고, 그때 넣으면 된다. 순서가 반대면 아무도 안 쓰는 구간이 화면에 굳는다.
 */

import { Link } from 'react-router-dom'
import { Filter } from 'lucide-react'

import { Button } from '@/shared/components/ui/button'
import { useResource } from '@/shared/hooks/useResource'
import { vocabularyApi } from '@/modules/vocabulary/api'

/** 그래프 노드 id 는 `<종류>:<uuid>` 다. */
function idOf(nodeId: string): string {
  const at = nodeId.indexOf(':')
  return at < 0 ? nodeId : nodeId.slice(at + 1)
}

function fmt(value: number): string {
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(3)))
}

export function ConditionReach({ nodeId }: { nodeId: string }) {
  const reach = useResource(() => vocabularyApi.reach(idOf(nodeId)), [nodeId])
  const found = reach.data
  if (!found) return null

  // 이 축에 걸린 칸이 없으면 신뢰성 시험 쪽에서는 아직 쓸 자리가 없다 — 그 사실만 말한다.
  if (found.definitions.length === 0) {
    return (
      <p className="text-muted-foreground text-xs">
        신뢰성 시험에 이 조건을 적는 칸이 아직 없습니다 — 「공통 → 속성 정의」 에서 만듭니다.
      </p>
    )
  }

  // **값으로 좁히는 자리로 넘긴다.** `attr` 이 받는 것은 축 id 가 아니라 칸의 key 다.
  const link = `/reliability-tests?${found.definitions
    .map((one) => `attr=${encodeURIComponent(`${one.key}*`)}`)
    .join('&')}`

  return (
    <div className="space-y-1.5 rounded-md border p-2">
      <p className="text-xs font-medium">신뢰성 시험에서의 쓰임</p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
        <dt className="text-muted-foreground">이 조건을 거는 시험</dt>
        <dd>{found.test_count}건</dd>
        <dt className="text-muted-foreground">값이 적힌 것</dt>
        <dd>
          {found.valued_count}건
          {found.test_count > found.valued_count && (
            // **칸만 꺼내 놓고 안 채운 것**이 있다는 뜻이다. 안 보이면 「이만큼 쓰인다」 로
            // 읽힌다.
            <span className="text-muted-foreground">
              {' '}
              · {found.test_count - found.valued_count}건은 칸만 있고 값이 없습니다
            </span>
          )}
        </dd>
        {found.low !== null && found.high !== null && (
          <>
            <dt className="text-muted-foreground">적힌 값의 범위</dt>
            <dd>
              {fmt(found.low)} ~ {fmt(found.high)}
              {found.display_unit ? ` ${found.display_unit}` : ''}
            </dd>
          </>
        )}
      </dl>

      {found.unconvertible_count > 0 && (
        // **조용히 빼면 「그만큼만 쓰인다」 로 읽힌다.**
        <p className="text-xs text-amber-700">
          단위를 못 바꿔 범위에서 빠진 시험 {found.unconvertible_count}건 — 위 범위가 전부가
          아닙니다.
        </p>
      )}

      <Button asChild size="sm" variant="outline" className="w-full">
        <Link to={link}>
          <Filter className="mr-1 size-3.5" />
          값으로 좁히기
        </Link>
      </Button>
      {/* 여기서 구간을 안 나누는 이유를 읽는 사람에게도 말해 둔다. */}
      <p className="text-muted-foreground text-xs">
        그래프는 「어느 축을 거는가」 까지 답합니다. 「값이 얼마인가」 는 검색이 답합니다 — 위
        단추가 이 조건이 적힌 시험으로 데려가고, 거기서 <code>{'>='}</code>·<code>{'<='}</code>{' '}
        로 좁힙니다.
      </p>
    </div>
  )
}

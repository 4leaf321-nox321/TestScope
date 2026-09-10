/**
 * 쪽 넘기기 — **몇 중 몇을 보고 있는지 말한다.**
 *
 * 서버가 한 번에 주는 수에는 상한이 있다(`shared/pagination.py`, 200). 화면이 그
 * 상한만큼 받아 그리고 말면 나머지는 **조용히 안 보인다** — 그리고 못 찾은 사람은
 * 「카탈로그에 없구나」 하고 빈 칸으로 저장하거나 같은 것을 새로 만든다. 실제로
 * 그랬다(`ModelPicker` 의 주석).
 *
 * 그래서 이 줄은 단추가 하나도 안 눌리는 상황에서도 **총계를 적는다.** 「714 중
 * 1–50」 이 보이면 지금 보는 것이 전부가 아니라는 사실이 화면에 있다.
 */

import { ChevronLeft, ChevronRight } from 'lucide-react'

import { Button } from '@/shared/components/ui/button'

interface PagerProps {
  total: number
  limit: number
  offset: number
  onOffset: (offset: number) => void
  /** 세는 단위. "기종" 처럼 적는다. */
  unit?: string
}

export function Pager({ total, limit, offset, onOffset, unit = '건' }: PagerProps) {
  const first = total === 0 ? 0 : offset + 1
  const last = Math.min(offset + limit, total)
  const hasPrev = offset > 0
  const hasNext = last < total

  // 한 쪽에 다 담기면 넘길 것이 없다. 그래도 총계는 적는다 — 없으면 「이게 전부인가」
  // 를 화면이 아니라 사람이 세게 된다.
  return (
    <div className="text-muted-foreground flex items-center justify-between gap-4 text-sm">
      <p>
        {total.toLocaleString()}
        {unit} 중 {first.toLocaleString()}–{last.toLocaleString()}
      </p>
      {(hasPrev || hasNext) && (
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={!hasPrev}
            onClick={() => onOffset(Math.max(0, offset - limit))}
          >
            <ChevronLeft className="size-4" />
            이전
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={!hasNext}
            onClick={() => onOffset(offset + limit)}
          >
            다음
            <ChevronRight className="size-4" />
          </Button>
        </div>
      )}
    </div>
  )
}

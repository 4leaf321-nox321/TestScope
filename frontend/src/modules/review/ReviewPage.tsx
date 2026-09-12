/**
 * 검토함 — **후보와 근거를 먼저 보여 주고, 도메인 전문가가 고른다.**
 *
 * 반입이 못 정한 것(어느 시험의 규격인가 · 무슨 조건을 묻나 · 이 물성이 나오나 · 이 사양을
 * 정의로 올리나)이 흩어진 화면마다 「미정」 으로 서 있었다. 정하는 손잡이는 있었지만 무엇을
 * 골라야 하는지가 안 보였다. 여기서는 물음마다 몇 건이 남았는지 한 화면에 세운다 — 0 이면
 * 그 물음은 끝난 것이다.
 */

import { Link } from 'react-router-dom'
import { RefreshCw } from 'lucide-react'
import { useState } from 'react'

import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { Button } from '@/shared/components/ui/button'
import { useResource } from '@/shared/hooks/useResource'
import { reviewApi } from '@/modules/review/api'

export default function ReviewPage() {
  const queues = useResource(() => reviewApi.queues(), [])
  const [busy, setBusy] = useState(false)

  return (
    <div className="space-y-6">
      <PageHeader
        title="검토함"
        description="반입이 못 정한 것을 후보와 근거와 함께 세워 둡니다. 고르면 기존 규칙대로 적용되고, 누가 골랐는지 남습니다."
        actions={
          <Button
            variant="outline"
            disabled={busy}
            onClick={async () => {
              setBusy(true)
              try {
                await reviewApi.refresh()
                queues.reload()
              } finally {
                setBusy(false)
              }
            }}
          >
            <RefreshCw className="mr-1 size-4" />
            후보 다시 세우기
          </Button>
        }
      />
      <ErrorNotice error={queues.error} />

      <ul className="grid gap-3 sm:grid-cols-2">
        {(queues.data ?? []).map((one) => (
          <li key={one.key} className="rounded-md border p-4">
            <div className="flex items-baseline justify-between gap-3">
              <h2 className="text-base font-semibold">{one.label}</h2>
              {/* **0 이면 끝난 것이다.** 숫자를 크게 — 이 화면의 물음은 「얼마나 남았나」 다. */}
              <span
                className={
                  one.open === 0 ? 'text-muted-foreground text-2xl' : 'text-2xl font-semibold'
                }
              >
                {one.open}
              </span>
            </div>
            <p className="text-muted-foreground mt-1 text-sm">{one.description}</p>
            <p className="text-muted-foreground mt-2 text-xs">
              정함 {one.decided} · 건너뜀 {one.skipped}
              {one.gone > 0 && ` · 대상 없어짐 ${one.gone}`}
            </p>
            <div className="mt-3">
              {one.open > 0 ? (
                <Button asChild size="sm">
                  <Link to={`/admin/review/${one.key}`}>고르러 가기</Link>
                </Button>
              ) : (
                <Button asChild size="sm" variant="outline">
                  <Link to={`/admin/review/${one.key}?status=decided`}>정한 것 보기</Link>
                </Button>
              )}
            </div>
          </li>
        ))}
      </ul>

      <p className="text-muted-foreground text-xs">
        후보는 반입(카탈로그)과 정본의 추천(
        <span className="font-mono">source/catalog/proposals</span>)에서 옵니다. 추천은 정답이
        아닙니다 — 근거를 읽고, 아니면 직접 고르세요. 건너뛴 것은 다시 뜹니다.
      </p>
    </div>
  )
}

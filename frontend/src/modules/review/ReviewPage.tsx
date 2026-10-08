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
import { useAuth } from '@/shared/auth/AuthContext'
import { useResource } from '@/shared/hooks/useResource'
import { reviewApi } from '@/modules/review/api'

export default function ReviewPage() {
  const queues = useResource(() => reviewApi.queues(), [])
  const [busy, setBusy] = useState(false)
  const isAdmin = useAuth().user?.is_system_admin ?? false

  return (
    <div className="space-y-6">
      <PageHeader
        title="검토함"
        description="반입 과정에서 정하지 못한 항목을 후보·근거와 함께 표시. 의견 제출은 누구나 가능, 시스템 관리자 확정 시 기존 규칙대로 적용."
        actions={
          isAdmin && (
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
              후보 재생성
            </Button>
          )
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
              {one.voted > 0 && `의견 있음 ${one.voted} · `}
              정함 {one.decided} · 건너뜀 {one.skipped}
              {one.gone > 0 && ` · 대상 삭제됨 ${one.gone}`}
            </p>
            <div className="mt-3">
              {one.open > 0 ? (
                <Button asChild size="sm">
                  <Link to={`/admin/review/${one.key}`}>{isAdmin ? '선택' : '의견 제출'}</Link>
                </Button>
              ) : (
                <Button asChild size="sm" variant="outline">
                  <Link to={`/admin/review/${one.key}?status=decided`}>결정 완료 보기</Link>
                </Button>
              )}
            </div>
          </li>
        ))}
      </ul>

      {/**
       * **시험 항목 제안은 다른 표에서 온다** — 위 목록은 반입·정본이 세운 후보인데,
       * 이것은 AI 가 문서를 읽다 「축에 없다」 고 남긴 말이다. 한 화면에 모아 두는 이유는
       * 「검토하러 오는 자리」 가 하나여야 사람이 그 습관을 들이기 때문이다.
       */}
      <div className="rounded-md border p-4">
        <h2 className="text-base font-semibold">시험 항목 제안</h2>
        <p className="text-muted-foreground mt-1 text-sm">
          AI가 문서에서 읽었으나 시험 항목 축에 없던 말. 축이 닫혀 있어 AI는 값 추가 불가. 축에
          등록하거나 기존 값에 연결하면 해당 말을 낸 시험 전체에 일괄 반영됨.
        </p>
        <div className="mt-3">
          <Button asChild size="sm" variant="outline">
            <Link to="/admin/item-proposals">보기</Link>
          </Button>
        </div>
      </div>

      {/**
       * **같은 모양의 다른 축** — 카탈로그 기종도 시스템 관리자만 세운다(기종을 고르면 그
       * 계열의 시험 항목이 복사되고 조건 판정이 그 사양을 쓴다). 못 세우는 쪽에 말할 자리를
       * 둔 것이 시험 항목 제안과 같아서, 검토하러 오는 자리도 같아야 한다.
       */}
      <div className="rounded-md border p-4">
        <h2 className="text-base font-semibold">기종 등록 요청</h2>
        <p className="text-muted-foreground mt-1 text-sm">
          장비 등록 시 카탈로그에서 찾지 못한 기종. 계열 선택 후 등록하면 해당 기종을 요청한
          장비 전체가 일괄 연결됨(장비별 재편집 불필요).
        </p>
        <div className="mt-3">
          <Button asChild size="sm" variant="outline">
            <Link to="/admin/model-proposals">보기</Link>
          </Button>
        </div>
      </div>

      {/**
       * **요청이 없는 미연결 장비까지** — 대장으로 들인 장비는 요청 없이 미연결로 남는다.
       * 왜 미연결인지(같은 기종 있음 · 계열만 있음 · 정본에 없음 · 모델명 없음)로 갈라 둔
       * 목록이라, 요청 화면 옆에 문을 둔다.
       */}
      <div className="rounded-md border p-4">
        <h2 className="text-base font-semibold">카탈로그 보강</h2>
        <p className="text-muted-foreground mt-1 text-sm">
          카탈로그 기종에 연결되지 않은 장비 전체를 사유별로 분류. 같은 기종이 있으면 연결,
          계열만 있으면 기종 등록, 카탈로그에 없으면 CSV로 사양서 조사. 시스템 관리자 전용.
        </p>
        <div className="mt-3">
          <Button asChild size="sm" variant="outline">
            <Link to="/admin/catalog-gaps">보기</Link>
          </Button>
        </div>
      </div>

      <p className="text-muted-foreground text-xs">
        후보 출처: 반입(카탈로그)과 정본의 추천(
        <span className="font-mono">source/catalog/proposals</span>). 추천은 정답이 아님. 근거
        확인 후 맞지 않으면 직접 선택. 의견은 수집만 되며 데이터 변경 없음. 데이터는 확정 시
        변경됨.
      </p>
    </div>
  )
}

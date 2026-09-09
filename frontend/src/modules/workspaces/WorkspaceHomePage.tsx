/**
 * 부서 홈 — **남은 일이 먼저 온다.**
 *
 * 관리 화면에 들어가야만 보이는 목록은 아무도 안 본다. 승인 대기가 며칠씩
 * 방치되고, 역량이 안 적힌 장비는 영영 안 적힌다.
 */

import { Link, useParams } from 'react-router-dom'

import { api } from '@/shared/api/client'
import { useAuth } from '@/shared/auth/AuthContext'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { Button } from '@/shared/components/ui/button'
import { useResource } from '@/shared/hooks/useResource'
import { shownDate } from '@/shared/lib/datetime'

interface MaintenanceItem {
  key: string
  label: string
  count: number
  link: string | null
  severity: string
}

interface CalibrationDue {
  equipment_id: string
  asset_no: string
  name: string
  next_due_on: string
  /** 음수면 이미 지났다. **지난 것을 빼지 않는다** — 빼면 조용히 계속 쓰인다. */
  days_left: number
}

export default function WorkspaceHomePage() {
  const { slug } = useParams<{ slug?: string }>()
  const { user } = useAuth()
  const maintenance = useResource(() => api.get<MaintenanceItem[]>('/server/maintenance'), [])
  const due = useResource(() => api.get<CalibrationDue[]>('/server/calibrations-due'), [])

  const workspace = user?.memberships.find((one) => one.slug === slug)

  return (
    <div className="space-y-8">
      <PageHeader
        title={workspace?.name ?? 'TestAtlas'}
        description="어떤 시험이 가능한지 찾고, 우리 장비의 역량을 채워 넣는 곳입니다."
        actions={
          <Button asChild>
            <Link to="/search">역량 검색</Link>
          </Button>
        }
      />

      <ErrorNotice error={maintenance.error} />

      <section className="space-y-3">
        <h2 className="text-base font-semibold">남은 일</h2>
        {/* **0 건인 항목은 서버가 안 내보낸다.** 다 0 인 목록을 매일 보면 사람은
            그 자리를 아예 안 읽게 되고, 그때 진짜 하나가 떠도 눈에 안 들어온다. */}
        {maintenance.data && maintenance.data.length === 0 ? (
          <p className="text-muted-foreground text-sm">지금 처리할 일이 없습니다.</p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {(maintenance.data ?? []).map((one) => (
              <li
                key={one.key}
                className={
                  one.severity === 'warning'
                    ? 'rounded-md border border-amber-500/40 bg-amber-500/5 p-4'
                    : 'rounded-md border p-4'
                }
              >
                <p className="text-2xl font-semibold">{one.count}</p>
                <p className="text-sm">{one.label}</p>
                {one.link && (
                  <Link
                    to={one.link}
                    className="text-muted-foreground mt-2 block text-xs underline"
                  >
                    보러 가기
                  </Link>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-base font-semibold">교정 예정·만료</h2>
        {due.data && due.data.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            60일 안에 교정이 필요한 장비가 없습니다.
          </p>
        ) : (
          <ul className="space-y-2">
            {(due.data ?? []).map((one) => (
              <li key={one.equipment_id} className="flex items-center gap-3 text-sm">
                <Link to={`/equipment/${one.equipment_id}`} className="hover:underline">
                  {one.asset_no} · {one.name}
                </Link>
                <span className="text-muted-foreground">{shownDate(one.next_due_on)}</span>
                <span className={one.days_left < 0 ? 'text-destructive' : 'text-amber-600'}>
                  {one.days_left < 0 ? `${-one.days_left}일 지남` : `${one.days_left}일 남음`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

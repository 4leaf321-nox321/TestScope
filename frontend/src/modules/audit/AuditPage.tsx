/**
 * 변경 이력.
 *
 * **만들기·고치기·지우기가 없다.** 고칠 수 있으면 감사가 아니다 — 쓰는 길은
 * 서버의 도메인 코드 하나뿐이다.
 *
 * 여기 남는 것은 **되돌릴 수 없거나 권한이 실린 일**만이다. 값 하나 고친 것까지
 * 남기면 그 안에서 정작 찾을 것을 못 찾는다.
 */

import { api } from '@/shared/api/client'
import type { Page } from '@/shared/api/paging'
import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table'
import { useResource } from '@/shared/hooks/useResource'
import { shownDateTime } from '@/shared/lib/datetime'

interface AuditEntry {
  id: string
  action: string
  /** **그때의 이름이다.** 계정이 지워져도 누가 했는지는 남아야 한다. */
  actor_label: string
  target_table: string
  target_id: string | null
  target_label: string
  changes: Record<string, { before?: unknown; after?: unknown }>
  reason: string | null
  /** 접근 로그·파일 로그와 잇는 끈. 이 값으로 그 요청의 전말을 볼 수 있다. */
  request_id: string | null
  created_at: string
}

function shownChanges(changes: AuditEntry['changes']): string {
  const parts = Object.entries(changes).map(
    ([key, value]) => `${key}: ${String(value.before ?? '—')} -> ${String(value.after ?? '—')}`,
  )
  return parts.join(', ') || '—'
}

export default function AuditPage() {
  const page = useResource(() => api.get<Page<AuditEntry>>('/audit/entries'), [])

  return (
    <div className="space-y-6">
      <PageHeader
        title="변경 이력"
        description="되돌릴 수 없거나 권한이 실린 변경만 남습니다. 여기서는 고칠 수 없습니다."
      />

      <ErrorNotice error={page.error} />

      {page.data && page.data.items.length === 0 ? (
        <EmptyState title="기록이 없습니다" hint="아직 남길 만한 변경이 없었습니다." />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>시각</TableHead>
              <TableHead>한 일</TableHead>
              <TableHead>누가</TableHead>
              <TableHead>대상</TableHead>
              <TableHead>바뀐 것</TableHead>
              <TableHead>요청 ID</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(page.data?.items ?? []).map((one) => (
              <TableRow key={one.id}>
                <TableCell className="whitespace-nowrap">
                  {shownDateTime(one.created_at)}
                </TableCell>
                <TableCell className="font-mono text-xs">{one.action}</TableCell>
                <TableCell>{one.actor_label}</TableCell>
                <TableCell>{one.target_label}</TableCell>
                <TableCell className="text-muted-foreground text-xs">
                  {shownChanges(one.changes)}
                  {one.reason && <p className="mt-1">사유: {one.reason}</p>}
                </TableCell>
                {/* **로그와 잇는 끈이다.** 이 값으로 app.log 에서 그 요청의 모든
                    줄을 찾을 수 있다. */}
                <TableCell className="font-mono text-xs">{one.request_id ?? '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}

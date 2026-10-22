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
  /** 어느 통로로 — 비면 화면, `mcp` 면 AI 도구, `mcp:confirmed` 면 AI 화면에서 사람이 수락. */
  actor_client: string | null
  /** 쓴 개인 토큰의 이름. */
  actor_token: string | null
  target_table: string
  target_id: string | null
  target_label: string
  changes: Record<string, { before?: unknown; after?: unknown }>
  reason: string | null
  /** 접근 로그·파일 로그와 잇는 끈. 이 값으로 그 요청의 전말을 볼 수 있다. */
  request_id: string | null
  created_at: string
}

/**
 * 누가 **어느 통로로** 했나. 「관리자가 바꿨다」 만으로는 그 관리자가 직접 눌렀는지, 자기 토큰을 쥔
 * AI 가 혼자 했는지, AI 화면의 확인 창에서 수락했는지 모른다 — 셋은 다른 이야기다.
 */
function shownChannel(one: AuditEntry): string {
  if (one.actor_client === 'mcp:confirmed') return 'MCP · 사용자 확인'
  if (one.actor_token) return 'MCP'
  if (one.actor_client === 'mcp') return 'MCP'
  return '화면'
}

function shownChanges(changes: AuditEntry['changes']): string {
  const parts = Object.entries(changes).map(
    ([key, value]) =>
      `${key}: ${String(value.before ?? '—')} -> ${String(value.after ?? '—')}`,
  )
  return parts.join(', ') || '—'
}

export default function AuditPage() {
  const page = useResource(() => api.get<Page<AuditEntry>>('/audit/entries'), [])

  return (
    <div className="space-y-6">
      <PageHeader
        title="변경 이력"
        description="되돌릴 수 없거나 권한 관련 변경만 기록됨. 이 화면에서는 수정 불가."
      />

      <ErrorNotice error={page.error} />

      {page.data && page.data.items.length === 0 ? (
        <EmptyState title="기록 없음" hint="기록 대상 변경 없음." />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>시각</TableHead>
              <TableHead>작업</TableHead>
              <TableHead>수행자</TableHead>
              <TableHead>통로</TableHead>
              <TableHead>대상</TableHead>
              <TableHead>변경 내용</TableHead>
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
                <TableCell className="text-xs whitespace-nowrap">
                  {shownChannel(one)}
                  {one.actor_token && (
                    <span className="text-muted-foreground block">{one.actor_token}</span>
                  )}
                </TableCell>
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

/**
 * **대체된 규격을 아직 가리키는 곳** — 신뢰성 시험의 근거 규격 · 장비 시험 항목의 규격.
 *
 * 규격의 판이 바뀌면 옛 판은 「대체됨」 으로 남는데, 그 옛 판을 근거로 적어 둔 시험과 장비는
 * 아무도 모르게 옛 판에 머물렀다(2026-10-16). 여기서 규격마다 모아 보고 고칠 화면으로 간다.
 * 새 판으로 고치면 목록에서 저절로 빠진다 — 서버가 그때그때 센다.
 */

import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

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
import { useAuth } from '@/shared/auth/AuthContext'
import { useResource } from '@/shared/hooks/useResource'
import { methodApi } from '@/modules/methods/api'
import type { SupersededRef } from '@/modules/methods/api'

const KIND_LABEL: Record<string, string> = {
  reliability_test: '신뢰성 시험',
  equipment: '장비 시험 항목',
}

export default function SupersededRefsPage() {
  const { user } = useAuth()
  const isAdmin = user?.is_system_admin ?? false
  /** 내 소속만 볼까, 전부 볼까. 시스템 관리자는 늘 전부. */
  const [all, setAll] = useState(false)
  const refs = useResource(() => methodApi.supersededRefs(all), [all])

  /** 옛 판마다 한 묶음 — 같은 규격을 가리키는 곳을 한 번에 고친다. */
  const groups = useMemo(() => {
    const out = new Map<string, { head: SupersededRef; rows: SupersededRef[] }>()
    for (const one of refs.data ?? []) {
      const held = out.get(one.method_id)
      if (held) held.rows.push(one)
      else out.set(one.method_id, { head: one, rows: [one] })
    }
    return [...out.values()]
  }, [refs.data])

  return (
    <div className="space-y-6">
      <PageHeader
        back={{ to: '/methods', label: '시험법·규격' }}
        title="대체된 규격을 가리키는 곳"
        description="옛 판(대체됨)을 근거로 적은 신뢰성 시험과 장비 시험 항목. 새 판으로 고치면 목록에서 빠짐. 신뢰성 시험은 사업부 화면, 장비는 장비 화면의 시험 항목에서 수정."
      />

      {!isAdmin && (
        <label className="text-muted-foreground flex items-center gap-1.5 text-sm">
          <input
            type="checkbox"
            checked={all}
            onChange={(event) => setAll(event.target.checked)}
            className="size-3.5"
          />
          다른 부서 것도 보기
        </label>
      )}

      <ErrorNotice error={refs.error} />

      {refs.data && groups.length === 0 ? (
        <EmptyState
          title="대체된 규격을 가리키는 곳 없음"
          hint={
            isAdmin || all
              ? undefined
              : '내 소속 부서·사업부 기준. 다른 부서 것도 보려면 위 체크.'
          }
        />
      ) : (
        groups.map(({ head, rows }) => (
          <section key={head.method_id} className="space-y-2">
            <h2 className="text-base font-semibold">
              <Link to={`/methods/${head.method_id}`} className="hover:underline">
                {head.method_label}
              </Link>
              <span className="text-muted-foreground font-normal"> → </span>
              {head.successor_id ? (
                <Link to={`/methods/${head.successor_id}`} className="hover:underline">
                  {head.successor_label}
                </Link>
              ) : (
                <span className="text-muted-foreground text-sm font-normal">
                  대체한 규격 미지정
                </span>
              )}
              <span className="text-muted-foreground ml-2 text-sm font-normal">
                {rows.length}곳
              </span>
            </h2>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>종류</TableHead>
                  <TableHead>대상</TableHead>
                  <TableHead>소속</TableHead>
                  <TableHead>가리키는 칸</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((one) => (
                  <TableRow key={`${one.kind}-${one.target_id}-${one.detail}`}>
                    <TableCell className="whitespace-nowrap">
                      {KIND_LABEL[one.kind] ?? one.kind}
                    </TableCell>
                    <TableCell>
                      <Link to={one.link} className="hover:underline">
                        {one.target_label}
                      </Link>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{one.owner ?? '—'}</TableCell>
                    <TableCell className="text-muted-foreground">{one.detail}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </section>
        ))
      )}
    </div>
  )
}

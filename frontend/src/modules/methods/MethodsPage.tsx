/**
 * 시험법·규격 목록.
 *
 * **가능 장비 수를 한 칸으로 보여 준다.** 0 인 규격은 지금 우리가 못 하는 시험이고,
 * 그 사실이 목록에 보여야 "이건 외주" 라는 판단이 선다.
 *
 * 기본은 현행만 보여 준다 — 대체된 판이 섞여 있으면 사람이 옛 규격을 고르고, 그
 * 사실은 시험이 끝난 뒤에야 드러난다.
 */

import { useState } from 'react'
import { Plus } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useAuth } from '@/shared/auth/AuthContext'
import { isAnyManager } from '@/shared/auth/roles'
import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table'
import { useResource } from '@/shared/hooks/useResource'
import { methodApi } from '@/modules/methods/api'
import { NewMethodDialog } from '@/modules/methods/NewMethodDialog'

export default function MethodsPage() {
  const { user } = useAuth()
  const [query, setQuery] = useState('')
  const [includeSuperseded, setIncludeSuperseded] = useState(false)
  const [creating, setCreating] = useState(false)
  const page = useResource(
    () => methodApi.list({ q: query || undefined, includeSuperseded }),
    [query, includeSuperseded],
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="시험법·규격"
        description="규격이 요구하는 조건을 적어 두면, 검색이 그 숫자를 그대로 물어 줍니다."
        actions={
          isAnyManager(user) ? (
            <Button onClick={() => setCreating(true)}>
              <Plus className="size-4" />
              시험법 등록
            </Button>
          ) : undefined
        }
      />

      <div className="flex flex-wrap items-center gap-3">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="규격 번호 또는 제목"
          className="max-w-sm"
        />
        <label className="text-muted-foreground flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={includeSuperseded}
            onChange={(event) => setIncludeSuperseded(event.target.checked)}
          />
          대체된 판도 보기
        </label>
      </div>

      <ErrorNotice error={page.error} />

      {page.data && page.data.items.length === 0 ? (
        <EmptyState
          title="시험법이 없습니다"
          hint="규격을 등록해 두면 장비 시험 항목에 그 규격을 걸 수 있고, 검색이 규격의 요구 조건을 자동으로 채웁니다."
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>규격</TableHead>
              <TableHead>판</TableHead>
              <TableHead>제목</TableHead>
              <TableHead>시험 항목</TableHead>
              <TableHead className="text-right">요구 조건</TableHead>
              <TableHead className="text-right">가능 장비</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(page.data?.items ?? []).map((one) => (
              <TableRow
                key={one.id}
                className={one.status === 'superseded' ? 'opacity-60' : undefined}
              >
                <TableCell className="font-medium">
                  <Link to={`/methods/${one.id}`} className="hover:underline">
                    {one.code}
                  </Link>
                </TableCell>
                <TableCell>{one.edition ?? '—'}</TableCell>
                <TableCell className="max-w-md truncate">{one.title}</TableCell>
                <TableCell>{one.test_item ?? '—'}</TableCell>
                <TableCell className="text-right">{one.requirements.length}</TableCell>
                <TableCell className="text-right">
                  {/* **0 을 그냥 0 으로 두지 않는다.** 그것이 이 표에서 가장 중요한 칸이다. */}
                  {one.equipment_count === 0 ? (
                    <span className="text-amber-600">없음</span>
                  ) : (
                    one.equipment_count
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <NewMethodDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={() => {
          setCreating(false)
          page.reload()
        }}
      />
    </div>
  )
}

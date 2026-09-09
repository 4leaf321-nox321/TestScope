/**
 * 보유 장비 목록.
 *
 * **역량 수를 한 칸으로 보여 준다.** 0 인 장비는 검색에 절대 안 걸리는데, 목록에서
 * 그것이 안 보이면 아무도 채우지 않는다 — 그리고 사람들은 시스템이 있는데도
 * 여전히 전화를 돌린다.
 */

import { useState } from 'react'
import { Plus } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useAuth } from '@/shared/auth/AuthContext'
import { isAnyManager } from '@/shared/auth/roles'
import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { StatusBadge } from '@/shared/components/StatusBadge'
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
import { shownDate } from '@/shared/lib/datetime'
import { equipmentApi } from '@/modules/equipment/api'
import { NewEquipmentDialog } from '@/modules/equipment/NewEquipmentDialog'

export default function EquipmentPage() {
  const { user } = useAuth()
  const [query, setQuery] = useState('')
  const [creating, setCreating] = useState(false)
  const page = useResource(() => equipmentApi.list({ q: query || undefined }), [query])

  const canCreate = isAnyManager(user)

  return (
    <div className="space-y-6">
      <PageHeader
        title="보유 장비"
        description="자산번호·이름으로 찾습니다. 역량이 0 인 장비는 검색에 걸리지 않습니다."
        actions={
          // **볼 수 있는 것만 보여 준다.** 눌러야 403 을 아는 단추는 할 수 있는
          // 일을 알려 주지 못한다. 판정은 서버가 다시 한다.
          canCreate ? (
            <Button onClick={() => setCreating(true)}>
              <Plus className="size-4" />
              장비 등록
            </Button>
          ) : undefined
        }
      />

      <Input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="자산번호 또는 장비 이름"
        className="max-w-sm"
      />

      <ErrorNotice error={page.error} />

      {page.data && page.data.items.length === 0 ? (
        <EmptyState
          title="장비가 없습니다"
          hint={
            query
              ? '찾는 말과 맞는 장비가 없습니다. 자산번호 일부만 넣어 보세요.'
              : '아직 등록된 장비가 없습니다. 부서 관리자가 등록할 수 있습니다.'
          }
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>자산번호</TableHead>
              <TableHead>이름</TableHead>
              <TableHead>분류</TableHead>
              <TableHead>보유</TableHead>
              <TableHead>위치</TableHead>
              <TableHead>상태</TableHead>
              <TableHead>시험 항목</TableHead>
              <TableHead>교정 예정</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(page.data?.items ?? []).map((one) => (
              <TableRow key={one.id}>
                <TableCell className="font-mono text-xs">
                  <Link to={`/equipment/${one.id}`} className="hover:underline">
                    {one.asset_no}
                  </Link>
                </TableCell>
                <TableCell>
                  <Link to={`/equipment/${one.id}`} className="hover:underline">
                    {one.name}
                  </Link>
                </TableCell>
                <TableCell>
                  {one.category ?? '—'}
                  {one.model_name && (
                    <p className="text-muted-foreground text-xs">
                      {[one.series_name, one.model_name].filter(Boolean).join(' · ')}
                    </p>
                  )}
                </TableCell>
                <TableCell>{one.workspace_name ?? '전사'}</TableCell>
                <TableCell>
                  {[one.site, one.location].filter(Boolean).join(' · ') || '—'}
                </TableCell>
                <TableCell>
                  <StatusBadge kind="equipment" value={one.status} />
                </TableCell>
                <TableCell>
                  {/* **이 표에서 가장 중요한 칸이다.** 「우리가 무슨 시험을 할 수
                      있나」 가 이 시스템이 존재하는 이유고, 그 답이 여기 있다.
                      비어 있으면 그 장비는 검색에 절대 안 걸린다. */}
                  {one.test_items.length === 0 ? (
                    <span className="text-amber-600">미등록</span>
                  ) : (
                    <span className="flex flex-wrap gap-1">
                      {one.test_items.slice(0, 4).map((item) => (
                        <span
                          key={item}
                          className="bg-muted rounded px-1.5 py-0.5 text-xs"
                        >
                          {item}
                        </span>
                      ))}
                      {one.test_items.length > 4 && (
                        <span className="text-muted-foreground text-xs">
                          외 {one.test_items.length - 4}
                        </span>
                      )}
                    </span>
                  )}
                </TableCell>
                <TableCell>{shownDate(one.calibration_due_on)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <NewEquipmentDialog
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

/**
 * 장비 기종 — **보유 장비가 가리키는 것.**
 *
 * 계열 아래의 한 기종이다(ADR 0006). 계열별로 보려면 계열 상세로 가고, 여기는
 * **기종을 이름으로 찾는 자리**다 — 라벨의 `68FM-300` 만 아는 채로 오는 일이 흔하다.
 *
 * 보유 대수를 함께 보여 주는 이유: **카탈로그가 답해야 하는 첫 물음이 그것**이고,
 * 전에는 기종이 행이 아니라 문자열이라 셀 수가 없었다.
 */

import { useState } from 'react'
import { Plus } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'

import { useAuth } from '@/shared/auth/AuthContext'
import { isSystemAdmin } from '@/shared/auth/roles'
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
import { catalogApi } from '@/modules/equipment/api'
import { NewEquipmentModelDialog } from '@/modules/equipment/NewEquipmentModelDialog'

/** 홈의 「남은 일」 이 거는 필터. 그 줄을 눌러 온 사람에게 **왜 이 목록인지**를
 *  말해 준다 — 안 말하면 목록이 짧은 것을 오류로 읽는다. */
const ISSUE_NOTE: Record<string, string> = {
  specs: '사양이 하나도 안 적힌 기종입니다. 비워 두면 이 기종으로 등록하는 장비가 조건 없이 복사되고, 검색은 그것을 「모름」 으로 답합니다.',
  uncertain:
    '반입이 원본 카탈로그의 표를 잘못 읽었을 수 있다고 표시한 기종입니다. 원본을 열어 확인한 뒤 비고의 표시를 지우세요.',
}

export default function EquipmentModelsPage() {
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const owned = params.get('owned') === '1' || params.get('owned') === 'true'
  const issue = params.get('issue') ?? undefined
  const [query, setQuery] = useState('')
  const [creating, setCreating] = useState(false)
  const page = useResource(
    () => catalogApi.list({ q: query || undefined, owned, issue, limit: 200 }),
    [query, owned, issue],
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="장비 기종"
        description="보유 장비는 여기서 기종을 골라 만듭니다. 무슨 시험이 되는지는 그 기종이 속한 계열이 정합니다."
        actions={
          // 전사 공용이라 시스템 관리자만 고친다 — 한 부서가 고치면 다른 부서가
          // 가리키던 모델의 뜻이 바뀐다.
          isSystemAdmin(user) ? (
            <Button onClick={() => setCreating(true)}>
              <Plus className="size-4" />
              기종 등록
            </Button>
          ) : undefined
        }
      />

      {(owned || issue) && (
        <div className="bg-muted/50 flex flex-wrap items-center gap-3 rounded-md border p-3">
          <p className="text-sm">
            {owned && <strong>보유한 기종만</strong>}
            {owned && issue && ' · '}
            {issue && (ISSUE_NOTE[issue] ?? '걸러진 목록입니다.')}
          </p>
          <Button size="sm" variant="outline" onClick={() => setParams({})}>
            필터 풀기
          </Button>
        </div>
      )}

      <Input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="기종명·계열명 또는 제조사"
        className="max-w-sm"
      />

      <ErrorNotice error={page.error} />

      {page.data && page.data.items.length === 0 ? (
        <EmptyState
          title="기종이 없습니다"
          hint={
            query
              ? '찾는 말과 맞는 기종이 없습니다.'
              : '기종을 등록해 두면 같은 장비를 여러 대 들일 때 사양을 한 번만 적으면 됩니다.'
          }
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>기종</TableHead>
              <TableHead>계열</TableHead>
              <TableHead>제조사</TableHead>
              <TableHead className="text-right">시험 항목</TableHead>
              <TableHead className="text-right">보유</TableHead>
              <TableHead>상태</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(page.data?.items ?? []).map((one) => (
              <TableRow
                key={one.id}
                className={one.status === 'discontinued' ? 'opacity-60' : undefined}
              >
                <TableCell className="font-medium">
                  <Link
                    to={`/catalog/equipment-models/${one.id}`}
                    className="hover:underline"
                  >
                    {one.name}
                  </Link>
                </TableCell>
                <TableCell>
                  <Link
                    to={`/catalog/equipment-series/${one.series_id}`}
                    className="text-muted-foreground hover:underline"
                  >
                    {one.series_name}
                  </Link>
                </TableCell>
                <TableCell>{one.maker ?? '—'}</TableCell>
                <TableCell className="text-right">
                  {/* 0 이면 이 기종으로 장비를 등록해도 복사될 것이 없다.
                      역량은 계열이 갖는다(ADR 0006). */}
                  {one.capabilities.length === 0 ? (
                    <span className="text-amber-600">미등록</span>
                  ) : (
                    one.capabilities.length
                  )}
                </TableCell>
                <TableCell className="text-right">
                  {/* **대수만 보면 여유 있어 보인다.** 다섯 대 중 한 대만 가동인
                      경우가 있어서 가동 수를 함께 적는다. */}
                  {one.unit_count === 0
                    ? '—'
                    : `${one.unit_count}대 (가동 ${one.operational_count})`}
                </TableCell>
                <TableCell>{one.status === 'active' ? '현행' : '단종'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <NewEquipmentModelDialog
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

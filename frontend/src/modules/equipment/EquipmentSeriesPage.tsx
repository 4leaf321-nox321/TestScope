/**
 * 장비 계열 카탈로그 — **제조사가 파는 계열.**
 *
 * 보유 장비와 다른 층이다(ADR 0004). 여기는 사양서고, 저기는 우리가 가진 개체다.
 *
 * 계열과 기종을 나눈 이유는 ADR 0006 에 있다: 한 계열 안에서 하중 용량이 중앙값
 * 60배, 최대 1200배 갈린다. 계열을 한 줄로 두면 0.5 kN 짜리 한 대를 가진 부서가
 * 「300 kN 인장 되나요」 에 된다고 답한다.
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
import { seriesApi } from '@/modules/equipment/api'
import { NewEquipmentSeriesDialog } from '@/modules/equipment/NewEquipmentSeriesDialog'

/** 부속을 목록에서 가르는 표. 챔버와 시험기가 한 줄씩 섞이면 「우리가 무슨 장비를
 *  가졌나」 가 안 보인다. */
const KIND_LABEL: Record<string, string> = {
  main: '본체',
  accessory: '부속',
  sensor: '센서',
  software: '소프트웨어',
}

export default function EquipmentSeriesPage() {
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const owned = params.get('owned') === '1' || params.get('owned') === 'true'
  const issue = params.get('issue') ?? undefined
  const [query, setQuery] = useState('')
  // 「남은 일」 에서 왔으면 종류로 좁히지 않는다 — 부속 계열도 역량이 빌 수 있다.
  const [kind, setKind] = useState(issue ? '' : 'main')
  const [creating, setCreating] = useState(false)
  const page = useResource(
    () =>
      seriesApi.list({
        q: query || undefined,
        kind: kind || undefined,
        owned,
        issue,
        limit: 200,
      }),
    [query, kind, owned, issue],
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="장비 계열"
        description="제조사가 파는 계열의 목록입니다. 무슨 시험이 되는지는 계열이 정하고, 어디까지 되는지는 그 안의 기종이 정합니다."
        actions={
          // 전사 공용이라 시스템 관리자만 고친다 — 한 부서가 고치면 다른 부서가
          // 가리키던 계열의 뜻이 바뀐다.
          isSystemAdmin(user) ? (
            <Button onClick={() => setCreating(true)}>
              <Plus className="size-4" />
              계열 등록
            </Button>
          ) : undefined
        }
      />

      {(owned || issue) && (
        <div className="bg-muted/50 flex flex-wrap items-center gap-3 rounded-md border p-3">
          <p className="text-sm">
            {owned && <strong>보유한 계열만</strong>}
            {owned && issue && ' · '}
            {issue === 'capabilities' &&
              '시험 항목이 하나도 안 적힌 계열입니다. 비워 두면 이 계열의 기종으로 장비를 등록해도 복사될 역량이 없어, 그 장비는 검색에 안 걸립니다.'}
          </p>
          <Button size="sm" variant="outline" onClick={() => setParams({})}>
            필터 풀기
          </Button>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="계열명·한글명 또는 제조사"
          className="max-w-sm"
        />
        <div className="flex gap-1">
          {[
            ['main', '본체'],
            ['accessory', '부속'],
            ['', '전체'],
          ].map(([value, label]) => (
            <Button
              key={label}
              size="sm"
              variant={kind === value ? 'default' : 'outline'}
              onClick={() => setKind(value)}
            >
              {label}
            </Button>
          ))}
        </div>
      </div>

      <ErrorNotice error={page.error} />

      {page.data && page.data.items.length === 0 ? (
        <EmptyState
          title="계열이 없습니다"
          hint={
            query
              ? '찾는 말과 맞는 계열이 없습니다.'
              : '계열을 등록해 두면 같은 계열의 기종을 여러 개 들일 때 시험 항목을 한 번만 적으면 됩니다.'
          }
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>계열</TableHead>
              <TableHead>제조사</TableHead>
              <TableHead>분류</TableHead>
              <TableHead className="text-right">기종</TableHead>
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
                    to={`/catalog/equipment-series/${one.id}`}
                    className="hover:underline"
                  >
                    {one.name_ko || one.name}
                  </Link>
                  {one.kind !== 'main' && (
                    <span className="text-muted-foreground ml-2 text-xs">
                      {KIND_LABEL[one.kind] ?? one.kind}
                    </span>
                  )}
                </TableCell>
                <TableCell>
                  {one.maker ?? '—'}
                  {one.brand && (
                    <span className="text-muted-foreground ml-1 text-xs">{one.brand}</span>
                  )}
                </TableCell>
                <TableCell>{one.category ?? '—'}</TableCell>
                <TableCell className="text-right">
                  {/* **0 이면 아무도 이 계열을 가리킬 수 없다** — 보유 장비는
                      기종을 가리키기 때문이다. */}
                  {one.model_count === 0 ? (
                    <span className="text-amber-600">없음</span>
                  ) : (
                    one.model_count
                  )}
                </TableCell>
                <TableCell className="text-right">
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

      <NewEquipmentSeriesDialog
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

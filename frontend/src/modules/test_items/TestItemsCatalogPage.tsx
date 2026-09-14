/**
 * 시험 항목 카탈로그 — **사슬의 가운데에서 출발하는 눈.**
 *
 *     물성  ⇄  시험 항목  →  규격(요구 조건)  →  계열/기종  →  보유 장비
 *
 * 카탈로그의 네 화면(계열·기종·규격·물성)이 전부 「→ 시험 항목」 으로 향하는데, 시험 항목에서
 * 출발하는 화면이 없었다. 「인장」 하나를 두고 얻는 물성 5 · 규격 12 · 되는 계열 42 · 보유
 * 7대를 한 눈에 보는 자리 — 그리고 **0 이 곧 공백**인 자리. 지난 현황에서 나온 「규격 없는
 * 계열 시험 항목 384」「물성 없는 시험 항목 37」 은 전부 이 단위로 봐야 채울 수 있다.
 *
 * ## 거르기는 공백을 고른다
 *
 * 「물성 없음」「규격 없음」「보유 없음」「검색 조건 없음」 — 각각 다른 사람의 할 일이다. 물성은
 * 재료 쪽이, 규격은 시험실이, 검색축은 시스템 관리자가 채운다.
 *
 * ## 「신뢰성 시험」 과 다르다
 *
 * 사이드바의 「신뢰성 시험」 은 부서가 제품 개발·검증을 위해 **수행하는 시험**(고온고습
 * 1000h)이고, 여기는 장비가 할 수 있는 **측정**(인장·경도)의 정의다. 신뢰성 시험이 시험
 * 항목을 써서 돈다 — 그래서 여기는 카탈로그 그룹에 있다.
 */

import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

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
import { testItemCatalogApi } from '@/modules/test_items/api'
import type { TestItemCatalogRow } from '@/modules/test_items/api'

type Gap = 'properties' | 'methods' | 'series' | 'equipment' | 'axes'

const GAP_LABEL: Record<Gap, string> = {
  properties: '물성 없음',
  methods: '규격 없음',
  series: '되는 계열 없음',
  equipment: '보유 장비 없음',
  axes: '검색 조건 없음',
}

function hasGap(row: TestItemCatalogRow, gap: Gap): boolean {
  switch (gap) {
    case 'properties':
      return row.properties_total === 0
    case 'methods':
      return row.methods_total === 0
    case 'series':
      return row.series_count === 0
    case 'equipment':
      return row.equipment_count === 0
    case 'axes':
      return row.condition_keys.length === 0
  }
}

/** 0 은 붉게 — 그것이 이 표에서 가장 중요한 칸이다. */
function Count({ value, warn = true }: { value: number; warn?: boolean }) {
  if (value === 0 && warn) return <span className="text-amber-600">0</span>
  return <>{value}</>
}

export default function TestItemsCatalogPage() {
  const rows = useResource(() => testItemCatalogApi.list(), [])
  const [params, setParams] = useSearchParams()
  const gap = (params.get('gap') as Gap | null) ?? null
  const [query, setQuery] = useState('')

  const shown = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return (rows.data ?? []).filter((row) => {
      if (gap && !hasGap(row, gap)) return false
      if (!needle) return true
      return [row.value, row.code ?? '', ...row.aliases].some((text) =>
        text.toLowerCase().includes(needle),
      )
    })
  }, [rows.data, gap, query])

  const all = rows.data ?? []
  const gaps = (Object.keys(GAP_LABEL) as Gap[]).map((one) => ({
    key: one,
    count: all.filter((row) => hasGap(row, one)).length,
  }))

  return (
    <div className="space-y-6">
      <PageHeader
        title="시험 항목"
        description="어떤 시험이 어떤 물성을 내고, 어떤 규격을 따르고, 어떤 계열이 하고, 우리가 몇 대 가졌나 — 한 줄에. 0 이 곧 공백입니다."
      />

      <div className="flex flex-wrap items-center gap-3">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="시험 항목 이름 · 코드 · 별칭"
          className="max-w-xs"
        />
        {/* **공백을 고른다.** 각각 다른 사람의 할 일이라 따로 센다. */}
        <div className="flex flex-wrap gap-1">
          {gaps.map(({ key, count }) => (
            <Button
              key={key}
              size="sm"
              variant={gap === key ? 'default' : 'outline'}
              onClick={() => setParams(gap === key ? {} : { gap: key })}
            >
              {GAP_LABEL[key]} {count}
            </Button>
          ))}
        </div>
      </div>

      {rows.data && (
        <p className="text-muted-foreground text-sm">
          시험 항목 {all.length}종
          {gap && (
            <>
              {' '}
              · <strong>{GAP_LABEL[gap]}</strong> {shown.length}종만 보는 중{' '}
              <button type="button" className="underline" onClick={() => setParams({})}>
                거르기 풀기
              </button>
            </>
          )}
        </p>
      )}

      <ErrorNotice error={rows.error} />

      {rows.data && shown.length === 0 ? (
        <EmptyState
          title="맞는 시험 항목이 없습니다"
          hint={
            gap ? '이 공백은 다 채워졌습니다 — 거르기를 풀어 보세요.' : '검색어를 바꿔 보세요.'
          }
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>시험 항목</TableHead>
              <TableHead className="text-right">얻는 물성</TableHead>
              <TableHead className="text-right">규격</TableHead>
              <TableHead className="text-right">되는 계열 / 기종</TableHead>
              <TableHead className="text-right">보유 장비</TableHead>
              <TableHead>검색 조건</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {shown.map((row) => (
              <TableRow key={row.id}>
                <TableCell>
                  <Link
                    to={`/catalog/test-items/${row.id}`}
                    className="font-medium hover:underline"
                  >
                    {row.value}
                  </Link>
                  {row.code && (
                    <span className="text-muted-foreground ml-2 font-mono text-xs">
                      {row.code}
                    </span>
                  )}
                  {row.aliases.length > 0 && (
                    <span className="text-muted-foreground block text-xs">
                      {row.aliases.join(' · ')}
                    </span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  <Count value={row.properties_total} />
                  {row.properties_total > 0 && (
                    // 제안과 확인을 섞어 세지 않는다 — 확인 0 이면 아직 기계의 말이다.
                    <span className="text-muted-foreground ml-1 text-xs">
                      (확인 {row.properties_confirmed})
                    </span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  <Count value={row.methods_total} />
                  {row.methods_total > 0 && (
                    <span className="text-muted-foreground ml-1 text-xs">
                      (조건 {row.methods_with_requirements})
                    </span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  <Count value={row.series_count} /> / {row.model_count}
                </TableCell>
                <TableCell className="text-right">
                  <Count value={row.equipment_count} />
                </TableCell>
                <TableCell className="text-sm">
                  {row.condition_keys.length === 0 ? (
                    <span className="text-amber-600">—</span>
                  ) : (
                    row.condition_keys.join(' · ')
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}

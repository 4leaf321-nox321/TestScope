/**
 * 장비 계열 카탈로그 — **제조사가 파는 계열.**
 *
 * 보유 장비와 다른 층이다(ADR 0004). 여기는 사양서고, 저기는 우리가 가진 개체다.
 *
 * 계열과 기종을 나눈 이유는 ADR 0006 에 있다: 한 계열 안에서 하중 용량이 중앙값
 * 60배, 최대 1200배 갈린다. 계열을 한 줄로 두면 0.5 kN 짜리 한 대를 가진 부서가
 * 「300 kN 인장 되나요」 에 된다고 답한다.
 *
 * ## 거르기는 머리글 아래에, 판정은 서버가
 *
 * 어느 열을 거르고 있는지가 **그 열 밑에** 보여야 한다. 위에 따로 모아 두면 「이 목록이
 * 왜 짧지」 를 사람이 되짚어야 하고, 되짚기는 대개 실패한다.
 *
 * 거르는 것은 서버다. 한 쪽을 받아 놓고 화면이 거르면 상한을 넘는 순간 나머지가 조용히
 * 빠지고, 그때 목록은 「그 조건에 맞는 계열이 이것뿐」 이라고 거짓말한다.
 */

import { useEffect, useState } from 'react'
import { Plus } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'

import { useAuth } from '@/shared/auth/AuthContext'
import { isSystemAdmin } from '@/shared/auth/roles'
import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { Pager } from '@/shared/components/Pager'
import { Button } from '@/shared/components/ui/button'
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
import {
  EMPTY_SERIES_FILTERS,
  SeriesFilters,
  activeCount,
} from '@/modules/equipment/CatalogFilters'
import type { SeriesFilterState } from '@/modules/equipment/CatalogFilters'
import { NewEquipmentSeriesDialog } from '@/modules/equipment/NewEquipmentSeriesDialog'

/** 부속을 목록에서 가르는 표. 챔버와 시험기가 한 줄씩 섞이면 「우리가 무슨 장비를
 *  가졌나」 가 안 보인다. */
const KIND_LABEL: Record<string, string> = {
  main: '본체',
  accessory: '부속',
  sensor: '센서',
  software: '소프트웨어',
}

/** 한 쪽에 몇 줄. 서버 상한(200)보다 작게 둔다 — 상한까지 받아 놓고 쪽 넘김을 안
 *  달면 나머지가 조용히 사라지고, 그 사실은 화면 어디에도 안 남는다. */
const PAGE_SIZE = 50

export default function EquipmentSeriesPage() {
  const { user } = useAuth()
  // **홈의 「남은 일」 이 이 주소로 온다.** 안 읽으면 눌러도 전체 목록이 떠서,
  // 사람은 「왜 안 걸러졌지」 를 겪고 그 목록을 안 믿게 된다.
  const [params, setParams] = useSearchParams()
  const fromUrl = (): SeriesFilterState => ({
    ...EMPTY_SERIES_FILTERS,
    // 「남은 일」 에서 왔으면 종류로 좁히지 않는다 — 부속 계열도 시험 항목이 빌 수 있고,
    // 그때 홈이 센 수와 여기 보이는 줄 수가 어긋난다.
    kind: params.has('test_item') || params.has('models') ? '' : 'main',
    testItem: params.get('test_item') ?? '',
    models: params.get('models') ?? '',
    owned: params.get('owned') ? 'owned' : '',
  })
  const [typed, setTyped] = useState<SeriesFilterState>(fromUrl)
  const [filters, setFilters] = useState<SeriesFilterState>(fromUrl)
  const [offset, setOffset] = useState(0)
  const [creating, setCreating] = useState(false)

  // 글자마다 조회하지 않는다 — 타이핑 중에 결과가 요동치면 읽는 눈이 미끄러진다.
  useEffect(() => {
    const timer = setTimeout(() => setFilters({ ...typed, name: typed.name.trim() }), 250)
    return () => clearTimeout(timer)
  }, [typed])

  // **거르기가 바뀌면 첫 쪽으로.** 안 그러면 세 번째 쪽을 보던 사람이 거르는 순간
  // 빈 화면을 보고 그것을 「결과 없음」 으로 읽는다.
  useEffect(() => {
    setOffset(0)
  }, [filters])

  // **한 번만 받는다.** 거를 때마다 다시 받으면 고르는 사이에 선택지가 흔들린다.
  const options = useResource(() => seriesApi.filterOptions(), [])

  const page = useResource(
    () =>
      seriesApi.list({
        name: filters.name || undefined,
        kind: filters.kind || undefined,
        makerTermId: filters.makerTermId || undefined,
        categoryTermId: filters.categoryTermId || undefined,
        status: filters.status || undefined,
        models: filters.models || undefined,
        testItem: filters.testItem || undefined,
        owned: filters.owned === 'owned',
        limit: PAGE_SIZE,
        offset,
      }),
    [filters, offset],
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

      {/* 찾는 칸은 **열마다** 있다(머리글 아래) — 여기 또 두면 같은 일을 하는 칸이
          둘이 되고, 둘은 반드시 어긋난다. */}
      {activeCount(filters) > 0 && (
        <div className="text-muted-foreground flex items-center gap-2 text-sm">
          <span>{activeCount(filters)}개 조건으로 걸렀습니다</span>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setTyped(EMPTY_SERIES_FILTERS)
              // 주소에 남은 거르기도 함께 푼다 — 안 그러면 새로고침에 되살아난다.
              setParams({})
            }}
          >
            필터 해제
          </Button>
        </div>
      )}

      <ErrorNotice error={page.error} />

      {/* **비어도 표를 지우지 않는다.** 거르다 0 건이 되었을 때 머리글째 사라지면
          방금 건 조건이 화면에서 없어져서, 무엇을 풀어야 할지가 안 보인다. */}
      {page.data && page.data.items.length === 0 && activeCount(filters) === 0 ? (
        <EmptyState
          title="계열이 없습니다"
          hint="계열을 등록해 두면 같은 계열의 기종을 여러 개 들일 때 시험 항목을 한 번만 적으면 됩니다."
        />
      ) : (
        <div className="space-y-3">
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
              {/* **머리글 바로 아래.** 어느 열을 거르고 있는지가 그 열 밑에 보인다. */}
              <TableRow className="hover:bg-transparent">
                <SeriesFilters
                  value={typed}
                  onChange={setTyped}
                  options={options.data ?? null}
                />
              </TableRow>
            </TableHeader>
            <TableBody>
              {page.data?.items.length === 0 && (
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={7} className="text-muted-foreground py-8 text-center">
                    필터에 맞는 계열이 없습니다. 조건을 해제해 보세요.
                  </TableCell>
                </TableRow>
              )}
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
                    {one.test_item_count === 0 ? (
                      <span className="text-amber-600">미등록</span>
                    ) : (
                      one.test_item_count
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

          {page.data && (
            <Pager
              total={page.data.total}
              limit={page.data.limit}
              offset={page.data.offset}
              onOffset={setOffset}
              unit="계열"
            />
          )}
        </div>
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

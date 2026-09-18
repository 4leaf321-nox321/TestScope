/**
 * 장비 기종 — **보유 장비가 가리키는 것.**
 *
 * 계열 아래의 한 기종이다(ADR 0006). 계열별로 보려면 계열 상세로 가고, 여기는
 * **기종을 이름으로 찾는 자리**다 — 라벨의 `68FM-300` 만 아는 채로 오는 일이 흔하다.
 *
 * ## 이름만으로는 못 고른다
 *
 * 한 계열에 기종이 열일곱까지 있고, 그 열일곱을 가르는 것은 **수치**다. 제조사·계열은
 * 형제 기종끼리 같고, 시험 항목은 계열이 갖는 값이라 역시 같다(ADR 0006) — 그러니
 * 그 세 열은 「어느 것을 고를까」 에 아무 답도 못 한다.
 *
 * 그래서 **대표 사양**을 한 줄에 박는다. 무엇이 대표인지는 분류가 정한다(온톨로지
 * `categories.json` 의 `headline_specs`): 만능시험기는 하중이고 챔버는 온도다.
 *
 * ## 보유 대수를 함께 보여 주는 이유
 *
 * **카탈로그가 답해야 하는 첫 물음이 그것**이고, 전에는 기종이 행이 아니라 문자열이라
 * 셀 수가 없었다.
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
import { Badge } from '@/shared/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table'
import { useResource } from '@/shared/hooks/useResource'
import { useBackFromReference } from '@/shared/hooks/useBackFromReference'
import { catalogApi } from '@/modules/equipment/api'
import type { EquipmentModelRow } from '@/modules/equipment/api'
import {
  EMPTY_MODEL_FILTERS,
  ModelFilters,
  activeCount,
} from '@/modules/equipment/CatalogFilters'
import type { ModelFilterState } from '@/modules/equipment/CatalogFilters'
import { shownSpecValue } from '@/modules/equipment/specValue'
import { NewEquipmentModelDialog } from '@/modules/equipment/NewEquipmentModelDialog'

/** 홈의 「남은 일」 이 거는 필터. 그 줄을 눌러 온 사람에게 **왜 이 목록인지**를
 *  말해 준다 — 안 말하면 목록이 짧은 것을 오류로 읽는다. */
const ISSUE_NOTE: Record<string, string> = {
  none: '사양이 하나도 안 적힌 기종입니다. 비워 두면 이 기종으로 등록하는 장비가 조건 없이 복사되고, 검색은 그것을 「조건 미상」 으로 답합니다.',
  uncertain:
    '반입이 원본 카탈로그의 표를 잘못 읽었을 수 있다고 표시한 기종입니다. 원본을 열어 확인한 뒤 비고의 표시를 지우세요.',
}

/** 한 쪽에 몇 줄. 서버 상한(200)보다 작게 둔다 — 상한까지 받아 놓고 안 그리면
 *  나머지가 조용히 사라지고, 그 사실은 화면 어디에도 안 남는다. */
const PAGE_SIZE = 50

/** 목록 한 줄에 시험 항목 이름을 몇 개까지. 나머지는 수로 접는다. */
const ITEMS_SHOWN = 2

/**
 * 그 기종을 가르는 수치 두어 칸.
 *
 * **값이 없으면 라벨도 안 그린다.** 「하중 용량 —」 은 0 으로도 모름으로도 읽히는데,
 * 그 둘은 장비를 고르는 사람에게 정반대다. 대신 사양이 몇 칸 적혔는지를 말한다.
 */
function HeadlineSpecs({ model }: { model: EquipmentModelRow }) {
  if (model.headline_specs.length === 0) {
    return model.spec_count === 0 ? (
      // 사양이 아예 없는 기종. 홈의 「남은 일」 이 거는 필터와 같은 말이다.
      <span className="text-amber-600">사양 없음</span>
    ) : (
      <span className="text-muted-foreground">사양 {model.spec_count}칸</span>
    )
  }
  return (
    <div className="flex flex-col gap-0.5">
      {model.headline_specs.map((spec) => (
        <span key={spec.definition_id} className="text-sm">
          <span className="text-muted-foreground">{spec.label} </span>
          <span className="font-medium">{shownSpecValue(spec)}</span>
        </span>
      ))}
    </div>
  )
}

export default function EquipmentModelsPage() {
  const { user } = useAuth()
  // **홈의 「남은 일」 이 이 주소로 온다.** 안 읽으면 눌러도 전체 목록이 떠서,
  // 사람은 「왜 안 걸러졌지」 를 겪고 그 목록을 안 믿게 된다.
  const [params, setParams] = useSearchParams()
  const fromUrl = (): ModelFilterState => ({
    ...EMPTY_MODEL_FILTERS,
    spec: params.get('spec') ?? '',
    testItem: params.get('test_item') ?? '',
    owned: params.get('owned') ? 'owned' : '',
  })
  const [typed, setTyped] = useState<ModelFilterState>(fromUrl)
  // **물어보는 쪽도 같은 값으로 시작한다.** 여기를 비우면 첫 조회가 거르기 없이
  // 나가고, 그 한순간이 「안 걸러졌다」 로 읽힌다.
  const [filters, setFilters] = useState<ModelFilterState>(fromUrl)
  const [offset, setOffset] = useState(0)
  const [creating, setCreating] = useState(false)

  // 글자마다 조회하지 않는다 — 타이핑 중에 결과가 요동치면 읽는 눈이 미끄러진다.
  useEffect(() => {
    const timer = setTimeout(() => setFilters({ ...typed, name: typed.name.trim() }), 250)
    return () => clearTimeout(timer)
  }, [typed])

  // **거르기가 바뀌면 첫 쪽으로 돌아간다.** 안 그러면 세 번째 쪽을 보던 사람이
  // 검색어를 치는 순간 빈 화면을 보고, 그것을 「결과 없음」 으로 읽는다.
  useEffect(() => {
    setOffset(0)
  }, [filters])

  // **한 번만 받는다.** 거를 때마다 다시 받으면 고르는 사이에 선택지가 흔들린다.
  const options = useResource(() => catalogApi.filterOptions(), [])

  const page = useResource(
    () =>
      catalogApi.list({
        name: filters.name || undefined,
        seriesId: filters.seriesId || undefined,
        makerTermId: filters.makerTermId || undefined,
        categoryTermId: filters.categoryTermId || undefined,
        spec: filters.spec || undefined,
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
        back={useBackFromReference()}
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

      {/* 홈의 「남은 일」 에서 왔으면 **왜 이 목록인지**를 말해 준다 — 안 말하면
          목록이 짧은 것을 오류로 읽는다. 푸는 자리는 그 열 밑에도 있다. */}
      {filters.spec && (
        <div className="bg-muted/50 rounded-md border p-3">
          <p className="text-sm">{ISSUE_NOTE[filters.spec] ?? '걸러진 목록입니다.'}</p>
        </div>
      )}

      {/* 찾는 칸은 **열마다** 있다(머리글 아래) — 여기 또 두면 같은 일을 하는 칸이
          둘이 되고, 둘은 반드시 어긋난다. */}
      {activeCount(filters) > 0 && (
        <div className="text-muted-foreground flex items-center gap-2 text-sm">
          <span>{activeCount(filters)}개 조건으로 걸렀습니다</span>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setTyped(EMPTY_MODEL_FILTERS)
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
          title="기종이 없습니다"
          hint="기종을 등록해 두면 같은 장비를 여러 대 들일 때 사양을 한 번만 적으면 됩니다."
        />
      ) : (
        <div className="space-y-3">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>기종</TableHead>
                <TableHead>분류</TableHead>
                <TableHead>제조사</TableHead>
                {/* **이 열이 기종을 가른다.** 분류가 정한 대표 사양이다. */}
                <TableHead>대표 사양</TableHead>
                <TableHead>시험 항목</TableHead>
                <TableHead className="text-right">보유</TableHead>
              </TableRow>
              {/* **머리글 바로 아래.** 어느 열을 거르고 있는지가 그 열 밑에 보인다. */}
              <TableRow className="hover:bg-transparent">
                <ModelFilters
                  value={typed}
                  onChange={setTyped}
                  options={options.data ?? null}
                />
              </TableRow>
            </TableHeader>
            <TableBody>
              {page.data?.items.length === 0 && (
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={6} className="text-muted-foreground py-8 text-center">
                    필터에 맞는 기종이 없습니다. 조건을 해제해 보세요.
                  </TableCell>
                </TableRow>
              )}
              {(page.data?.items ?? []).map((one) => (
                <TableRow
                  key={one.id}
                  className={one.status === 'discontinued' ? 'opacity-60' : undefined}
                >
                  <TableCell>
                    <div className="flex flex-col gap-0.5">
                      <span className="flex items-center gap-2">
                        <Link
                          to={`/catalog/equipment-models/${one.id}`}
                          className="font-medium hover:underline"
                        >
                          {one.name}
                        </Link>
                        {/* **단종일 때만 말한다.** 거의 모두가 현행이라, 열을 따로
                            두면 같은 글자가 700줄 반복되고 그 열은 아무 말도 안 하게
                            된다. */}
                        {one.status === 'discontinued' && (
                          <Badge variant="secondary">단종</Badge>
                        )}
                      </span>
                      {/* 계열은 이름 아래에 둔다 — 형제 기종끼리 같은 값이라 열
                          하나를 차지할 만큼 가르는 힘이 없다. */}
                      <Link
                        to={`/catalog/equipment-series/${one.series_id}`}
                        className="text-muted-foreground text-xs hover:underline"
                      >
                        {one.series_name}
                      </Link>
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {/* **행만 보고 이게 무슨 장비인지 알 수 있어야 한다.** 계열에서
                        끌어온 값이다(ADR 0006). */}
                    {one.category ?? '—'}
                  </TableCell>
                  <TableCell className="text-sm">{one.maker ?? '—'}</TableCell>
                  <TableCell>
                    <HeadlineSpecs model={one} />
                  </TableCell>
                  <TableCell className="text-sm">
                    {/* **계열의 시험 항목이다.** 수가 아니라 이름을 적는다 — 「2」 는
                        무슨 시험이 되는지에 아무 답도 못 한다. */}
                    {one.test_items.length === 0 ? (
                      <span className="text-amber-600">미등록</span>
                    ) : (
                      <span>
                        {/* 목록 줄은 **이름만** 받는다 — 조건 수치는 계열이 갖는
                          값이라 형제 기종끼리 전부 같고, 이 화면은 안 그린다. */}
                        {one.test_items.slice(0, ITEMS_SHOWN).join(' · ')}
                        {one.test_items.length > ITEMS_SHOWN && (
                          <span className="text-muted-foreground">
                            {' '}
                            +{one.test_items.length - ITEMS_SHOWN}
                          </span>
                        )}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right text-sm">
                    {/* **대수만 보면 여유 있어 보인다.** 다섯 대 중 한 대만 가동인
                        경우가 있어서 가동 수를 함께 적는다. */}
                    {one.unit_count === 0 ? (
                      <span className="text-muted-foreground">—</span>
                    ) : (
                      `${one.unit_count}대 (가동 ${one.operational_count})`
                    )}
                  </TableCell>
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
              unit="기종"
            />
          )}
        </div>
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

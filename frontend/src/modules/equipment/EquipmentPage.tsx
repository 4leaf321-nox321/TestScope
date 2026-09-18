/**
 * 보유 장비 목록. **이 시스템의 대장이다.**
 *
 * **시험 항목 수를 한 칸으로 보여 준다.** 0 인 장비는 검색에 절대 안 걸리는데, 목록에서
 * 그것이 안 보이면 아무도 채우지 않는다 — 그리고 사람들은 시스템이 있는데도
 * 여전히 전화를 돌린다.
 *
 * ## 거르기는 머리글 아래에, 판정은 서버가
 *
 * 어느 열을 거르고 있는지가 **그 열 밑에** 보여야 한다. 위에 따로 모아 두면 「이 목록이
 * 왜 짧지」 를 사람이 되짚어야 하고, 되짚기는 대개 실패한다.
 *
 * 거르는 것은 서버다. 한 쪽을 받아 놓고 화면이 거르면 상한을 넘는 순간 나머지가 조용히
 * 빠지고, 그때 목록은 「그 조건에 맞는 장비가 이것뿐」 이라고 거짓말한다.
 */

import { useEffect, useState } from 'react'
import { Plus, Upload } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'

import { useAuth } from '@/shared/auth/AuthContext'
import { isAnyManager } from '@/shared/auth/roles'
import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { StatusBadge } from '@/shared/components/StatusBadge'
import { Badge } from '@/shared/components/ui/badge'
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
import { Pager } from '@/shared/components/Pager'
import { shownDate } from '@/shared/lib/datetime'
import { useBackFromReference } from '@/shared/hooks/useBackFromReference'
import { equipmentApi } from '@/modules/equipment/api'
import {
  EMPTY_FILTERS,
  EquipmentFilters,
  activeCount,
} from '@/modules/equipment/EquipmentFilters'
import type { EquipmentFilterState } from '@/modules/equipment/EquipmentFilters'
import { EquipmentImportDialog } from '@/modules/equipment/EquipmentImportDialog'
import { NewEquipmentDialog } from '@/modules/equipment/NewEquipmentDialog'
import { AttributeFilterBar } from '@/modules/attributes/AttributeFilterBar'

/** 한 쪽에 몇 줄. 서버 상한(200)보다 작게 둔다. */
const PAGE_SIZE = 50

export default function EquipmentPage() {
  const { user } = useAuth()
  // **홈의 「남은 일」 이 이 주소로 온다.** 안 읽으면 눌러도 전체 목록이 떠서,
  // 사람은 「왜 안 걸러졌지」 를 겪고 그 목록을 안 믿게 된다.
  const [params, setParams] = useSearchParams()
  // 부서별 「신뢰성 시험」 화면의 「장비 N대」 도 여기로 온다(부서 + 시험 항목).
  const fromUrl = (): EquipmentFilterState => ({
    ...EMPTY_FILTERS,
    calibration: params.get('calibration') ?? '',
    testItem: params.get('test_item') ?? '',
    catalog: params.get('catalog') ?? '',
    status: params.get('status') ?? '',
    workspace: params.get('workspace') ?? '',
    testItemTermId: params.get('test_item_term_id') ?? '',
  })
  const [typed, setTyped] = useState<EquipmentFilterState>(fromUrl)
  // **거르기를 물어보는 쪽도 같은 값으로 시작한다.** 여기를 비워 두면 첫 조회가
  // 거르기 없이 나가서, 눌러 들어온 사람이 한순간 전체 목록을 본다 — 그리고 그
  // 한순간이 「안 걸러졌다」 로 읽힌다.
  const [filters, setFilters] = useState<EquipmentFilterState>(fromUrl)
  const [offset, setOffset] = useState(0)
  // 속성 조건은 주소에 실린다 — 「투자 연도 2020 이후」 를 물은 화면을 그대로 보낼 수 있다.
  const [attrs, setAttrs] = useState<string[]>(() => params.getAll('attr'))
  const [creating, setCreating] = useState(false)
  const [importing, setImporting] = useState(false)

  // 글자마다 조회하지 않는다 — 타이핑 중에 결과가 요동치면 읽는 눈이 미끄러진다.
  // 고르는 칸(피커·드롭다운)은 기다릴 것이 없지만, 한 자리에서 다루는 편이 낫다.
  useEffect(() => {
    const timer = setTimeout(
      () => setFilters({ ...typed, assetNo: typed.assetNo.trim(), name: typed.name.trim() }),
      250,
    )
    return () => clearTimeout(timer)
  }, [typed])

  // **거르기가 바뀌면 첫 쪽으로.** 안 그러면 세 번째 쪽을 보던 사람이 거르는 순간
  // 빈 화면을 보고 그것을 「결과 없음」 으로 읽는다.
  useEffect(() => {
    setOffset(0)
  }, [filters])

  const page = useResource(
    () =>
      equipmentApi.list({
        assetNo: filters.assetNo || undefined,
        name: filters.name || undefined,
        status: filters.status || undefined,
        workspace: filters.workspace || undefined,
        categoryTermId: filters.categoryTermId || undefined,
        siteTermId: filters.siteTermId || undefined,
        testItemTermId: filters.testItemTermId || undefined,
        testItem: filters.testItem || undefined,
        catalog: filters.catalog || undefined,
        calibration: filters.calibration || undefined,
        attrs,
        limit: PAGE_SIZE,
        offset,
      }),
    [filters, attrs, offset],
  )

  const canCreate = isAnyManager(user)

  return (
    <div className="space-y-6">
      <PageHeader
        back={useBackFromReference()}
        title="보유 장비"
        description="자산번호·이름으로 찾습니다. 시험 항목이 0 인 장비는 검색에 걸리지 않습니다."
        actions={
          // **볼 수 있는 것만 보여 준다.** 눌러야 403 을 아는 단추는 할 수 있는
          // 일을 알려 주지 못한다. 판정은 서버가 다시 한다.
          canCreate ? (
            <div className="flex gap-2">
              {/* **대장은 대개 엑셀로 온다.** 한 대씩 넣게 두면 수백 대를 가진
                  부서는 시작조차 못 하고, 대장이 비면 검색은 아무 답도 못 한다. */}
              <Button variant="outline" onClick={() => setImporting(true)}>
                <Upload className="size-4" />
                일괄 반입
              </Button>
              <Button onClick={() => setCreating(true)}>
                <Plus className="size-4" />
                장비 등록
              </Button>
            </div>
          ) : undefined
        }
      />

      {/* 속성 값으로 거르기 — 열이 아니라 행으로 적힌 것은 여기서만 되찾을 수 있다. */}
      <AttributeFilterBar target="equipment" value={attrs} onChange={setAttrs} />

      {/* 찾는 칸은 **열마다** 있다(머리글 아래) — 여기 또 두면 같은 일을 하는 칸이
          둘이 되고, 둘은 반드시 어긋난다. */}
      {activeCount(filters) > 0 && (
        <div className="text-muted-foreground flex items-center gap-2 text-sm">
          <span>{activeCount(filters)}개 조건으로 걸렀습니다</span>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setTyped(EMPTY_FILTERS)
              setAttrs([])
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
          방금 건 조건이 화면에서 없어져서, 무엇을 풀어야 할지가 안 보인다.
          정말 한 대도 없을 때만(거르기 없음) 안내로 갈음한다. */}
      {page.data && page.data.items.length === 0 && activeCount(filters) === 0 ? (
        <EmptyState
          title="장비가 없습니다"
          hint="아직 등록된 장비가 없습니다. 부서 관리자가 등록할 수 있습니다."
        />
      ) : (
        <div className="space-y-3">
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
              {/* **머리글 바로 아래.** 어느 열을 거르고 있는지가 그 열 밑에 보인다. */}
              <TableRow className="hover:bg-transparent">
                <EquipmentFilters value={typed} onChange={setTyped} />
              </TableRow>
            </TableHeader>
            <TableBody>
              {page.data?.items.length === 0 && (
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={8} className="text-muted-foreground py-8 text-center">
                    필터에 맞는 장비가 없습니다. 조건을 해제해 보세요.
                  </TableCell>
                </TableRow>
              )}
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
                    {one.model_name ? (
                      <p className="text-muted-foreground text-xs">
                        {[one.series_name, one.model_name].filter(Boolean).join(' · ')}
                        {/* 카탈로그에 안 이어진 모델명은 **검색이 안 보는 글자**다.
                          그 사실을 안 적으면 사람은 이어진 줄 안다. */}
                        {!one.catalog_linked && ' · 카탈로그 미연결'}
                      </p>
                    ) : (
                      !one.catalog_linked && (
                        <p className="text-amber-600 text-xs">카탈로그 미연결</p>
                      )
                    )}
                  </TableCell>
                  <TableCell>
                    {one.workspace_name ?? '—'}
                    {/* **공용은 부서를 대신하지 않는다** — 관리 부서는 그대로 있고,
                      이 표시는 「빌릴 수 있나」 에 답한다. */}
                    {one.shared_use && (
                      <Badge variant="secondary" className="ml-1">
                        공용
                      </Badge>
                    )}
                  </TableCell>
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
                          <span key={item} className="bg-muted rounded px-1.5 py-0.5 text-xs">
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
                  <TableCell className="text-sm">
                    {/* **셋을 구별해 말한다.** 대상이 아닌 장비와 빠뜨린 장비가 같아
                      보이면, 빠뜨린 것은 영영 안 채워진다. */}
                    {!one.calibration_required ? (
                      <span className="text-muted-foreground">대상 아님</span>
                    ) : one.calibration_missing ? (
                      <span className="text-amber-600">이력 없음</span>
                    ) : (
                      <span>
                        {shownDate(one.calibration_due_on)}
                        {one.calibration_due_estimated && (
                          <span className="text-muted-foreground text-xs"> 계산</span>
                        )}
                      </span>
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
              unit="대"
            />
          )}
        </div>
      )}

      <EquipmentImportDialog
        open={importing}
        onClose={() => setImporting(false)}
        onDone={() => page.reload()}
      />

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

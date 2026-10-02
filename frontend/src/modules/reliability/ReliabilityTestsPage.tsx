/**
 * 신뢰성 시험 전체 — **「누가 무슨 시험을 하나」 를 부서를 가로질러 한 표로.**
 *
 * 사이드바 「신뢰성 시험」 아래에는 부서마다 화면이 하나씩 서는데(부서 관리자가 거기서 등록·
 * 수정), 이 화면은 그 전부를 한 번에 본다: 다른 부서가 이미 같은 절차를 하는지, 어느 시험
 * 항목이 어느 부서에 몰려 있는지. 고치는 문은 부서 화면이다 — 줄의 부서 이름을 누르면 간다.
 *
 * 찾기는 이름·목적·부서·시험 항목·속성 값을 한 칸으로 거른다 — 「85 degC」 로 치면 그 조건을
 * 적은 절차가 걸린다(속성 값은 서버가 만든 display 글자).
 *
 * **확인 전 후보는 기본적으로 안 나온다.** 이 표는 「저 부서가 무슨 시험을 하나」 에 답하는
 * 표인데, AI 가 올리고 아직 아무도 안 본 것은 그 답이 아니다 — 옆 부서 사람은 배지를 안 보고
 * 읽는다. 일부러 보려는 사람을 위해 체크 하나를 둔다.
 *
 * **줄을 누르면 보기 창이 열린다.** 여기 오는 사람은 대개 옆 부서 사람이라 고칠 권한이
 * 없는데, 그 전에는 카드 안을 볼 길이 아예 없었다 — 목록의 요약만 읽고 돌아갔다.
 *
 * ## 속성은 **열로** 선다
 *
 * 한 칸에 「시험 온도: 85 ℃ / 시험 시간: 1000 h / …」 를 쌓아 두면 세로로 못 읽는다 —
 * 「온도를 안 적은 시험이 몇 건인가」 는 한 열을 위아래로 훑어야 보이는 것인데, 덩어리
 * 안에서는 같은 속성이 줄마다 다른 높이에 있다. 그래서 정의마다 열을 세우고, 머리글의
 * 깔때기로 **그 열만** 거른다(「값 없음」 을 포함해서).
 *
 * 열이 서른을 넘으므로 표를 **화면 높이에 가둔다**(`viewport`) — 안 그러면 가로 스크롤
 * 막대가 표 맨 아래에 있어서, 오른쪽 열을 보려면 먼저 세로로 끝까지 내려가야 한다.
 *
 * ## 한 줄에 **한 줄**
 *
 * 열마다 폭을 안 내놓으면 긴 값이 접히고, 접힌 칸 하나가 그 줄 전체를 높게 만든다 — 줄이
 * 열 줄 높이면 위아래 줄을 눈으로 못 잇고, 그러면 표가 아니라 카드 더미가 된다(2026-10-03).
 *
 * 그래서 **값 칸은 안 접는다**: 속성 열과 시험 항목은 `whitespace-nowrap` 이고 폭 상한이
 * 없다 — 내용만큼 넓어지고, 넘치는 것은 표가 가로로 스크롤한다(`viewport`).
 *
 * **목적만 다르다.** 프로즈라서 「안 접힐 만큼 넓게」 가 성립하지 않는다 — 한 문단을 한
 * 줄로 펼치면 그 열 하나가 수천 픽셀이 되고 나머지 열이 저 밖으로 밀린다. 그래서 목적은
 * 한 줄로 자르고(`truncate`) 전문은 툴팁과 보기 창에 둔다. 자르려면 **확정 상한**이
 * 있어야 한다(`max-w-96`): `w-full` 이면 표가 그 한 줄을 다 담으려고 열을 늘려서 생략표가
 * 아예 안 생긴다.
 *
 * ## 좁은 창에서는 열을 접는다
 *
 * 시험 항목은 줄바꿈이 안 되는 덩어리라 폭을 안 내놓는다. 줄을 누르면 카드 전체가 보기
 * 창에 열리므로, 좁을 때는 **덜 급한 열을 아예 접는다**: 목적(lg) → 시험 항목(md) 순으로
 * 사라지고 이름과 단추는 끝까지 남는다.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Image as ImageIcon, Wrench } from 'lucide-react'

import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { Input } from '@/shared/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table'
import { useBackFromReference } from '@/shared/hooks/useBackFromReference'
import { useResource } from '@/shared/hooks/useResource'
import { isPlainRowClick } from '@/shared/lib/rowClick'
import { Button } from '@/shared/components/ui/button'
import { AttachmentsDialog } from '@/modules/attachments/AttachmentsDialog'
import { AttributeFilterBar } from '@/modules/attributes/AttributeFilterBar'
import {
  AttributeBodyCells,
  AttributeColumnPicker,
  AttributeHeadCells,
  useAttributeColumns,
} from '@/modules/attributes/AttributeColumns'
import { CandidateBadge } from '@/modules/reliability/CandidateReview'
import {
  NameHead,
  PurposeHead,
  RowFilterChips,
  TestItemHead,
  useRowFilters,
} from '@/modules/reliability/ColumnFilters'
import { CapabilityDialog } from '@/modules/reliability/CapabilityDialog'
import {
  ReliabilityTestViewDialog,
  RowOpener,
} from '@/modules/reliability/ReliabilityTestViewDialog'
import { PAGE, reliabilityApi } from '@/modules/reliability/api'
import type { ReliabilityTest } from '@/modules/reliability/api'

export default function ReliabilityTestsPage() {
  /**
   * 속성 조건은 **서버가** 거른다 — 아래 찾기 칸은 받은 쪽 안에서만 훑는다.
   *
   * **조건을 주소에 싣는다.** 그래야 온톨로지 쪽에서 「값으로 좁히기」 로 넘어올 수 있고,
   * 좁혀 놓은 화면을 옆 사람에게 링크로 건넬 수 있다. 조건이 화면 안에만 있으면 그 둘이
   * 다 안 되고, 「-40 °C 이하인 시험」 을 물으려던 사람은 매번 조건을 다시 친다.
   */
  const [params, setParams] = useSearchParams()
  const attrs = useMemo(() => params.getAll('attr'), [params])
  const setAttrs = useCallback(
    (next: string[]) => {
      setParams(
        (before) => {
          const moved = new URLSearchParams(before)
          moved.delete('attr')
          for (const one of next) moved.append('attr', one)
          return moved
        },
        // 거르기는 **되돌아갈 자리가 아니다** — 뒤로 가기가 조건 하나씩 풀리면
        // 목록으로 못 나간다.
        { replace: true },
      )
    },
    [setParams],
  )
  /** 확인 전 후보까지 볼까. **기본은 안 본다** — 확정된 것만이 이 표의 답이다. */
  const [withCandidates, setWithCandidates] = useState(false)
  /** 속성 아닌 열의 조건 — 이름 · 목적 · 시험 항목 · 보유 장비. 주소에 함께 실린다. */
  const rowFilters = useRowFilters()
  /**
   * 지난 판까지 볼까. **기본은 최신판만** — 판마다 줄이 서므로(0049) 안 가리면 목록이 판
   * 수만큼 부푼다. 사업부 화면과 같은 체크다: 한쪽에만 두면 전사 목록에서는 과거 판을 볼
   * 길이 아예 없다(0.42.0 에서 그렇게 두었다).
   */
  const [withOld, setWithOld] = useState(false)
  /** 열로 세울 속성 — 고른 것은 브라우저에 남는다. */
  const columns = useAttributeColumns('reliability_test')
  /** 몇 번째 쪽. 조건이 바뀌면 처음으로 — 세 번째 쪽을 보다 좁히면 빈 화면이 뜬다. */
  const [page, setPage] = useState(0)
  const [query, setQuery] = useState('')
  /** 친 뒤 잠깐 기다렸다 묻는다 — 글자마다 부르면 스무 번 왕복한다. */
  const [asked, setAsked] = useState('')
  useEffect(() => {
    const timer = setTimeout(() => setAsked(query), 400)
    return () => clearTimeout(timer)
  }, [query])
  const tests = useResource(
    () =>
      reliabilityApi.listAll(
        attrs,
        withCandidates,
        PAGE,
        page * PAGE,
        asked,
        rowFilters.value,
        withOld,
      ),
    [attrs, withCandidates, page, asked, rowFilters.value, withOld],
  )
  useEffect(() => setPage(0), [attrs, withCandidates, asked, rowFilters.value, withOld])
  const [asking, setAsking] = useState<ReliabilityTest | null>(null)
  /** 그림 보기 — **조회하는 사람의 자리.** 수정 창을 열지 않고 본다. */
  const [showing, setShowing] = useState<typeof asking>(null)
  /** 카드 전체 보기 — 줄을 누르면 이것. */
  const [viewing, setViewing] = useState<typeof asking>(null)
  const rows = tests.data?.items ?? []
  // **서버가 좁혀 준 것이 곧 결과다** — 화면 안에서 다시 훑으면 지금 쪽만 뒤진다.
  const shown = rows
  const workspaces = new Set(rows.map((row) => row.division_code)).size
  /**
   * 필터나 검색어가 걸렸나. **0건이어도 표는 남긴다** — 표가 사라지면 머리글의 필터도
   * 함께 사라져서, 어느 열에 무엇이 걸렸는지 볼 수도 풀 수도 없다.
   */
  const filtered = attrs.length > 0 || rowFilters.count > 0 || Boolean(asked)

  return (
    <div className="space-y-6">
      <PageHeader
        back={useBackFromReference()}
        title="신뢰성 시험"
        description="부서가 제품 개발·검증을 위해 수행하는 시험 전부 — 부서를 가로질러 한 표로. 등록·수정은 그 부서의 화면(사이드바 아래 부서 이름)에서 합니다."
      />

      {/* 조건 속성으로 거르기 — 「-40 °C 이하로 내려가는 시험」 을 물을 수 있어야 조건을 적는다. */}
      <AttributeFilterBar
        target="reliability_test"
        value={attrs}
        onChange={setAttrs}
        empty={tests.data?.total === 0}
      />

      {/* 열 머리글에서 걸든 여기서 풀든 **같은 목록**이다. */}
      <RowFilterChips rows={rowFilters} />

      <div className="flex flex-wrap items-center gap-3">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="검색 — 시험 · 목적 · 부서 · 시험 항목 · 속성 값"
          className="w-80"
        />
        {tests.data && (
          <p className="text-muted-foreground text-sm">
            신뢰성 시험 {tests.data?.total ?? rows.length}종 · 이 쪽 {rows.length}종 · 부서{' '}
            {workspaces}곳{asked && ' · 검색어 적용됨'}
          </p>
        )}
        <label className="text-muted-foreground flex items-center gap-1.5 text-sm">
          <input
            type="checkbox"
            checked={withCandidates}
            onChange={(event) => setWithCandidates(event.target.checked)}
            className="size-3.5"
          />
          미확인 후보 포함
        </label>
        {/* **지난 판은 일부러 펼친다.** 섞어 두면 같은 시험이 여러 줄로 선다. */}
        <label className="text-muted-foreground flex items-center gap-1.5 text-sm">
          <input
            type="checkbox"
            checked={withOld}
            onChange={(event) => setWithOld(event.target.checked)}
            className="size-3.5"
          />
          과거 판 포함
        </label>
        <AttributeColumnPicker columns={columns} />
      </div>

      <ErrorNotice error={tests.error} />

      {tests.data && rows.length === 0 && !filtered ? (
        <EmptyState
          title="등록된 신뢰성 시험이 없습니다"
          hint="사이드바 「신뢰성 시험」 아래의 부서 화면에서 그 부서의 관리자가 등록합니다. 부서가 안 보이면 「관리 → 부서 정보」 의 「신뢰성 시험」 표시를 켭니다."
        />
      ) : (
        <Table viewport>
          <TableHeader>
            <TableRow>
              {/* 부서는 **누르면 그 부서 화면**이라 여기에 따로 거르기를 안 둔다 —
                  그 화면이 곧 「이 부서만」 이고, 후보까지 보여 준다. */}
              <TableHead>부서</TableHead>
              <TableHead className="min-w-44">
                <NameHead rows={rowFilters} />
              </TableHead>
              <TableHead className="hidden max-w-96 min-w-96 lg:table-cell">
                <PurposeHead rows={rowFilters} />
              </TableHead>
              <TableHead className="hidden min-w-48 md:table-cell">
                <TestItemHead rows={rowFilters} />
              </TableHead>
              <AttributeHeadCells columns={columns.shown} value={attrs} onChange={setAttrs} />
              <TableHead className="w-32" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 && (
              // **표는 남기고 줄 자리에 적는다.** 표가 통째로 사라지면 머리글의 필터도
              // 사라져서, 어느 열에 무엇이 걸렸는지 볼 수도 풀 수도 없다 — 사람에게는
              // 「눌렀더니 다 없어졌다」 로 보인다.
              <TableRow>
                <TableCell colSpan={99} className="text-muted-foreground py-10 text-center">
                  필터 조건에 해당하는 신뢰성 시험이 없습니다. 위의 조건을 하나씩 해제해
                  보십시오 — 등록된 시험이 사라진 것은 아닙니다.
                </TableCell>
              </TableRow>
            )}
            {shown.map((row) => (
              <TableRow
                key={row.id}
                className="hover:bg-muted/50 cursor-pointer"
                // 부서 이름·시험 항목은 링크다 — 그 위에서는 안 연다.
                onClick={(event) => isPlainRowClick(event) && setViewing(row)}
              >
                <TableCell className="whitespace-nowrap">
                  {/* 고치는 문 — 부서 화면. 여기서는 읽기만. */}
                  <Link
                    to={`/reliability-tests/${row.division_code}`}
                    className="hover:underline"
                  >
                    {row.division_name}
                  </Link>
                </TableCell>
                <TableCell>
                  <RowOpener name={row.name} onOpen={() => setViewing(row)}>
                    <CandidateBadge row={row} />
                  </RowOpener>
                </TableCell>
                {/* **줄 수를 묶는다.** 목적이 열 줄이면 표가 그만큼 성기어져 위아래 줄을
                    눈으로 못 잇는다. 전문은 줄을 눌러 보기 창에서 읽는다. */}
                <TableCell className="text-muted-foreground hidden max-w-96 min-w-96 align-top text-sm lg:table-cell">
                  <p className="truncate" title={row.purpose}>
                    {row.purpose || '—'}
                  </p>
                </TableCell>
                <TableCell className="hidden align-top md:table-cell">
                  {row.test_items.length === 0 ? (
                    <span className="text-muted-foreground text-sm">시험 항목 미지정</span>
                  ) : (
                    <ul className="flex gap-x-3 text-sm">
                      {row.test_items.map((item) => (
                        <li key={item.term_id} className="flex items-center gap-1">
                          <Link
                            to={`/catalog/test-items/${item.term_id}`}
                            className="hover:underline"
                          >
                            {item.value}
                          </Link>
                          <span
                            className={`text-xs ${item.equipment_count === 0 ? 'text-amber-600' : 'text-muted-foreground'}`}
                            title={
                              item.equipment_count === 0
                                ? '이 항목이 되는 장비가 그 부서에 없습니다'
                                : undefined
                            }
                          >
                            {item.equipment_count}대
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </TableCell>
                <AttributeBodyCells columns={columns.shown} values={row.attributes} />
                <TableCell className="text-right whitespace-nowrap">
                  {/* **이 시험, 어느 장비로 돌리나.** 조건 속성이 그대로 검색 조건이 된다 —
                      시험 항목까지만 이으면 답이 「인장 되는 장비 N대」 라서, 사람이 다시
                      장비를 하나씩 열어 봐야 한다. */}
                  {row.attachment_count > 0 && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="mr-1"
                      onClick={() => setShowing(row)}
                    >
                      <ImageIcon className="mr-1 size-3.5" />
                      이미지 {row.attachment_count}
                    </Button>
                  )}
                  <Button size="sm" variant="outline" onClick={() => setAsking(row)}>
                    <Wrench className="mr-1 size-3.5" />
                    수행 가능 장비
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* **쪽을 넘는다** — 전사 목록은 사업부를 가로지르므로 더 길다. */}
      {(tests.data?.total ?? 0) > PAGE && (
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <Button
            size="sm"
            variant="outline"
            disabled={page === 0 || tests.loading}
            onClick={() => setPage((before) => Math.max(0, before - 1))}
          >
            이전
          </Button>
          <span className="text-muted-foreground">
            {page + 1} / {Math.max(1, Math.ceil((tests.data?.total ?? 0) / PAGE))} 쪽 · 전체{' '}
            {tests.data?.total ?? 0}건
          </span>
          <Button
            size="sm"
            variant="outline"
            disabled={(page + 1) * PAGE >= (tests.data?.total ?? 0) || tests.loading}
            onClick={() => setPage((before) => before + 1)}
          >
            다음
          </Button>
        </div>
      )}

      {asking && <CapabilityDialog test={asking} onClose={() => setAsking(null)} />}

      {/* 고치는 문은 부서 화면이다 — 여기서는 읽기만이라 「수정」 을 안 준다. */}
      <ReliabilityTestViewDialog
        test={viewing}
        onClose={() => setViewing(null)}
        onChanged={(next) => {
          setViewing(next)
          tests.reload()
        }}
      />

      <AttachmentsDialog
        open={showing !== null}
        testId={showing?.id ?? null}
        title={showing?.name ?? ''}
        onClose={() => setShowing(null)}
      />
    </div>
  )
}

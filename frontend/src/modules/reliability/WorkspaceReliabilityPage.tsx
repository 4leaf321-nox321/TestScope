/**
 * 부서 하나의 신뢰성 시험 — **「저 부서는 무슨 시험을 하나」 의 답.**
 *
 * 신뢰성 시험은 부서가 제품 개발·검증을 위해 수행하는 시험이고(고온고습 1000h · 열충격
 * 500 cycle), 「시험 항목」(장비가 할 수 있는 측정 — 인장·경도·열충격)과 다른 층이다.
 * 신뢰성 시험 하나가 시험 항목 하나 이상을 써서 돌고, 그 항목이 장비로 이어진다:
 *
 *     신뢰성 시험  →  시험 항목  →  장비
 *
 * 사이드바 「신뢰성 시험」 아래에 「부서 정보」 에서 고른 부서가 서고, 누르면 이 화면이다.
 * 등록은 그 부서의 관리자와 시스템 관리자. 등록 단추는 roles.ts 가, 줄마다의 수정 단추는
 * 서버의 `can_edit` 가 정한다 — 둘 다 표시일 뿐이고 권한은 서버가 판정한다.
 *
 * **후보를 검토하는 자리가 여기다.** AI 가 MCP 로 올린 시험은 확인 전까지 전사 목록에
 * 안 나오고 이 화면에만 선다 — 그래서 맨 위에 몇 건인지 적고, 줄에 배지를 단다. 목록
 * 아래쪽에 섞여 있으면 아무도 안 본다.
 *
 * **줄을 누르면 보기 창, 연필을 누르면 수정 창이다.** 읽으려고 수정 창을 여는 것은
 * 위험하고(읽다가 글자를 건드린다), 고칠 권한이 없는 사람은 연필이 없어 카드를 열 길이
 * 아예 없었다.
 *
 * 좁은 창에서는 **덜 급한 열을 접는다**(목적 → 시험 항목 순). 시험 항목은 줄바꿈이 안 되는
 * 덩어리라 폭을 안 내놓고, 그러면 목적 열만 혼자 찌그러져 글자 한 자 폭이 된다 — 전사
 * 목록과 같은 규칙이다. 목적 열은 `w-` 가 아니라 **`min-w-`** 라야 한다: `w-` 는 표가
 * 눌리면 브라우저가 무시한다.
 *
 * ## 속성은 **열로** 선다
 *
 * 한 칸에 「시험 온도: 85 ℃ / 시험 시간: 1000 h / …」 를 쌓아 두면 세로로 못 읽는다 —
 * 「온도를 안 적은 시험이 몇 건인가」 는 한 열을 위아래로 훑어야 보이는 것인데, 덩어리
 * 안에서는 같은 속성이 줄마다 다른 높이에 있다. 그래서 정의마다 열을 세우고, 머리글의
 * 깔때기로 **그 열만** 거른다(「값 없음」 을 포함해서). 열이 서른을 넘으므로 고르는 자리를
 * 함께 둔다.
 *
 * 열이 늘어난 만큼 표를 **화면 높이에 가둔다**(`viewport`): 안 그러면 가로 스크롤 막대가
 * 표 맨 아래에 있어서, 오른쪽 열을 보려면 먼저 세로로 끝까지 내려가야 한다.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { Pencil, Plus, Trash2, Wrench } from 'lucide-react'

import { ConfirmDialog } from '@/shared/components/ConfirmDialog'
import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
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
import { isPlainRowClick } from '@/shared/lib/rowClick'
import { useBackFromReference } from '@/shared/hooks/useBackFromReference'
import { ActiveFilterChips, FilterDiagnosis } from '@/modules/attributes/AttributeFilterBar'
import {
  AttributeBodyCells,
  AttributeColumnPicker,
  AttributeHeadCells,
  useAttributeColumns,
} from '@/modules/attributes/AttributeColumns'
import { CandidateBadge, isCandidate } from '@/modules/reliability/CandidateReview'
import {
  NameHead,
  PurposeHead,
  RowFilterChips,
  TestItemHead,
  useRowFilters,
} from '@/modules/reliability/ColumnFilters'
import { CapabilityDialog } from '@/modules/reliability/CapabilityDialog'
import { ReliabilityTestDialog } from '@/modules/reliability/ReliabilityTestDialog'
import {
  ReliabilityTestViewDialog,
  RowOpener,
} from '@/modules/reliability/ReliabilityTestViewDialog'
import { MAX_PAGE, PAGE, reliabilityApi } from '@/modules/reliability/api'
import { useBulkRunner } from '@/modules/reliability/useBulkRunner'
import type { BulkAction } from '@/modules/reliability/api'
import { BulkBar } from '@/shared/components/BulkBar'
import { useSelection } from '@/shared/hooks/useSelection'
import type { ReliabilityTest } from '@/modules/reliability/api'

export default function DivisionReliabilityPage() {
  // 주소에는 사업부 **코드**(`mx`)가 온다 — 이름이 바뀌어도 걸어 둔 주소가 안 깨진다.
  const { slug: code = '' } = useParams<{ slug: string }>()
  // 사업부 이름은 메뉴와 같은 목록에서 받는다 — 여기 없으면 메뉴에도 없는 사업부다.
  const listed = useResource(() => reliabilityApi.divisions(), [])
  /** 몇 번째 쪽. 운영에서 한 사업부에 1784건이 들어왔다 — 통째로 그리면 브라우저가 멎는다. */
  const [page, setPage] = useState(0)
  /**
   * 속성 조건. **주소에 싣는다** — 좁혀 놓은 화면을 옆 사람에게 링크로 건넬 수 있어야 하고,
   * 「조건을 안 적은 시험」 같은 물음은 한 번 만들면 계속 쓴다. 화면 안에만 두면 매번 다시 건다.
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
        // 거르기는 **되돌아갈 자리가 아니다** — 뒤로 가기가 조건 하나씩 풀리면 못 나간다.
        { replace: true },
      )
    },
    [setParams],
  )
  /** 속성 아닌 열의 조건 — 이름 · 목적 · 시험 항목 · 보유 장비. 주소에 함께 실린다. */
  const rowFilters = useRowFilters()
  /** 열로 세울 속성 — 고른 것은 브라우저에 남는다. */
  const columns = useAttributeColumns('reliability_test')
  const tests = useResource(
    () => reliabilityApi.list(code, PAGE, page * PAGE, attrs, rowFilters.value),
    [code, page, attrs, rowFilters.value],
  )
  useEffect(() => setPage(0), [code, attrs, rowFilters.value])
  const [editing, setEditing] = useState<ReliabilityTest | null>(null)
  const [creating, setCreating] = useState(false)
  const [removing, setRemoving] = useState<ReliabilityTest | null>(null)
  const [asking, setAsking] = useState<ReliabilityTest | null>(null)
  /** 읽기만 하는 창 — 줄을 누르면 이것. */
  const [viewing, setViewing] = useState<ReliabilityTest | null>(null)
  /** 끊어 보내고, 막히면 말한다 — 문서 단위 검토와 **같은 것 하나**를 쓴다. */
  const bulk = useBulkRunner(() => {
    picked.clear()
    setWholeSet(false)
    tests.reload()
  })

  const division = listed.data?.find((one) => one.code === code)
  const rows = tests.data?.items ?? []
  const total = tests.data?.total ?? 0
  // **고른 것은 목록에 있는 것만** — 거르기를 좁혔는데 안 보이는 줄이 골라진 채로 남으면,
  // 열 줄을 보면서 500건을 지우게 된다.
  const picked = useSelection(rows.map((one) => one.id))
  /** 쪽을 넘어 **전부**에 적용할까. 끈 채로 두면 보이는 쪽만 건드린다. */
  const [wholeSet, setWholeSet] = useState(false)

  /** 고른 줄(또는 조건에 맞는 전부)에 한 번에. */
  function runBulk(action: BulkAction, reason?: string) {
    void bulk.run(wholeSet ? everyId : picked.ids, action, reason)
  }

  /** 지금 조건에 맞는 **전부**의 id. 쪽을 넘어 적용할 때만 부른다. */
  async function everyId(): Promise<string[]> {
    const out: string[] = []
    for (let at = 0; at < total; at += MAX_PAGE) {
      // **거른 조건을 그대로 들고 간다** — 안 그러면 「이 조건의 전체 20건」 이라고 적어
      // 놓고 사업부의 1784건을 전부 확인한다.
      const got = await reliabilityApi.list(code, MAX_PAGE, at, attrs, rowFilters.value)
      out.push(...got.items.map((one) => one.id))
      if (got.items.length === 0) break
    }
    return out
  }
  // 서버가 후보를 앞으로 보내 준다 — 여기서는 세기만 한다.
  /**
   * 필터가 걸렸나. **0건이어도 표는 남긴다** — 표가 사라지면 머리글의 필터도 함께
   * 사라져서, 어느 열에 무엇이 걸렸는지 볼 수도 풀 수도 없다.
   */
  const filtered = attrs.length > 0 || rowFilters.count > 0
  const pending = rows.filter(isCandidate).length
  const pages = Math.max(1, Math.ceil(total / PAGE))
  // **표시일 뿐 권한이 아니다.** 서버가 줄마다 `can_edit` 을, 사업부마다 `can_register` 를
  // 판정한다 — 눌러야 403 을 아는 단추는 「할 수 있는 일」 을 알려 주지 못한다.
  const canEdit = division?.can_register ?? false

  if (listed.data && !division) {
    return (
      <div className="space-y-6">
        <PageHeader title="신뢰성 시험" />
        <EmptyState
          title="그런 사업부가 없습니다"
          hint="사업부는 「관리 → 온톨로지」 의 사업부 축에 있습니다. 지운 값이면 주소도 함께 사라집니다."
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        back={useBackFromReference()}
        title={division ? `${division.name} · 신뢰성 시험` : '신뢰성 시험'}
        description={
          division
            ? `${division.name} 사업부가 제품 개발·검증을 위해 수행하는 시험. 적용 시험 항목 옆의 수는 이 사업부에 속한 부서들의 장비 중 그 항목이 되는 대수입니다.`
            : undefined
        }
        actions={
          canEdit && (
            <Button onClick={() => setCreating(true)}>
              <Plus className="size-4" />
              신뢰성 시험 등록
            </Button>
          )
        }
      />

      <div className="flex flex-wrap items-center gap-3">
        {tests.data && (
          <p className="text-muted-foreground text-sm">
            신뢰성 시험 {total}종{filtered && ' · 필터 적용됨'}
            {pending > 0 && (
              // **숫자를 눈에 띄게 둔다.** 「확인 전 3건」 이 안 보이면 아무도 안 연다.
              <span className="text-destructive ml-2 font-medium">
                확인 전 {pending}건 — 내용을 읽고 확인해 주십시오
              </span>
            )}
          </p>
        )}
        <AttributeColumnPicker columns={columns} />
      </div>

      {/* 열 머리글에서 걸든 여기서 풀든 **같은 목록**이다 — 두 곳에 나눠 그리면 한쪽에서
          건 조건이 다른 쪽에서 안 보이고, 그러면 왜 스무 건만 뜨는지 못 찾는다. */}
      <div className="flex flex-wrap items-center gap-2">
        <ActiveFilterChips definitions={columns.all} value={attrs} onChange={setAttrs} />
        <RowFilterChips rows={rowFilters} />
      </div>
      {attrs.length > 0 && total === 0 && (
        <FilterDiagnosis target="reliability_test" attrs={attrs} />
      )}

      <ErrorNotice error={bulk.error ?? tests.error ?? listed.error} />

      {canEdit && (
        <BulkBar
          count={wholeSet ? total : picked.ids.length}
          onClear={() => {
            picked.clear()
            setWholeSet(false)
          }}
          busy={bulk.busy}
          outcome={bulk.outcome}
        >
          {/**
           * **쪽을 넘어 전부에 적용할까.** 쪽을 나누고 나면 「보이는 것 전부」 가 쉰 건
           * 뿐이라, 1784건을 확인하려면 서른여섯 번을 눌러야 한다 — 그것은 쪽을 나누기
           * 전과 똑같이 아무도 안 하는 일이다. 대신 **일부러 켜야** 하고, 켜면 몇 건인지
           * 숫자로 보인다.
           */}
          {total > rows.length && (
            <label className="flex items-center gap-1 text-xs">
              <input
                type="checkbox"
                checked={wholeSet}
                disabled={bulk.busy}
                onChange={(event) => setWholeSet(event.target.checked)}
              />
              필터 결과 전체 {total}건 적용
            </label>
          )}
          <Button size="sm" disabled={bulk.busy} onClick={() => runBulk('confirm')}>
            확인
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={bulk.busy}
            onClick={() => {
              // **사유를 받는다** — 없으면 AI 가 무엇을 자주 틀리는지 셀 수 없다.
              const said = window.prompt(
                `${wholeSet ? total : picked.ids.length}건을 반려합니다. 사유를 적어 주십시오`,
              )
              if (said?.trim()) runBulk('reject', said.trim())
            }}
          >
            반려
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={bulk.busy}
            onClick={() => {
              // **확정을 푸는 것이라 사유를 받는다.** 한 건씩 누를 때는 그 자리에서 보고
              // 누르지만, 서른 건이 한꺼번에 풀리면 반년 뒤에 「왜 풀렸나」 를 묻는 사람이
              // 반드시 있다 — 감사에 「누가 열었나」 만 있으면 답할 수 없다.
              const said = window.prompt(
                `${wholeSet ? total : picked.ids.length}건의 확정을 풀어 다시 후보로 돌립니다.` +
                  ' 그 순간부터 AI 가 다시 채울 수 있습니다. 사유를 적어 주십시오',
              )
              if (said?.trim()) runBulk('reopen', said.trim())
            }}
          >
            다시 후보로
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={bulk.busy}
            onClick={() => {
              const many = wholeSet ? total : picked.ids.length
              if (window.confirm(`${many}건을 지웁니다. 되돌릴 수 없습니다.`)) {
                runBulk('delete')
              }
            }}
          >
            지우기
          </Button>
        </BulkBar>
      )}

      {tests.data && rows.length === 0 && !filtered ? (
        <EmptyState
          title="등록된 신뢰성 시험이 없습니다"
          hint={
            canEdit
              ? '위의 「신뢰성 시험 등록」 으로 첫 시험을 적으십시오.'
              : '이 부서의 관리자 또는 시스템 관리자가 등록합니다.'
          }
        />
      ) : (
        <Table viewport>
          <TableHeader>
            <TableRow>
              {canEdit && (
                <TableHead className="w-8">
                  <input
                    type="checkbox"
                    aria-label="보이는 줄 전부 고르기"
                    checked={picked.allPicked}
                    ref={(box) => {
                      // 하나라도 골랐지만 전부는 아니면 **반쯤 찬 모양** — 「전부 골랐다」
                      // 로 읽히면 그대로 지우기를 누른다.
                      if (box) box.indeterminate = picked.somePicked
                    }}
                    onChange={picked.toggleAll}
                  />
                </TableHead>
              )}
              <TableHead className="min-w-44">
                <NameHead rows={rowFilters} />
              </TableHead>
              <TableHead className="hidden w-full min-w-96 lg:table-cell">
                <PurposeHead rows={rowFilters} />
              </TableHead>
              <TableHead className="hidden min-w-48 md:table-cell">
                <TestItemHead rows={rowFilters} />
              </TableHead>
              <AttributeHeadCells columns={columns.shown} value={attrs} onChange={setAttrs} />
              <TableHead className="w-32" />
              {canEdit && <TableHead className="w-24" />}
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
            {rows.map((row) => (
              <TableRow
                key={row.id}
                className="hover:bg-muted/50 cursor-pointer"
                // 줄 어디를 눌러도 열되 **링크·단추 위에서는 안 연다** — 시험 항목 링크를
                // 누른 사람은 그 항목으로 가려던 것이다.
                onClick={(event) => isPlainRowClick(event) && setViewing(row)}
              >
                {canEdit && (
                  <TableCell onClick={(event) => event.stopPropagation()}>
                    <input
                      type="checkbox"
                      aria-label={`${row.name} 고르기`}
                      checked={picked.has(row.id)}
                      onChange={() => picked.toggle(row.id)}
                    />
                  </TableCell>
                )}
                <TableCell>
                  <RowOpener name={row.name} onOpen={() => setViewing(row)}>
                    <CandidateBadge row={row} />
                  </RowOpener>
                </TableCell>
                {/* **줄 수를 묶는다.** 전문은 줄을 눌러 보기 창에서 읽는다. */}
                <TableCell className="text-muted-foreground hidden w-full min-w-96 align-top text-sm lg:table-cell">
                  <p className="line-clamp-3 whitespace-pre-line" title={row.purpose}>
                    {row.purpose || '—'}
                  </p>
                </TableCell>
                <TableCell className="hidden align-top md:table-cell">
                  {row.test_items.length === 0 ? (
                    // 「장비 없음」 이 아니라 「안 정함」 — 둘은 해야 할 일이 다르다.
                    <span className="text-muted-foreground text-sm">시험 항목 미지정</span>
                  ) : (
                    <ul className="flex flex-wrap gap-x-3 gap-y-1 text-sm">
                      {row.test_items.map((item) => (
                        <li key={item.term_id} className="flex items-center gap-1">
                          <Link
                            to={`/catalog/test-items/${item.term_id}`}
                            className="hover:underline"
                          >
                            {item.value}
                          </Link>
                          {item.equipment_count === 0 ? (
                            <span
                              className="text-amber-600 text-xs"
                              title="이 항목이 되는 장비가 이 부서에 없습니다"
                            >
                              0대
                            </span>
                          ) : (
                            <Link
                              to={`/equipment?test_item_term_id=${item.term_id}`}
                              className="text-muted-foreground text-xs hover:underline"
                            >
                              {item.equipment_count}대
                            </Link>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </TableCell>
                <AttributeBodyCells columns={columns.shown} values={row.attributes} />
                {/* **이 시험, 어느 장비로 돌리나.** 조건 속성이 그대로 검색 조건이 된다 —
                    「이 부서 장비 N대」 는 조건을 안 본 수라, 그 N 대를 사람이 다시 하나씩
                    열어 봐야 했다. 읽기는 누구나 — 빌릴 곳을 찾는 것이 이 화면의 쓸모다. */}
                <TableCell className="text-right whitespace-nowrap">
                  <Button size="sm" variant="outline" onClick={() => setAsking(row)}>
                    <Wrench className="mr-1 size-3.5" />
                    수행 가능 장비
                  </Button>
                </TableCell>
                {canEdit && (
                  <TableCell className="text-right whitespace-nowrap">
                    {row.can_edit && (
                      <>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`${row.name} 수정`}
                          onClick={() => setEditing(row)}
                        >
                          <Pencil className="size-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`${row.name} 삭제`}
                          onClick={() => setRemoving(row)}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      </>
                    )}
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* **쪽을 넘는다.** 1784건을 한 화면에 그리면 브라우저가 멎는다 — 줄마다 속성과
          시험 항목과 장비 수가 딸려 온다. */}
      {pages > 1 && (
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
            {page + 1} / {pages} 쪽 · 전체 {total}건
          </span>
          <Button
            size="sm"
            variant="outline"
            disabled={page + 1 >= pages || tests.loading}
            onClick={() => setPage((before) => before + 1)}
          >
            다음
          </Button>
        </div>
      )}

      {asking && <CapabilityDialog test={asking} onClose={() => setAsking(null)} />}

      <ReliabilityTestViewDialog
        test={viewing}
        onClose={() => setViewing(null)}
        onEdit={(row) => {
          setViewing(null)
          setEditing(row)
        }}
        onChanged={(next) => {
          setViewing(next)
          tests.reload()
        }}
      />

      <ReliabilityTestDialog
        open={creating || editing !== null}
        division={code}
        editing={editing}
        onReviewed={(next) => {
          // 창은 열어 둔다 — 확인한 뒤에 이어서 고칠 수 있어야 한다.
          setEditing(next)
          tests.reload()
        }}
        onClose={() => {
          setCreating(false)
          setEditing(null)
        }}
        onSaved={() => {
          setCreating(false)
          setEditing(null)
          tests.reload()
        }}
      />

      <ConfirmDialog
        open={removing !== null}
        title="신뢰성 시험을 삭제합니다"
        description={
          <>
            <strong>{removing?.name}</strong> 을 목록에서 삭제합니다. 데이터는 보존되며 변경
            이력에 남습니다.
          </>
        }
        confirmLabel="삭제"
        destructive
        onConfirm={async () => {
          if (removing) await reliabilityApi.remove(removing.id)
          setRemoving(null)
          tests.reload()
        }}
        onClose={() => setRemoving(null)}
      />
    </div>
  )
}

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
 * ## 좁은 창에서는 열을 접는다
 *
 * 열이 여섯인데 시험 항목·속성은 줄바꿈이 안 되는 덩어리라 폭을 안 내놓는다. 그래서 창이
 * 좁아지면 **목적 열만 혼자 찌그러져** 글자 한 자 폭이 되고(높이는 수십 줄), 그러고도
 * 가로 스크롤이 생긴다 — 둘 다 겪는 최악이다.
 *
 * 줄을 누르면 카드 전체가 보기 창에 열리므로, 좁을 때는 **덜 급한 열을 아예 접는다**:
 * 속성(xl) → 목적(lg) → 시험 항목(md) 순으로 사라지고 이름과 단추는 끝까지 남는다.
 *
 * 목적 열은 `w-` 가 아니라 **`min-w-`** 다. `w-` 는 표가 눌리면 브라우저가 그냥 무시해서
 * 다시 한 자 폭이 된다. `w-full` 을 같이 둬서 **남는 폭은 목적이 가져간다** — 글을 담는
 * 열이 하나뿐이므로 넓어진 화면의 여유는 거기로 가는 것이 맞다.
 */

import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
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
import { CandidateBadge } from '@/modules/reliability/CandidateReview'
import { CapabilityDialog } from '@/modules/reliability/CapabilityDialog'
import {
  ReliabilityTestViewDialog,
  RowOpener,
} from '@/modules/reliability/ReliabilityTestViewDialog'
import { reliabilityApi } from '@/modules/reliability/api'
import type { ReliabilityTest } from '@/modules/reliability/api'

function haystack(row: ReliabilityTest): string {
  return [
    row.name,
    row.purpose,
    row.workspace_name,
    ...row.test_items.map((one) => one.value),
    ...row.attributes.map((one) => `${one.label} ${one.display}`),
  ]
    .join(' ')
    .toLowerCase()
}

export default function ReliabilityTestsPage() {
  // 속성 조건은 **서버가** 거른다 — 아래 찾기 칸은 받은 쪽 안에서만 훑는다.
  const [attrs, setAttrs] = useState<string[]>([])
  /** 확인 전 후보까지 볼까. **기본은 안 본다** — 확정된 것만이 이 표의 답이다. */
  const [withCandidates, setWithCandidates] = useState(false)
  const tests = useResource(
    () => reliabilityApi.listAll(attrs, withCandidates),
    [attrs, withCandidates],
  )
  const [query, setQuery] = useState('')
  const [asking, setAsking] = useState<ReliabilityTest | null>(null)
  /** 그림 보기 — **조회하는 사람의 자리.** 수정 창을 열지 않고 본다. */
  const [showing, setShowing] = useState<typeof asking>(null)
  /** 카드 전체 보기 — 줄을 누르면 이것. */
  const [viewing, setViewing] = useState<typeof asking>(null)
  const rows = tests.data ?? []
  const needle = query.trim().toLowerCase()
  const shown = useMemo(
    () => (needle ? rows.filter((row) => haystack(row).includes(needle)) : rows),
    [rows, needle],
  )
  const workspaces = new Set(rows.map((row) => row.workspace_slug)).size

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
        empty={tests.data?.length === 0}
      />

      <div className="flex flex-wrap items-center gap-3">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="찾기 — 시험 · 목적 · 부서 · 시험 항목 · 속성 값"
          className="w-80"
        />
        {tests.data && (
          <p className="text-muted-foreground text-sm">
            신뢰성 시험 {rows.length}종 · 부서 {workspaces}곳
            {needle && ` · 걸린 것 ${shown.length}종`}
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
      </div>

      <ErrorNotice error={tests.error} />

      {tests.data && rows.length === 0 ? (
        <EmptyState
          title="등록된 신뢰성 시험이 없습니다"
          hint="사이드바 「신뢰성 시험」 아래의 부서 화면에서 그 부서의 관리자가 등록합니다. 부서가 안 보이면 「관리 → 부서 정보」 의 「신뢰성 시험」 표시를 켭니다."
        />
      ) : tests.data && shown.length === 0 ? (
        <EmptyState
          title="조건에 맞는 신뢰성 시험이 없습니다"
          hint="검색어를 줄여 보십시오."
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>부서</TableHead>
              <TableHead>신뢰성 시험</TableHead>
              <TableHead className="hidden w-full min-w-96 lg:table-cell">목적</TableHead>
              <TableHead className="hidden min-w-48 md:table-cell">
                적용 시험 항목 · 보유 장비
              </TableHead>
              <TableHead className="hidden min-w-56 xl:table-cell">속성</TableHead>
              <TableHead className="w-32" />
            </TableRow>
          </TableHeader>
          <TableBody>
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
                    to={`/reliability-tests/${row.workspace_slug}`}
                    className="hover:underline"
                  >
                    {row.workspace_name}
                  </Link>
                </TableCell>
                <TableCell>
                  <RowOpener name={row.name} onOpen={() => setViewing(row)}>
                    <CandidateBadge row={row} />
                  </RowOpener>
                </TableCell>
                {/* **줄 수를 묶는다.** 목적이 열 줄이면 표가 그만큼 성기어져 위아래 줄을
                    눈으로 못 잇는다. 전문은 줄을 눌러 보기 창에서 읽는다. */}
                <TableCell className="text-muted-foreground hidden w-full min-w-96 align-top text-sm lg:table-cell">
                  <p className="line-clamp-3 whitespace-pre-line" title={row.purpose}>
                    {row.purpose || '—'}
                  </p>
                </TableCell>
                <TableCell className="hidden align-top md:table-cell">
                  {row.test_items.length === 0 ? (
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
                <TableCell className="hidden align-top xl:table-cell">
                  {row.attributes.length === 0 ? (
                    <span className="text-muted-foreground text-sm">—</span>
                  ) : (
                    <ul className="space-y-0.5 text-sm">
                      {row.attributes.map((item) => (
                        <li key={item.definition_id} className="flex flex-wrap gap-x-1">
                          <span className="text-muted-foreground">{item.label}</span>
                          <span>{item.display}</span>
                          {item.status === 'draft' && (
                            <span className="text-muted-foreground text-xs">초안</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </TableCell>
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

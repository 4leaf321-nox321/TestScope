/**
 * 신뢰성 시험 **수행 가능 현황** — 시험마다 지금 돌릴 수 있는 장비 수.
 *
 * 시험 하나씩 「되는 장비」 창을 열면 답은 있는데, 장비가 0대인 시험 · 1대뿐이라 그 장비가 서면
 * 멈추는 시험 · 교정이 곧 끝나는 장비에 기대는 시험을 한눈에 볼 자리가 없었다(2026-10-16).
 *
 * 판정은 서버가 「되는 장비」 와 같은 규칙으로 한다(조건 · 장비 상태)에 교정을 더해서다. 시험의
 * 상태는 **가장 적은 시험 항목(병목)** 이 정하므로, 수는 병목 항목의 것을 보여 주고 항목이
 * 여럿이면 줄 아래에 전부 적는다.
 */

import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

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
import { shownDateTime } from '@/shared/lib/datetime'
import { CapabilityDialog } from '@/modules/reliability/CapabilityDialog'
import { reliabilityApi } from '@/modules/reliability/api'
import type { CoverageRow, CoverageState, ReliabilityTest } from '@/modules/reliability/api'

/** 상태 — 급한 것부터. 서버 `coverage.STATES` 와 같은 차례. */
export const COVERAGE_STATES: { value: CoverageState; label: string; hint: string }[] = [
  { value: 'none', label: '불가', hint: '돌릴 장비 0대(조건·상태·교정 기준)' },
  {
    value: 'check',
    label: '확인 필요',
    hint: '돌릴 장비 0대이나 조건 미기재·교정 이력 없는 장비 있음',
  },
  { value: 'single', label: '1대뿐', hint: '그 장비가 서면 시험 중단' },
  { value: 'soon', label: '교정 임박', hint: '교정이 곧 끝나는 장비가 빠지면 1대 이하' },
  { value: 'no_items', label: '항목 없음', hint: '시험 항목이 지정되지 않아 셀 수 없음' },
  { value: 'ok', label: '여유', hint: '2대 이상' },
]

const STATE_CLASS: Record<CoverageState, string> = {
  none: 'bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-200',
  check: 'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200',
  single: 'bg-orange-100 text-orange-900 dark:bg-orange-900/40 dark:text-orange-200',
  soon: 'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200',
  no_items: 'bg-muted text-muted-foreground',
  ok: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200',
}

export function StateBadge({ state }: { state: CoverageState }) {
  const meta = COVERAGE_STATES.find((one) => one.value === state)
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-xs whitespace-nowrap ${STATE_CLASS[state]}`}
      title={meta?.hint}
    >
      {meta?.label ?? state}
    </span>
  )
}

/** 병목 항목 — 수를 보여 줄 항목. 서버가 이름으로 알려 준다. */
function bottleneckOf(row: CoverageRow) {
  return row.items.find((one) => one.value === row.bottleneck) ?? row.items[0]
}

export default function CoveragePage() {
  const [params, setParams] = useSearchParams()
  const division = params.get('division') ?? ''
  const state = (params.get('state') ?? '') as CoverageState | ''
  const divisions = useResource(() => reliabilityApi.divisions(), [])
  const board = useResource(() => reliabilityApi.coverage(division || undefined), [division])
  /** 「장비 보기」 — 시험을 읽어 와서 되는 장비 창을 연다. */
  const [opening, setOpening] = useState<ReliabilityTest | null>(null)
  const [openError, setOpenError] = useState<Error | null>(null)

  const rows = useMemo(
    () => (board.data?.rows ?? []).filter((one) => !state || one.state === state),
    [board.data, state],
  )

  function setParam(key: string, value: string) {
    setParams(
      (before) => {
        const next = new URLSearchParams(before)
        if (value) next.set(key, value)
        else next.delete(key)
        return next
      },
      { replace: true },
    )
  }

  async function open(row: CoverageRow) {
    setOpenError(null)
    try {
      setOpening(await reliabilityApi.read(row.test_id))
    } catch (caught) {
      setOpenError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

  const total = board.data?.rows.length ?? 0
  return (
    <div className="space-y-6">
      <PageHeader
        back={{ to: '/reliability-tests', label: '신뢰성 시험' }}
        title="수행 가능 현황"
        description={`확정된 최신판 신뢰성 시험마다 지금 돌릴 수 있는 장비 수. 조건이 다 맞고, 가동 상태이고, 교정이 유효한 장비만 셈. 교정 임박은 ${board.data?.horizon_days ?? 60}일 이내 만료.`}
      />

      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label="사업부"
          className="border-input bg-background h-8 rounded-md border px-2 text-sm"
          value={division}
          onChange={(event) => setParam('division', event.target.value)}
        >
          <option value="">전 사업부</option>
          {(divisions.data ?? []).map((one) => (
            <option key={one.code} value={one.code}>
              {one.name}
            </option>
          ))}
        </select>
        <Button
          size="sm"
          variant={state ? 'ghost' : 'secondary'}
          onClick={() => setParam('state', '')}
        >
          전체 {total}
        </Button>
        {COVERAGE_STATES.map((one) => (
          <Button
            key={one.value}
            size="sm"
            variant={state === one.value ? 'secondary' : 'ghost'}
            title={one.hint}
            onClick={() => setParam('state', state === one.value ? '' : one.value)}
          >
            {one.label} {board.data?.counts[one.value] ?? 0}
          </Button>
        ))}
        {board.data && (
          <span className="text-muted-foreground ml-auto text-xs">
            계산 {shownDateTime(board.data.computed_at)}
          </span>
        )}
      </div>

      <ErrorNotice error={board.error ?? openError} />

      {board.data && rows.length === 0 ? (
        <EmptyState
          title={total === 0 ? '확정된 신뢰성 시험 없음' : '해당 상태의 시험 없음'}
          hint={
            total === 0
              ? '사업부 화면에서 신뢰성 시험을 등록·확인하면 여기에 표시됨.'
              : undefined
          }
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>상태</TableHead>
              <TableHead>사업부</TableHead>
              <TableHead className="min-w-56">신뢰성 시험</TableHead>
              <TableHead>병목 시험 항목</TableHead>
              <TableHead
                className="text-right"
                title="조건 충족·가동·교정 유효(괄호: 시험 사업부 소유)"
              >
                돌릴 수 있음
              </TableHead>
              <TableHead className="text-right">교정 임박</TableHead>
              <TableHead
                className="text-right"
                title="조건 미기재 또는 교정 대상인데 이력 없음"
              >
                확인 필요
              </TableHead>
              <TableHead className="text-right">교정 만료</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => {
              const weakest = row.items.length > 0 ? bottleneckOf(row) : undefined
              return (
                <TableRow key={row.test_id}>
                  <TableCell>
                    <StateBadge state={row.state} />
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    <Link
                      to={`/reliability-tests/${row.division_code}`}
                      className="hover:underline"
                    >
                      {row.division_name}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <Link
                      to={`/reliability-tests/${row.division_code}?name=${encodeURIComponent(row.name)}`}
                      className="font-medium hover:underline"
                    >
                      {row.name}
                    </Link>
                    {row.items.length > 1 && (
                      <span className="text-muted-foreground block text-xs">
                        항목별 돌릴 수 있음:{' '}
                        {row.items.map((one) => `${one.value} ${one.ready}대`).join(' · ')}
                      </span>
                    )}
                    {row.skipped_conditions > 0 && (
                      <span className="block text-xs text-amber-700 dark:text-amber-400">
                        단위를 옮기지 못해 뺀 조건 {row.skipped_conditions}개 — 실제보다 넓게
                        셈
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="whitespace-nowrap">{row.bottleneck ?? '—'}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {weakest ? (
                      <>
                        {weakest.ready}
                        <span className="text-muted-foreground"> ({weakest.in_division})</span>
                      </>
                    ) : (
                      '—'
                    )}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {weakest?.soon ?? '—'}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {weakest?.check ?? '—'}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {weakest?.expired ?? '—'}
                  </TableCell>
                  <TableCell>
                    {row.items.length > 0 && (
                      <Button size="sm" variant="outline" onClick={() => void open(row)}>
                        장비 보기
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      )}

      {opening && <CapabilityDialog test={opening} onClose={() => setOpening(null)} />}
    </div>
  )
}

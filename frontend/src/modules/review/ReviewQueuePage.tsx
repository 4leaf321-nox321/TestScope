/**
 * 검토함의 한 물음 — 줄마다 **후보 · 추천 · 근거**를 놓고 고른다.
 *
 * ## 추천은 정답이 아니다
 *
 * 첫 보기를 습관적으로 누르게 되므로 추천에는 늘 근거가 붙고, 확신이 낮은 줄에는 추천이 없다.
 * ## 의견과 확정은 다르다
 *
 * 로그인한 누구나 한 줄에 의견 하나를 낸다 — 데이터는 안 바뀌고 모이기만 한다. 갈리는 줄이
 * 보이게(「의견 3 · 2:1」). 확정은 시스템 관리자가 하고 그때 적용된다. 의견 없이도 확정할 수
 * 있어 사람이 적을 때 느려지지 않는다. 확정 칸은 다수 의견으로 미리 채우되 자동 확정은 없다.
 *
 * 후보에 없는 답을 위해 「직접 고르기」 를, 지금 모르겠으면 「건너뛰기」 를 둔다 — 건너뛴 것은
 * 다시 뜬다. 고르면 기존 규칙(규격 → 인용 계열에 붙임)이 그대로 돌고, 누가 골랐는지 남는다.
 *
 * ## 고른 줄은 사라진다
 *
 * 172건을 하나씩 정하는 자리라 고른 줄이 목록에 남아 있으면 어디까지 했는지 모른다. 정한 것은
 * `?status=decided` 에서 보고, 거기서 「다시 열기」 로 다른 걸로 고칠 수 있다 — 이미 일어난
 * 일(지운 연결·만든 정의)은 안 되돌린다. 대상이 지워진 줄은 `?status=gone` 에 따로 선다:
 * 정한 것이 아니라 물음이 사라진 것이다.
 */

import { useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ExternalLink } from 'lucide-react'

import { ApiError } from '@/shared/api/client'
import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { SearchablePicker } from '@/shared/components/SearchablePicker'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { useAuth } from '@/shared/auth/AuthContext'
import { useResource } from '@/shared/hooks/useResource'
import { shownDateTime } from '@/shared/lib/datetime'
import { AXIS, vocabularyApi } from '@/modules/vocabulary/api'
import { reviewApi } from '@/modules/review/api'
import type { ReviewProposal } from '@/modules/review/api'

const PAGE = 50

/** 「직접 고르기」 가 여는 어휘 — 물음마다 다르다. 예/아니오 물음에는 없다. */
function directAxis(queue: string): 'test_item' | 'condition' | null {
  if (queue === 'method_test_items') return 'test_item'
  if (queue === 'test_item_axes') return 'condition'
  return null
}

export default function ReviewQueuePage() {
  const { queue = '' } = useParams<{ queue: string }>()
  const { user } = useAuth()
  const isAdmin = user?.is_system_admin ?? false
  const [params, setParams] = useSearchParams()
  const status = params.get('status') ?? 'open'
  const [offset, setOffset] = useState(0)
  const queues = useResource(() => reviewApi.queues(), [])
  const page = useResource(
    () => reviewApi.list(queue, { status, limit: PAGE, offset }),
    [queue, status, offset],
  )
  // 직접 고르기의 어휘. 96·12개라 한 번에 받아 둔다.
  const axis = directAxis(queue)
  const testItems = useResource(
    () => (axis === 'test_item' ? vocabularyApi.terms(AXIS.testItem) : Promise.resolve([])),
    [axis],
  )
  const conditions = useResource(
    () => (axis === 'condition' ? vocabularyApi.conditions() : Promise.resolve([])),
    [axis],
  )
  const directOptions = useMemo(() => {
    if (axis === 'test_item')
      return (testItems.data ?? [])
        .filter((one) => one.code)
        .map((one) => ({ id: one.code as string, label: one.value }))
    if (axis === 'condition')
      return (conditions.data ?? []).map((one) => ({ id: one.key, label: one.label }))
    return []
  }, [axis, testItems.data, conditions.data])

  /** 이 화면에서 정한 줄 — 목록에서 빼되 다시 받지는 않는다(자리가 뛰지 않게). */
  const [gone, setGone] = useState<Set<string>>(new Set())
  const [error, setError] = useState<ApiError | Error | null>(null)

  const meta = (queues.data ?? []).find((one) => one.key === queue)
  const rows = (page.data?.items ?? []).filter((one) => !gone.has(one.id))
  const total = page.data?.total ?? 0

  async function act(row: ReviewProposal, run: () => Promise<unknown>) {
    setError(null)
    try {
      await run()
      setGone((current) => new Set(current).add(row.id))
      queues.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={meta?.label ?? '검토함'}
        description={meta?.description}
        back={{ to: '/admin/review', label: '검토함' }}
        actions={
          <div className="flex gap-1">
            {(
              [
                ['open', '남은 것'],
                ['voted', '의견 있음'],
                ['skipped', '건너뛴 것'],
                ['decided', '정한 것'],
                ['gone', '대상 없음'],
              ] as const
            ).map(([value, label]) => (
              <Button
                key={value}
                size="sm"
                variant={status === value ? 'secondary' : 'ghost'}
                onClick={() => {
                  setOffset(0)
                  setGone(new Set())
                  setParams(value === 'open' ? {} : { status: value })
                }}
              >
                {label}
              </Button>
            ))}
          </div>
        }
      />
      <ErrorNotice error={page.error ?? error} />

      {page.data && rows.length === 0 ? (
        <EmptyState
          title={status === 'open' ? '남은 것이 없습니다' : '없습니다'}
          hint={status === 'open' ? '이 물음은 끝났습니다.' : undefined}
        />
      ) : (
        <ul className="space-y-3">
          {rows.map((row) => (
            <ProposalRow
              key={row.id}
              row={row}
              multi={meta?.multi ?? false}
              directOptions={directOptions}
              readOnly={status === 'decided' || status === 'gone'}
              isAdmin={isAdmin}
              onDecide={(choice, note) =>
                act(row, () => reviewApi.decide(queue, row.id, choice, note))
              }
              onSkip={() => act(row, () => reviewApi.skip(queue, row.id))}
              onVote={(choice, note) => reviewApi.vote(queue, row.id, choice, note)}
              onWithdraw={() => reviewApi.withdrawVote(queue, row.id)}
              onReopen={
                status === 'decided' && isAdmin
                  ? () => act(row, () => reviewApi.reopen(queue, row.id))
                  : undefined
              }
            />
          ))}
        </ul>
      )}

      {total > PAGE && (
        <div className="text-muted-foreground flex items-center justify-between text-sm">
          <span>
            {total}건 중 {Math.min(offset + PAGE, total)}건까지
          </span>
          <div className="flex gap-1">
            <Button
              size="sm"
              variant="outline"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE))}
            >
              이전
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={offset + PAGE >= total}
              onClick={() => setOffset(offset + PAGE)}
            >
              다음
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

function ProposalRow({
  row,
  multi,
  directOptions,
  readOnly,
  isAdmin,
  onDecide,
  onSkip,
  onVote,
  onWithdraw,
  onReopen,
}: {
  row: ReviewProposal
  multi: boolean
  directOptions: { id: string; label: string }[]
  readOnly: boolean
  isAdmin: boolean
  onDecide: (choice: string[], note?: string) => Promise<void>
  onSkip: () => Promise<void>
  /** 의견 — 줄은 남고 의견만 갱신된다. */
  onVote: (choice: string[], note?: string) => Promise<ReviewProposal>
  onWithdraw: () => Promise<ReviewProposal>
  /** 정한 줄에서만 — 다시 열어 다른 걸로 고른다. */
  onReopen?: () => Promise<void>
}) {
  /** 의견은 이 줄 안에서 갱신된다 — 목록을 다시 받으면 자리가 뛴다. */
  const [live, setLive] = useState(row)
  const votes = live.votes
  const tally = useMemo(() => {
    const counts = new Map<string, string[]>()
    for (const one of votes)
      for (const code of one.choice) counts.set(code, [...(counts.get(code) ?? []), one.user])
    return counts
  }, [votes])
  /** 다수 의견 — 확정 칸을 미리 채운다. 동수면 없다. */
  const majority = useMemo<string[] | null>(() => {
    if (votes.length === 0) return null
    const seen = new Map<string, number>()
    for (const one of votes) {
      const key = [...one.choice].sort().join('|')
      seen.set(key, (seen.get(key) ?? 0) + 1)
    }
    const ranked = [...seen.entries()].sort((a, b) => b[1] - a[1])
    if (ranked.length > 1 && ranked[0][1] === ranked[1][1]) return null
    return ranked[0][0] === '' ? [] : ranked[0][0].split('|')
  }, [votes])
  const split =
    votes.length > 1 && new Set(votes.map((one) => [...one.choice].sort().join('|'))).size > 1
  const [picked, setPicked] = useState<string[]>(live.my_vote ?? majority ?? [])
  const [direct, setDirect] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const recommended = row.candidates.find((one) => one.recommended)

  function toggle(code: string) {
    setDirect('')
    setPicked((current) =>
      multi
        ? current.includes(code)
          ? current.filter((one) => one !== code)
          : [...current, code]
        : [code],
    )
  }

  const choice = direct ? (multi ? [...picked, direct] : [direct]) : picked
  const canDecide = choice.length > 0 || multi

  async function submit(chosen: string[]) {
    setBusy(true)
    try {
      await onDecide(chosen, note.trim() || undefined)
    } finally {
      setBusy(false)
    }
  }

  return (
    <li className="rounded-md border p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium">
            {row.subject_label}
            {votes.length > 0 && (
              // **갈리는 줄이 보인다.** 합의된 건 훑어 확정하고, 갈린 것만 모여 얘기한다.
              <span
                className={`ml-2 rounded px-1.5 py-0.5 text-xs font-normal ${
                  split
                    ? 'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200'
                    : 'bg-muted text-muted-foreground'
                }`}
              >
                의견 {votes.length}
                {split ? ' · 갈림' : votes.length > 1 ? ' · 합의' : ''}
              </span>
            )}
          </p>
          {row.context && (
            <p className="text-muted-foreground mt-0.5 text-sm">{row.context}</p>
          )}
        </div>
        {row.link && (
          <Link
            to={row.link}
            target="_blank"
            className="text-muted-foreground hover:text-foreground inline-flex shrink-0 items-center gap-1 text-xs"
          >
            상세 <ExternalLink className="size-3" />
          </Link>
        )}
      </div>

      {readOnly ? (
        <div className="mt-2 flex items-start justify-between gap-3 text-sm">
          <p className="min-w-0">
            {row.status === 'gone' ? (
              // **정한 것이 아니다.** 물음 자체가 사라진 것 — 정한 것과 섞이면 셈이 틀린다.
              <span className="text-muted-foreground">
                {row.decided_by ?? '대상 없어짐'} · {shownDateTime(row.decided_at)}
              </span>
            ) : (
              <>
                <span className="font-medium">
                  {(row.choice ?? []).length === 0
                    ? '해당 없음'
                    : (row.choice ?? [])
                        .map(
                          (code) =>
                            row.candidates.find((one) => one.code === code)?.label ?? code,
                        )
                        .join(' · ')}
                </span>
                <span className="text-muted-foreground">
                  {' '}
                  — {row.decided_by ?? '?'} · {shownDateTime(row.decided_at)}
                  {row.followed === true && ' · 추천대로'}
                  {row.followed === false && ' · 추천과 다르게'}
                </span>
              </>
            )}
            {row.note && (
              <span className="text-muted-foreground block text-xs">{row.note}</span>
            )}
            {votes.length > 0 && (
              <span className="text-muted-foreground block text-xs">
                의견:{' '}
                {votes
                  .map(
                    (one) =>
                      `${one.user} → ${
                        one.choice.length === 0
                          ? '해당 없음'
                          : one.choice
                              .map(
                                (code) =>
                                  row.candidates.find((c) => c.code === code)?.label ?? code,
                              )
                              .join('·')
                      }`,
                  )
                  .join(' · ')}
              </span>
            )}
          </p>
          {onReopen && (
            <Button
              size="sm"
              variant="outline"
              className="shrink-0"
              disabled={busy}
              title="다른 걸로 고르려고 다시 엽니다. 이미 일어난 일(지운 연결·만든 정의)은 안 되돌립니다."
              onClick={async () => {
                setBusy(true)
                try {
                  await onReopen()
                } finally {
                  setBusy(false)
                }
              }}
            >
              다시 열기
            </Button>
          )}
        </div>
      ) : (
        <>
          <ul className="mt-3 space-y-1">
            {row.candidates.map((one) => {
              const on = picked.includes(one.code) && !direct
              return (
                <li key={one.code}>
                  <label className="flex cursor-pointer items-start gap-2 text-sm">
                    <input
                      type={multi ? 'checkbox' : 'radio'}
                      name={row.id}
                      checked={on}
                      onChange={() => toggle(one.code)}
                      className="mt-1"
                    />
                    <span>
                      {one.label}
                      {tally.has(one.code) && (
                        <span className="text-muted-foreground ml-2 text-xs">
                          {tally.get(one.code)?.join(' · ')}
                        </span>
                      )}
                      {one.recommended && (
                        <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-900 dark:bg-amber-900/40 dark:text-amber-200">
                          추천
                        </span>
                      )}
                      {/* **근거는 추천 옆에 늘 붙는다.** 근거 없는 추천은 첫 보기를 누르게 할 뿐이다. */}
                      {one.reason && (
                        <span className="text-muted-foreground block text-xs">
                          {one.reason}
                        </span>
                      )}
                    </span>
                  </label>
                </li>
              )
            })}
          </ul>

          <div className="mt-3 flex flex-wrap items-end gap-2">
            {directOptions.length > 0 && (
              <div className="w-64">
                <SearchablePicker
                  value={direct}
                  onChange={(next) => {
                    setDirect(next)
                    if (!multi) setPicked([])
                  }}
                  options={directOptions}
                  placeholder="직접 고르기"
                  detailTitle="직접 고르기"
                  detailHint="후보에 없는 답. 이 물음의 어휘 전부에서 고릅니다."
                />
              </div>
            )}
            <Input
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="메모 (선택) — 왜 그렇게 정했나"
              className="max-w-xs"
            />
            {/* 의견 — 누구나. 줄은 남고 의견만 바뀐다. */}
            <Button
              size="sm"
              variant={isAdmin ? 'outline' : 'default'}
              disabled={busy || !canDecide}
              onClick={async () => {
                setBusy(true)
                try {
                  setLive(await onVote(choice, note.trim() || undefined))
                } finally {
                  setBusy(false)
                }
              }}
            >
              {live.my_vote
                ? '의견 바꾸기'
                : multi && choice.length === 0
                  ? '축 없음 의견'
                  : '의견 내기'}
            </Button>
            {live.my_vote && (
              <Button
                size="sm"
                variant="ghost"
                disabled={busy}
                onClick={async () => {
                  setBusy(true)
                  try {
                    setLive(await onWithdraw())
                  } finally {
                    setBusy(false)
                  }
                }}
              >
                의견 거두기
              </Button>
            )}
            {/* 확정 — 시스템 관리자만. 그때 데이터가 바뀐다. */}
            {isAdmin && (
              <Button size="sm" disabled={busy || !canDecide} onClick={() => submit(choice)}>
                {multi && choice.length === 0 ? '축 없음으로 확정' : '확정'}
              </Button>
            )}
            {isAdmin && (
              <Button
                size="sm"
                variant="ghost"
                disabled={busy}
                onClick={async () => {
                  setBusy(true)
                  try {
                    await onSkip()
                  } finally {
                    setBusy(false)
                  }
                }}
              >
                건너뛰기
              </Button>
            )}
            {recommended && !picked.length && !direct && (
              <span className="text-muted-foreground text-xs">
                추천을 따르려면 「{recommended.label}」 을 누르세요 — 자동으로 고르지 않습니다.
              </span>
            )}
            {majority && !live.my_vote && picked.length > 0 && (
              <span className="text-muted-foreground text-xs">
                다수 의견으로 미리 골라 두었습니다.
              </span>
            )}
          </div>
        </>
      )}
    </li>
  )
}

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
 *
 * ## 합의된 줄은 **골라서 한꺼번에**
 *
 * 하나씩 열어 「추천」 을 누르는 일이 고됐다(2026-10-03). 고된 것은 「훑어 확정」 쪽이라,
 * 줄을 골라 **각자의 추천대로** 한 번에 확정한다. 다만 고를 수 있는 것은 합의된 줄뿐이다:
 *
 *   * **추천이 없는 줄** — 확신이 낮아 추천을 안 세웠다. 무엇으로 정할지가 없다.
 *   * **추천과 다른 의견이 있는 줄** — 누군가 다르게 봤다. 한꺼번에 넘기면 그 의견을
 *     아무도 안 읽은 채 지나간다. 하나씩 열면 같은 추천으로 정할 수도 있다.
 *
 * 그 판단은 서버도 똑같이 한다(`decide_recommended`) — 화면만 막으면 API 로는 넘어간다.
 * 「자동 확정은 없다」 는 그대로다: 사람이 고르고 누른다.
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
function directAxis(queue: string): 'test_item' | 'condition' | 'property' | null {
  if (queue === 'method_test_items') return 'test_item'
  if (queue === 'test_item_axes') return 'condition'
  if (queue === 'test_item_properties') return 'property'
  return null
}

/** 여러 개를 고르는 물음에서 「아무것도 아님」 이 뜻하는 말. 물음마다 다르다. */
function emptyLabel(queue: string): string {
  if (queue === 'test_item_properties') return '물성 없음'
  if (queue === 'series_standards') return '추가할 규격 없음'
  if (queue === 'series_test_items') return '추가할 시험 없음'
  if (queue === 'series_summary') return '추가할 문장 없음'
  if (queue === 'test_item_aliases') return '추가할 별칭 없음'
  return '조건 없음'
}

/** 출처를 링크로 — url 이면 그대로, 논문 id(PMC…)면 Europe PMC 로. */
function sourceHref(source: string): string {
  if (/^PMC\d+$/.test(source)) return `https://europepmc.org/article/PMC/${source}`
  return source
}

/** 링크 글자는 짧게 — 도메인만. 주소 전체는 후보 한 줄을 세 줄로 만든다. */
function sourceText(source: string): string {
  if (/^PMC\d+$/.test(source)) return source
  try {
    return new URL(source).hostname.replace(/^www\./, '')
  } catch {
    return source
  }
}

/**
 * 이 줄을 **추천대로 한꺼번에** 확정할 수 없는 이유. 고를 수 있으면 `null`.
 *
 * 서버의 `decide_recommended` 와 **같은 판단**이어야 한다 — 여기서 고를 수 있는데 서버가
 * 돌려보내면 사람은 「눌렀는데 일부가 안 됐다」 를 이유도 모른 채 본다.
 */
export function bulkBlock(row: ReviewProposal): string | null {
  const recommended = new Set(
    row.candidates.filter((one) => one.recommended).map((one) => one.code),
  )
  if (recommended.size === 0) return '추천이 없는 줄입니다 — 하나씩 열어 골라 주십시오.'
  const same = (choice: string[]) =>
    choice.length === recommended.size && choice.every((code) => recommended.has(code))
  const dissent = row.votes.filter((one) => !same(one.choice)).length
  if (dissent > 0)
    return `추천과 다른 의견이 ${dissent}건 있습니다 — 의견을 보고 하나씩 정해 주십시오.`
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
  // 물성은 271개 — 후보엔 추천만 두고 나머지는 여기서 고른다.
  const properties = useResource(
    () => (axis === 'property' ? vocabularyApi.terms('property') : Promise.resolve([])),
    [axis],
  )
  const directOptions = useMemo(() => {
    if (axis === 'test_item')
      return (testItems.data ?? [])
        .filter((one) => one.code)
        .map((one) => ({ id: one.code as string, label: one.value }))
    if (axis === 'condition')
      return (conditions.data ?? []).map((one) => ({ id: one.key, label: one.label }))
    if (axis === 'property')
      return (properties.data ?? [])
        .filter((one) => one.code)
        .map((one) => ({ id: one.code as string, label: one.value, detail: one.code }))
    return []
  }, [axis, testItems.data, conditions.data, properties.data])

  /** 이 화면에서 정한 줄 — 목록에서 빼되 다시 받지는 않는다(자리가 뛰지 않게). */
  const [gone, setGone] = useState<Set<string>>(new Set())
  /** 한꺼번에 확정하려고 고른 줄. */
  const [chosen, setChosen] = useState<Set<string>>(new Set())
  /** 「정말 확정합니까」 한 번 더 — 확정하면 바로 적용되고 되돌리지 않는다. */
  const [asking, setAsking] = useState(false)
  const [bulkBusy, setBulkBusy] = useState(false)
  /** 확정하지 못하고 돌아온 줄 — 이유와 함께 목록 위에 남긴다. */
  const [bounced, setBounced] = useState<{ label: string; message: string }[]>([])
  const [error, setError] = useState<ApiError | Error | null>(null)

  const meta = (queues.data ?? []).find((one) => one.key === queue)
  const rows = (page.data?.items ?? []).filter((one) => !gone.has(one.id))
  const total = page.data?.total ?? 0
  /** 정한 줄 · 사라진 줄에서는 고를 것이 없다 — 이미 닫혔다. */
  const selectable = isAdmin && status !== 'decided' && status !== 'gone'
  const eligible = rows.filter((one) => bulkBlock(one) === null)
  const picked = rows.filter((one) => chosen.has(one.id))

  async function decideChosen() {
    setBulkBusy(true)
    setError(null)
    try {
      const result = await reviewApi.decideRecommended(
        queue,
        picked.map((one) => one.id),
      )
      setGone((current) => {
        const next = new Set(current)
        for (const id of result.done) next.add(id)
        return next
      })
      const labelOf = new Map(rows.map((one) => [one.id, one.subject_label]))
      setBounced(
        result.failed.map((one) => ({
          label: labelOf.get(one.id) ?? one.id,
          message: one.message,
        })),
      )
      setChosen(new Set())
      setAsking(false)
      queues.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBulkBusy(false)
    }
  }

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
                ['open', '미처리'],
                ['voted', '의견 있음'],
                ['skipped', '보류됨'],
                ['decided', '결정 완료'],
                ['gone', '대상 삭제됨'],
              ] as const
            ).map(([value, label]) => (
              <Button
                key={value}
                size="sm"
                variant={status === value ? 'secondary' : 'ghost'}
                onClick={() => {
                  setOffset(0)
                  setGone(new Set())
                  setChosen(new Set())
                  setBounced([])
                  setAsking(false)
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

      {selectable && rows.length > 0 && (
        // **합의된 줄만 고를 수 있다** — 추천이 없거나 추천과 다른 의견이 있는 줄은 체크칸이
        // 꺼져 있고, 왜 꺼졌는지가 그 칸에 올려 있다.
        <div className="bg-muted/40 flex flex-wrap items-center gap-2 rounded-md border px-3 py-2 text-sm">
          <Button
            size="sm"
            variant="outline"
            disabled={eligible.length === 0}
            onClick={() =>
              setChosen((current) =>
                current.size === eligible.length && eligible.length > 0
                  ? new Set()
                  : new Set(eligible.map((one) => one.id)),
              )
            }
          >
            {chosen.size === eligible.length && eligible.length > 0
              ? '고른 것 풀기'
              : `추천 있는 줄 고르기 (${eligible.length})`}
          </Button>
          <span className="text-muted-foreground">
            {picked.length}건 고름
            {rows.length > eligible.length &&
              ` · ${rows.length - eligible.length}건은 하나씩 정할 줄`}
          </span>
          <div className="flex-1" />
          {asking ? (
            <>
              {/* **한 번 더 묻는다.** 확정하면 기존 규칙(규격 → 인용 계열에 붙임 …)이 바로
                  돌고, 다시 열어도 이미 일어난 일은 안 되돌린다. */}
              <span>
                {picked.length}건을 <strong>각자의 추천대로</strong> 확정합니다. 바로
                적용됩니다.
              </span>
              {/* 이름을 줄의 「확정」 과 **다르게** 둔다 — 같은 이름의 단추가 둘이면 어느 쪽이
                  몇 건을 정하는지 눌러 보기 전에는 모른다. */}
              <Button size="sm" disabled={bulkBusy} onClick={() => void decideChosen()}>
                {bulkBusy ? '확정하는 중…' : `${picked.length}건 확정`}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setAsking(false)}>
                취소
              </Button>
            </>
          ) : (
            <Button size="sm" disabled={picked.length === 0} onClick={() => setAsking(true)}>
              고른 {picked.length}건 추천대로 확정
            </Button>
          )}
        </div>
      )}

      {bounced.length > 0 && (
        // 확정하지 못한 줄 — **이유와 함께.** 「눌렀는데 일부가 안 됐다」 만 보이면 어느 줄을
        // 왜 다시 봐야 하는지 모른다.
        <div className="rounded-md border border-amber-500/40 bg-amber-500/5 p-3 text-sm">
          <p className="font-medium">{bounced.length}건은 확정하지 않았습니다</p>
          <ul className="mt-1 space-y-0.5">
            {bounced.map((one) => (
              <li key={one.label}>
                {one.label} — <span className="text-muted-foreground">{one.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

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
              selectable={selectable}
              selected={chosen.has(row.id)}
              blocked={bulkBlock(row)}
              onSelect={() =>
                setChosen((current) => {
                  const next = new Set(current)
                  if (next.has(row.id)) next.delete(row.id)
                  else next.add(row.id)
                  return next
                })
              }
              multi={meta?.multi ?? false}
              emptyWord={emptyLabel(queue)}
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
  emptyWord,
  directOptions,
  readOnly,
  isAdmin,
  selectable,
  selected,
  blocked,
  onSelect,
  onDecide,
  onSkip,
  onVote,
  onWithdraw,
  onReopen,
}: {
  row: ReviewProposal
  /** 한꺼번에 확정할 줄을 고르는 칸을 그리나. */
  selectable: boolean
  selected: boolean
  /** 고를 수 없는 이유. 고를 수 있으면 `null` — 칸을 끄고 이 말을 올려 둔다. */
  blocked: string | null
  onSelect: () => void
  multi: boolean
  emptyWord: string
  directOptions: { id: string; label: string; detail?: string | null }[]
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
    <li className={`rounded-md border p-4 ${selected ? 'border-primary bg-primary/5' : ''}`}>
      <div className="flex items-start justify-between gap-3">
        {selectable && (
          // **못 고르는 줄은 칸을 끄고 왜인지 올려 둔다.** 숨기면 「이 줄은 왜 안 골라지지」
          // 를 사람이 되짚어야 하고, 되짚기는 대개 실패한다.
          <input
            type="checkbox"
            className="mt-1.5 shrink-0"
            aria-label={`${row.subject_label} 고르기`}
            checked={selected}
            disabled={blocked !== null}
            title={blocked ?? '고르면 위의 단추로 추천대로 한꺼번에 확정합니다'}
            onChange={onSelect}
          />
        )}
        <div className="min-w-0 flex-1">
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
                {split ? ' · 의견 불일치' : votes.length > 1 ? ' · 의견 일치' : ''}
              </span>
            )}
          </p>
          {/* **무엇을 묻는지가 먼저다.** 「3400」 만 주고 후보를 세우면 도메인 전문가도 못 정한다 —
              물음은 완전한 문장으로, 그 아래 대상을 이해할 사실 몇 줄(제조사·분류·소개·지금
              하는 시험 …). 후보 옆의 근거가 「왜 이 후보인가」 라면 여기는 「대상이 무엇인가」. */}
          {row.question && <p className="mt-1 text-sm">{row.question}</p>}
          {row.facts && row.facts.length > 0 && (
            <dl className="text-muted-foreground mt-2 space-y-0.5 text-xs">
              {row.facts.map((one, index) => (
                <div key={`${one.label}-${index}`} className="flex gap-2">
                  {one.label && <dt className="shrink-0 font-medium">{one.label}</dt>}
                  <dd className="min-w-0">
                    {one.link ? (
                      <Link to={one.link} target="_blank" className="hover:underline">
                        {one.value}
                      </Link>
                    ) : (
                      one.value
                    )}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          {row.context && <p className="text-muted-foreground mt-1 text-xs">{row.context}</p>}
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
                {row.decided_by ?? '대상 삭제됨'} · {shownDateTime(row.decided_at)}
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
              재검토
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
                      {one.sources && one.sources.length > 0 && (
                        <span className="block text-xs">
                          {one.sources.map((source) => (
                            <a
                              key={source}
                              href={sourceHref(source)}
                              target="_blank"
                              rel="noreferrer"
                              className="text-primary mr-2 underline"
                              onClick={(event) => event.stopPropagation()}
                            >
                              {sourceText(source)}
                            </a>
                          ))}
                        </span>
                      )}
                    </span>
                  </label>
                </li>
              )
            })}
          </ul>

          <div className="mt-3 flex flex-wrap items-end gap-2">
            {/* 별칭은 어휘가 아니라 **글자**라 고르는 목록이 없다 — 후보에 없는 표기는 적는다. */}
            {row.queue === 'test_item_aliases' && (
              <Input
                value={direct}
                onChange={(event) => setDirect(event.target.value)}
                placeholder="직접 입력 — 후보에 없는 표기"
                aria-label="별칭 직접 입력"
                className="w-56"
              />
            )}
            {directOptions.length > 0 && (
              <div className="w-64">
                <SearchablePicker
                  value={direct}
                  onChange={(next) => {
                    setDirect(next)
                    if (!multi) setPicked([])
                  }}
                  options={directOptions}
                  placeholder="직접 선택"
                  detailTitle="직접 선택"
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
                ? '의견 수정'
                : multi && choice.length === 0
                  ? `${emptyWord} 의견`
                  : '의견 제출'}
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
                의견 철회
              </Button>
            )}
            {/* 확정 — 시스템 관리자만. 그때 데이터가 바뀐다. */}
            {isAdmin && (
              <Button size="sm" disabled={busy || !canDecide} onClick={() => submit(choice)}>
                {multi && choice.length === 0 ? `${emptyWord}으로 확정` : '확정'}
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
                보류
              </Button>
            )}
            {recommended && !picked.length && !direct && (
              <span className="text-muted-foreground text-xs">
                추천을 따르려면 「{recommended.label}」 을 누르십시오 — 자동으로 고르지
                않습니다.
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

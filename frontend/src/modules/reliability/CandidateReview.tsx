/**
 * 후보와 확정 — **AI 가 올린 것은 사람이 본 뒤에 쓴다.**
 *
 * 신뢰성 시험은 값 하나가 틀리면 그 조건으로 장비를 고르고, 그 장비로 보고서가 나간다.
 * AI 는 시험 표준서를 읽어 스물두 칸을 한 번에 채울 수 있지만 틀려도 그만큼 빠르다 —
 * 그래서 기계 자격으로 들어온 것은 후보로 서고, 사람이 읽고 확인해야 확정이다(ADR 0009).
 *
 * 확인하는 자리를 **새 화면으로 만들지 않았다.** 「맞으면 ok, 아니면 수정」 이 정확히
 * 등록·수정 창이 하는 일이라, 그 창 위에 띠 하나를 얹는 것으로 족하다. 검토용 화면을 따로
 * 두면 거기서 고칠 수 없어 결국 창을 한 번 더 열게 된다.
 */

import { useState } from 'react'
import { AlertTriangle, Check, FileClock, Undo2 } from 'lucide-react'

import { ApiError } from '@/shared/api/client'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { Alert } from '@/shared/components/ui/alert'
import { Badge } from '@/shared/components/ui/badge'
import { Button } from '@/shared/components/ui/button'
import type { ReliabilityTest } from '@/modules/reliability/api'
import { reliabilityApi } from '@/modules/reliability/api'

export function isCandidate(row: Pick<ReliabilityTest, 'status'>): boolean {
  return row.status === 'candidate'
}

/** 목록의 줄에 붙는 표 — **눈에 띄어야 한다.** 못 보고 읽으면 배지가 없는 것과 같다. */
export function CandidateBadge({
  row,
}: {
  row: Pick<ReliabilityTest, 'status' | 'submitted_via'>
}) {
  if (!isCandidate(row)) return null
  return (
    <Badge
      variant="destructive"
      title={
        row.submitted_via
          ? `등록: ${row.submitted_via}. 아직 사람 확인 전`
          : '아직 사람 확인 전'
      }
    >
      <AlertTriangle />
      확인 전
    </Badge>
  )
}

function when(iso: string | null | undefined): string {
  if (!iso) return ''
  const at = new Date(iso)
  return Number.isNaN(at.getTime()) ? '' : at.toLocaleDateString('ko-KR')
}

/**
 * 등록·수정 창 위의 띠 — 이 시험이 후보인지, 확정이면 누가 보증했는지.
 *
 * 저장 안 한 새 시험(`row === null`)에는 안 붙는다 — 아직 상태랄 것이 없다.
 */
/** 규격서 최신판을 **아직 안 본** 시험의 표. 확정은 그대로라, 이 표가 없으면 다시 볼 줄이 안 보인다. */
export function UnreviewedBadge({
  row,
}: {
  row: Pick<ReliabilityTest, 'unreviewed_revision'>
}) {
  const unseen = row.unreviewed_revision
  if (!unseen) return null
  return (
    <Badge
      variant="outline"
      className="border-amber-400 text-amber-700 dark:text-amber-300"
      title={`${unseen.document_code ?? '규격서'} 개정 ${unseen.label} 아직 안 봄`}
    >
      <FileClock />
      개정 {unseen.label} 미확인
    </Badge>
  )
}

/**
 * 「이 개정 봤음」 — 규격서가 개정됐는데 이 시험을 아직 안 봤다는 띠.
 *
 * 개정이 올라와도 확정은 그대로 둔다(수십 건이 한꺼번에 내려가면 그날 일이 멈춘다). 대신 이
 * 띠가 서고, 사람이 개정 내용(`summary`)과 이 시험을 견줘 본 뒤 누르면 떨어진다. 고칠 것이
 * 있으면 먼저 고치고 누른다.
 */
export function RevisionBanner({
  row,
  onChanged,
}: {
  row: ReliabilityTest | null
  onChanged: (next: ReliabilityTest) => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | Error | null>(null)
  const unseen = row?.unreviewed_revision
  if (!row || !unseen) return null

  async function seen() {
    if (!row || !unseen) return
    setBusy(true)
    setError(null)
    try {
      await reliabilityApi.markReviewed(row.id, unseen.revision_id)
      onChanged(await reliabilityApi.read(row.id))
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Alert className="border-amber-300 bg-amber-50 dark:bg-amber-950/30">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <FileClock className="size-4 text-amber-600" />
        <span>
          규격서 {unseen.document_code ?? unseen.document_title ?? ''} 개정 {unseen.label}을
          아직 안 봄. 바뀐 내용과 견줘 보고 고칠 것이 없으면 확인.
        </span>
        {row.can_edit && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() => void seen()}
          >
            이 개정 봤음
          </Button>
        )}
      </div>
      <ErrorNotice error={error} />
    </Alert>
  )
}

export function ReviewBanner({
  row,
  onChanged,
}: {
  row: ReliabilityTest | null
  /** 확인·되돌리기가 끝났다. 창과 목록이 새 상태를 다시 받아야 한다. */
  onChanged: (next: ReliabilityTest) => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | Error | null>(null)

  if (!row) return null

  async function run(action: 'confirm' | 'reopen') {
    if (!row) return
    setBusy(true)
    setError(null)
    try {
      onChanged(await reliabilityApi[action](row.id))
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  if (!isCandidate(row)) {
    // 확정된 것에도 한 줄 둔다 — **「이 값 누가 보증했어」 의 답이 여기다.** 그리고
    // 「다시 후보로」 가 AI 에게 다시 채우게 하는 유일한 문이라 이 자리에 있어야 한다.
    return (
      <div className="text-muted-foreground flex flex-wrap items-center gap-2 text-xs">
        <Check className="size-3.5 text-emerald-600" />
        {row.confirmed_by
          ? `${row.confirmed_by} 확인${when(row.confirmed_at) && ` · ${when(row.confirmed_at)}`}`
          : '확정'}
        {row.can_edit && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={busy}
            className="h-6 px-2"
            onClick={() => void run('reopen')}
          >
            <Undo2 className="size-3" />
            후보로 되돌리기
          </Button>
        )}
        <ErrorNotice error={error} />
      </div>
    )
  }

  return (
    <Alert variant="destructive">
      <AlertTriangle />
      <div className="space-y-2">
        <p className="font-medium">
          확인 전 후보
          {row.submitted_via ? ` (등록: ${row.submitted_via})` : ''}
        </p>
        <p className="text-xs">
          내용 검토 후 이상 없으면 확인. 틀린 칸은 여기서 수정 후 확인. 확인 전까지는 전사
          ‘신뢰성 시험’ 목록에 표시되지 않음.
        </p>
        <ErrorNotice error={error} />
        {row.can_edit && (
          <Button type="button" size="sm" disabled={busy} onClick={() => void run('confirm')}>
            <Check className="size-3.5" />
            내용 확인
          </Button>
        )}
      </div>
    </Alert>
  )
}

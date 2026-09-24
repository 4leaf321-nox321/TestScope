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
import { AlertTriangle, Check, Undo2 } from 'lucide-react'

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
          ? `${row.submitted_via} 가 올렸습니다 — 아직 사람이 확인하지 않았습니다`
          : '아직 사람이 확인하지 않았습니다'
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
          아직 확인 전인 후보입니다
          {row.submitted_via ? ` — ${row.submitted_via} 가 올렸습니다.` : '.'}
        </p>
        <p className="text-xs">
          내용을 읽고 맞으면 확인하십시오. 틀린 칸은 여기서 고친 뒤에 확인하면 됩니다. 확인하기
          전까지는 전사 「신뢰성 시험」 목록에 나오지 않습니다.
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

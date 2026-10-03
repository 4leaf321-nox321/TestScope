/**
 * VOC 한 건 — **흐름이 곧 답변이다.**
 *
 * 답변 한 줄로 두면 「접수됐나 → 보고 있나 → 됐나」 의 중간이 사라지고, 무엇을 했는지가
 * 마지막 한 줄에만 남는다. 그래서 상태가 바뀔 때마다 **누가·언제·무슨 말로** 바꿨는지를
 * 줄로 쌓고, 화면은 그것을 시간 순으로 그린다.
 *
 * ## 옮길 수 있는 곳은 **서버가 말해 준다**
 *
 * `can_move` 를 그대로 단추로 만든다. 화면이 권한을 다시 계산하면 서버와 갈라지고, 그때
 * 사람은 눌리는 단추가 403 을 돌려주는 것을 본다 — 그 403 은 고장으로 읽힌다.
 *
 * `note_required` 도 서버가 준다. 「해결」 을 말 없이 누르면 400 인데, 그것을 눌러 보고
 * 알게 하는 대신 **누르기 전에** 적으라고 한다.
 */

import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { Button } from '@/shared/components/ui/button'
import { Textarea } from '@/shared/components/ui/textarea'
import { useResource } from '@/shared/hooks/useResource'
import { shownDate } from '@/shared/lib/datetime'
import { VOC_STATUS_LABELS, type VocEvent, vocApi } from '@/modules/voc/api'

/** 한 줄이 무슨 일이었는지 — 등록 · 상태 변경 · 댓글. */
function what(event: VocEvent): string {
  if (event.from_status === null) return '냈습니다'
  if (event.from_status === event.to_status) return '말을 보탰습니다'
  const from = VOC_STATUS_LABELS[event.from_status] ?? event.from_status
  const to = VOC_STATUS_LABELS[event.to_status] ?? event.to_status
  return `${from} → ${to}`
}

export default function VocDetailPage() {
  const { id = '' } = useParams()
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const item = useResource(() => vocApi.get(id), [id])

  async function move(to: string) {
    setBusy(true)
    setError(null)
    try {
      await vocApi.move(id, { to_status: to, note: note.trim() || null })
      setNote('')
      item.reload()
    } catch (problem) {
      setError(problem as Error)
    } finally {
      setBusy(false)
    }
  }

  const shown = item.data
  const needsNote = (to: string) => (shown?.note_required ?? []).includes(to)

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        back={{ to: '/voc', label: 'VOC 목록' }}
        title={shown ? `${shown.seq}. ${shown.title}` : 'VOC'}
        description={
          shown
            ? `${VOC_STATUS_LABELS[shown.status] ?? shown.status_label} · ${shown.created_by_name ?? '알 수 없음'} · ${shownDate(shown.created_at)}`
            : undefined
        }
      />

      <ErrorNotice error={error ?? item.error} />

      {shown && (
        <>
          <div className="space-y-2 rounded-md border p-4">
            <p className="text-sm whitespace-pre-wrap">{shown.body}</p>
            {shown.page_path && (
              // 접수 당시 보던 화면 — 재현의 실마리다.
              <p className="text-muted-foreground text-xs">
                낸 화면:{' '}
                {shown.page_path.startsWith('/') ? (
                  <Link to={shown.page_path} className="underline">
                    {shown.page_path}
                  </Link>
                ) : (
                  <span className="font-mono">{shown.page_path}</span>
                )}
              </p>
            )}
          </div>

          <section className="space-y-3">
            <h2 className="text-base font-semibold">처리 과정</h2>
            <ol className="space-y-3">
              {shown.events.map((one) => (
                <li key={one.id} className="border-l-2 pl-4">
                  <p className="text-sm">
                    <strong>{one.by_name ?? '알 수 없음'}</strong>
                    <span className="text-muted-foreground"> — {what(one)}</span>
                    <span className="text-muted-foreground ml-2 text-xs">
                      {shownDate(one.at)}
                    </span>
                  </p>
                  {one.note && <p className="mt-1 text-sm whitespace-pre-wrap">{one.note}</p>}
                </li>
              ))}
            </ol>
          </section>

          <section className="space-y-3 rounded-md border p-4">
            <Textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={3}
              placeholder="무엇을 했는지(또는 무엇이 여전히 안 되는지) 적어 주십시오."
            />
            <div className="flex flex-wrap gap-2">
              {/* **같은 상태로 보내는 것이 댓글이다.** 누구나 할 수 있다. */}
              <Button
                size="sm"
                variant="outline"
                disabled={busy || !note.trim()}
                onClick={() => move(shown.status)}
              >
                말 보태기
              </Button>
              {shown.can_move.map((to) => (
                <Button
                  key={to}
                  size="sm"
                  disabled={busy || (needsNote(to) && !note.trim())}
                  // 말이 필요한 단추는 **왜 안 눌리는지**를 올려 둔다 — 안 그러면
                  // 「단추가 죽었다」 로 읽힌다.
                  title={
                    needsNote(to) && !note.trim()
                      ? '이 단추는 무엇을 했는지(또는 왜 안 하는지) 적어야 눌립니다'
                      : undefined
                  }
                  onClick={() => move(to)}
                >
                  {VOC_STATUS_LABELS[to] ?? to}
                  {needsNote(to) && ' *'}
                </Button>
              ))}
            </div>
            {shown.can_move.length === 0 && (
              <p className="text-muted-foreground text-xs">
                상태를 옮기는 것은 <strong>낸 사람과 관리자</strong>입니다. 말은 누구나 보탤 수
                있습니다.
              </p>
            )}
            {shown.note_required.length > 0 && (
              <p className="text-muted-foreground text-xs">
                <strong>*</strong> 표시된 단추는 말을 적어야 눌립니다 — 「해결」 만 찍힌 건은
                무엇이 바뀌었는지 아무도 모릅니다.
              </p>
            )}
          </section>
        </>
      )}
    </div>
  )
}

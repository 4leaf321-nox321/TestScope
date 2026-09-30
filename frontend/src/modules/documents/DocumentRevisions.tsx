/**
 * 규격서 개정 이력 — **판 글자 하나로는 「이 시험은 개정 18에서 신설」 을 못 적는다.**
 *
 * 개정을 줄로 쌓아야 시험이 어느 판에서 들어왔는지, 사람이 어느 판까지 확인했는지를
 * 각각 가리킬 수 있다.
 *
 * **개정이 올라와도 딸린 시험은 확정인 채로 둔다.** 수십 건이 한꺼번에 후보로 내려가면
 * 그날 일이 멈추고, 멈춘 일은 미뤄진다 — 미뤄진 확인은 안 한 확인과 같다. 대신 최신판
 * 줄에 「아직 안 본 시험 N건」 이 서고, 사람이 본 것부터 그 수가 줄어든다.
 */

import { useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError } from '@/shared/api/client'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import { Textarea } from '@/shared/components/ui/textarea'
import { useResource } from '@/shared/hooks/useResource'
import { specDocumentApi } from '@/modules/documents/api'
import { RevisionCompare } from '@/modules/documents/RevisionCompare'

export function DocumentRevisions({
  documentId,
  canEdit,
  onChanged,
}: {
  documentId: string
  canEdit: boolean
  /** 판이 올라가면 문서 줄의 「판」 칸도 따라 바뀐다. */
  onChanged?: () => void
}) {
  const rows = useResource(() => specDocumentApi.revisions(documentId), [documentId])
  const [adding, setAdding] = useState(false)
  const [label, setLabel] = useState('')
  const [issuedOn, setIssuedOn] = useState('')
  const [summary, setSummary] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | Error | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!label.trim()) return
    setBusy(true)
    setError(null)
    try {
      await specDocumentApi.addRevision(documentId, {
        label: label.trim(),
        issued_on: issuedOn || null,
        summary: summary.trim() || null,
      })
      setLabel('')
      setIssuedOn('')
      setSummary('')
      setAdding(false)
      rows.reload()
      onChanged?.()
    } catch (failed) {
      setError(failed as ApiError | Error)
    } finally {
      setBusy(false)
    }
  }

  const listed = rows.data ?? []
  if (listed.length === 0 && !canEdit) return null

  return (
    <section className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-medium">개정 이력</h3>
        {canEdit && !adding && (
          <Button type="button" variant="outline" size="sm" onClick={() => setAdding(true)}>
            개정 추가
          </Button>
        )}
      </div>

      <ErrorNotice error={error ?? rows.error} />

      {adding && (
        <form onSubmit={submit} className="space-y-2 rounded-md border p-3">
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="rev-label">판</Label>
              <Input
                id="rev-label"
                value={label}
                onChange={(event) => setLabel(event.target.value)}
                placeholder="18 · Rev.3"
                maxLength={60}
                required
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="rev-date">발행일</Label>
              <Input
                id="rev-date"
                type="date"
                value={issuedOn}
                onChange={(event) => setIssuedOn(event.target.value)}
              />
            </div>
          </div>
          <div className="space-y-1">
            <Label htmlFor="rev-summary">무엇이 바뀌었나</Label>
            <Textarea
              id="rev-summary"
              value={summary}
              onChange={(event) => setSummary(event.target.value)}
              placeholder="시험 온도 상향(85 → 95 °C)"
              rows={2}
              maxLength={4000}
            />
            {/* **이 한 줄이 재검토의 범위를 정한다.** */}
            <p className="text-muted-foreground text-xs">
              「오타 수정」 이면 딸린 시험을 다시 볼 이유가 없고, 「시험 온도 상향」 이면 전부
              다시 봐야 합니다 — 그 판단을 여기 적힌 말로 합니다.
            </p>
          </div>
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={busy || !label.trim()}>
              쌓기
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setAdding(false)}
              disabled={busy}
            >
              취소
            </Button>
          </div>
        </form>
      )}

      {/* **개정이 오면 무엇을 다시 봐야 하는가** — 판마다 한 벌이라 두 목록을 견주면 된다. */}
      <RevisionCompare revisions={listed} />

      {listed.length > 0 && (
        <ul className="divide-y rounded-md border text-sm">
          {listed.map((one) => (
            <li key={one.id} className="space-y-0.5 p-2">
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="font-medium">{one.label}</span>
                {one.issued_on && (
                  <span className="text-muted-foreground text-xs">{one.issued_on}</span>
                )}
                {one.stale_test_count > 0 && (
                  // **남은 일이 여기 보인다.** 안 보이면 개정은 쌓이고 확인은 안 된다.
                  <span className="text-destructive text-xs font-medium">
                    이 개정을 아직 안 본 시험 {one.stale_test_count}건
                  </span>
                )}
                {one.submitted_via && (
                  <span
                    className="text-muted-foreground text-xs"
                    title={`${one.submitted_via} 가 올렸습니다`}
                  >
                    AI
                  </span>
                )}
              </div>
              {one.summary ? (
                <p className="text-muted-foreground whitespace-pre-line">{one.summary}</p>
              ) : (
                <p className="text-muted-foreground text-xs">
                  무엇이 바뀌었는지가 안 적혀 있습니다 — 딸린 시험을 다시 볼지 정할 근거가
                  없습니다.
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/**
 * 적으면서 보는 자리 — **저장하고 나서 알면 늦는 것들.**
 *
 * 등록·수정 창은 지금까지 「적는 칸」 만 있었다. 그래서 이런 것을 저장한 뒤에 알았다:
 *
 *   * 95 °C 로 올리면 **돌릴 장비가 0대**라는 것 (따로 창을 열어야 보였다)
 *   * 개정 14에서는 85 °C 였다는 것 (이력을 볼 길이 없었다)
 *   * 같은 이름이 옆 제품군에 이미 있다는 것 (중복으로 올리다 409 를 받았다)
 *   * 고른 규격서가 **발췌**라는 것 (규격서 화면으로 나갔다 와야 했다)
 *
 * 넷 다 **적는 동안** 알아야 손을 고칠 수 있다.
 */

import { useEffect, useState } from 'react'

import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { Button } from '@/shared/components/ui/button'
import { useResource } from '@/shared/hooks/useResource'
import type { AttributeValueIn } from '@/modules/attributes/api'
import { specDocumentApi } from '@/modules/documents/api'
import { ValueHistory } from '@/modules/reliability/ValueHistory'
import { reliabilityApi } from '@/modules/reliability/api'
import type { Capability } from '@/modules/reliability/api'

export function EditingAside({
  divisionCode,
  testId,
  name,
  termIds,
  attributes,
  documentId,
}: {
  divisionCode: string
  /** 고치는 중이면 그 시험. 새로 만드는 중이면 `null` — 이력이 없다. */
  testId: string | null
  name: string
  termIds: string[]
  attributes: AttributeValueIn[]
  /** 지금 고른 규격서. 없으면 그 칸을 안 그린다. */
  documentId: string | null
}) {
  return (
    <div className="space-y-4">
      <Capable termIds={termIds} attributes={attributes} />
      <Siblings divisionCode={divisionCode} name={name} testId={testId} />
      {documentId && <Paper documentId={documentId} />}
      {testId && (
        <section className="space-y-1">
          <h3 className="text-sm font-medium">판별 이력</h3>
          <ValueHistory testId={testId} />
        </section>
      )}
    </div>
  )
}

/**
 * 지금 적은 조건으로 **돌릴 수 있는 장비.**
 *
 * 누를 때 센다 — 칸을 칠 때마다 서버를 부르면 스무 번 치는 동안 스무 번 왕복한다.
 * 그 값이 조건을 바꿀 때마다 저절로 낡으므로, 낡았다는 것을 화면이 말한다.
 */
function Capable({
  termIds,
  attributes,
}: {
  termIds: string[]
  attributes: AttributeValueIn[]
}) {
  const [answer, setAnswer] = useState<Capability | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const mark = JSON.stringify([termIds, attributes])
  const [askedAt, setAskedAt] = useState<string | null>(null)

  // 조건이 바뀌면 앞서 센 답은 **낡았다** — 지우지 않고 낡았다고 말한다(지우면 비교가 안 된다).
  const stale = answer !== null && askedAt !== mark

  async function ask() {
    setBusy(true)
    setError(null)
    try {
      setAnswer(await reliabilityApi.capabilityPreview(termIds, attributes))
      setAskedAt(mark)
    } catch (failed) {
      setError(failed as Error)
    } finally {
      setBusy(false)
    }
  }

  if (termIds.length === 0) {
    return (
      <p className="text-muted-foreground text-xs">
        적용 시험 항목 선택 시 이 조건으로 수행 가능한 장비 수 확인 가능.
      </p>
    )
  }

  return (
    <section className="space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-medium">이 조건으로 수행 가능한 장비</h3>
        <Button type="button" size="sm" variant="outline" disabled={busy} onClick={ask}>
          {answer ? '다시 세기' : '세어 보기'}
        </Button>
      </div>
      <ErrorNotice error={error} />
      {answer && (
        <div className="space-y-0.5 text-sm">
          {stale && (
            <p className="text-xs text-amber-700">조건 변경됨. 아래는 변경 전 기준.</p>
          )}
          <p className="text-muted-foreground text-xs">
            조건 {answer.conditions_asked}개로 조회.
          </p>
          <ul>
            {answer.items.map((one) => (
              <li key={one.term_id}>
                {one.value}{' '}
                <span className={one.total === 0 ? 'font-medium text-amber-700' : ''}>
                  {one.total}대
                </span>
                {one.unmet_count > 0 && (
                  <span className="text-muted-foreground text-xs">
                    {' '}
                    · 조건 불충족으로 제외된 장비 {one.unmet_count}대
                  </span>
                )}
              </li>
            ))}
          </ul>
          {answer.skipped.length > 0 && (
            // **조용히 빼지 않는다** — 뺀 줄 모르면 조건을 다 본 것처럼 읽힌다.
            <p className="text-xs text-amber-700">
              조회에서 제외된 조건 {answer.skipped.length}개(단위 변환 불가).
            </p>
          )}
        </div>
      )}
    </section>
  )
}

/** 이름이 같은 다른 시험 — **무엇으로 갈렸는지** 함께. */
function Siblings({
  divisionCode,
  name,
  testId,
}: {
  divisionCode: string
  name: string
  testId: string | null
}) {
  const [asked, setAsked] = useState('')
  // 이름을 다 친 뒤에 묻는다 — 글자마다 부르면 스무 번 왕복한다.
  useEffect(() => {
    const timer = setTimeout(() => setAsked(name.trim()), 600)
    return () => clearTimeout(timer)
  }, [name])
  const rows = useResource(
    () =>
      asked.length >= 2
        ? reliabilityApi.siblings(divisionCode, asked, testId)
        : Promise.resolve([]),
    [divisionCode, asked, testId],
  )
  const listed = rows.data ?? []
  if (listed.length === 0) return null
  return (
    <section className="space-y-1">
      <h3 className="text-sm font-medium">같은 이름의 다른 시험 {listed.length}건</h3>
      <ul className="text-muted-foreground space-y-0.5 text-xs">
        {listed.map((one) => (
          <li key={one.id}>
            {[one.product_group, one.spec_document_code, one.document_revision_label]
              .filter(Boolean)
              .join(' · ') || '적용군·규격서 없음'}
          </li>
        ))}
      </ul>
      {/* **적용군이나 규격서를 적어 갈라야** 같은 이름이 들어간다. */}
      <p className="text-muted-foreground text-xs">
        같은 이름이라도 적용군이나 규격서가 다르면 별개의 시험. 해당 칸 입력으로 구분 필요.
      </p>
    </section>
  )
}

/** 고른 규격서의 원본·쪽수·발췌 여부. */
function Paper({ documentId }: { documentId: string }) {
  const found = useResource(() => specDocumentApi.read(documentId), [documentId])
  const row = found.data
  if (!row) return null
  return (
    <section className="space-y-0.5">
      <h3 className="text-sm font-medium">선택한 규격서</h3>
      <p className="text-sm">
        {[row.code, row.title].filter(Boolean).join(' ')}
        {row.revision && (
          <span className="text-muted-foreground text-xs"> · 판 {row.revision}</span>
        )}
      </p>
      <p className="text-muted-foreground text-xs">
        {row.pages ? `본 자리 ${row.pages}` : '본 자리 미기재'} · 파일 {row.file_count}개
        {row.is_excerpt && (
          // **전문을 안 본 채 옮긴 것은 그렇게 보여야 한다.**
          <span className="ml-1 font-medium text-amber-700">발췌(전문 아님)</span>
        )}
      </p>
      {row.source_path && (
        <p className="text-muted-foreground text-xs break-all">{row.source_path}</p>
      )}
    </section>
  )
}

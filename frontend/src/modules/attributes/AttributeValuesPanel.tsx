/**
 * 속성 값 보기·고치기 — 상세 화면의 한 탭.
 *
 * 보기는 「이름 값」 줄 목록이고 초안엔 표시가 붙는다. 고치기는 편집기(AttributeValuesEditor)를
 * 그 자리에 펴고, 저장은 **통째로**(대상 API 의 `attributes` 규칙) 보낸다. 저장 뒤 부모가 다시
 * 읽는다 — 서버가 만든 `display` 로 다시 그려야 화면과 서버가 같은 글자를 쓴다.
 */

import { useState } from 'react'
import { Pencil } from 'lucide-react'

import { ApiError } from '@/shared/api/client'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { Button } from '@/shared/components/ui/button'
import {
  AttributeValuesEditor,
  fromValues,
  toPayload,
} from '@/modules/attributes/AttributeValuesEditor'
import type { AttributeRow } from '@/modules/attributes/AttributeValuesEditor'
import type {
  AttributeTarget,
  AttributeValue,
  AttributeValueIn,
} from '@/modules/attributes/api'

export function AttributeValuesList({ values }: { values: AttributeValue[] }) {
  // 응답 스키마가 기본값 [] 라 없을 수 없지만, 오래된 응답을 그린 화면이 죽지는 않게.
  if (!values || values.length === 0) {
    return <p className="text-muted-foreground text-sm">적힌 속성이 없습니다.</p>
  }
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
      {values.map((one) => (
        <div key={one.definition_id} className="flex flex-wrap items-baseline gap-x-2">
          <dt className="text-muted-foreground text-xs">
            {one.label}
            {one.status === 'draft' && (
              <span
                className="ml-1"
                title="초안 속성 — 시스템 관리자가 정식으로 올리기 전입니다. 표시·수집만 됩니다."
              >
                · 초안
              </span>
            )}
          </dt>
          <dd className="text-sm">
            {/* 주소는 링크로 — 「장비 예약 URL」 을 복사해 붙이게 하지 않는다. */}
            {/^https?:\/\//i.test(one.display) ? (
              <a
                href={one.display}
                target="_blank"
                rel="noreferrer"
                className="text-primary underline break-all"
              >
                {one.display}
              </a>
            ) : (
              one.display || '—'
            )}
            {one.note && (
              <span className="text-muted-foreground ml-1 text-xs">({one.note})</span>
            )}
          </dd>
        </div>
      ))}
    </dl>
  )
}

export function AttributeValuesPanel({
  target,
  values,
  canEdit,
  onSave,
}: {
  target: AttributeTarget
  values: AttributeValue[]
  canEdit: boolean
  /** 통째로 저장한다. 끝나면 부모가 다시 읽는다. */
  onSave: (attributes: AttributeValueIn[]) => Promise<void>
}) {
  const [editing, setEditing] = useState(false)
  const [rows, setRows] = useState<AttributeRow[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | Error | null>(null)

  function open() {
    setRows(fromValues(values))
    setError(null)
    setEditing(true)
  }

  async function save() {
    setBusy(true)
    setError(null)
    try {
      await onSave(toPayload(rows))
      setEditing(false)
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  if (!editing) {
    return (
      <div className="space-y-3">
        <AttributeValuesList values={values} />
        {canEdit && (
          <Button type="button" variant="outline" size="sm" onClick={open}>
            <Pencil className="size-4" />
            속성 편집
          </Button>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <AttributeValuesEditor target={target} rows={rows} onChange={setRows} />
      <ErrorNotice error={error} />
      <div className="flex gap-2">
        <Button type="button" size="sm" onClick={() => void save()} disabled={busy}>
          {busy ? '저장 중…' : '저장'}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => setEditing(false)}
          disabled={busy}
        >
          취소
        </Button>
      </div>
    </div>
  )
}

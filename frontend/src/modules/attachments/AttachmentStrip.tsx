/**
 * 한 자리에 붙은 그림들 — 칸 아래에 줄지어 선다.
 *
 * **그림은 플랫폼에 들어와 조회하는 사람의 것이다.** 그래서 목록이 아니라 그림 자체가
 * 보여야 하고, 설명이 그 아래 붙어야 한다 — 파일 이름만 줄줄이 있으면 아무도 안 연다.
 *
 * 올리기는 **한 장씩**이다. 여러 장을 한 요청에 담으면 열째에서 막혔을 때 앞의 아홉이
 * 들어갔는지 사람이 알 수 없다 — 줄마다 성패를 보인다.
 */

import { useEffect, useRef, useState } from 'react'
import { ImagePlus, X } from 'lucide-react'

import { ApiError, fetchBlobUrl } from '@/shared/api/client'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { attachmentApi } from '@/modules/attachments/api'
import type { Attachment, AttachmentTarget } from '@/modules/attachments/api'

/** 그림 한 장. **자격을 실어 받아 온다** — `<img src="/api/…">` 는 401 이 난다. */
function Thumb({ row }: { row: Attachment }) {
  const [url, setUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let dropped = false
    let made: string | null = null
    fetchBlobUrl(row.url)
      .then((next) => {
        if (dropped) {
          URL.revokeObjectURL(next)
          return
        }
        made = next
        setUrl(next)
      })
      .catch(() => setFailed(true))
    return () => {
      dropped = true
      // 안 돌려주면 그 탭이 살아 있는 동안 메모리에 남는다.
      if (made) URL.revokeObjectURL(made)
    }
  }, [row.url])

  if (failed) {
    return (
      <div className="bg-muted text-muted-foreground flex size-24 items-center justify-center rounded-md border text-xs">
        못 읽음
      </div>
    )
  }
  if (row.content_type === 'application/pdf') {
    return (
      <div className="bg-muted flex size-24 items-center justify-center rounded-md border text-xs">
        PDF
      </div>
    )
  }
  return url ? (
    <img
      src={url}
      alt={row.caption || row.original_name}
      className="size-24 rounded-md border object-cover"
    />
  ) : (
    <div className="bg-muted size-24 animate-pulse rounded-md border" />
  )
}

export function AttachmentStrip({
  target,
  objectId,
  definitionId = null,
  rows,
  canEdit,
  onChanged,
  label,
}: {
  target: AttachmentTarget
  objectId: string | null
  /** 어느 칸에 붙나. `null` 이면 카드 전체. */
  definitionId?: string | null
  rows: Attachment[]
  canEdit: boolean
  onChanged: () => void
  /** 올리기 단추의 말 — 「그림 넣기」. */
  label?: string
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | Error | null>(null)
  const picker = useRef<HTMLInputElement>(null)

  async function pick(files: FileList | null) {
    if (!files || !objectId) return
    setBusy(true)
    setError(null)
    try {
      // **한 장씩 보낸다** — 하나가 막혀도 나머지는 들어간다.
      for (const file of Array.from(files)) {
        await attachmentApi.upload(target, objectId, file, { definitionId })
      }
      onChanged()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
      if (picker.current) picker.current.value = ''
    }
  }

  if (!objectId) {
    // 아직 저장 안 한 시험에는 붙일 곳이 없다 — 대상 id 가 있어야 붙는다.
    return canEdit ? (
      <p className="text-muted-foreground text-xs">저장한 뒤에 그림을 넣을 수 있습니다.</p>
    ) : null
  }

  return (
    <div className="space-y-2">
      {rows.length > 0 && (
        <ul className="flex flex-wrap gap-3">
          {rows.map((row) => (
            <li key={row.id} className="w-24 space-y-1">
              <div className="relative">
                <Thumb row={row} />
                {canEdit && (
                  <button
                    type="button"
                    aria-label={`${row.caption || row.original_name} 빼기`}
                    className="bg-background absolute -top-2 -right-2 rounded-full border p-0.5"
                    onClick={async () => {
                      setError(null)
                      try {
                        await attachmentApi.remove(row.id)
                        onChanged()
                      } catch (caught) {
                        setError(caught instanceof Error ? caught : new Error('오류'))
                      }
                    }}
                  >
                    <X className="size-3" />
                  </button>
                )}
              </div>
              {canEdit ? (
                <Input
                  defaultValue={row.caption}
                  placeholder="무엇을 찍었나"
                  aria-label={`${row.original_name} 설명`}
                  className="h-7 text-xs"
                  maxLength={300}
                  onBlur={async (event) => {
                    if (event.target.value === row.caption) return
                    await attachmentApi.update(row.id, { caption: event.target.value })
                    onChanged()
                  }}
                />
              ) : (
                <p className="text-muted-foreground truncate text-xs" title={row.caption}>
                  {row.caption || row.original_name}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}

      {canEdit && (
        <>
          <input
            ref={picker}
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif,application/pdf"
            multiple
            hidden
            onChange={(event) => void pick(event.target.files)}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={busy}
            onClick={() => picker.current?.click()}
          >
            <ImagePlus className="size-3" /> {label ?? '그림 넣기'}
          </Button>
          {rows.length === 0 && (
            <p className="text-muted-foreground text-xs">
              png · jpg · webp · pdf, 장당 10 MB 까지. **설명을 적어 두세요** — AI 는 그림을 못
              보고 그 글자만 읽습니다.
            </p>
          )}
        </>
      )}
      <ErrorNotice error={error} />
    </div>
  )
}

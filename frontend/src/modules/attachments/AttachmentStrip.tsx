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
import { FileText, ImagePlus, X } from 'lucide-react'

import { ApiError, fetchBlobUrl } from '@/shared/api/client'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { ImageLightbox } from '@/modules/attachments/ImageLightbox'
import { attachmentApi } from '@/modules/attachments/api'
import { ACCEPT, ACCEPT_WORDS, kindOf, programOf } from '@/modules/attachments/fileKind'
import type { Attachment, AttachmentTarget } from '@/modules/attachments/api'

/**
 * 크기 두 벌.
 *
 * `sm` 은 **고치는 자리**의 것이다 — 칸마다 입력 상자가 있고 그 아래 붙으므로 작아야
 * 카드가 안 길어진다. `lg` 는 **읽는 자리**의 것이다: 온습도 프로파일을 96 px 로 줄이면
 * 눈금도 범례도 안 읽혀서, 이미지를 붙인 이유가 사라진다.
 *
 * `lg` 는 `object-contain` 이다 — 정사각으로 자르면(`object-cover`) 가로로 긴 그래프의
 * 양 끝이 잘려 나간다. 잘린 줄도 모른다.
 */
const SIZES = {
  sm: { box: 'size-24', img: 'size-24 object-cover', cell: 'w-24' },
  lg: {
    box: 'h-56 w-80',
    img: 'max-h-96 w-auto max-w-full object-contain',
    cell: 'w-auto max-w-full',
  },
} as const

export type StripSize = keyof typeof SIZES

/**
 * 한 장. **자격을 실어 받아 온다** — `<img src="/api/…">` 는 401 이 난다.
 *
 * **그릴 수 있는 것만 받아 온다.** 워드·한글·PDF 는 상자로 서므로 바이트가 필요 없다 —
 * 50 MB 짜리 스캔본 열 장이 목록을 여는 것만으로 내려오면 사내망에서 바로 느껴진다.
 * 그 바이트는 크게 보기를 누를 때 그쪽에서 받는다.
 */
function Thumb({
  row,
  size,
  onReady,
}: {
  row: Attachment
  size: StripSize
  /** 받아 둔 blob 주소를 위로 — 크게 볼 때 **다시 받지 않으려고.** */
  onReady?: (url: string) => void
}) {
  const look = SIZES[size]
  const kind = kindOf(row)
  const [url, setUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  // 콜백을 의존성에 넣으면 그릴 때마다 다시 받는다 — 최신 것만 들고 있는다.
  const report = useRef(onReady)
  report.current = onReady

  useEffect(() => {
    if (kind !== 'image') return
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
        report.current?.(next)
      })
      .catch(() => setFailed(true))
    return () => {
      dropped = true
      // 안 돌려주면 그 탭이 살아 있는 동안 메모리에 남는다.
      if (made) URL.revokeObjectURL(made)
    }
  }, [row.url, kind])

  if (failed) {
    return (
      <div
        className={`bg-muted text-muted-foreground flex ${look.box} items-center justify-center rounded-md border text-xs`}
      >
        못 읽음
      </div>
    )
  }
  if (kind !== 'image') {
    // **무엇으로 여는지 적는다.** 브라우저는 이 형식들을 못 그리므로 상자가 전부다 —
    // 「워드」 라고 써 두면 누르기 전에 무엇인지 안다.
    return (
      <div
        className={`bg-muted text-muted-foreground flex ${look.box} flex-col items-center justify-center gap-1 rounded-md border`}
      >
        <FileText className="size-6" />
        <span className="text-xs font-medium">{programOf(row)}</span>
      </div>
    )
  }
  return url ? (
    <img
      src={url}
      alt={row.caption || row.original_name}
      className={`${look.img} rounded-md border`}
    />
  ) : (
    <div className={`bg-muted ${look.box} animate-pulse rounded-md border`} />
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
  size = 'sm',
}: {
  target: AttachmentTarget
  objectId: string | null
  /** 어느 칸에 붙나. `null` 이면 카드 전체. */
  definitionId?: string | null
  rows: Attachment[]
  canEdit: boolean
  onChanged: () => void
  /** 올리기 단추의 말 — 「이미지 첨부」. */
  label?: string
  /** `sm` 고치는 자리 · `lg` 읽는 자리. 자세한 것은 `SIZES`. */
  size?: StripSize
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | Error | null>(null)
  const picker = useRef<HTMLInputElement>(null)
  /** 줄마다 받아 둔 blob 주소 — 크게 볼 때 그대로 쓴다. */
  const [urls, setUrls] = useState<Record<string, string>>({})
  const [showing, setShowing] = useState<Attachment | null>(null)

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
      <p className="text-muted-foreground text-xs">저장한 뒤에 이미지를 첨부할 수 있습니다.</p>
    ) : null
  }

  return (
    <div className="space-y-2">
      {rows.length > 0 && (
        <ul className="flex flex-wrap gap-3">
          {rows.map((row) => (
            <li key={row.id} className={`${SIZES[size].cell} space-y-1`}>
              <div className="relative w-fit">
                {/* **눌러서 크게 본다.** 줄에 선 크기는 「있다」 는 표시일 뿐이라,
                    프로파일의 눈금이나 표를 찍은 사진은 여기서 안 읽힌다.
                    단추라서 키보드로도 닿는다. */}
                <button
                  type="button"
                  aria-label={`${row.caption || row.original_name} 크게 보기`}
                  className="block cursor-zoom-in rounded-md"
                  onClick={() => setShowing(row)}
                >
                  <Thumb
                    row={row}
                    size={size}
                    onReady={(url) => setUrls((prev) => ({ ...prev, [row.id]: url }))}
                  />
                </button>
                {canEdit && (
                  <button
                    type="button"
                    aria-label={`${row.caption || row.original_name} 제거`}
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
                  placeholder="이미지 설명"
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
                <p
                  className={
                    size === 'lg'
                      ? 'text-muted-foreground max-w-full text-xs'
                      : 'text-muted-foreground truncate text-xs'
                  }
                  title={row.caption}
                >
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
            accept={ACCEPT}
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
            <ImagePlus className="size-3" /> {label ?? '이미지 첨부'}
          </Button>
          {rows.length === 0 && (
            <p className="text-muted-foreground text-xs">
              {ACCEPT_WORDS}, 장당 100 MB 까지. **설명을 적어 두십시오** — AI 는 이미지를 못
              보고 그 글자만 읽습니다.
            </p>
          )}
        </>
      )}
      <ErrorNotice error={error} />

      <ImageLightbox
        shown={showing ? { row: showing, url: urls[showing.id] ?? null } : null}
        onClose={() => setShowing(null)}
      />
    </div>
  )
}

/**
 * 이미지 크게 보기 — **줄에 선 이미지는 「있다」 는 표시이지 읽을 수 있는 크기가 아니다.**
 *
 * 온습도 프로파일이나 표를 찍은 사진은 줄 안에서는 눈금도 글자도 안 읽힌다. 그러면 이미지를
 * 붙인 이유가 사라진다 — 읽는 사람은 「그림이 있네」 까지만 알고 지나간다.
 *
 * **받아 둔 blob 을 그대로 쓴다.** 다시 받으면 10 MB 짜리 사진을 두 번 받게 되고, 느린
 * 사내망에서 그 차이는 바로 느껴진다. 줄이 살아 있는 동안 blob 도 살아 있다.
 *
 * 줄이 안 받아 둔 것(워드·한글·PDF)은 **여기서 받는다** — 누른 사람은 파일을 원한다.
 * 그중 브라우저가 못 그리는 것은 그리는 시늉을 하지 않고 **내려받기를 내민다.**
 */

import { useEffect, useState } from 'react'
import { Download, FileText } from 'lucide-react'

import { fetchBlobUrl } from '@/shared/api/client'
import { Button } from '@/shared/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
import { kindOf, programOf } from '@/modules/attachments/fileKind'
import type { Attachment } from '@/modules/attachments/api'

/**
 * 어느 폭으로 그릴까 — **원본이 작아도 키운다.**
 *
 * `max-w-full` 만 두면 `<img>` 는 원본 크기로 선다. 560 px 짜리 프로파일은 크게 보기를
 * 눌러도 560 px 그대로라 「눌렀는데 그대로인데」 가 된다. 그렇다고 화면 가득 늘리면 작은
 * 그림이 뭉개지므로 **원본의 두 배**를 넘지 않게 묶는다.
 *
 * 창(`w-auto`)이 이미지에 맞춰 자라므로, 폭을 정하는 것이 곧 창 크기를 정하는 것이다.
 */
export function widthOf(natural: { w: number; h: number } | null): string | undefined {
  if (natural === null || natural.w === 0 || natural.h === 0) return undefined
  return `min(88vw, ${natural.w * 2}px, calc(74vh * ${natural.w / natural.h}))`
}

/**
 * 바이트가 아직 없으면 **여기서 받는다.**
 *
 * 줄은 그릴 수 있는 것만 받아 온다 — 워드·한글·PDF 는 상자로 서므로 바이트가 필요 없다.
 * 그것을 누른 사람은 파일을 원하는 것이니 그때 받는다. 받은 것은 닫을 때 돌려준다.
 */
function useBytes(path: string | null, given: string | null): string | null {
  const [own, setOwn] = useState<string | null>(null)

  useEffect(() => {
    setOwn(null)
    if (path === null || given !== null) return
    let dropped = false
    let made: string | null = null
    fetchBlobUrl(path)
      .then((next) => {
        if (dropped) {
          URL.revokeObjectURL(next)
          return
        }
        made = next
        setOwn(next)
      })
      .catch(() => setOwn(null))
    return () => {
      dropped = true
      // 안 돌려주면 그 탭이 살아 있는 동안 메모리에 남는다.
      if (made) URL.revokeObjectURL(made)
    }
  }, [path, given])

  return given ?? own
}

function size(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function ImageLightbox({
  shown,
  onClose,
}: {
  /** 볼 이미지와 그 blob 주소. `null` 이면 닫힌 것이다. */
  shown: { row: Attachment; url: string | null } | null
  onClose: () => void
}) {
  const row = shown?.row
  const url = useBytes(row?.url ?? null, shown?.url ?? null)
  const kind = row ? kindOf(row) : 'image'
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null)
  // 다른 이미지를 열면 지난 크기를 버린다 — 안 버리면 새 이미지가 옛 폭으로 한 번 뜬다.
  useEffect(() => setNatural(null), [row?.id])

  return (
    <Dialog open={shown !== null} onOpenChange={(next) => !next && onClose()}>
      {/* 기본 모달은 `sm:max-w-lg` 다 — 이미지에는 좁다. 화면을 거의 다 쓴다. */}
      <DialogContent className="max-h-[92vh] w-auto max-w-[92vw] sm:max-w-[92vw]">
        <DialogHeader>
          {/* 제목이 없으면 Radix 가 접근성 경고를 낸다 — 그리고 읽는 사람도 무엇을 보는지
              알아야 한다. 설명이 비어 있으면 파일 이름이 그 자리를 대신한다. */}
          <DialogTitle>{row?.caption || row?.original_name || '이미지'}</DialogTitle>
          <DialogDescription>
            {row ? `${row.original_name} · ${size(row.bytes)}` : ''}
            {row?.definition_label ? ` · ${row.definition_label}` : ''}
          </DialogDescription>
        </DialogHeader>

        <div className="flex min-h-0 items-center justify-center">
          {row && kind === 'document' ? (
            // **그리는 시늉을 하지 않는다.** 브라우저는 이 형식을 못 열고, MS·구글의 온라인
            // 뷰어는 파일이 인터넷에 공개돼 있어야 해서 사내망에서는 원리상 못 쓴다.
            // `<img>` 로 떠넘기면 깨진 그림이 뜨고, 사람은 「올리기가 잘못됐나」 한다.
            <div className="flex w-96 max-w-full flex-col items-center gap-3 px-6 py-10 text-center">
              <FileText className="text-muted-foreground size-10" />
              <p className="text-sm font-medium">
                {programOf(row)} 문서입니다 — 브라우저는 이 형식을 못 그립니다.
              </p>
              <p className="text-muted-foreground text-xs">
                내려받아 그 프로그램에서 여십시오. 사내망에서는 온라인 뷰어를 쓸 수 없습니다 —
                파일이 인터넷에 공개돼 있어야 하기 때문입니다.
              </p>
            </div>
          ) : url === null ? (
            <div className="bg-muted h-64 w-96 animate-pulse rounded-md" />
          ) : kind === 'pdf' && row ? (
            // PDF 는 그려 봐야 첫 장뿐이다 — 브라우저의 뷰어에 맡긴다.
            <iframe src={url} title={row.original_name} className="h-[70vh] w-[80vw]" />
          ) : (
            <img
              src={url}
              alt={row?.caption || row?.original_name || ''}
              className="h-auto max-h-[74vh] max-w-[88vw] rounded-md object-contain"
              style={{ width: widthOf(natural) }}
              onLoad={(event) =>
                setNatural({
                  w: event.currentTarget.naturalWidth,
                  h: event.currentTarget.naturalHeight,
                })
              }
            />
          )}
        </div>

        <DialogFooter>
          {url && row && (
            // **내려받기를 둔다.** 사내 보고서에 붙이려면 파일이 필요하고, 지금은 화면
            // 밖으로 꺼낼 길이 없다.
            // 문서는 **내려받는 것이 곧 여는 것**이라 그쪽이 주된 단추다.
            <Button variant={kind === 'document' ? 'default' : 'outline'} asChild>
              <a href={url} download={row.original_name}>
                <Download className="size-4" />
                내려받기
              </a>
            </Button>
          )}
          <Button variant={kind === 'document' ? 'outline' : 'default'} onClick={onClose}>
            닫기
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

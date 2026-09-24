/**
 * 이미지 크게 보기 — **줄에 선 이미지는 「있다」 는 표시이지 읽을 수 있는 크기가 아니다.**
 *
 * 온습도 프로파일이나 표를 찍은 사진은 줄 안에서는 눈금도 글자도 안 읽힌다. 그러면 이미지를
 * 붙인 이유가 사라진다 — 읽는 사람은 「그림이 있네」 까지만 알고 지나간다.
 *
 * **받아 둔 blob 을 그대로 쓴다.** 다시 받으면 10 MB 짜리 사진을 두 번 받게 되고, 느린
 * 사내망에서 그 차이는 바로 느껴진다. 줄이 살아 있는 동안 blob 도 살아 있다.
 */

import { useEffect, useState } from 'react'
import { Download } from 'lucide-react'

import { Button } from '@/shared/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
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
  const url = shown?.url ?? null
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
          {url === null ? (
            <div className="bg-muted h-64 w-96 animate-pulse rounded-md" />
          ) : row?.content_type === 'application/pdf' ? (
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
            <Button variant="outline" asChild>
              <a href={url} download={row.original_name}>
                <Download className="size-4" />
                내려받기
              </a>
            </Button>
          )}
          <Button onClick={onClose}>닫기</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

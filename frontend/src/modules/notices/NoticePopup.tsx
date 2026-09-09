/**
 * 읽지 않은 팝업 공지는 **스스로 뜬다.**
 *
 * 공지 화면에 들어가야만 보이면 "배포 없이 안내를 전한다" 는 목적이 성립하지
 * 않는다. 읽음은 서버가 기록하므로 다른 PC 에서 또 뜨지 않는다.
 */

import { useEffect, useState } from 'react'

import { Button } from '@/shared/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
import { noticeApi } from '@/modules/notices/api'
import type { Notice } from '@/modules/notices/api'

export function NoticePopup() {
  const [queue, setQueue] = useState<Notice[]>([])

  useEffect(() => {
    let cancelled = false
    noticeApi
      .popup()
      .then((rows) => {
        if (!cancelled) setQueue(rows)
      })
      .catch(() => {
        // 세션이 없거나 서버가 잠깐 없다. **공지 하나 때문에 화면에 오류를 띄우지
        // 않는다** — 사람이 하던 일과 아무 상관이 없다.
      })
    return () => {
      cancelled = true
    }
  }, [])

  const current = queue[0]
  if (!current) return null

  async function dismiss() {
    // **읽음을 먼저 보낸다.** 닫고 나서 보내면 그 사이에 창을 닫은 사람에게 다음
    // 로드에서 같은 공지가 또 뜬다.
    try {
      await noticeApi.markRead(current.id)
    } finally {
      setQueue((rows) => rows.slice(1))
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && dismiss()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{current.title}</DialogTitle>
          <DialogDescription asChild>
            <div className="text-foreground text-sm whitespace-pre-wrap">{current.body}</div>
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button onClick={dismiss}>확인</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/**
 * 되돌릴 수 없는 일을 누르기 전에.
 *
 * **무엇이 사라지는지 적는다.** "정말 삭제하시겠습니까" 만 묻는 창은 아무도 안
 * 읽고 예를 누른다 — 읽을 것이 없기 때문이다.
 */

import { useState } from 'react'
import type { ReactNode } from 'react'

import { ApiError } from '@/shared/api/client'
import { Button } from '@/shared/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
import { ErrorNotice } from '@/shared/components/ErrorNotice'

interface ConfirmDialogProps {
  open: boolean
  title: string
  /** 무엇이 사라지는가. 숫자가 있으면 숫자를 적는다. */
  description: ReactNode
  confirmLabel?: string
  destructive?: boolean
  onConfirm: () => Promise<void>
  onClose: () => void
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = '확인',
  destructive = false,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | Error | null>(null)

  async function run() {
    setBusy(true)
    setError(null)
    try {
      await onConfirm()
      onClose()
    } catch (caught) {
      // **창을 닫지 않는다.** 닫으면 오류가 어디에도 안 남고, 사람은 일이 된 줄 안다.
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && !busy && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription asChild>
            <div className="text-sm">{description}</div>
          </DialogDescription>
        </DialogHeader>
        <ErrorNotice error={error} />
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy}>
            취소
          </Button>
          <Button
            variant={destructive ? 'destructive' : 'default'}
            onClick={run}
            disabled={busy}
          >
            {busy ? '처리 중…' : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

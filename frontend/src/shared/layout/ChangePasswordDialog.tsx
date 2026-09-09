/**
 * 비밀번호 변경.
 *
 * 바꾸고 나면 **서버가 모든 세션을 끊는다** — 바꾼 이유가 유출일 수 있기 때문이다.
 * 그래서 이 창이 닫힌 뒤 호출부는 로그아웃까지 해야 클라이언트 상태가 맞는다.
 */

import { useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError, api } from '@/shared/api/client'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { Button } from '@/shared/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'

export function ChangePasswordDialog({
  open,
  onClose,
  onChanged,
}: {
  open: boolean
  onClose: () => void
  onChanged: () => void
}) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [again, setAgain] = useState('')
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    // **한 번 더 받는 이유**: 서버는 새 비밀번호가 무엇이었는지 모른다. 오타로
    // 바꾸면 그 사람은 아무도 모르는 값으로 잠기고, 복구는 관리자뿐이다.
    if (next !== again) {
      setError(new Error('새 비밀번호가 서로 다릅니다.'))
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api.post('/auth/change-password', {
        current_password: current,
        new_password: next,
      })
      setCurrent('')
      setNext('')
      setAgain('')
      onChanged()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(value) => !value && !busy && onClose()}>
      <DialogContent>
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>비밀번호 변경</DialogTitle>
            <DialogDescription>
              바꾸면 다른 기기의 로그인이 모두 끊깁니다. 다시 로그인해 주세요.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label htmlFor="current">현재 비밀번호</Label>
            <Input
              id="current"
              type="password"
              value={current}
              onChange={(event) => setCurrent(event.target.value)}
              autoComplete="current-password"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="next">새 비밀번호</Label>
            <Input
              id="next"
              type="password"
              value={next}
              onChange={(event) => setNext(event.target.value)}
              autoComplete="new-password"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="again">새 비밀번호 확인</Label>
            <Input
              id="again"
              type="password"
              value={again}
              onChange={(event) => setAgain(event.target.value)}
              autoComplete="new-password"
              required
            />
          </div>

          <ErrorNotice error={error} />

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
              취소
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? '바꾸는 중…' : '바꾸기'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

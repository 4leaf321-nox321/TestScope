/**
 * 첫 로그인 강제 변경.
 *
 * **다른 화면으로 나갈 길을 두지 않는다.** 임시 비밀번호가 그대로 남는 사고를
 * 막는 것이 이 화면의 존재 이유인데, 우회할 수 있으면 무의미하다.
 */

import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError, api } from '@/shared/api/client'
import { useAuth } from '@/shared/auth/AuthContext'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'

export default function ForcePasswordChangePage() {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [again, setAgain] = useState('')
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
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
      // 서버가 모든 세션을 끊었다 — 클라이언트 상태도 맞추고 다시 로그인시킨다.
      await logout()
      navigate('/login', { replace: true })
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-svh items-center justify-center p-6">
      <form onSubmit={submit} className="w-full max-w-sm space-y-5">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">비밀번호를 바꿔 주세요</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            임시 비밀번호로 로그인했습니다. 바꾸기 전에는 다른 화면을 쓸 수 없습니다.
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="current">임시 비밀번호</Label>
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

        <Button type="submit" className="w-full" disabled={busy}>
          {busy ? '바꾸는 중…' : '바꾸고 다시 로그인'}
        </Button>
      </form>
    </div>
  )
}

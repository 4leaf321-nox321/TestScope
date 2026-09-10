/**
 * 로그인.
 *
 * **원래 가려던 곳으로 되돌려 보낸다.** 링크로 받은 주소가 로그인 후 홈으로
 * 흘러가 버리면, 사람은 그 링크를 다시 찾아야 한다.
 */

import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { ApiError } from '@/shared/api/client'
import { useAuth } from '@/shared/auth/AuthContext'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'

export default function LoginPage() {
  const { status, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [busy, setBusy] = useState(false)

  const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname

  if (status === 'authenticated') return <Navigate to={from ?? '/'} replace />

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const user = await login(email, password)
      // 임시 비밀번호로 들어왔으면 다른 화면을 못 쓴다. 가드도 막지만, 여기서
      // 바로 보내면 한 번 깜빡이는 것을 없앨 수 있다.
      navigate(user.must_change_password ? '/force-password-change' : (from ?? '/'), {
        replace: true,
      })
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
          <h1 className="text-2xl font-semibold tracking-tight">TestScope</h1>
          <p className="text-muted-foreground mt-1 text-sm">조직이 보유한 시험 역량의 지도</p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="email">아이디</Label>
          <Input
            id="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="username"
            autoFocus
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">비밀번호</Label>
          <Input
            id="password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
          />
        </div>

        {/* **왜 안 되는지 그대로 보여 준다.** 승인 대기와 정지는 사람이 할 일이
            다르고, 그 차이는 서버가 이미 메시지로 말해 준다. */}
        <ErrorNotice error={error} />

        <Button type="submit" className="w-full" disabled={busy}>
          {busy ? '확인 중…' : '로그인'}
        </Button>

        <p className="text-muted-foreground text-center text-sm">
          계정이 없나요?{' '}
          <Link to="/signup" className="hover:text-foreground underline">
            가입 신청
          </Link>
        </p>
      </form>
    </div>
  )
}

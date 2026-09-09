/**
 * 가입 신청.
 *
 * 승인 전까지는 로그인할 수 없다. **그 사실을 신청 화면에서 말한다** — 안 말하면
 * 신청 직후 로그인을 시도하고, 거절 메시지를 고장으로 읽는다.
 */

import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ApiError, api } from '@/shared/api/client'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import { useResource } from '@/shared/hooks/useResource'

interface WorkspaceOption {
  slug: string
  name: string
  path: string
  depth: number
}

export default function SignupPage() {
  const navigate = useNavigate()
  // 로그인 전에도 부르는 유일한 목록이다(서버에서도 인증이 없다).
  const options = useResource(() => api.get<WorkspaceOption[]>('/workspaces/options'), [])
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [workspace, setWorkspace] = useState('')
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.post('/accounts/signup', {
        email,
        password,
        display_name: displayName,
        workspace_slug: workspace,
      })
      setDone(true)
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <div className="flex min-h-svh items-center justify-center p-6">
        <div className="w-full max-w-sm space-y-4 text-center">
          <h1 className="text-xl font-semibold">신청이 접수되었습니다</h1>
          <p className="text-muted-foreground text-sm">
            관리자가 승인하면 로그인할 수 있습니다. 메일 통보는 없으니 담당자에게 직접
            알려 주세요.
          </p>
          <Button onClick={() => navigate('/login')} className="w-full">
            로그인 화면으로
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-svh items-center justify-center p-6">
      <form onSubmit={submit} className="w-full max-w-sm space-y-5">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">가입 신청</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            관리자 승인 뒤에 로그인할 수 있습니다.
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="email">아이디</Label>
          <Input
            id="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="username"
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="name">이름</Label>
          <Input
            id="name"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
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
            autoComplete="new-password"
            minLength={8}
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="workspace">희망 부서</Label>
          {/* **경로를 보여 준다.** 같은 이름의 팀이 본부마다 있을 수 있고, 이름만
              보여 주면 신청자가 어느 쪽인지 고를 수 없다. */}
          <Select value={workspace} onValueChange={setWorkspace}>
            <SelectTrigger id="workspace">
              <SelectValue placeholder="부서를 고르세요" />
            </SelectTrigger>
            <SelectContent>
              {(options.data ?? []).map((one) => (
                <SelectItem key={one.slug} value={one.slug}>
                  {one.path}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <ErrorNotice error={error ?? options.error} />

        <Button type="submit" className="w-full" disabled={busy || !workspace}>
          {busy ? '보내는 중…' : '신청'}
        </Button>

        <p className="text-muted-foreground text-center text-sm">
          <Link to="/login" className="hover:text-foreground underline">
            로그인 화면으로
          </Link>
        </p>
      </form>
    </div>
  )
}

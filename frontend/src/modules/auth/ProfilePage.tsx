/**
 * 내 정보 — 표시 이름과 액세스 토큰.
 *
 * 팝업이 아니라 화면인 이유: 토큰 목록이 붙으면 팝업이 좁다.
 */

import { useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError, api } from '@/shared/api/client'
import { useAuth } from '@/shared/auth/AuthContext'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table'
import { useResource } from '@/shared/hooks/useResource'
import { shownDate } from '@/shared/lib/datetime'

interface Pat {
  id: string
  name: string
  prefix: string
  created_at: string
  expires_at: string | null
  last_used_at: string | null
  revoked_at: string | null
}

export default function ProfilePage() {
  const { user, reload } = useAuth()
  const [displayName, setDisplayName] = useState(user?.display_name ?? '')
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [busy, setBusy] = useState(false)

  const tokens = useResource(() => api.get<Pat[]>('/auth/tokens'), [])
  const [tokenName, setTokenName] = useState('')
  // 평문은 발급 응답에서 **한 번만** 나온다. 새로고침하면 다시 볼 수 없다.
  const [issued, setIssued] = useState<string | null>(null)

  async function saveName(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.patch('/auth/me', { display_name: displayName })
      await reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  async function createToken(event: FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      const body = await api.post<{ token: string }>('/auth/tokens', { name: tokenName })
      setIssued(body.token)
      setTokenName('')
      tokens.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

  async function revoke(id: string) {
    await api.delete(`/auth/tokens/${id}`)
    tokens.reload()
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <PageHeader title="내 정보" description={user?.email} />

      <form onSubmit={saveName} className="space-y-3">
        <div className="space-y-2">
          <Label htmlFor="display-name">표시 이름</Label>
          <Input
            id="display-name"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            className="max-w-sm"
          />
          {/* **아이디는 여기서 못 바꾼다.** 로그인 식별자라 본인이 바꾸면 감사
              기록이 가리키는 대상이 흔들린다 — 그것은 관리자의 일이다. */}
          <p className="text-muted-foreground text-xs">아이디는 관리자만 바꿀 수 있습니다.</p>
        </div>
        <Button type="submit" disabled={busy}>
          {busy ? '저장 중…' : '저장'}
        </Button>
      </form>

      <ErrorNotice error={error} />

      <section className="space-y-3">
        <div>
          <h2 className="text-base font-semibold">액세스 토큰</h2>
          <p className="text-muted-foreground mt-1 text-sm">
            장비 PC 나 스크립트가 이 시스템의 API 를 부를 때 쓰는 자격입니다. 사람 세션과 달리
            만료가 길고, 안 쓰면 지웁니다.
          </p>
        </div>

        {issued && (
          <div className="rounded-md border border-amber-500/40 bg-amber-500/5 p-3 text-sm">
            {/* **여기서 한 번만 보인다.** 다시 볼 수 없다는 것을 말하지 않으면
                사람은 창을 닫고 나서 다시 찾는다. */}
            <p className="font-medium">지금 복사해 두십시오. 다시 볼 수 없습니다.</p>
            <p className="mt-1 font-mono text-xs break-all">{issued}</p>
          </div>
        )}

        <form onSubmit={createToken} className="flex max-w-md gap-2">
          <Input
            value={tokenName}
            onChange={(event) => setTokenName(event.target.value)}
            placeholder="토큰 용도"
            required
          />
          <Button type="submit">발급</Button>
        </form>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>이름</TableHead>
              <TableHead>접두어</TableHead>
              <TableHead>발급</TableHead>
              <TableHead>마지막 사용</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {(tokens.data ?? []).map((one) => (
              <TableRow key={one.id} className={one.revoked_at ? 'opacity-50' : undefined}>
                <TableCell>{one.name}</TableCell>
                <TableCell className="font-mono text-xs">{one.prefix}</TableCell>
                <TableCell>{shownDate(one.created_at)}</TableCell>
                <TableCell>{shownDate(one.last_used_at)}</TableCell>
                <TableCell className="text-right">
                  {!one.revoked_at && (
                    <Button variant="ghost" size="sm" onClick={() => revoke(one.id)}>
                      폐기
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </section>
    </div>
  )
}

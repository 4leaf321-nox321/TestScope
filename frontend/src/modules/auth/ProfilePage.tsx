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
  scopes: string[]
  created_at: string
  expires_at: string | null
  last_used_at: string | null
  revoked_at: string | null
}

/**
 * 고를 수 있는 쓰기 범위. **읽기(`read`)는 늘 붙으므로 여기 없다.**
 *
 * 이름은 서버의 판정 기준(`app/shared/auth.py` 의 경로 앞자리)과 같은 말로 적는다 —
 * 화면이 「장비」 라 하고 서버가 다른 것을 여는 순간, 403 을 받은 사람은 제가 무엇을
 * 골랐는지 되짚을 수 없다.
 */
const WRITE_SCOPES = [
  {
    value: 'catalog:write',
    label: '카탈로그 쓰기',
    hint: '장비 계열·기종·사양·시험법·온톨로지',
  },
  {
    value: 'equipment:write',
    label: '장비·시험 쓰기',
    hint: '보유 장비·시험 항목·교정·신뢰성 시험',
  },
] as const

const SCOPE_LABEL: Record<string, string> = Object.fromEntries(
  WRITE_SCOPES.map((one) => [one.value, one.label]),
)

/** 목록에 보일 한 줄. **이름과 이것뿐이 폐기 판단의 근거다.** */
function shownScopes(scopes: string[]): string {
  const writes = (scopes ?? []).filter((one) => one !== 'read')
  if (writes.length === 0) return '읽기 전용'
  return writes.map((one) => SCOPE_LABEL[one] ?? one).join(' · ')
}

export default function ProfilePage() {
  const { user, reload } = useAuth()
  const [displayName, setDisplayName] = useState(user?.display_name ?? '')
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [busy, setBusy] = useState(false)

  const tokens = useResource(() => api.get<Pat[]>('/auth/tokens'), [])
  const [tokenName, setTokenName] = useState('')
  /**
   * 고른 쓰기 범위. **기본은 빈 집합 — 읽기 전용이다.**
   *
   * 기본을 전권으로 두면 「일단 만들고 나중에 좁히자」 가 되고 나중은 오지 않는다.
   * 서버도 안 주면 `["read"]` 로 본다(`PatCreateRequest`).
   */
  const [writes, setWrites] = useState<string[]>([])
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
      // **읽기는 늘 보낸다.** 쓰기만 준 토큰은 목록을 못 읽어서, 쓰기 직전에 찾아보는
      // 일(만들기 전에 resolve)이 그대로 막힌다.
      const body = await api.post<{ token: string }>('/auth/tokens', {
        name: tokenName,
        scopes: ['read', ...writes],
      })
      setIssued(body.token)
      setTokenName('')
      setWrites([])
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

        <form onSubmit={createToken} className="max-w-md space-y-3">
          <div className="flex gap-2">
            <Input
              value={tokenName}
              onChange={(event) => setTokenName(event.target.value)}
              placeholder="토큰 용도"
              required
            />
            <Button type="submit">발급</Button>
          </div>

          {/* **범위를 발급할 때 고른다.** 전에는 화면이 이름만 보내서 무엇을 하든
              읽기 전용이 나왔고, 쓰기 도구를 부르면 403 이 왔다 — 그 403 은 「권한이
              없다」 로 읽혀서, 사람은 관리자에게 권한을 달라고 하러 갔다. */}
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">이 토큰으로 할 수 있는 일</legend>
            <p className="text-muted-foreground text-xs">
              읽기는 항상 포함됩니다. <strong>발급한 뒤에는 넓힐 수 없습니다</strong> —
              넓히려면 새로 발급하고 옛 토큰을 폐기합니다.
            </p>
            {WRITE_SCOPES.map((scope) => (
              <label
                key={scope.value}
                className="flex cursor-pointer items-start gap-2 text-sm"
              >
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={writes.includes(scope.value)}
                  onChange={(event) =>
                    setWrites((before) =>
                      event.target.checked
                        ? [...before, scope.value]
                        : before.filter((one) => one !== scope.value),
                    )
                  }
                />
                <span>
                  {scope.label}
                  <span className="text-muted-foreground ml-1.5 text-xs">{scope.hint}</span>
                </span>
              </label>
            ))}
            {/* 어느 범위로도 안 열리는 것이 있다 — 고르고 나서 알면 늦다. */}
            <p className="text-muted-foreground text-xs">
              계정 관리와 서버 설정은 어느 범위로도 열리지 않습니다.
            </p>
          </fieldset>
        </form>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>이름</TableHead>
              <TableHead>접두어</TableHead>
              <TableHead>범위</TableHead>
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
                {/* 폐기할지 판단하는 근거가 이름과 이것뿐이다. */}
                <TableCell className="text-sm">{shownScopes(one.scopes)}</TableCell>
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

/**
 * 소속 바꾸기 — **한 번에 정한다.**
 *
 * 부서를 옮기는 일은 「떼고 붙이기」 두 걸음인데, 두 번에 나누면 그 사이에 **아무 데도 안
 * 속한 사람**이 남는다. 두 번째가 실패하면 그 상태로 굳고, 그 사람은 로그인해도 갈 곳이
 * 없으면서 무엇이 잘못됐는지도 모른다. 그래서 창이 목록 전체를 들고 있다가 한 번에 보낸다.
 *
 * **대표 소속은 서버가 따라 옮긴다** — 뺀 부서가 대표였으면 남은 것 중 첫 번째로. 화면이
 * 그것까지 시키면 두 벌이 되고, 그때 한쪽만 고쳐진다.
 */

import { useEffect, useState } from 'react'
import { Plus, X } from 'lucide-react'

import { ApiError } from '@/shared/api/client'
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
import { Label } from '@/shared/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import { accountApi } from '@/modules/accounts/api'
import type { Account } from '@/modules/accounts/api'
import { workspaceApi } from '@/modules/workspaces/api'
import type { WorkspaceOption } from '@/modules/workspaces/api'

interface Row {
  workspace_slug: string
  role: string
}

export function MembershipsDialog({
  account,
  onClose,
  onSaved,
}: {
  /** 소속을 바꿀 사람. `null` 이면 닫힌 것이다. */
  account: Account | null
  onClose: () => void
  onSaved: () => void
}) {
  /** 지금 소속. **아직 못 읽었으면 `null`** — 그 상태로 저장하면 소속을 통째로 지운다. */
  const [rows, setRows] = useState<Row[] | null>(null)
  const [options, setOptions] = useState<WorkspaceOption[]>([])
  const [adding, setAdding] = useState('')
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [busy, setBusy] = useState(false)

  const id = account?.id ?? null
  useEffect(() => {
    setError(null)
    setAdding('')
    setRows(null)
    if (!id) return
    let dropped = false
    // **역할까지 받아 온다.** 목록은 slug 만 주므로, 그것만 보고 채우면 역할을 모르는
    // 채로 되보내게 되고 **부서 관리자가 조용히 멤버로 내려앉는다**(2026-09-28 실측).
    // 그래서 다 받기 전에는 아무것도 안 보낸다(`rows === null`).
    Promise.all([accountApi.memberships(id), workspaceApi.options()])
      .then(([mine, all]) => {
        if (dropped) return
        setOptions(all)
        setRows(mine.map((one) => ({ workspace_slug: one.workspace_slug, role: one.role })))
      })
      .catch((caught) => !dropped && setError(caught as Error))
    return () => {
      dropped = true
    }
  }, [id])

  const left = options.filter(
    (one) => !(rows ?? []).some((row) => row.workspace_slug === one.slug),
  )

  async function save() {
    // **못 읽었으면 저장하지 않는다.** 빈 목록을 보내면 소속을 통째로 지우는 것이 된다.
    if (!id || rows === null) return
    setBusy(true)
    setError(null)
    try {
      await accountApi.setMemberships(id, rows)
      onSaved()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={account !== null} onOpenChange={(next) => !next && !busy && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{account?.display_name} 소속</DialogTitle>
          <DialogDescription>
            여기 적힌 것이 <strong>곧 소속</strong>입니다 — 뺀 부서는 지워집니다. 대표 소속은
            서버가 따라 옮깁니다(뺀 곳이 대표였으면 남은 첫 부서로, 남은 것이 없으면 비움).
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          {rows === null ? (
            <p className="text-muted-foreground text-sm">읽는 중…</p>
          ) : rows.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              소속이 없습니다 — 이대로 저장하면 이 사람은 갈 부서가 없습니다.
            </p>
          ) : (
            <ul className="space-y-2">
              {rows.map((row, at) => (
                <li key={row.workspace_slug} className="flex items-center gap-2">
                  <span className="flex-1 truncate text-sm" title={row.workspace_slug}>
                    {options.find((one) => one.slug === row.workspace_slug)?.name ??
                      row.workspace_slug}
                  </span>
                  <Select
                    value={row.role}
                    onValueChange={(next) =>
                      setRows((prev) =>
                        (prev ?? []).map((one, index) =>
                          index === at ? { ...one, role: next } : one,
                        ),
                      )
                    }
                  >
                    <SelectTrigger className="w-28" aria-label={`${row.workspace_slug} 역할`}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="member">멤버</SelectItem>
                      <SelectItem value="manager">관리자</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={`${row.workspace_slug} 빼기`}
                    onClick={() =>
                      setRows((prev) => (prev ?? []).filter((_, index) => index !== at))
                    }
                  >
                    <X className="size-4" />
                  </Button>
                </li>
              ))}
            </ul>
          )}

          <div className="flex items-end gap-2 border-t pt-3">
            <div className="flex-1 space-y-1">
              <Label htmlFor="add-workspace">부서 더하기</Label>
              <Select value={adding} onValueChange={setAdding}>
                <SelectTrigger id="add-workspace">
                  <SelectValue placeholder="부서 선택" />
                </SelectTrigger>
                <SelectContent>
                  {left.map((one) => (
                    <SelectItem key={one.slug} value={one.slug}>
                      {one.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              type="button"
              variant="outline"
              disabled={!adding}
              onClick={() => {
                setRows((prev) => [
                  ...(prev ?? []),
                  { workspace_slug: adding, role: 'member' },
                ])
                setAdding('')
              }}
            >
              <Plus className="size-4" />
              더하기
            </Button>
          </div>
        </div>

        <ErrorNotice error={error} />

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy}>
            취소
          </Button>
          <Button onClick={save} disabled={busy || rows === null}>
            저장
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

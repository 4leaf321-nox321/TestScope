/**
 * 부서 지우기 — **가진 것이 있으면 어디로 보낼지 먼저 정한다.**
 *
 * 조직은 개편된다. 팀이 본부에 합쳐지고 본부가 없어지는데, 그때 그 부서의 장비 수십 대와
 * 신뢰성 시험과 규격서가 함께 사라지면 안 된다. 그래서 이 창은 순서가 있다:
 *
 *     무엇이 딸려 있나(references)  →  어디로 보낼까(대상)  →  무엇이 옮겨지나(preview)
 *
 * **누르기 전에 답한다.** 「장비 12대가 옮겨집니다」 를 보고 누르는 것과, 누르고 나서 아는
 * 것은 다른 일이다. 겹치는 이름이 있으면 **단추를 막는다** — 둘 중 무엇을 남길지는
 * 사람이 정할 일이라 우리가 고르지 않는다.
 */

import { useEffect, useState } from 'react'
import { AlertTriangle, Trash2 } from 'lucide-react'

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
import { workspaceApi } from '@/modules/workspaces/api'
import type {
  Workspace,
  WorkspaceReassign,
  WorkspaceReference,
} from '@/modules/workspaces/api'

/** 옮기지 않고 지우기를 고른 상태. 빈 문자열은 Select 가 못 쓰는 값이라 이름을 준다. */
export const NONE = '__none__'

/**
 * 지금 지울 수 있나, 단추에 뭐라고 쓸까 — **판정만 떼어 둔다.**
 *
 * 창에 두면 이 규칙을 확인하려고 Select 를 눌러야 하는데, 그건 브라우저 밖에서는
 * 잘 안 되는 일이다. 규칙은 둘이다:
 *
 * * 옮기지 않고 지우려면 **막는 것이 하나도 없어야** 한다(장비·시험·규격서·하위 부서).
 * * 옮기고 지우려면 **겹치는 이름이 없어야** 한다 — 옮긴 순간 같은 이름이 둘이 된다.
 */
export function removalState(input: {
  to: string
  references: WorkspaceReference[] | null
  clashes: { values: string[] }[]
}): { blocked: boolean; label: string } {
  const moving = input.to !== NONE
  const blocking = (input.references ?? []).filter((one) => one.blocks_delete)
  return {
    blocked: moving ? input.clashes.length > 0 : blocking.length > 0,
    label: moving ? '옮기고 지우기' : '지우기',
  }
}

export function DeleteWorkspaceDialog({
  target,
  all,
  onClose,
  onDeleted,
}: {
  /** 지울 부서. `null` 이면 닫힌 것이다. */
  target: Workspace | null
  /** 이관 대상 후보 — 자기 자신은 뺀다. */
  all: Workspace[]
  onClose: () => void
  onDeleted: () => void
}) {
  const [refs, setRefs] = useState<WorkspaceReference[] | null>(null)
  const [to, setTo] = useState(NONE)
  const [preview, setPreview] = useState<WorkspaceReassign | null>(null)
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [busy, setBusy] = useState(false)

  const slug = target?.slug ?? null
  useEffect(() => {
    setRefs(null)
    setTo(NONE)
    setPreview(null)
    setError(null)
    if (!slug) return
    let dropped = false
    workspaceApi
      .references(slug)
      .then((rows) => !dropped && setRefs(rows))
      .catch((caught) => !dropped && setError(caught as Error))
    return () => {
      dropped = true
    }
  }, [slug])

  // 대상을 고르는 **그 순간** 무엇이 옮겨지고 무엇이 겹치는지 받아 온다.
  useEffect(() => {
    setPreview(null)
    if (!slug || to === NONE) return
    let dropped = false
    workspaceApi
      .reassignPreview(slug, to)
      .then((got) => !dropped && setPreview(got))
      .catch((caught) => !dropped && setError(caught as Error))
    return () => {
      dropped = true
    }
  }, [slug, to])

  const blocking = (refs ?? []).filter((one) => one.blocks_delete)
  const clashes = preview?.clashes ?? []
  const { blocked, label } = removalState({ to, references: refs, clashes })

  async function remove() {
    if (!slug) return
    setBusy(true)
    setError(null)
    try {
      await workspaceApi.remove(slug, to === NONE ? null : to)
      onDeleted()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={target !== null} onOpenChange={(next) => !next && !busy && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{target?.name} 부서 지우기</DialogTitle>
          <DialogDescription>
            되돌릴 수 없습니다. <strong>보관(사용 → 보관)</strong> 은 자료를 남기고 새 활동만
            막습니다 — 조직이 없어진 것이 아니라면 그쪽이 맞습니다.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <section className="space-y-1">
            <p className="text-sm font-medium">이 부서가 가진 것</p>
            {refs === null ? (
              <p className="text-muted-foreground text-sm">세는 중…</p>
            ) : refs.length === 0 ? (
              <p className="text-muted-foreground text-sm">
                없습니다 — 그냥 지울 수 있습니다.
              </p>
            ) : (
              <ul className="text-sm">
                {refs.map((one) => (
                  <li key={one.table} className="flex justify-between gap-4">
                    <span>{one.label}</span>
                    <span
                      className={one.blocks_delete ? 'font-medium' : 'text-muted-foreground'}
                    >
                      {one.count}건{one.blocks_delete ? ' · 옮겨야 함' : ''}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="space-y-2">
            <Label htmlFor="reassign-to">어디로 옮길까</Label>
            <Select value={to} onValueChange={setTo}>
              <SelectTrigger id="reassign-to">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>옮기지 않음</SelectItem>
                {all
                  .filter((one) => one.slug !== target?.slug)
                  .map((one) => (
                    <SelectItem key={one.slug} value={one.slug}>
                      {one.name}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
            {to === NONE && blocking.length > 0 && (
              <p className="text-muted-foreground text-xs">
                옮길 곳을 정해야 지울 수 있습니다 — 위의 것들이 이 부서를 가리키고 있습니다.
              </p>
            )}
          </section>

          {preview && (
            <section className="space-y-2 rounded-md border p-3">
              <p className="text-sm">
                <strong>{preview.target_name}</strong> 으로 옮깁니다
              </p>
              {preview.moves.length === 0 ? (
                <p className="text-muted-foreground text-sm">옮길 것이 없습니다.</p>
              ) : (
                <ul className="text-sm">
                  {preview.moves.map((one) => (
                    <li key={one.table} className="flex justify-between gap-4">
                      <span>{one.label}</span>
                      <span className="text-muted-foreground">{one.count}건</span>
                    </li>
                  ))}
                </ul>
              )}
              {clashes.length > 0 && (
                // **우리가 고르지 않는다.** 무엇이 겹치는지 값까지 보이고 사람이 고친다.
                <div className="space-y-1 border-t pt-2">
                  <p className="text-destructive flex items-center gap-1 text-sm font-medium">
                    <AlertTriangle className="size-4" />
                    이름이 겹쳐서 그대로는 못 옮깁니다
                  </p>
                  {clashes.map((one) => (
                    <p key={one.table} className="text-xs">
                      <span className="font-medium">{one.label}</span>{' '}
                      <span className="text-muted-foreground">
                        {one.values.slice(0, 5).join(', ')}
                        {one.values.length > 5 ? ` 외 ${one.values.length - 5}건` : ''}
                      </span>
                    </p>
                  ))}
                  <p className="text-muted-foreground text-xs">
                    한쪽 이름을 먼저 고치십시오 — 둘 중 무엇을 남길지는 사람이 정할 일입니다.
                  </p>
                </div>
              )}
            </section>
          )}
        </div>

        <ErrorNotice error={error} />

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy}>
            취소
          </Button>
          <Button variant="destructive" onClick={remove} disabled={busy || blocked}>
            <Trash2 className="size-4" />
            {label}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

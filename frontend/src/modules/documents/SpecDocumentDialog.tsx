/**
 * 사내 규격서 등록·수정 — **한 벌이다.**
 *
 * 따로 두면 칸이 갈라지고, 그때 「등록은 되는데 수정은 안 되는 칸」 이 생긴다.
 *
 * 파일은 여기서 안 올린다 — **저장한 뒤에** 보기 창에서 붙인다. 문서 줄이 있어야 파일이
 * 붙을 자리가 정해지기 때문이다(첨부는 대상 id 를 요구한다).
 */

import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError } from '@/shared/api/client'
import { useAuth } from '@/shared/auth/AuthContext'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import { Textarea } from '@/shared/components/ui/textarea'
import { specDocumentApi } from '@/modules/documents/api'
import type { SpecDocument } from '@/modules/documents/api'

export function SpecDocumentDialog({
  open,
  editing = null,
  onClose,
  onSaved,
}: {
  open: boolean
  /** 있으면 수정, 없으면 등록. */
  editing?: SpecDocument | null
  onClose: () => void
  onSaved: () => void
}) {
  const { user } = useAuth()
  const managed = (user?.memberships ?? []).filter(
    (one) => one.role === 'manager' || user?.is_system_admin,
  )

  const [workspace, setWorkspace] = useState('')
  const [code, setCode] = useState('')
  const [title, setTitle] = useState('')
  const [revision, setRevision] = useState('')
  const [note, setNote] = useState('')
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return
    setError(null)
    setWorkspace(editing?.workspace_slug ?? managed[0]?.slug ?? '')
    setCode(editing?.code ?? '')
    setTitle(editing?.title ?? '')
    setRevision(editing?.revision ?? '')
    setNote(editing?.note ?? '')
    // 열 때마다 대상에 맞춰 채운다 — 지난번 값이 남아 있으면 안 된다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, editing])

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const body = {
        code: code.trim(),
        title: title.trim(),
        revision: revision.trim() || null,
        note: note.trim() || null,
      }
      if (editing) await specDocumentApi.update(editing.id, body)
      else await specDocumentApi.create(workspace, body)
      onSaved()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && !busy && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>{editing ? '사내 규격서 수정' : '사내 규격서 등록'}</DialogTitle>
            <DialogDescription>
              부서가 만든 시험 문서입니다. 공개 규격(ASTM·ISO·KS)은 「시험법·규격」 에
              등록합니다. <strong>원본 파일은 저장한 뒤에 붙입니다.</strong>
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="doc-code">문서 번호</Label>
              <Input
                id="doc-code"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                placeholder="MX-REL-012"
                required
                maxLength={100}
              />
              <p className="text-muted-foreground text-xs">
                문서관리 시스템의 번호를 그대로 적습니다. 같은 부서에 같은 번호는 하나입니다.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="doc-revision">판</Label>
              <Input
                id="doc-revision"
                value={revision}
                onChange={(event) => setRevision(event.target.value)}
                placeholder="Rev.3"
                maxLength={30}
              />
              {/* **판을 고치는 것이 개정이다.** 줄을 새로 만들면 걸어 둔 시험 수십 건의
                  링크를 사람이 옮겨야 하고, 그러면 아무도 안 옮긴다. */}
              <p className="text-muted-foreground text-xs">
                개정하면 이 칸을 고치고 새 파일을 더합니다. 줄을 새로 만들지 않아서 걸어 둔
                시험의 링크가 끊기지 않습니다.
              </p>
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="doc-title">제목</Label>
              <Input
                id="doc-title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="신뢰성 시험 표준 — 환경 시험"
                required
                maxLength={300}
              />
            </div>
            {!editing && (
              <div className="space-y-2">
                <Label htmlFor="doc-workspace">부서</Label>
                <Select value={workspace} onValueChange={setWorkspace}>
                  <SelectTrigger id="doc-workspace">
                    <SelectValue placeholder="부서 선택" />
                  </SelectTrigger>
                  <SelectContent>
                    {managed.map((one) => (
                      <SelectItem key={one.slug} value={one.slug}>
                        {one.name ?? one.slug}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="doc-note">비고</Label>
              <Textarea
                id="doc-note"
                value={note}
                onChange={(event) => setNote(event.target.value)}
                rows={3}
                maxLength={4000}
                placeholder="적용 범위·개정 사유처럼 목록에서 보이면 좋은 한두 줄."
              />
            </div>
          </div>

          <ErrorNotice error={error} />

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
              취소
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? '저장 중…' : editing ? '저장' : '등록'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

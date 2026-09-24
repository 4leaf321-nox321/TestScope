/**
 * 사내 규격서 등록·수정 — **한 벌이다.**
 *
 * 따로 두면 칸이 갈라지고, 그때 「등록은 되는데 수정은 안 되는 칸」 이 생긴다.
 *
 * **파일도 여기서 고른다.** 첨부는 대상 id 를 요구해서 문서 줄이 먼저 있어야 하지만,
 * 그 두 걸음을 사람에게 시키면 「만들고 → 다시 열고 → 올리기」 가 된다 — 그러면 대개
 * 만들기까지만 하고 파일은 안 올라온다. 창이 저장한 뒤에 이어서 올린다.
 *
 * 저장은 됐는데 올리기가 막히는 경우가 있다(형식·크기). 그때 **창을 닫지 않는다** —
 * 문서는 이미 만들어졌고 어느 파일이 안 갔는지 말해 줘야 사람이 다시 고를 수 있다.
 */

import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { FileUp, X } from 'lucide-react'

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
import { attachmentApi } from '@/modules/attachments/api'
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
  /** 저장한 뒤에 올릴 것들. 문서 줄이 없으면 붙을 자리가 없어서 여기 들고 있는다. */
  const [picked, setPicked] = useState<File[]>([])
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [busy, setBusy] = useState(false)
  const picker = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) return
    setError(null)
    setWorkspace(editing?.workspace_slug ?? managed[0]?.slug ?? '')
    setCode(editing?.code ?? '')
    setTitle(editing?.title ?? '')
    setRevision(editing?.revision ?? '')
    setNote(editing?.note ?? '')
    setPicked([])
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
      const saved = editing
        ? await specDocumentApi.update(editing.id, body)
        : await specDocumentApi.create(workspace, body)

      // **한 장씩 보낸다** — 하나가 막혀도 나머지는 들어가고, 어느 것이 막혔는지 말한다.
      const failed: string[] = []
      for (const file of picked) {
        try {
          await attachmentApi.upload('spec_document', saved.id, file)
        } catch {
          failed.push(file.name)
        }
      }
      if (failed.length > 0) {
        // 문서는 이미 만들어졌다 — 창을 닫으면 사람은 파일이 갔는지 모른 채 나간다.
        setPicked([])
        setError(
          new Error(
            `문서는 저장됐지만 파일 ${failed.length}개가 안 올라갔습니다: ${failed.join(', ')}. ` +
              '형식(png·jpg·webp·pdf)과 크기(100 MB)를 보고 다시 올려 주십시오.',
          ),
        )
        return
      }
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
              등록합니다. <strong>원본 파일을 여기서 같이 올립니다.</strong>
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

          {/* **파일도 여기서 고른다.** 만들고 다시 열어 올리게 하면 대개 만들기까지만
              하고 파일은 안 올라온다 — 그러면 번호만 있는 문서가 남는다. */}
          <div className="space-y-2 border-t pt-4">
            <Label>원본 파일</Label>
            <input
              ref={picker}
              type="file"
              accept="image/png,image/jpeg,image/webp,application/pdf"
              multiple
              hidden
              onChange={(event) => {
                setPicked((prev) => [...prev, ...Array.from(event.target.files ?? [])])
                if (picker.current) picker.current.value = ''
              }}
            />
            {picked.length > 0 && (
              <ul className="space-y-1">
                {picked.map((file, at) => (
                  <li
                    key={`${file.name}-${at}`}
                    className="bg-muted/40 flex items-center justify-between gap-2 rounded-md px-2.5 py-1 text-sm"
                  >
                    <span className="truncate">{file.name}</span>
                    <button
                      type="button"
                      aria-label={`${file.name} 빼기`}
                      className="text-muted-foreground hover:text-foreground shrink-0"
                      onClick={() =>
                        setPicked((prev) => prev.filter((_, index) => index !== at))
                      }
                    >
                      <X className="size-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={() => picker.current?.click()}
            >
              <FileUp className="size-3.5" />
              파일 고르기
            </Button>
            <p className="text-muted-foreground text-xs">
              {editing
                ? '여기서 고른 파일은 저장할 때 더해집니다. 이미 붙은 파일은 보기 창에서 지웁니다.'
                : '저장하면 문서가 만들어지고 이어서 올라갑니다. 나중에 보기 창에서 더할 수도 있습니다.'}{' '}
              pdf · png · jpg · webp, 장당 100 MB 까지.
            </p>
          </div>

          <ErrorNotice error={error} />

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
              취소
            </Button>
            <Button type="submit" disabled={busy}>
              {busy
                ? picked.length > 0
                  ? '올리는 중…'
                  : '저장 중…'
                : editing
                  ? '저장'
                  : '등록'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/**
 * 시험법 등록.
 *
 * **판(edition)을 이름에 섞지 않는다.** 섞으면 ASTM E8 과 ASTM E8-24 가 별개
 * 값으로 갈리고, 그 둘을 나중에 묶을 방법이 없다.
 */

import { useState } from 'react'
import type { FormEvent } from 'react'

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
import { useResource } from '@/shared/hooks/useResource'
import { AXIS, vocabularyApi } from '@/modules/vocabulary/api'
import { methodApi } from '@/modules/methods/api'

export function NewMethodDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean
  onClose: () => void
  onCreated: () => void
}) {
  const items = useResource(() => vocabularyApi.terms(AXIS.testItem), [])
  const bodies = useResource(() => vocabularyApi.terms(AXIS.standardBody), [])

  const [code, setCode] = useState('')
  const [edition, setEdition] = useState('')
  const [title, setTitle] = useState('')
  const [testItem, setTestItem] = useState('')
  const [bodyTerm, setBodyTerm] = useState('')
  const [summary, setSummary] = useState('')
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await methodApi.create({
        code,
        edition: edition || null,
        title,
        // **목록이다** — 규격 하나가 시험 항목 여럿을 덮는다. 모르면 빈 목록.
        test_item_term_ids: testItem ? [testItem] : [],
        body_term_id: bodyTerm || null,
        summary: summary || null,
        // 비우면 전사 공용 — 공개 규격은 대개 이쪽이고, 시스템 관리자만 만들 수 있다.
        workspace_slug: null,
      })
      setCode('')
      setEdition('')
      setTitle('')
      onCreated()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && !busy && onClose()}>
      <DialogContent>
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>시험법 등록</DialogTitle>
            <DialogDescription>
              요구 조건은 등록한 뒤 상세 화면에서 적습니다.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="code">규격 번호</Label>
              <Input
                id="code"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                placeholder="ASTM E8/E8M"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edition">판</Label>
              <Input
                id="edition"
                value={edition}
                onChange={(event) => setEdition(event.target.value)}
                placeholder="2024"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="title">제목</Label>
            <Input
              id="title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              required
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="method-item">시험 항목</Label>
              <Select value={testItem} onValueChange={setTestItem}>
                <SelectTrigger id="method-item">
                  <SelectValue placeholder="선택" />
                </SelectTrigger>
                <SelectContent>
                  {(items.data ?? []).map((one) => (
                    <SelectItem key={one.id} value={one.id}>
                      {one.value}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="body">제정 기관</Label>
              <Select value={bodyTerm} onValueChange={setBodyTerm}>
                <SelectTrigger id="body">
                  <SelectValue placeholder="선택" />
                </SelectTrigger>
                <SelectContent>
                  {(bodies.data ?? []).map((one) => (
                    <SelectItem key={one.id} value={one.id}>
                      {one.value}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="summary">요약</Label>
            <Textarea
              id="summary"
              value={summary}
              onChange={(event) => setSummary(event.target.value)}
              rows={3}
            />
          </div>

          <ErrorNotice error={error} />

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
              취소
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? '등록 중…' : '등록'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

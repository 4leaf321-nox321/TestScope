/**
 * 신뢰성 시험 등록·수정.
 *
 * 고정 칸은 이름·목적·쓰는 시험 항목 셋이다. **나머지(조건·판정 기준·근거 규격·시료 수 …)는
 * 「항목」 으로 붙인다** — 열을 미리 뚫지 않고 이름을 데이터로 둔 것(attributes 모듈). 정식
 * 항목은 관리자가 정하고, 없는 이름은 초안으로 남아 나중에 정식으로 올라간다.
 *
 * 시험 항목은 **이 부서에 장비가 몇 대인지**를 옆에 달아 고른다. 「열충격」 을 고르는 순간
 * 「우리 부서에 챔버가 0대」 가 보여야, 등록하면서 「돌릴 장비가 없다」 를 안다.
 */

import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { X } from 'lucide-react'

import { ApiError } from '@/shared/api/client'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { SearchablePicker } from '@/shared/components/SearchablePicker'
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
import { Textarea } from '@/shared/components/ui/textarea'
import { useResource } from '@/shared/hooks/useResource'
import {
  AttributeValuesEditor,
  fromValues,
  toPayload,
} from '@/modules/attributes/AttributeValuesEditor'
import type { AttributeRow } from '@/modules/attributes/AttributeValuesEditor'
import { reliabilityApi } from '@/modules/reliability/api'
import type { ReliabilityTest } from '@/modules/reliability/api'
import { testItemCatalogApi } from '@/modules/test_items/api'

export function ReliabilityTestDialog({
  open,
  workspace,
  editing,
  onClose,
  onSaved,
}: {
  open: boolean
  /** 부서 주소. 등록은 이 부서로 들어간다. */
  workspace: string
  /** 있으면 수정, 없으면 등록. */
  editing: ReliabilityTest | null
  onClose: () => void
  onSaved: () => void
}) {
  // 시험 항목 목록 — 이 부서 장비 수를 함께 받는다(카탈로그의 `?workspace=`).
  const catalog = useResource(() => testItemCatalogApi.list(workspace), [workspace])

  const [name, setName] = useState('')
  const [purpose, setPurpose] = useState('')
  const [termIds, setTermIds] = useState<string[]>([])
  const [attributes, setAttributes] = useState<AttributeRow[]>([])
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [busy, setBusy] = useState(false)

  // 열 때마다 대상에 맞춰 채운다 — 수정 창에 지난번 등록 값이 남아 있으면 안 된다.
  useEffect(() => {
    if (!open) return
    setName(editing?.name ?? '')
    setPurpose(editing?.purpose ?? '')
    setTermIds(editing?.test_items.map((one) => one.term_id) ?? [])
    setAttributes(editing ? fromValues(editing.attributes) : [])
    setError(null)
  }, [open, editing])

  const byId = useMemo(
    () => new Map((catalog.data ?? []).map((row) => [row.id, row])),
    [catalog.data],
  )
  const options = useMemo(
    () =>
      (catalog.data ?? [])
        .filter((row) => !termIds.includes(row.id))
        .map((row) => ({
          id: row.id,
          label: row.value,
          detail: row.aliases.length ? row.aliases.join(' · ') : null,
          // **0 을 숨기지 않는다.** 고르는 순간 돌릴 장비가 없다는 것을 알아야 한다.
          badge: row.equipment_count > 0 ? `이 부서 ${row.equipment_count}대` : '이 부서 0대',
        })),
    [catalog.data, termIds],
  )

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const body = {
        name: name.trim(),
        purpose: purpose.trim(),
        test_item_term_ids: termIds,
        attributes: toPayload(attributes),
      }
      if (editing) await reliabilityApi.update(editing.id, body)
      else await reliabilityApi.create(workspace, body)
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
            <DialogTitle>{editing ? '신뢰성 시험 수정' : '신뢰성 시험 등록'}</DialogTitle>
            <DialogDescription>
              이 부서가 제품 개발·검증을 위해 수행하는 시험입니다. 쓰는 시험 항목을 이어 두면
              그 항목이 되는 장비로 연결됩니다.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label htmlFor="rt-name">이름</Label>
            <Input
              id="rt-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="고온고습 1000h"
              required
              maxLength={200}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="rt-purpose">목적</Label>
            <Textarea
              id="rt-purpose"
              value={purpose}
              onChange={(event) => setPurpose(event.target.value)}
              placeholder="무엇을 확인하는 시험인지. 옆 부서 사람이 이름만 보고는 모릅니다."
              rows={3}
              maxLength={4000}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="rt-item">쓰는 시험 항목</Label>
            {termIds.length > 0 && (
              <ul className="flex flex-wrap gap-1">
                {termIds.map((id) => {
                  const row = byId.get(id)
                  const label =
                    row?.value ?? editing?.test_items.find((one) => one.term_id === id)?.value
                  return (
                    <li
                      key={id}
                      className="bg-muted flex items-center gap-1 rounded-md px-2 py-0.5 text-sm"
                    >
                      <span>{label ?? id}</span>
                      {row && (
                        <span className="text-muted-foreground text-xs">
                          {row.equipment_count}대
                        </span>
                      )}
                      <button
                        type="button"
                        aria-label={`${label ?? id} 빼기`}
                        className="text-muted-foreground hover:text-foreground"
                        onClick={() => setTermIds((prev) => prev.filter((one) => one !== id))}
                      >
                        <X className="size-3" />
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
            <SearchablePicker
              id="rt-item"
              options={options}
              value=""
              onChange={(id) => id && setTermIds((prev) => [...prev, id])}
              placeholder="시험 항목 추가"
              detailTitle="시험 항목 전부"
              detailHint="배지의 수는 이 부서 장비 중 그 항목이 되는 대수입니다."
            />
            <p className="text-muted-foreground text-xs">
              비워 둘 수 있습니다 — 장비 없이 하는 시험이거나 아직 안 정한 경우.
            </p>
          </div>

          <div className="space-y-2">
            <Label>속성</Label>
            <AttributeValuesEditor
              target="reliability_test"
              rows={attributes}
              onChange={setAttributes}
            />
          </div>

          <ErrorNotice error={error ?? catalog.error} />

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
              취소
            </Button>
            <Button type="submit" disabled={busy || !name.trim()}>
              {editing ? '저장' : '등록'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

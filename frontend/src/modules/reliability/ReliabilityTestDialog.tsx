/**
 * 신뢰성 시험 등록·수정.
 *
 * 열을 미리 뚫지 않고 이름을 데이터로 둔다(attributes 모듈). 그런데 **사내 시험 카드의
 * 칸들(유형·참조 규격·시험 조건·절차·판정 기준 …)은 새로 만드는 것이 아니라 원래 있는
 * 것**이라, 「속성 추가」 뒤에 두면 사람은 선택 사항으로 읽고 안 채운다 — 그리고 안 채운
 * 조건은 장비 판정에 안 실린다. 그래서 정식 항목은 이름·목적과 **나란히 칸으로** 서고,
 * 그 밖의 것을 적고 싶은 사람만 아래 편집기를 쓴다.
 *
 * 창이 넓은 이유: 칸이 스물이라 좁은 창에서는 스크롤만 하다 끝난다.
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
import {
  StandardAttributeFields,
  fromValues as fromStandardValues,
  toStandardPayload,
} from '@/modules/attributes/StandardAttributeFields'
import type { StandardValue } from '@/modules/attributes/StandardAttributeFields'
import type { AttributeDefinition } from '@/modules/attributes/api'
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
  /** 정식 칸의 값과 그 정의 — 정의는 칸을 그린 쪽이 알려 준다(보낼 때 종류가 필요하다). */
  const [standard, setStandard] = useState<Record<string, StandardValue>>({})
  const [standardDefs, setStandardDefs] = useState<AttributeDefinition[]>([])
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [busy, setBusy] = useState(false)

  // 열 때마다 대상에 맞춰 채운다 — 수정 창에 지난번 등록 값이 남아 있으면 안 된다.
  useEffect(() => {
    if (!open) return
    setName(editing?.name ?? '')
    setPurpose(editing?.purpose ?? '')
    setTermIds(editing?.test_items.map((one) => one.term_id) ?? [])
    // 정식 칸은 위에서 따로 그리므로 **아래 편집기에는 초안만** 남긴다 — 둘 다 그리면
    // 같은 값이 두 번 서고, 저장할 때 뒤의 것이 이긴다.
    setStandard(editing ? fromStandardValues(editing.attributes) : {})
    setAttributes(
      editing
        ? fromValues((editing.attributes ?? []).filter((one) => one.status === 'draft'))
        : [],
    )
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
        attributes: [...toStandardPayload(standardDefs, standard), ...toPayload(attributes)],
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
      <DialogContent className="max-h-[85vh] w-[80vw] overflow-y-auto sm:max-w-[80vw] lg:max-w-6xl">
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>{editing ? '신뢰성 시험 수정' : '신뢰성 시험 등록'}</DialogTitle>
            <DialogDescription>
              이 부서가 제품 개발·검증을 위해 수행하는 시험입니다. 쓰는 시험 항목을 이어 두면
              그 항목이 되는 장비로 연결됩니다.
            </DialogDescription>
          </DialogHeader>

          <fieldset className="rounded-lg border p-4">
            <legend className="px-1.5 text-sm font-medium">이름과 목적</legend>
            <div className="grid gap-x-6 gap-y-4 md:grid-cols-2 xl:grid-cols-3">
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
              <div className="space-y-2 md:col-span-2 xl:col-span-3">
                <Label htmlFor="rt-purpose">목적</Label>
                <Textarea
                  id="rt-purpose"
                  className="max-w-3xl"
                  value={purpose}
                  onChange={(event) => setPurpose(event.target.value)}
                  placeholder="무엇을 확인하는 시험인지. 옆 부서 사람이 이름만 보고는 모릅니다."
                  rows={3}
                  maxLength={4000}
                />
              </div>
            </div>
          </fieldset>

          <fieldset className="max-w-2xl space-y-2 rounded-lg border p-4">
            <legend className="px-1.5 text-sm font-medium">쓰는 시험 항목</legend>
            <Label htmlFor="rt-item" className="sr-only">
              쓰는 시험 항목
            </Label>
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
          </fieldset>

          {/* 사내 시험 카드의 칸들 — 이름·목적과 나란히 선다. */}
          <StandardAttributeFields
            target="reliability_test"
            values={standard}
            onChange={setStandard}
            onLoaded={setStandardDefs}
          />

          <fieldset className="rounded-lg border p-4">
            <legend className="px-1.5 text-sm font-medium">그 밖에 적을 것</legend>
            <p className="text-muted-foreground text-xs">
              위 칸으로 안 잡히는 것만. 여기서 새로 적은 이름은 **초안**으로 남고, 관리자가
              정식으로 올리면 그때부터 모두의 칸이 됩니다.
            </p>
            <AttributeValuesEditor
              target="reliability_test"
              rows={attributes}
              onChange={setAttributes}
            />
          </fieldset>

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

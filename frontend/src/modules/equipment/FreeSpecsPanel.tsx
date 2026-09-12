/**
 * 이 기종만의 사양 — **정의 없이 붙는 값, 그리고 정의로 올리는 단추.**
 *
 * 카탈로그 원본의 사양 키 950종 중 803종이 한 기종에만 나온다. 정의로 다 세우면 「사양
 * 추가」 목록이 1,100줄이 되어 못 쓰고, 버리면 「이 점도계의 스핀들 종류」 가 원문 JSON
 * 안에만 남는다. 그래서 세 자리로 가른다:
 *
 *     정의 있는 사양   여러 기종이 공유 — 비교·대표 사양·검색(위 「사양」 패널)
 *     이 기종만의 사양 한 기종에만 — 값은 들어가고 정의 목록은 안 부푼다(여기)
 *     원문             옮겨 적기 전의 전부 — 근거(아래 「카탈로그 원문」)
 *
 * ## 이름은 지어내지 않는다
 *
 * 반입이 만든 줄은 온톨로지가 아는 이름이면 그것(「제어 방식」), 모르면 원본 키 그대로
 * (`stroke_mm_pk_pk`)다. 기계가 「스트로크 밀리미터 피크피크」 라고 지으면 그것이 진실이
 * 되어 아무도 못 고친다. 사람이 여기서 고친다.
 *
 * ## 여럿이 되면 올린다
 *
 * 같은 원본 키가 다른 기종에도 있으면 「다른 기종 N개도」 라고 말한다 — 여러 기종이
 * 공유하는 값은 비교할 수 있어야 하고, 그것이 정의의 자리다. 「정의로 세우기」 는 이름·
 * 단위·종류를 사람이 적어 누르고, 같은 키의 다른 기종 줄도 함께 옮겨 간다.
 */

import { useState } from 'react'
import { ArrowUpToLine, Pencil, Plus, Trash2 } from 'lucide-react'

import { ApiError } from '@/shared/api/client'
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
import { useResource } from '@/shared/hooks/useResource'
import { vocabularyApi } from '@/modules/vocabulary/api'
import { freeSpecApi } from '@/modules/equipment/api'
import type { FreeSpec } from '@/modules/equipment/api'

const KIND_LABEL: Record<string, string> = {
  range: '범위 (최소~최대)',
  number: '수치 하나',
  text: '글자',
  boolean: '있음/없음',
}

/** 원본 키에서 정의 키 후보를 만든다 — 단위 꼬리만 뗀다. 사람이 고친다. */
function suggestKey(source: string | null, label: string): string {
  const base = (source || label)
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, '_')
    .replace(/^_+|_+$/g, '')
  return base.replace(
    /_(mm|um|nm|kn|n|kgf|degc|k|hz|v|a|w|pa|mpa|kpa|bar|rpm|pct|s|min|l)$/,
    '',
  )
}

/** 범위처럼 보이는 값이면 범위, 숫자면 수치, 아니면 글자 — 첫 제안일 뿐이다. */
function suggestKind(value: string): string {
  if (/^[-+]?\d+(\.\d+)?$/.test(value.trim())) return 'number'
  if (/^[-+]?\d+(\.\d+)?\s*(~|-|–)\s*[-+]?\d+(\.\d+)?$/.test(value.trim())) return 'range'
  return 'text'
}

function PromoteDialog({
  modelId,
  row,
  onClose,
  onDone,
}: {
  modelId: string
  row: FreeSpec
  onClose: () => void
  onDone: (message: string) => void
}) {
  const groups = useResource(() => vocabularyApi.specGroups(), [])
  const [key, setKey] = useState(() => suggestKey(row.source_key, row.label))
  const [label, setLabel] = useState(row.label)
  const [group, setGroup] = useState('')
  const [kind, setKind] = useState(() => suggestKind(row.value_text))
  const [unit, setUnit] = useState(row.unit ?? '')
  const [applySameKey, setApplySameKey] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      const got = await freeSpecApi.promote(modelId, row.id, {
        key,
        label,
        group_id: group,
        kind,
        unit,
        apply_same_key: applySameKey,
      })
      onDone(
        `「${label}」 정의를 세웠습니다. ${got.moved}줄을 옮겼고` +
          (got.left > 0 ? `, 수치로 못 읽은 ${got.left}줄은 그대로 뒀습니다.` : '.'),
      )
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '알 수 없는 오류')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(next) => !next && !busy && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>정의로 세우기</DialogTitle>
          <DialogDescription>
            이 값을 정식 사양 정의로 올립니다. 정의는 이 기종의 분류에 붙고, 앞으로 그 분류의
            모든 기종에서 「사양 추가」 에 뜹니다.{' '}
            <strong>이름과 단위는 사람이 정합니다</strong> — 기계가 지으면 그것이 진실이
            됩니다.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3">
          <div className="grid gap-1">
            <Label htmlFor="promote-label">이름</Label>
            <Input
              id="promote-label"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
            />
          </div>
          <div className="grid gap-1">
            <Label htmlFor="promote-key">키 (코드와 반입이 거는 이름 — 만든 뒤 못 바꿈)</Label>
            <Input
              id="promote-key"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              pattern="[a-z][a-z0-9_]{1,59}"
              className="font-mono"
            />
          </div>
          <div className="grid gap-1 sm:grid-cols-3 sm:gap-2">
            <div className="grid gap-1">
              <Label>그룹</Label>
              <Select value={group} onValueChange={setGroup}>
                <SelectTrigger aria-label="사양 그룹">
                  <SelectValue placeholder="고르기" />
                </SelectTrigger>
                <SelectContent>
                  {(groups.data ?? []).map((one) => (
                    <SelectItem key={one.id} value={one.id}>
                      {one.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1">
              <Label>종류</Label>
              <Select value={kind} onValueChange={setKind}>
                <SelectTrigger aria-label="값 종류">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(KIND_LABEL).map(([value, text]) => (
                    <SelectItem key={value} value={value}>
                      {text}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1">
              <Label htmlFor="promote-unit">단위</Label>
              <Input
                id="promote-unit"
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                placeholder="mm · kN · 없으면 비움"
              />
            </div>
          </div>
          {row.same_key_models > 0 && (
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={applySameKey}
                onChange={(e) => setApplySameKey(e.target.checked)}
              />
              {/* 한 기종만 옮기면 같은 값이 두 자리에 산다. */}
              같은 원본 키를 가진 다른 기종 {row.same_key_models}개의 값도 함께 옮기기
            </label>
          )}
          <p className="text-muted-foreground text-xs">
            지금 값 「{row.value_text}」 를 {KIND_LABEL[kind]} 로 읽습니다. 못 읽으면(「약
            300」) 그 줄은 그대로 남습니다 — 지어서 옮기지 않습니다.
          </p>
          {error && <p className="text-destructive text-sm">{error}</p>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy}>
            취소
          </Button>
          <Button onClick={submit} disabled={busy || !group || !key || !label}>
            정의로 세우기
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function FreeSpecsPanel({
  modelId,
  rows,
  canEdit,
  onChanged,
}: {
  modelId: string
  rows: FreeSpec[]
  canEdit: boolean
  /** 값이 정의로 옮겨 가면 위 사양 패널도 다시 읽어야 한다. */
  onChanged: () => void
}) {
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [promoting, setPromoting] = useState<FreeSpec | null>(null)
  const [adding, setAdding] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function run(work: () => Promise<unknown>) {
    setError(null)
    try {
      await work()
      onChanged()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '알 수 없는 오류')
    }
  }

  function startEdit(row: FreeSpec) {
    setEditing(row.id)
    setAdding(false)
    setDraft({ label: row.label, value_text: row.value_text, unit: row.unit ?? '' })
  }

  const form = (onSave: () => void, onCancel: () => void) => (
    <div className="flex flex-wrap items-center gap-2">
      <Input
        value={draft.label ?? ''}
        onChange={(e) => setDraft({ ...draft, label: e.target.value })}
        placeholder="이름"
        aria-label="사양 이름"
        className="w-48"
      />
      <Input
        value={draft.value_text ?? ''}
        onChange={(e) => setDraft({ ...draft, value_text: e.target.value })}
        placeholder="값 — 원문 그대로"
        aria-label="사양 값"
        className="w-64"
      />
      <Input
        value={draft.unit ?? ''}
        onChange={(e) => setDraft({ ...draft, unit: e.target.value })}
        placeholder="단위"
        aria-label="사양 단위"
        className="w-24"
      />
      <Button
        size="sm"
        onClick={onSave}
        disabled={!draft.label?.trim() || !draft.value_text?.trim()}
      >
        저장
      </Button>
      <Button size="sm" variant="ghost" onClick={onCancel}>
        취소
      </Button>
    </div>
  )

  if (rows.length === 0 && !canEdit) return null

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-base font-semibold">이 기종만의 사양</h2>
        <p className="text-muted-foreground mt-1 text-sm">
          정의 없이 이 기종에만 붙은 값입니다. 카탈로그 키 950종 중 803종이 한 기종에만
          나오는데, 전부 정의로 세우면 「사양 추가」 목록이 못 쓰게 되고 버리면 사라지므로 여기
          둡니다. <strong>다른 기종에도 같은 값이 있으면 정의로 세우세요</strong> — 그때부터
          비교가 됩니다.
        </p>
      </div>

      {message && <p className="text-sm text-emerald-700">{message}</p>}
      {error && <p className="text-destructive text-sm">{error}</p>}

      {rows.length === 0 ? (
        <p className="text-muted-foreground text-sm">아직 없습니다.</p>
      ) : (
        <ul className="divide-y rounded-md border text-sm">
          {rows.map((row) => (
            <li key={row.id} className="flex flex-wrap items-start gap-2 px-3 py-2">
              {editing === row.id ? (
                form(
                  () =>
                    void run(async () => {
                      await freeSpecApi.update(modelId, row.id, {
                        label: draft.label,
                        value_text: draft.value_text,
                        unit: draft.unit || null,
                        note: row.note,
                        source_id: row.source_id,
                        source_page: row.source_page,
                      })
                      setEditing(null)
                    }),
                  () => setEditing(null),
                )
              ) : (
                <>
                  <span className="w-56 shrink-0">
                    <span className={row.source_key === row.label ? 'font-mono text-xs' : ''}>
                      {row.label}
                    </span>
                    {/* 원본 키 그대로인 이름 — 아직 사람이 안 읽은 것이라 그렇게 보인다. */}
                    {row.source_key && row.source_key !== row.label && (
                      <span className="text-muted-foreground ml-1 font-mono text-xs">
                        {row.source_key}
                      </span>
                    )}
                  </span>
                  <span className="min-w-0 flex-1 break-words">
                    {row.value_text}
                    {row.unit && <span className="text-muted-foreground"> {row.unit}</span>}
                    {row.note && (
                      <span className="text-muted-foreground block text-xs">{row.note}</span>
                    )}
                  </span>
                  {row.same_key_models > 0 && (
                    <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-xs text-amber-700">
                      다른 기종 {row.same_key_models}개도
                    </span>
                  )}
                  {canEdit && (
                    <span className="flex shrink-0 gap-0.5">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 px-1.5"
                        aria-label={`${row.label} 정의로 세우기`}
                        onClick={() => setPromoting(row)}
                      >
                        <ArrowUpToLine className="size-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 px-1.5"
                        aria-label={`${row.label} 고치기`}
                        onClick={() => startEdit(row)}
                      >
                        <Pencil className="size-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 px-1.5"
                        aria-label={`${row.label} 지우기`}
                        onClick={() => void run(() => freeSpecApi.remove(modelId, row.id))}
                      >
                        <Trash2 className="size-3.5" />
                      </Button>
                    </span>
                  )}
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      {canEdit &&
        (adding ? (
          form(
            () =>
              void run(async () => {
                await freeSpecApi.add(modelId, {
                  label: draft.label,
                  value_text: draft.value_text,
                  unit: draft.unit || null,
                })
                setAdding(false)
                setDraft({})
              }),
            () => setAdding(false),
          )
        ) : (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setAdding(true)
              setEditing(null)
              setDraft({})
            }}
          >
            <Plus className="size-4" />이 기종만의 사양 추가
          </Button>
        ))}

      {promoting && (
        <PromoteDialog
          modelId={modelId}
          row={promoting}
          onClose={() => setPromoting(null)}
          onDone={(text) => {
            setPromoting(null)
            setMessage(text)
            onChanged()
          }}
        />
      )}
    </section>
  )
}

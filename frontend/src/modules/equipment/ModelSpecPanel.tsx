/**
 * 모델 사양표 — 정의는 통제하고, 값은 자유롭게(ADR 0005).
 *
 * ## 두 목록을 겹쳐 그린다
 *
 * `sheet` 는 **적힌 값**을, `specDefinitions` 는 **적을 수 있는 칸**을 준다. 빈
 * 칸까지 사양표에 실으면 한 모델을 열 때마다 수백 줄이 오간다.
 *
 * ## 분류 밖 사양도 지우지 않는다
 *
 * 정의에 붙은 분류가 이 모델과 안 맞아도(`applies=false`) 값은 그대로 보여 주고
 * 표만 단다. 분류를 나중에 고쳤다고 이미 적은 사양이 사라지면, 사람은 그것이
 * 지워졌다고 믿는다.
 */

import { useState } from 'react'
import { Trash2 } from 'lucide-react'

import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import { useResource } from '@/shared/hooks/useResource'
import { vocabularyApi } from '@/modules/vocabulary/api'
import type { SpecDefinition } from '@/modules/vocabulary/api'
import { specApi } from '@/modules/equipment/api'
import type { ModelSpecValue } from '@/modules/equipment/api'

/** 종류마다 읽는 칸이 다르다. 한 칸에 다 담았으면 여기가 필요 없었을 것이다. */
function shownValue(item: ModelSpecValue): string {
  const unit = item.display_unit || item.si_unit
  const withUnit = (value: number) => `${value}${unit ? ` ${unit}` : ''}`
  switch (item.kind) {
    case 'range': {
      // **비운 쪽은 "제한 없음" 이다.** 0 으로 적으면 하한이 0 인 것과 구별되지 않는다.
      const low = item.num_min === null ? '제한 없음' : withUnit(item.num_min)
      const high = item.num_max === null ? '제한 없음' : withUnit(item.num_max)
      return `${low} ~ ${high}`
    }
    case 'boolean':
      return item.bool_value ? '있음' : '없음'
    case 'number':
      return item.num_value === null ? '—' : withUnit(item.num_value)
    default:
      return item.text_value ?? '—'
  }
}

/** 빈 문자열은 안 보낸 것과 같다 — 숫자 칸의 0 과 구별해야 한다. */
function numberOrNull(raw: string | undefined): number | null {
  return raw === undefined || raw.trim() === '' ? null : Number(raw)
}

/** 종류에 맞는 칸만 채워 보낸다. 나머지는 서버가 비운다. */
function toBody(definition: SpecDefinition, draft: Record<string, string>) {
  const isText = definition.kind === 'choice' || definition.kind === 'text'
  return {
    definition_id: definition.id,
    num_value: definition.kind === 'number' ? numberOrNull(draft.num_value) : null,
    num_min: definition.kind === 'range' ? numberOrNull(draft.num_min) : null,
    num_max: definition.kind === 'range' ? numberOrNull(draft.num_max) : null,
    text_value: isText ? (draft.text_value?.trim() ?? '') : null,
    bool_value: definition.kind === 'boolean' ? draft.bool_value === 'yes' : null,
    note: draft.note?.trim() ? draft.note.trim() : null,
    source_id: draft.source_id ? draft.source_id : null,
    source_page: numberOrNull(draft.source_page),
  }
}

/** 고른 사양의 종류에 맞는 입력 칸만 띄운다. */
function ValueFields({
  definition,
  draft,
  setDraft,
}: {
  definition: SpecDefinition
  draft: Record<string, string>
  setDraft: (next: Record<string, string>) => void
}) {
  const unit = definition.display_unit || definition.si_unit
  const set = (field: string, value: string) => setDraft({ ...draft, [field]: value })

  if (definition.kind === 'range') {
    return (
      <>
        {/* **비워 두는 것이 "제한 없음" 이다.** 0 이 아니다. */}
        <Input
          type="number"
          value={draft.num_min ?? ''}
          onChange={(event) => set('num_min', event.target.value)}
          placeholder={`최소${unit ? ` (${unit})` : ''} — 비우면 제한 없음`}
          className="w-56"
        />
        <Input
          type="number"
          value={draft.num_max ?? ''}
          onChange={(event) => set('num_max', event.target.value)}
          placeholder={`최대${unit ? ` (${unit})` : ''} — 비우면 제한 없음`}
          className="w-56"
        />
      </>
    )
  }
  if (definition.kind === 'number') {
    return (
      <Input
        type="number"
        value={draft.num_value ?? ''}
        onChange={(event) => set('num_value', event.target.value)}
        placeholder={unit ? `값 (${unit})` : '값'}
        className="w-44"
      />
    )
  }
  if (definition.kind === 'boolean') {
    return (
      <Select
        value={draft.bool_value ?? ''}
        onValueChange={(value) => set('bool_value', value)}
      >
        <SelectTrigger className="w-32">
          <SelectValue placeholder="있음/없음" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="yes">있음</SelectItem>
          <SelectItem value="no">없음</SelectItem>
        </SelectContent>
      </Select>
    )
  }
  if (definition.kind === 'choice' && definition.choices.length > 0) {
    return (
      <Select
        value={draft.text_value ?? ''}
        onValueChange={(value) => set('text_value', value)}
      >
        <SelectTrigger className="w-56">
          <SelectValue placeholder="고르기" />
        </SelectTrigger>
        <SelectContent>
          {definition.choices.map((choice) => (
            <SelectItem key={choice} value={choice}>
              {choice}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    )
  }
  // 정확도 서술처럼 **수치로 못 담는 문장**이 여기 온다. 원문을 그대로 받는다.
  return (
    <Input
      value={draft.text_value ?? ''}
      onChange={(event) => set('text_value', event.target.value)}
      placeholder="원문 그대로 적습니다"
      className="w-96"
    />
  )
}

export function ModelSpecPanel({
  modelId,
  categoryTermId,
  canEdit,
  onSaved,
}: {
  modelId: string
  categoryTermId: string | null
  canEdit: boolean
  /** 사양이 역량으로 반영될 수 있어서 **위쪽도 다시 읽어야 한다.** */
  onSaved: () => void
}) {
  const sheet = useResource(() => specApi.sheet(modelId), [modelId])
  const definitions = useResource(
    () => vocabularyApi.specDefinitions({ categoryTermId }),
    [modelId, categoryTermId],
  )
  const sources = useResource(() => specApi.sources(), [])

  const [pick, setPick] = useState('')
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const groups = sheet.data?.groups ?? []
  const filled = new Set(
    groups.flatMap((group) => group.items.map((item) => item.definition_id)),
  )
  // 이미 적은 칸은 목록에서 뺀다 — 같은 사양이 두 줄이면 어느 쪽이 맞는지 알 수 없다.
  const available = (definitions.data ?? []).filter((one) => !filled.has(one.id))
  const chosen = available.find((one) => one.id === pick) ?? null

  async function save() {
    if (!chosen) return
    setError(null)
    setMessage(null)
    try {
      const result = await specApi.put(modelId, toBody(chosen, draft))
      // **둘을 말해 준다.** 이 값이 검색에 쓰이는지, 이미 등록된 장비는 어떻게
      // 되는지 — 둘 다 모르면 사람은 바뀌었다고 믿고, 그 믿음은 검색 결과가
      // 어긋난 날에야 깨진다.
      const parts = [`${chosen.label} 저장.`]
      if (result.search_axis) {
        parts.push(
          `「${result.search_axis}」 검색축이라, 앞으로 이 기종으로 등록하는 장비의 역량 조건이 됩니다.`,
        )
      }
      if (result.existing_units > 0) {
        parts.push(
          `이미 등록된 ${result.existing_units}대에는 반영되지 않습니다 — 개체의 값은 개체가 갖습니다.`,
        )
      }
      setMessage(parts.join(' '))
      setPick('')
      setDraft({})
      sheet.reload()
      onSaved()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '알 수 없는 오류')
    }
  }

  async function drop(definitionId: string) {
    setError(null)
    setMessage(null)
    try {
      await specApi.remove(modelId, definitionId)
      sheet.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '알 수 없는 오류')
    }
  }

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-base font-semibold">사양</h2>
        <p className="text-muted-foreground mt-1 text-sm">
          제조사 카탈로그의 값입니다. <strong>검색축에 이어진 사양</strong>(하중 용량·시험
          온도 등)은 이 기종으로 보유 장비를 등록할 때 역량 조건이 됩니다 — 같은 숫자를
          두 번 적지 않기 위해서입니다.
        </p>
      </div>

      {message && <p className="text-sm text-emerald-700">{message}</p>}
      {error && <p className="text-destructive text-sm">{error}</p>}

      {groups.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          아직 적힌 사양이 없습니다. 아래에서 칸을 골라 채우세요.
        </p>
      ) : (
        <div className="space-y-4">
          {groups.map((group) => (
            <div key={group.group_id} className="rounded-md border p-4">
              <h3 className="text-sm font-medium">{group.label}</h3>
              <dl className="mt-2 space-y-1 text-sm">
                {group.items.map((item) => (
                  <div key={item.id} className="flex flex-wrap items-baseline gap-2">
                    <dt className="text-muted-foreground w-40 shrink-0">
                      {item.label}
                      {/* 분류가 안 맞는 사양. **지우지 않고 표만 단다.** */}
                      {!item.applies && (
                        <span className="text-muted-foreground/70 ml-1 text-xs">
                          (이 분류 밖)
                        </span>
                      )}
                    </dt>
                    <dd className="flex flex-wrap items-baseline gap-2">
                      <span>{shownValue(item)}</span>
                      {item.note && (
                        <span className="text-muted-foreground text-xs">{item.note}</span>
                      )}
                      {item.source_path && (
                        <span className="text-muted-foreground font-mono text-xs">
                          {item.source_path}
                          {item.source_page ? ` p.${item.source_page}` : ''}
                        </span>
                      )}
                      {canEdit && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => drop(item.definition_id)}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      )}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          ))}
        </div>
      )}

      {canEdit && (
        <div className="space-y-2 border-t pt-3">
          <div className="flex flex-wrap items-center gap-2">
            <Select
              value={pick}
              onValueChange={(value) => {
                setPick(value)
                setDraft({})
              }}
            >
              <SelectTrigger className="w-72">
                <SelectValue placeholder="사양 추가" />
              </SelectTrigger>
              <SelectContent>
                {available.map((one) => (
                  <SelectItem key={one.id} value={one.id}>
                    {one.group_label} · {one.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {chosen && <ValueFields definition={chosen} draft={draft} setDraft={setDraft} />}
            {chosen && <Button onClick={save}>저장</Button>}
          </div>

          {chosen && (
            <>
              {chosen.help && <p className="text-muted-foreground text-xs">{chosen.help}</p>}
              <div className="flex flex-wrap items-center gap-2">
                <Input
                  value={draft.note ?? ''}
                  onChange={(event) => setDraft({ ...draft, note: event.target.value })}
                  placeholder="비고 — 「챔버 장착 시」 처럼 값이 언제 성립하는지"
                  className="w-96"
                />
                {/* **어디서 나온 값이냐에 답하는 자리.** 반년 뒤 물을 사람은 반드시 있다. */}
                <Select
                  value={draft.source_id ?? ''}
                  onValueChange={(value) => setDraft({ ...draft, source_id: value })}
                >
                  <SelectTrigger className="w-72">
                    <SelectValue placeholder="출처 문서 (선택)" />
                  </SelectTrigger>
                  <SelectContent>
                    {(sources.data?.items ?? []).map((one) => (
                      <SelectItem key={one.id} value={one.id}>
                        {one.title || one.path}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input
                  type="number"
                  value={draft.source_page ?? ''}
                  onChange={(event) =>
                    setDraft({ ...draft, source_page: event.target.value })
                  }
                  placeholder="쪽"
                  className="w-20"
                />
              </div>
            </>
          )}
        </div>
      )}
    </section>
  )
}

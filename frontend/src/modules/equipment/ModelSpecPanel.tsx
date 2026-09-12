/**
 * 모델 사양표 — 정의는 통제하고, 값은 자유롭게(ADR 0005).
 *
 * ## 두 목록을 겹쳐 그린다
 *
 * `sheet` 는 **적힌 값**을, `specDefinitions` 는 **적을 수 있는 칸**을 준다. 빈
 * 칸까지 사양표에 실으면 한 모델을 열 때마다 수백 줄이 오간다.
 *
 * ## 원문 단위 그대로 친다
 *
 * 카탈로그는 「4,000 cP」 라고 적혀 있는데 정의는 Pa·s 다. 사람이 머리로 0.001 을 곱하던
 * 자리가 **자릿수를 틀리는 자리**라, 값 칸이 단위째 받아 바꿔 넣고 무엇을 무엇으로 바꿨는지
 * 적는다(`shared/units`). 모르는 단위는 거절한다 — 조용히 숫자만 취하면 천 배 틀린다.
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
import { SearchablePicker } from '@/shared/components/SearchablePicker'
import { vocabularyApi } from '@/modules/vocabulary/api'
import type { SpecDefinition } from '@/modules/vocabulary/api'
import { specApi } from '@/modules/equipment/api'
import { convertValue, isError } from '@/shared/units'
import { shownSpecValue } from '@/modules/equipment/specValue'

/** 빈 문자열은 안 보낸 것과 같다 — 숫자 칸의 0 과 구별해야 한다.
 *
 *  단위가 붙어 있으면(「4000 cP」) 그 칸의 단위로 바꾼다. 못 바꾸는 것은 저장 전에
 *  막히므로(`problem`) 여기서는 `null` 로 둔다 — 숫자만 떼어 담으면 천 배 틀린다. */
function numberOrNull(raw: string | undefined, unit: string): number | null {
  const got = convertValue(raw ?? '', unit)
  if (got === null || isError(got)) return null
  return got.value
}

/** 종류에 맞는 칸만 채워 보낸다. 나머지는 서버가 비운다. */
function toBody(definition: SpecDefinition, draft: Record<string, string>) {
  const isText = definition.kind === 'choice' || definition.kind === 'text'
  const unit = definition.display_unit || definition.si_unit
  return {
    definition_id: definition.id,
    num_value: definition.kind === 'number' ? numberOrNull(draft.num_value, unit) : null,
    num_min: definition.kind === 'range' ? numberOrNull(draft.num_min, unit) : null,
    num_max: definition.kind === 'range' ? numberOrNull(draft.num_max, unit) : null,
    text_value: isText ? (draft.text_value?.trim() ?? '') : null,
    bool_value: definition.kind === 'boolean' ? draft.bool_value === 'yes' : null,
    note: draft.note?.trim() ? draft.note.trim() : null,
    requires_accessory: draft.requires_accessory === 'yes',
    source_id: draft.source_id ? draft.source_id : null,
    source_page: numberOrNull(draft.source_page, ''),
  }
}

/** 숫자 칸 하나 — **원문 단위를 그대로 받는다.**
 *
 *  바꿨으면 무엇을 무엇으로 바꿨는지 적는다(사람이 검산할 수 있어야 한다). 모르는 단위면
 *  붉게 말하고, 저장은 부르는 쪽이 막는다. */
function NumberField({
  value,
  onChange,
  unit,
  placeholder,
  className,
}: {
  value: string
  onChange: (next: string) => void
  unit: string
  placeholder: string
  className?: string
}) {
  const got = convertValue(value, unit)
  return (
    <div className={className}>
      {/* `type="number"` 가 아니다 — 그러면 「4000 cP」 를 아예 못 친다. */}
      <Input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        inputMode="decimal"
      />
      {got !== null && isError(got) && (
        <p className="text-destructive mt-1 text-xs">{got.error}</p>
      )}
      {got !== null && !isError(got) && got.note && (
        <p className="mt-1 text-xs text-emerald-700">{got.note}</p>
      )}
    </div>
  )
}

/** 그 칸의 값이 저장할 수 있는 모양인가. 못 바꾸는 단위가 하나라도 있으면 막는다. */
function fieldProblem(
  definition: SpecDefinition,
  draft: Record<string, string>,
): string | null {
  const unit = definition.display_unit || definition.si_unit
  const fields =
    definition.kind === 'range'
      ? ['num_min', 'num_max']
      : definition.kind === 'number'
        ? ['num_value']
        : []
  for (const field of fields) {
    const got = convertValue(draft[field] ?? '', unit)
    if (got !== null && isError(got)) return got.error
  }
  return null
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
        <NumberField
          value={draft.num_min ?? ''}
          onChange={(value) => set('num_min', value)}
          unit={unit}
          placeholder={`최소${unit ? ` (${unit})` : ''} — 비우면 제한 없음`}
          className="w-56"
        />
        <NumberField
          value={draft.num_max ?? ''}
          onChange={(value) => set('num_max', value)}
          unit={unit}
          placeholder={`최대${unit ? ` (${unit})` : ''} — 비우면 제한 없음`}
          className="w-56"
        />
      </>
    )
  }
  if (definition.kind === 'number') {
    return (
      <NumberField
        value={draft.num_value ?? ''}
        onChange={(value) => set('num_value', value)}
        unit={unit}
        placeholder={unit ? `값 (${unit}) — 「4000 cP」 처럼 원문 단위로 쳐도 됩니다` : '값'}
        className="w-64"
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
  /** 사양이 시험 항목으로 반영될 수 있어서 **위쪽도 다시 읽어야 한다.** */
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
          `「${result.search_axis}」 검색 조건이라, 앞으로 이 기종으로 등록하는 장비의 시험 조건이 됩니다.`,
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
          제조사 카탈로그의 값입니다. <strong>검색 조건에 이어진 사양</strong>(하중 용량·시험
          온도 등)은 이 기종으로 보유 장비를 등록할 때 시험 조건이 됩니다 — 같은 숫자를 두 번
          적지 않기 위해서입니다.
        </p>
      </div>

      {message && <p className="text-sm text-emerald-700">{message}</p>}
      {error && <p className="text-destructive text-sm">{error}</p>}

      {groups.length === 0 ? (
        <p className="text-sm text-amber-700">
          {/* **「모름」 의 출처가 여기다.** 사양이 없으면 검색이 이 기종을 판정하지 못하고,
              사람은 되는지 안 되는지를 못 본다 — 891 중 224 가 이 상태다. */}
          <strong>아직 적힌 사양이 없습니다.</strong> 그래서 검색은 이 기종을 「모름」 으로
          답합니다. 아래에서 칸을 골라, 이 쪽 맨 아래 <strong>「카탈로그 원문」</strong> 에
          적힌 값을 한 칸씩 옮겨 적으세요.
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
                      <span>{shownSpecValue(item)}</span>
                      {item.axis_unit_mismatch && (
                        // 검색축에 이었는데 단위를 못 맞춘다 — 조용히 빠지면 「검색축인데 왜
                        // 모름이라 하지」 가 된다.
                        <span
                          className="text-destructive rounded bg-red-500/10 px-1.5 py-0.5 text-xs"
                          title="이 사양은 검색 조건에 이어져 있지만 단위를 조건의 단위로 못 바꿔 검색에 안 실립니다. 「장비 사양 정의」 에서 단위나 축을 고치세요."
                        >
                          단위 안 맞음 · 검색에 안 실림
                        </span>
                      )}
                      {item.requires_accessory && (
                        <span
                          className="rounded bg-amber-500/10 px-1.5 py-0.5 text-xs text-amber-700"
                          title="옵션 부속(챔버·노)이 있어야 나오는 값 — 이 기종으로 등록한 장비의 조건에 그대로 따라가고, 검색이 「부속 있으면」 으로 답합니다."
                        >
                          부속 필요
                        </span>
                      )}
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
            {/* **드롭다운으로는 못 찾는다.** 사양 정의가 209종이고, 이 기종의 분류에
                걸리는 것만 해도 여든 가까이 된다. 「상세」 는 무엇이 있는지 모를 때
                여는 자리다 — 치는 것만 두면 무엇을 칠지 모르는 사람이 막힌다. */}
            <SearchablePicker
              className="w-80"
              options={available.map((one) => ({
                id: one.id,
                label: one.label,
                detail: [one.group_label, one.display_unit || one.si_unit]
                  .filter(Boolean)
                  .join(' · '),
                // 검색 조건에 이어진 사양은 값이 곧 시험 조건이 된다 — 고르기 전에
                // 그 사실이 보여야 한다.
                badge: one.condition_key_id ? '검색 조건' : null,
              }))}
              value={pick}
              onChange={(value) => {
                setPick(value)
                setDraft({})
              }}
              placeholder="사양 추가"
              searchPlaceholder="하중 · 온도 · 무게 …"
              detailTitle="적을 수 있는 사양"
              detailHint="이 기종의 분류에 붙는 사양과 공통 사양입니다. 「검색 조건」 이 붙은 것은 값이 이 기종으로 등록하는 장비의 시험 조건이 됩니다."
            />
            {chosen && <ValueFields definition={chosen} draft={draft} setDraft={setDraft} />}
            {/* 못 바꾸는 단위가 남아 있으면 저장을 막는다 — 그대로 저장하면 숫자만
                떼어 담기고, 그 값은 천 배 틀린 채로 검색에 쓰인다. */}
            {chosen && (
              <Button onClick={save} disabled={fieldProblem(chosen, draft) !== null}>
                저장
              </Button>
            )}
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
                {/* 비고에 「챔버 장착 시」 라고 적어도 검색은 글자를 못 읽는다 — 표시로 둬야
                    판정이 갈린다. */}
                <label className="text-muted-foreground flex items-center gap-1.5 text-sm">
                  <input
                    type="checkbox"
                    checked={draft.requires_accessory === 'yes'}
                    onChange={(event) =>
                      setDraft({
                        ...draft,
                        requires_accessory: event.target.checked ? 'yes' : '',
                      })
                    }
                  />
                  옵션 부속이 있어야 나오는 값
                </label>
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
                  onChange={(event) => setDraft({ ...draft, source_page: event.target.value })}
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

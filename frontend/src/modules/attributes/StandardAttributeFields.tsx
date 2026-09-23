/**
 * 정식 속성을 **그냥 칸으로** 그린다 — 「속성」 이라는 묶음 없이, 이름·목적과 나란히.
 *
 * 속성 편집기(`AttributeValuesEditor`)는 「없는 칸을 새로 만들며 적는」 자리다. 그런데 사내
 * 시험 카드의 칸들(유형·참조 규격·시험 절차 …)은 **새로 만드는 것이 아니라 원래 있는 것**
 * 이다. 그것을 「속성 추가」 뒤에 두면 사람은 그 칸이 선택 사항이라고 읽고 안 채운다 —
 * 그리고 안 채운 조건은 장비 판정에 안 실린다.
 *
 * 그래서 정식(standard) 항목은 여기서 폼의 칸으로 서고, 그 밖의 것을 적고 싶은 사람만
 * 아래 편집기를 쓴다.
 */

import { useEffect, useMemo, useState } from 'react'
import { X } from 'lucide-react'

import { SearchablePicker } from '@/shared/components/SearchablePicker'
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
import { attributeApi } from '@/modules/attributes/api'
import type {
  AttributeDefinition,
  AttributeTarget,
  AttributeValue,
  AttributeValueIn,
} from '@/modules/attributes/api'
import type { MatrixRow, Pair } from '@/modules/attributes/kinds'
import { MatrixEditor, PairsEditor } from '@/modules/attributes/PairsEditor'
import { methodApi } from '@/modules/methods/api'
import { vocabularyApi } from '@/modules/vocabulary/api'

/** 칸 하나의 지금 값. 종류에 따라 쓰는 자리가 다르다. */
export interface StandardValue {
  numValue: number | null
  numMin: number | null
  numMax: number | null
  textValue: string
  termId: string | null
  methodId: string | null
  pairs: Pair[]
  matrix: MatrixRow[]
  /** 조건 줄의 비고 — 숫자로 못 적는 것(「상온」·「규격에 따름」). */
  note: string
}

function empty(): StandardValue {
  return {
    numValue: null,
    numMin: null,
    numMax: null,
    textValue: '',
    termId: null,
    methodId: null,
    pairs: [],
    matrix: [],
    note: '',
  }
}

/** 서버가 준 값 → 편집 상태. 정의 id 로 묶는다. */
export function fromValues(rows: AttributeValue[] | undefined): Record<string, StandardValue> {
  const out: Record<string, StandardValue> = {}
  for (const row of rows ?? []) {
    const json = row.json_value as unknown
    out[row.definition_id] = {
      numValue: row.num_value ?? null,
      numMin: row.num_min ?? null,
      numMax: row.num_max ?? null,
      textValue: row.text_value ?? '',
      termId: row.term_id ?? null,
      methodId: row.method_id ?? null,
      pairs: Array.isArray(json) && row.kind === 'pairs' ? (json as Pair[]) : [],
      matrix: Array.isArray(json) && row.kind === 'matrix' ? (json as MatrixRow[]) : [],
      note: row.note ?? '',
    }
  }
  return out
}

/** 채워진 칸만 서버로. **빈 칸은 보내지 않는다** — 빈 값은 저장이 아니라 지우기다. */
export function toStandardPayload(
  definitions: AttributeDefinition[],
  values: Record<string, StandardValue>,
): AttributeValueIn[] {
  const out: AttributeValueIn[] = []
  for (const definition of definitions) {
    const value = values[definition.id]
    if (!value) continue
    const base = { definition_id: definition.id, new_kind: definition.kind }
    if (definition.kind === 'number' && value.numValue !== null) {
      out.push({ ...base, num_value: value.numValue, unit: definition.unit })
    } else if (
      (definition.kind === 'condition' || definition.kind === 'range') &&
      // **숫자가 없어도 비고가 있으면 보낸다** — 「상온」 처럼 숫자로 못 적는 조건이 있다.
      (value.numMin !== null || value.numMax !== null || value.note.trim())
    ) {
      out.push({
        ...base,
        num_min: value.numMin,
        num_max: value.numMax,
        unit: definition.unit,
        note: value.note.trim() || null,
      })
    } else if (definition.kind === 'term' && value.termId) {
      out.push({ ...base, term_id: value.termId })
    } else if (definition.kind === 'method' && value.methodId) {
      out.push({ ...base, method_id: value.methodId })
    } else if (definition.kind === 'pairs') {
      const rows = value.pairs.filter((one) => one.label.trim() && one.value !== null)
      if (rows.length > 0) out.push({ ...base, json_value: rows })
    } else if (definition.kind === 'matrix') {
      const rows = value.matrix
        .map((row) => ({
          label: row.label.trim(),
          entries: row.entries.filter((one) => one.label.trim() && one.value !== null),
        }))
        .filter((row) => row.label && row.entries.length > 0)
      if (rows.length > 0) out.push({ ...base, json_value: rows })
    } else if (value.textValue.trim()) {
      out.push({ ...base, text_value: value.textValue.trim() })
    }
  }
  return out
}

/** 글이 길어질 칸 — 절차·방법처럼 여러 줄로 적는 것. */
const LONG = new Set([
  'reliability_procedure',
  'reliability_method',
  'reliability_criteria',
  'reliability_caution',
  'reliability_other_conditions',
  'reliability_target',
  'reliability_equipment_note',
])

/**
 * 칸을 **갈래로 묶는다.** 스물을 한 줄로 세우면 사람은 스크롤만 하다 끝나고, 무엇이 무엇과
 * 한 묶음인지도 안 보인다. 묶음은 카드로 서서 경계가 눈에 띈다.
 *
 * 여기 없는 key 는 마지막 묶음으로 간다 — 다른 대상(보유 장비·계열)이나 나중에 는 칸도
 * 자리를 잃지 않는다.
 */
const SECTIONS: {
  title: string
  hint?: string
  keys: string[]
  /** 참이면 조건 종류(`kind="condition"`) 칸을 전부 이 갈래가 가져간다. */
  conditions?: boolean
}[] = [
  {
    title: '무엇을 왜',
    keys: ['reliability_type', 'reliability_category', 'reliability_product_group'],
  },
  {
    title: '근거',
    hint: '공인 규격도 사내 규격서도 **목록에서 고릅니다** — 글자로 적으면 같은 문서가 판마다 다른 값이 되어 「이 규격서를 쓰는 시험」 을 못 묶습니다.',
    keys: [
      'reliability_reference_method',
      'reliability_spec_document',
      'reliability_document_type',
    ],
  },
  {
    // 조건 칸은 **축마다 하나**라 열하나가 된다. 키로 적지 않고 종류로 모은다 —
    // 축이 늘면 칸도 따라 늘어야 하고, 그때 이 표를 고치는 것을 누가 잊는다.
    title: '시험 조건',
    hint: '적은 수치가 그대로 「이 시험 돌릴 수 있는 장비」 판정이 됩니다. 한쪽만 적으면 「이상」·「이하」 이고, 숫자로 못 적는 것은 비고에 적습니다(그 줄은 판정에 안 쓰입니다).',
    keys: ['reliability_other_conditions'],
    conditions: true,
  },
  {
    title: '대상과 수량',
    keys: [
      'reliability_target',
      'reliability_sample_count',
      'reliability_equipment_note',
      'reliability_grade_counts',
      'reliability_stage_counts',
      'reliability_spec_matrix',
    ],
  },
  {
    title: '방법과 판정',
    keys: [
      'reliability_procedure',
      'reliability_method',
      'reliability_criteria',
      'reliability_caution',
    ],
  },
]

/** 한 줄을 통째로 쓰는 종류 — 글상자와 짝 목록은 좁은 칸에 못 담는다. */
function isWide(definition: AttributeDefinition): boolean {
  return (
    definition.kind === 'pairs' || definition.kind === 'matrix' || LONG.has(definition.key)
  )
}

export function StandardAttributeFields({
  target,
  values,
  onChange,
  onLoaded,
}: {
  target: AttributeTarget
  values: Record<string, StandardValue>
  onChange: (next: Record<string, StandardValue>) => void
  onLoaded?: (definitions: AttributeDefinition[]) => void
}) {
  const listed = useResource(() => attributeApi.definitions(target), [target])
  const definitions = useMemo(
    () => (listed.data ?? []).filter((one) => one.status === 'standard' && one.is_active),
    [listed.data],
  )

  useEffect(() => {
    if (definitions.length > 0) onLoaded?.(definitions)
  }, [definitions, onLoaded])

  const set = (id: string, patch: Partial<StandardValue>) =>
    onChange({ ...values, [id]: { ...(values[id] ?? empty()), ...patch } })

  // 갈래마다 제 칸을 모은다. 표에 없는 key 는 마지막 갈래로 — 나중에 는 칸도 자리를 잃지 않는다.
  const grouped = useMemo(() => {
    const placed = new Set<string>()
    const take = (one: AttributeDefinition | undefined): one is AttributeDefinition => {
      if (!one) return false
      placed.add(one.key)
      return true
    }
    const out = SECTIONS.map((section) => ({
      ...section,
      rows: section.keys.map((key) => definitions.find((one) => one.key === key)).filter(take),
      // 조건 칸은 축마다 하나라 이름으로 못 적는다 — 종류로 모은다.
      conditionRows: section.conditions
        ? definitions.filter((one) => one.kind === 'condition').filter(take)
        : [],
    })).filter((section) => section.rows.length > 0 || section.conditionRows.length > 0)
    const rest = definitions.filter((one) => !placed.has(one.key))
    if (rest.length > 0)
      out.push({
        title: '그 밖의 칸',
        hint: undefined,
        keys: [],
        conditions: false,
        rows: rest,
        conditionRows: [],
      })
    return out
  }, [definitions])

  if (definitions.length === 0) return null

  return (
    <>
      {grouped.map((section) => (
        <fieldset key={section.title} className="rounded-lg border p-4">
          <legend className="px-1.5 text-sm font-medium">{section.title}</legend>
          {section.hint && (
            <p className="text-muted-foreground mb-3 text-xs">{section.hint}</p>
          )}
          {section.conditionRows.length > 0 && (
            <ConditionRows
              definitions={section.conditionRows}
              values={values}
              onChange={onChange}
            />
          )}
          {/* **가로로 다 벌리지 않는다.** 창이 넓어도 입력 칸이 화면을 가로지르면 라벨과
              칸이 멀어져 무엇을 적는 자리인지 안 보인다 — 열을 늘려 칸 폭을 잡아 둔다. */}
          <div className="grid gap-x-6 gap-y-4 md:grid-cols-2 xl:grid-cols-3">
            {section.rows.map((definition) => {
              const value = values[definition.id] ?? empty()
              const id = `attr-${definition.id}`
              return (
                <div
                  key={definition.id}
                  className={
                    isWide(definition) ? 'space-y-2 md:col-span-2 xl:col-span-3' : 'space-y-2'
                  }
                >
                  <Label htmlFor={id}>
                    {definition.label}
                    {definition.unit && (
                      <span className="text-muted-foreground ml-1 text-xs">
                        ({definition.unit})
                      </span>
                    )}
                  </Label>

                  {definition.kind === 'condition' || definition.kind === 'range' ? (
                    // **구간은 두 칸이다.** 「-40 ~ 85」 를 한 칸에 받으면 글자가 되고,
                    // 글자가 된 조건은 장비 판정에 안 실린다.
                    <div className="flex items-center gap-2">
                      <Input
                        id={id}
                        type="number"
                        value={value.numMin ?? ''}
                        onChange={(event) =>
                          set(definition.id, {
                            numMin:
                              event.target.value === '' ? null : Number(event.target.value),
                          })
                        }
                        placeholder="최소"
                        className="w-32"
                      />
                      <span className="text-muted-foreground">~</span>
                      <Input
                        type="number"
                        value={value.numMax ?? ''}
                        onChange={(event) =>
                          set(definition.id, {
                            numMax:
                              event.target.value === '' ? null : Number(event.target.value),
                          })
                        }
                        placeholder="최대"
                        aria-label={`${definition.label} 최대`}
                        className="w-32"
                      />
                      <span className="text-muted-foreground text-sm">{definition.unit}</span>
                    </div>
                  ) : definition.kind === 'number' ? (
                    <Input
                      id={id}
                      type="number"
                      value={value.numValue ?? ''}
                      onChange={(event) =>
                        set(definition.id, {
                          numValue:
                            event.target.value === '' ? null : Number(event.target.value),
                        })
                      }
                      className="w-40"
                    />
                  ) : definition.kind === 'term' ? (
                    <TermField
                      id={id}
                      definition={definition}
                      value={value.termId}
                      onChange={(termId) => set(definition.id, { termId })}
                    />
                  ) : definition.kind === 'method' ? (
                    <MethodField
                      id={id}
                      value={value.methodId}
                      onChange={(methodId) => set(definition.id, { methodId })}
                    />
                  ) : definition.kind === 'choice' ? (
                    <Select
                      value={value.textValue || undefined}
                      onValueChange={(next) => set(definition.id, { textValue: next })}
                    >
                      <SelectTrigger id={id}>
                        <SelectValue placeholder="고르기" />
                      </SelectTrigger>
                      <SelectContent>
                        {(definition.choices ?? []).map((one) => (
                          <SelectItem key={one} value={one}>
                            {one}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : definition.kind === 'pairs' ? (
                    <div className="max-w-xl">
                      <PairsEditor
                        rows={value.pairs}
                        unit={definition.unit}
                        onChange={(pairs) => set(definition.id, { pairs })}
                      />
                    </div>
                  ) : definition.kind === 'matrix' ? (
                    <div className="max-w-2xl">
                      <MatrixEditor
                        rows={value.matrix}
                        unit={definition.unit}
                        onChange={(matrix) => set(definition.id, { matrix })}
                      />
                    </div>
                  ) : LONG.has(definition.key) ? (
                    <Textarea
                      className="max-w-3xl"
                      id={id}
                      value={value.textValue}
                      onChange={(event) =>
                        set(definition.id, { textValue: event.target.value })
                      }
                      rows={3}
                      maxLength={4000}
                    />
                  ) : (
                    <Input
                      id={id}
                      value={value.textValue}
                      onChange={(event) =>
                        set(definition.id, { textValue: event.target.value })
                      }
                      maxLength={4000}
                    />
                  )}

                  {definition.help && (
                    <p className="text-muted-foreground text-xs">{definition.help}</p>
                  )}
                </div>
              )
            })}
          </div>
        </fieldset>
      ))}
    </>
  )
}

/**
 * 시험 조건 — **줄을 필요한 만큼 늘린다.**
 *
 * 조건 축은 열하나다. 전부 빈 칸으로 세워 두면 카드가 빈 칸으로만 길어지고, 정작 적을
 * 두 줄이 그 사이에 묻힌다. 그래서 **적은 것만 서고**, 나머지는 「조건 추가」 로 꺼낸다.
 *
 * 한 줄이 셋 중 하나가 된다:
 *
 *     -40 ~ 85       양쪽 다 적음 — 그 사이
 *     85 이상         최대만 비움
 *     -40 이하        최소만 비움
 *     (비고만)        숫자로 못 적는 것 — 「상온」·「규격에 따름」. 판정에는 안 쓰인다
 */
function ConditionRows({
  definitions,
  values,
  onChange,
}: {
  definitions: AttributeDefinition[]
  values: Record<string, StandardValue>
  onChange: (next: Record<string, StandardValue>) => void
}) {
  const filled = (one: AttributeDefinition) => {
    const value = values[one.id]
    if (!value) return false
    return value.numMin !== null || value.numMax !== null || value.note.trim() !== ''
  }
  // 한 번 꺼낸 줄은 비워도 남는다 — 지우려고 값을 비웠는데 줄이 사라지면 놀란다.
  const [shown, setShown] = useState<string[]>(() =>
    definitions.filter(filled).map((one) => one.id),
  )
  useEffect(() => {
    setShown((prev) => {
      const next = definitions.filter((one) => filled(one) && !prev.includes(one.id))
      return next.length > 0 ? [...prev, ...next.map((one) => one.id)] : prev
    })
    // 값이 밖에서 통째로 바뀔 때(수정 창 열기)만 맞춘다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [definitions, values])

  const rows = definitions.filter((one) => shown.includes(one.id))
  const rest = definitions.filter((one) => !shown.includes(one.id))
  const set = (id: string, patch: Partial<StandardValue>) =>
    onChange({ ...values, [id]: { ...(values[id] ?? empty()), ...patch } })

  return (
    <div className="mb-4 max-w-4xl space-y-2">
      {rows.map((definition) => {
        const value = values[definition.id] ?? empty()
        const id = `attr-${definition.id}`
        return (
          <div key={definition.id} className="bg-muted/30 rounded-md border p-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <Label htmlFor={id} className="w-28 shrink-0 text-sm">
                {definition.label}
              </Label>
              <Input
                id={id}
                type="number"
                value={value.numMin ?? ''}
                onChange={(event) =>
                  set(definition.id, {
                    numMin: event.target.value === '' ? null : Number(event.target.value),
                  })
                }
                placeholder="최소"
                className="w-24"
              />
              <span className="text-muted-foreground text-sm">~</span>
              <Input
                type="number"
                value={value.numMax ?? ''}
                onChange={(event) =>
                  set(definition.id, {
                    numMax: event.target.value === '' ? null : Number(event.target.value),
                  })
                }
                placeholder="최대"
                aria-label={`${definition.label} 최대`}
                className="w-24"
              />
              <span className="text-muted-foreground w-12 text-sm">{definition.unit}</span>
              <Input
                value={value.note}
                onChange={(event) => set(definition.id, { note: event.target.value })}
                placeholder="비고 — 숫자로 못 적는 것 (상온 · 규격에 따름)"
                aria-label={`${definition.label} 비고`}
                className="min-w-40 flex-1"
                maxLength={2000}
              />
              <button
                type="button"
                aria-label={`${definition.label} 빼기`}
                className="text-muted-foreground hover:text-foreground"
                onClick={() => {
                  setShown((prev) => prev.filter((one) => one !== definition.id))
                  set(definition.id, { numMin: null, numMax: null, note: '' })
                }}
              >
                <X className="size-4" />
              </button>
            </div>
            <p className="text-muted-foreground mt-1 pl-30 text-xs">
              {describeRange(value, definition.unit)}
            </p>
          </div>
        )
      })}

      {rest.length > 0 && (
        <SearchablePicker
          id="condition-add"
          options={rest.map((one) => ({ id: one.id, label: one.label, detail: one.unit }))}
          value=""
          onChange={(id) => id && setShown((prev) => [...prev, id])}
          placeholder="조건 추가"
          detailTitle="시험 조건"
          detailHint="여기 없는 축이 필요하면 관리자가 「검색 조건」 에 축을 더합니다."
        />
      )}
    </div>
  )
}

/** 지금 적힌 것이 무슨 뜻인지 한 줄로 — 한쪽만 적은 것이 실수인지 뜻인지 사람이 본다. */
function describeRange(value: StandardValue, unit: string): string {
  const suffix = unit ? ` ${unit}` : ''
  if (value.numMin !== null && value.numMax !== null) {
    return `${value.numMin} ~ ${value.numMax}${suffix} 사이`
  }
  if (value.numMin !== null) return `${value.numMin}${suffix} 이상 (최대는 제한 없음)`
  if (value.numMax !== null) return `${value.numMax}${suffix} 이하 (최소는 제한 없음)`
  if (value.note.trim()) return '숫자가 없어 장비 판정에는 안 쓰입니다 — 사람이 읽는 줄입니다.'
  return '최소·최대 중 하나만 적어도 됩니다.'
}

function TermField({
  id,
  definition,
  value,
  onChange,
}: {
  id: string
  definition: AttributeDefinition
  value: string | null
  onChange: (next: string | null) => void
}) {
  const slug = definition.vocabulary_slug ?? ''
  const terms = useResource(
    () => (slug ? vocabularyApi.terms(slug) : Promise.resolve([])),
    [slug],
  )
  const options = (terms.data ?? []).map((one) => ({ id: one.id, label: one.value }))
  return (
    <SearchablePicker
      id={id}
      options={options}
      value={value ?? ''}
      onChange={(next) => onChange(next || null)}
      placeholder={options.length > 0 ? '고르기' : '값이 아직 없습니다'}
      detailTitle={definition.label}
      detailHint="기준정보에서 고릅니다 — 없으면 관리자가 값을 더합니다."
    />
  )
}

function MethodField({
  id,
  value,
  onChange,
}: {
  id: string
  value: string | null
  onChange: (next: string | null) => void
}) {
  const [typed, setTyped] = useState('')
  const [query, setQuery] = useState('')
  useEffect(() => {
    const timer = setTimeout(() => setQuery(typed.trim()), 250)
    return () => clearTimeout(timer)
  }, [typed])
  const found = useResource(
    () => methodApi.list({ q: query || undefined, limit: 50 }),
    [query],
  )
  const options = (found.data?.items ?? []).map((one) => ({
    id: one.id,
    label: `${one.code} ${one.title}`.trim(),
  }))
  return (
    <SearchablePicker
      id={id}
      options={options}
      value={value ?? ''}
      onChange={(next) => onChange(next || null)}
      onSearch={setTyped}
      placeholder="규격 고르기"
      detailTitle="규격"
      detailHint="규격 사전에서 고릅니다 — 글자로 적으면 같은 규격이 둘로 갈립니다."
    />
  )
}

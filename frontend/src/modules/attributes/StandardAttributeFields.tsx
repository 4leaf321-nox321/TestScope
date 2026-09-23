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
      (value.numMin !== null || value.numMax !== null)
    ) {
      out.push({
        ...base,
        num_min: value.numMin,
        num_max: value.numMax,
        unit: definition.unit,
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
const SECTIONS: { title: string; hint?: string; keys: string[] }[] = [
  {
    title: '무엇을 왜',
    keys: ['reliability_type', 'reliability_product_group'],
  },
  {
    title: '근거',
    hint: '공인 규격은 사전에서 고르고, 사내 문서는 번호를 적습니다.',
    keys: ['reliability_reference_method', 'reliability_spec_document'],
  },
  {
    title: '시험 조건',
    hint: '여기 적은 수치가 그대로 「이 시험 돌릴 수 있는 장비」 판정이 됩니다. 「기타 조건」 은 글이라 판정에 안 쓰입니다.',
    keys: [
      'reliability_temperature',
      'reliability_humidity',
      'reliability_frequency',
      'reliability_acceleration',
      'reliability_other_conditions',
    ],
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
    const out = SECTIONS.map((section) => ({
      ...section,
      rows: section.keys
        .map((key) => definitions.find((one) => one.key === key))
        .filter((one): one is AttributeDefinition => {
          if (!one) return false
          placed.add(one.key)
          return true
        }),
    })).filter((section) => section.rows.length > 0)
    const rest = definitions.filter((one) => !placed.has(one.key))
    if (rest.length > 0)
      out.push({ title: '그 밖의 칸', hint: undefined, keys: [], rows: rest })
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

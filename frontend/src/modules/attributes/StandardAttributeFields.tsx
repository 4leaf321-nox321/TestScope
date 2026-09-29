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
import { AttachmentStrip } from '@/modules/attachments/AttachmentStrip'
import type { Attachment } from '@/modules/attachments/api'
import type { MatrixRow, Pair } from '@/modules/attributes/kinds'
import { MatrixEditor, PairsEditor } from '@/modules/attributes/PairsEditor'
import { specDocumentApi } from '@/modules/documents/api'
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
  documentId: string | null
  pairs: Pair[]
  matrix: MatrixRow[]
  /** 조건 줄의 비고 — 숫자로 못 적는 것(「상온」·「규격에 따름」). */
  note: string
  /** 문서에 적힌 그대로. **비고와 다른 칸이다** — 비고는 *해석*이고 이것은 *증거*다. */
  sourceText: string
  /** 환산 전 값·단위 — `158` `degF`. 안 남기면 환산이 틀렸을 때 되짚을 자리가 없다. */
  originalValue: string
  originalUnit: string
  /** 어느 칸의 값인가. **키가 칸 id 가 아니게 되면서** 줄이 제 칸을 알아야 한다. */
  definitionId: string
  /** 조건 묶음 — 「동작」·「저장」·「주」·「불량 시」. 비우면 이름 없는 한 벌. */
  setLabel: string
  /** 묶음 안의 차례. 비우면 묶음 전체에 걸린다(사이클 수 같은 것). */
  stepOrder: number | null
  /** 그 차례의 이름(「승온」·「유지」). 없어도 된다. */
  stepLabel: string
}

/**
 * 값 하나의 자리 — **칸 하나가 아니라 (칸, 묶음, 차례)다.**
 *
 * 묶음이 없는 줄의 키는 **칸 id 그대로**다. 조건 아닌 칸에는 묶음이 없고, 없는 것 때문에
 * 키가 바뀌면 이 파일 바깥(수정 창·시험)까지 같이 고쳐야 한다 — 고칠 이유가 없는 것을
 * 고치면 그중 하나를 빠뜨린다.
 */
export function valueKey(
  definitionId: string,
  setLabel = '',
  stepOrder: number | null = null,
): string {
  if (!setLabel && stepOrder === null) return definitionId
  return JSON.stringify([definitionId, setLabel, stepOrder])
}

/** 자리에서 (칸, 묶음, 차례)를 되읽는다 — **값이 아직 없는 줄**도 그려야 한다(그림만 붙은 칸). */
export function parseKey(key: string): {
  definitionId: string
  setLabel: string
  stepOrder: number | null
} {
  if (!key.startsWith('[')) return { definitionId: key, setLabel: '', stepOrder: null }
  const [definitionId, setLabel, stepOrder] = JSON.parse(key) as [
    string,
    string,
    number | null,
  ]
  return { definitionId, setLabel, stepOrder }
}

function empty(definitionId = ''): StandardValue {
  return {
    numValue: null,
    numMin: null,
    numMax: null,
    textValue: '',
    termId: null,
    methodId: null,
    documentId: null,
    pairs: [],
    matrix: [],
    note: '',
    sourceText: '',
    originalValue: '',
    originalUnit: '',
    definitionId,
    setLabel: '',
    stepOrder: null,
    stepLabel: '',
  }
}

/** 서버가 준 값 → 편집 상태. **(칸, 묶음, 차례)로 묶는다** — 동작 -15~45 와 저장 -40~25 는
 *  같은 칸 두 줄이라, 칸 id 로만 묶으면 수정 창을 여는 것만으로 하나가 사라진다. */
export function fromValues(rows: AttributeValue[] | undefined): Record<string, StandardValue> {
  const out: Record<string, StandardValue> = {}
  for (const row of rows ?? []) {
    const json = row.json_value as unknown
    const setLabel = row.set_label ?? ''
    const stepOrder = row.step_order ?? null
    out[valueKey(row.definition_id, setLabel, stepOrder)] = {
      definitionId: row.definition_id,
      setLabel,
      stepOrder,
      stepLabel: row.step_label ?? '',
      numValue: row.num_value ?? null,
      numMin: row.num_min ?? null,
      numMax: row.num_max ?? null,
      textValue: row.text_value ?? '',
      termId: row.term_id ?? null,
      methodId: row.method_id ?? null,
      documentId: row.document_id ?? null,
      pairs: Array.isArray(json) && row.kind === 'pairs' ? (json as Pair[]) : [],
      matrix: Array.isArray(json) && row.kind === 'matrix' ? (json as MatrixRow[]) : [],
      note: row.note ?? '',
      sourceText: row.source_text ?? '',
      originalValue: row.original_value ?? '',
      originalUnit: row.original_unit ?? '',
    }
  }
  return out
}

/** 채워진 칸만 서버로. **빈 칸은 보내지 않는다** — 빈 값은 저장이 아니라 지우기다. */
export function toStandardPayload(
  definitions: AttributeDefinition[],
  values: Record<string, StandardValue>,
): AttributeValueIn[] {
  const byId = new Map(definitions.map((one) => [one.id, one]))
  const order = new Map(definitions.map((one, index) => [one.id, index]))
  // **줄을 값에서 센다.** 칸마다 하나였을 때는 정의를 돌면 됐지만, 묶음이 생기면서 한 칸이
  // 여러 줄이 된다(동작 · 저장) — 정의를 돌면 그중 하나만 나가고 나머지는 조용히 사라진다.
  // 순서는 읽을 때와 같게 둔다(이름 없는 묶음 먼저 · 묶음 · 차례 · 칸).
  const rows = Object.values(values)
    .filter((one) => byId.has(one.definitionId))
    .sort(
      (a, b) =>
        a.setLabel.localeCompare(b.setLabel) ||
        (a.stepOrder ?? -1) - (b.stepOrder ?? -1) ||
        (order.get(a.definitionId) ?? 0) - (order.get(b.definitionId) ?? 0),
    )
  const out: AttributeValueIn[] = []
  for (const value of rows) {
    const definition = byId.get(value.definitionId)
    if (!definition) continue
    // `unit` 은 생성 타입에서 필수 칸이다 — 안 쓰는 종류도 빈 값으로 채운다.
    const base = {
      definition_id: definition.id,
      new_kind: definition.kind,
      unit: '',
      set_label: value.setLabel.trim() || null,
      step_order: value.stepOrder,
      step_label: value.stepLabel.trim() || null,
    }
    if (definition.kind === 'number' && value.numValue !== null) {
      out.push({ ...base, num_value: value.numValue, unit: definition.unit })
    } else if (
      (definition.kind === 'condition' || definition.kind === 'range') &&
      // **숫자가 없어도 비고가 있으면 보낸다** — 「상온」 처럼 숫자로 못 적는 조건이 있다.
      (value.numMin !== null ||
        value.numMax !== null ||
        value.numValue !== null ||
        value.note.trim() ||
        // 숫자를 아직 못 옮겼어도 **원문은 남는다** — 그 줄이 다음 사람의 시작점이다.
        value.sourceText.trim())
    ) {
      out.push({
        ...base,
        // 점(-40 · 25 · 85)은 조건에만 있다. 구간 칸과 섞이지 않게 화면이 한쪽만 채운다.
        num_value: definition.kind === 'condition' ? value.numValue : null,
        num_min: value.numMin,
        num_max: value.numMax,
        unit: definition.unit,
        note: value.note.trim() || null,
        // **원문은 안 다듬는다** — 줄바꿈과 띄어쓰기가 문서의 모양이다.
        source_text: value.sourceText.trim() || null,
        original_value: value.originalValue.trim() || null,
        original_unit: value.originalUnit.trim() || null,
      })
    } else if (definition.kind === 'term' && value.termId) {
      out.push({ ...base, term_id: value.termId })
    } else if (definition.kind === 'method' && value.methodId) {
      out.push({ ...base, method_id: value.methodId })
    } else if (definition.kind === 'document' && value.documentId) {
      out.push({ ...base, document_id: value.documentId })
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
/**
 * 칸을 묶는 갈래 — **등록 창과 보기 창이 같은 표를 쓴다.**
 *
 * 둘이 따로 갖고 있으면 칸이 하나 늘 때 한쪽만 고쳐지고, 그때부터 같은 카드가 자리에 따라
 * 다른 순서로 읽힌다. 그것은 「어디 적혀 있었더라」 를 매번 다시 찾게 만든다.
 */
export const SECTIONS: {
  title: string
  hint?: string
  keys: string[]
  /** 참이면 조건 종류(`kind="condition"`) 칸을 전부 이 갈래가 가져간다. */
  conditions?: boolean
}[] = [
  {
    title: '시험 구분',
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

export interface GroupedSection {
  title: string
  hint?: string
  rows: AttributeDefinition[]
  /** 조건 종류 칸 — 축마다 하나라 이름으로 못 적고 종류로 모은다. */
  conditionRows: AttributeDefinition[]
}

/**
 * 갈래마다 제 칸을 모은다. 표에 없는 key 는 마지막 갈래로 — 나중에 는 칸도 자리를 잃지 않는다.
 *
 * **함수로 빼 둔 이유:** 목차(왼쪽 줄)와 본문이 같은 표를 봐야 한다. 두 벌로 두면 칸이
 * 하나 늘 때 한쪽만 고쳐지고, 그때 목차가 없는 자리를 가리킨다.
 */
export function groupDefinitions(definitions: AttributeDefinition[]): GroupedSection[] {
  const placed = new Set<string>()
  const take = (one: AttributeDefinition | undefined): one is AttributeDefinition => {
    if (!one) return false
    placed.add(one.key)
    return true
  }
  const out: GroupedSection[] = SECTIONS.map((section) => ({
    title: section.title,
    hint: section.hint,
    rows: section.keys.map((key) => definitions.find((one) => one.key === key)).filter(take),
    conditionRows: section.conditions
      ? definitions.filter((one) => one.kind === 'condition').filter(take)
      : [],
  })).filter((section) => section.rows.length > 0 || section.conditionRows.length > 0)
  const rest = definitions.filter((one) => !placed.has(one.key))
  if (rest.length > 0) {
    out.push({ title: '기타 항목', rows: rest, conditionRows: [] })
  }
  return out
}

/** 목차가 가리키는 자리. 본문의 갈래·칸에 같은 id 를 단다. */
export function anchorOf(kind: 'section' | 'field', key: string): string {
  return `rt-${kind}-${key.replace(/\s+/g, '-')}`
}

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
  attachments,
}: {
  target: AttributeTarget
  values: Record<string, StandardValue>
  onChange: (next: Record<string, StandardValue>) => void
  onLoaded?: (definitions: AttributeDefinition[]) => void
  /** 칸마다 그림을 그릴 때. **어느 칸에 붙는지가 문서마다 다르므로** 칸이 아니라
   *  그림이 자리를 안다 — 여기서는 그 칸의 것만 골라 준다. */
  attachments?: {
    rows: Attachment[]
    canEdit: boolean
    objectId: string | null
    onChanged: () => void
  }
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
    onChange({ ...values, [id]: { ...(values[id] ?? empty(id)), ...patch } })

  const grouped = useMemo(() => groupDefinitions(definitions), [definitions])

  if (definitions.length === 0) return null

  return (
    <>
      {grouped.map((section) => (
        <fieldset
          key={section.title}
          id={anchorOf('section', section.title)}
          className="scroll-mt-4 rounded-lg border p-4"
        >
          <legend className="px-1.5 text-sm font-medium">{section.title}</legend>
          {section.hint && (
            <p className="text-muted-foreground mb-3 text-xs">{section.hint}</p>
          )}
          {section.conditionRows.length > 0 && (
            <ConditionRows
              definitions={section.conditionRows}
              values={values}
              onChange={onChange}
              attachments={attachments}
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
                  id={anchorOf('field', definition.key)}
                  className={
                    isWide(definition)
                      ? 'scroll-mt-4 space-y-2 md:col-span-2 xl:col-span-3'
                      : 'scroll-mt-4 space-y-2'
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
                  ) : definition.kind === 'document' ? (
                    <DocumentField
                      id={id}
                      value={value.documentId}
                      onChange={(documentId) => set(definition.id, { documentId })}
                    />
                  ) : definition.kind === 'choice' ? (
                    <Select
                      value={value.textValue || undefined}
                      onValueChange={(next) => set(definition.id, { textValue: next })}
                    >
                      <SelectTrigger id={id}>
                        <SelectValue placeholder="선택" />
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
                  {attachments && (
                    <FieldAttachments definition={definition} bag={attachments} />
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
 * 시험 조건 — **줄을 필요한 만큼 늘리고, 한 벌이 아니면 묶음으로 가른다.**
 *
 * 조건 축은 스물이다. 전부 빈 칸으로 세워 두면 카드가 빈 칸으로만 길어지고, 정작 적을
 * 두 줄이 그 사이에 묻힌다. 그래서 **적은 것만 서고**, 나머지는 「조건 추가」 로 꺼낸다.
 *
 * 한 줄이 넷 중 하나가 된다:
 *
 *     -40 ~ 85       양쪽 다 적음 — 그 사이
 *     85 이상         최대만 비움
 *     -40 이하        최소만 비움
 *     85             점 하나 — 폭이 없다(이산 점 · 프로파일의 한 차례)
 *     (비고만)        숫자로 못 적는 것 — 「상온」·「규격에 따름」. 판정에는 안 쓰인다
 *
 * **묶음**은 문서의 조건이 한 벌이 아닐 때 쓴다 — 동작 -15 ~ 45 와 저장 -40 ~ 25, 주 조건과
 * 「불량 시」, 24 cycle 을 도는 프로파일. 한 벌로 뭉치면 -40 ~ 45 라는 **문서에 없는 조건**이
 * 생기고, 그 조건으로 장비를 고른다. 묶음을 안 쓰는 시험은 화면이 예전 그대로다 — 안 쓰는
 * 것 때문에 칸이 둘 늘면, 늘 쓰는 사람이 그 값을 치른다.
 */
function ConditionRows({
  definitions,
  values,
  onChange,
  attachments,
}: {
  definitions: AttributeDefinition[]
  values: Record<string, StandardValue>
  onChange: (next: Record<string, StandardValue>) => void
  /** 조건 줄에도 이미지가 붙는다 — 온습도 프로파일은 「시험 온도」 의 그림이다. */
  attachments?: {
    rows: Attachment[]
    canEdit: boolean
    objectId: string | null
    onChanged: () => void
  }
}) {
  const byId = useMemo(() => new Map(definitions.map((one) => [one.id, one])), [definitions])
  const order = useMemo(
    () => new Map(definitions.map((one, index) => [one.id, index])),
    [definitions],
  )

  const written = (one: StandardValue | undefined) =>
    !!one &&
    (one.numMin !== null ||
      one.numMax !== null ||
      one.numValue !== null ||
      one.note.trim() !== '')

  /**
   * 줄을 꺼낼 이유 — 값이 있거나 **이미지가 붙어 있거나.**
   *
   * 이미지만 있고 수치는 아직 못 적은 조건이 실제로 있다(프로파일 그림은 받았는데 램프
   * 시간을 아직 모름). 값만 보고 줄을 접으면 그 이미지는 수정 창에서 **찾을 길이 없다** —
   * 붙인 사람은 붙인 줄 알고, 고치려는 사람은 없는 줄 안다.
   */
  const wanted = () => {
    const keys = Object.entries(values)
      .filter(([, one]) => byId.has(one.definitionId) && written(one))
      .map(([key]) => key)
    for (const row of attachments?.rows ?? []) {
      // 그림은 **칸**에 붙지 묶음에 붙지 않는다 — 이름 없는 줄로 꺼낸다.
      if (row.definition_id && byId.has(row.definition_id))
        keys.push(valueKey(row.definition_id))
    }
    return [...new Set(keys)]
  }

  const [shown, setShown] = useState<string[]>(wanted)
  useEffect(() => {
    setShown((prev) => {
      const next = wanted().filter((one) => !prev.includes(one))
      return next.length > 0 ? [...prev, ...next] : prev
    })
    // 값이 밖에서 통째로 바뀔 때(수정 창 열기)와 이미지가 붙고 빠질 때 맞춘다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [definitions, values, attachments?.rows])

  /**
   * 묶음 칸을 꺼낼까. **이미 묶음이 있으면 켜 둔다** — 안 그러면 AI 가 올린 동작/저장을
   * 사람이 열었을 때 묶음이 안 보이고, 안 보이는 것은 고칠 수 없다.
   */
  const hasSets = shown.some((key) => (values[key]?.setLabel ?? '') !== '')
  const [grouping, setGrouping] = useState(false)
  useEffect(() => {
    if (hasSets) setGrouping(true)
  }, [hasSets])

  const rows = shown
    .map((key) => {
      const at = parseKey(key)
      // 값이 없는 자리도 줄로 선다 — 그림만 붙은 조건이 그렇다.
      const value = values[key] ?? {
        ...empty(at.definitionId),
        setLabel: at.setLabel,
        stepOrder: at.stepOrder,
      }
      return { key, value, definition: byId.get(at.definitionId) }
    })
    .filter(
      (row): row is { key: string; value: StandardValue; definition: AttributeDefinition } =>
        !!row.value && !!row.definition,
    )
    .sort(
      (a, b) =>
        a.value.setLabel.localeCompare(b.value.setLabel) ||
        (a.value.stepOrder ?? -1) - (b.value.stepOrder ?? -1) ||
        (order.get(a.definition.id) ?? 0) - (order.get(b.definition.id) ?? 0),
    )

  const set = (key: string, patch: Partial<StandardValue>) => {
    const at = parseKey(key)
    const now = values[key] ?? {
      ...empty(at.definitionId),
      setLabel: at.setLabel,
      stepOrder: at.stepOrder,
    }
    onChange({ ...values, [key]: { ...now, ...patch } })
  }

  /** 줄을 다른 묶음·차례로 옮긴다 — **자리(키)가 바뀌므로 값과 목록을 함께 옮긴다.** */
  function move(key: string, patch: { setLabel?: string; stepOrder?: number | null }) {
    const at = parseKey(key)
    const now = values[key] ?? {
      ...empty(at.definitionId),
      setLabel: at.setLabel,
      stepOrder: at.stepOrder,
    }
    if (!byId.has(now.definitionId)) return
    const moved = { ...now, ...patch }
    const next = valueKey(moved.definitionId, moved.setLabel, moved.stepOrder)
    if (next === key) return
    if (values[next] && written(values[next])) return // 이미 적힌 줄을 덮지 않는다
    const rest = { ...values }
    delete rest[key]
    onChange({ ...rest, [next]: moved })
    setShown((prev) => prev.map((one) => (one === key ? next : one)).filter(unique))
  }

  function add(definitionId: string, setLabel: string) {
    // 같은 묶음에 같은 칸이 이미 있으면 **다음 차례**로 붙는다 — 프로파일이 그렇게 늘어난다.
    const mine = rows.filter(
      (row) => row.definition.id === definitionId && row.value.setLabel === setLabel,
    )
    if (mine.length === 0) {
      const key = valueKey(definitionId, setLabel, null)
      if (shown.includes(key)) return
      onChange({ ...values, [key]: { ...empty(definitionId), setLabel, stepOrder: null } })
      setShown((prev) => [...prev, key])
      return
    }
    // **첫 줄도 함께 번호를 받는다.** 하나는 「묶음 전체」 이고 하나는 「2번째」 이면, 프로파일
    // 넷 중 첫 도막이 어디 갔는지 읽는 사람이 못 찾는다.
    const numbered = mine.filter((row) => row.value.stepOrder !== null)
    if (numbered.length === 0) mine.forEach((row) => move(row.key, { stepOrder: 1 }))
    const step = Math.max(0, ...mine.map((row) => row.value.stepOrder ?? 1)) + 1
    const key = valueKey(definitionId, setLabel, step)
    if (shown.includes(key)) return
    onChange({ ...values, [key]: { ...empty(definitionId), setLabel, stepOrder: step } })
    setShown((prev) => [...prev, key])
  }

  function drop(key: string) {
    const rest = { ...values }
    delete rest[key]
    onChange(rest)
    setShown((prev) => prev.filter((one) => one !== key))
  }

  /** 화면에 설 묶음 — 이름 없는 것이 먼저다. 비어 있어도 사람이 만든 묶음은 남는다. */
  const [extraSets, setExtraSets] = useState<string[]>([])
  const setNames = [
    ...new Set(['', ...rows.map((row) => row.value.setLabel), ...extraSets]),
  ].sort((a, b) => (a === '' ? -1 : b === '' ? 1 : a.localeCompare(b)))
  // 이름 없는 묶음은 **줄이 있을 때만** 선다(다른 묶음이 하나도 없으면 그것이 유일한 자리다).
  // 늘 세워 두면 이름을 다 지어 둔 카드 위에 빈 카드가 하나 더 붙어 어디에 적을지 흐려진다.
  const groups = grouping
    ? setNames.filter(
        (one) =>
          one !== '' || setNames.length === 1 || rows.some((row) => row.value.setLabel === ''),
      )
    : ['']

  return (
    <div className="mb-4 max-w-4xl space-y-3">
      {groups.map((name) => {
        const mine = grouping ? rows.filter((row) => row.value.setLabel === name) : rows
        // 묶음을 쓸 때는 **이미 적은 칸도 다시 고를 수 있다** — 프로파일 한 벌은 시험 온도가
        // 네 줄이다(차례 1·2·3·4). 묶음을 안 쓰면 예전대로 칸마다 하나다.
        const taken = new Set(mine.map((row) => row.definition.id))
        const rest = grouping ? definitions : definitions.filter((one) => !taken.has(one.id))
        return (
          <div
            key={name || '(기본)'}
            className={grouping && name ? 'rounded-md border border-dashed p-2' : ''}
          >
            {grouping && (
              <div className="mb-1.5 flex flex-wrap items-center gap-2">
                <SetNameInput
                  value={name}
                  placeholder="묶음 이름 — 동작 · 저장 · 주 · 불량 시"
                  onCommit={(next) => {
                    if (next === name || setNames.includes(next)) return
                    for (const row of mine) move(row.key, { setLabel: next })
                    // **줄이 없어도 이름은 남는다.** 사람은 묶음을 만들고 이름부터 짓는다 —
                    // 그때 이름이 안 붙으면, 다음에 적는 조건이 이름 없는 한 벌로 들어간다.
                    setExtraSets((prev) =>
                      prev.includes(name)
                        ? prev.map((one) => (one === name ? next : one))
                        : [...prev, next],
                    )
                  }}
                />
                {name === '' && mine.length === 0 && (
                  <span className="text-muted-foreground text-xs">
                    이름을 비워 두면 「이름 없는 한 벌」 입니다.
                  </span>
                )}
              </div>
            )}

            <div className="space-y-2">
              {mine.map((row) => (
                <ConditionRow
                  key={row.key}
                  definition={row.definition}
                  value={row.value}
                  grouping={grouping}
                  onChange={(patch) => set(row.key, patch)}
                  onStep={(step) => move(row.key, { stepOrder: step })}
                  onRemove={() => drop(row.key)}
                  attachments={attachments}
                />
              ))}
            </div>

            {rest.length > 0 && (
              <div className="mt-2">
                <SearchablePicker
                  id={name === '' ? 'condition-add' : undefined}
                  options={rest.map((one) => ({
                    id: one.id,
                    label: one.label,
                    detail: one.unit,
                  }))}
                  value=""
                  onChange={(id) => id && add(id, name)}
                  placeholder="조건 추가"
                  detailTitle="시험 조건"
                  detailHint="여기 없는 축이 필요하면 관리자가 「검색 조건」 에 축을 더합니다."
                />
              </div>
            )}
          </div>
        )
      })}

      <div className="flex flex-wrap items-center gap-2">
        {!grouping ? (
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground text-xs underline"
            onClick={() => setGrouping(true)}
          >
            조건 묶음 나누기
          </button>
        ) : (
          <>
            <button
              type="button"
              className="text-muted-foreground hover:text-foreground text-xs underline"
              onClick={() => setExtraSets((prev) => [...prev, nextSetName(setNames)])}
            >
              묶음 추가
            </button>
            {!hasSets && (
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground text-xs underline"
                onClick={() => {
                  setExtraSets([])
                  setGrouping(false)
                }}
              >
                묶음 없이
              </button>
            )}
          </>
        )}
        <span className="text-muted-foreground text-xs">
          {grouping
            ? '동작 -15 ~ 45 와 저장 -40 ~ 25 처럼 한 벌이 아닌 조건을 가릅니다. 프로파일은 묶음 안에서 차례로 적고, 몇 번 도는지는 「사이클 수」 를 차례 없이 적습니다.'
            : '문서의 조건이 한 벌이 아니면(동작·저장, 주 조건과 예외, 프로파일) 묶음으로 가릅니다.'}
        </span>
      </div>
    </div>
  )
}

function unique<T>(one: T, index: number, all: T[]): boolean {
  return all.indexOf(one) === index
}

/** 「묶음 2」 · 「묶음 3」 … — 이미 있는 이름은 피한다. */
function nextSetName(taken: string[]): string {
  for (let index = 2; index < 100; index += 1) {
    const name = `묶음 ${index}`
    if (!taken.includes(name)) return name
  }
  return '묶음'
}

/**
 * 친 뒤 **빠져나갈 때** 반영하는 칸.
 *
 * 묶음 이름은 줄의 자리(키)를 이룬다 — 글자마다 반영하면 한 글자 칠 때마다 줄이 옮겨 다니고,
 * 치던 칸이 사라진다.
 */
function SetNameInput({
  value,
  placeholder,
  onCommit,
}: {
  value: string
  placeholder: string
  onCommit: (next: string) => void
}) {
  const [draft, setDraft] = useState(value)
  useEffect(() => setDraft(value), [value])
  return (
    <Input
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={() => onCommit(draft.trim())}
      onKeyDown={(event) => {
        if (event.key === 'Enter') {
          event.preventDefault()
          ;(event.target as HTMLInputElement).blur()
        }
      }}
      placeholder={placeholder}
      aria-label="묶음 이름"
      className="w-72"
      maxLength={60}
    />
  )
}

/** 조건 한 줄. 구간이거나 점이거나 — 둘을 함께 적을 수는 없다. */
function ConditionRow({
  definition,
  value,
  grouping,
  onChange,
  onStep,
  onRemove,
  attachments,
}: {
  definition: AttributeDefinition
  value: StandardValue
  grouping: boolean
  onChange: (patch: Partial<StandardValue>) => void
  onStep: (step: number | null) => void
  onRemove: () => void
  attachments?: {
    rows: Attachment[]
    canEdit: boolean
    objectId: string | null
    onChanged: () => void
  }
}) {
  const id = `attr-${definition.id}-${value.setLabel}-${value.stepOrder ?? ''}`
  const point = value.numValue !== null
  const num = (text: string) => (text === '' ? null : Number(text))
  return (
    <div
      id={anchorOf('field', definition.key)}
      className="bg-muted/30 scroll-mt-4 rounded-md border p-2.5"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Label htmlFor={id} className="w-28 shrink-0 text-sm">
          {definition.label}
        </Label>
        {grouping && (
          <Input
            type="number"
            value={value.stepOrder ?? ''}
            onChange={(event) => onStep(num(event.target.value))}
            placeholder="차례"
            aria-label={`${definition.label} 차례`}
            className="w-16"
            min={0}
            max={999}
          />
        )}
        <Select
          value={point ? 'point' : 'range'}
          onValueChange={(next) =>
            // **한쪽만 채운다.** 구간과 점이 한 줄에 함께 있으면 어느 쪽이 참인지 알 수 없다.
            next === 'point'
              ? onChange({
                  numValue: value.numMin ?? value.numMax,
                  numMin: null,
                  numMax: null,
                })
              : onChange({ numMin: value.numValue, numMax: value.numValue, numValue: null })
          }
        >
          <SelectTrigger className="w-20" aria-label={`${definition.label} 모양`}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="range">범위</SelectItem>
            <SelectItem value="point">점</SelectItem>
          </SelectContent>
        </Select>
        {point ? (
          <Input
            id={id}
            type="number"
            value={value.numValue ?? ''}
            onChange={(event) => onChange({ numValue: num(event.target.value) })}
            placeholder="값"
            className="w-24"
          />
        ) : (
          <>
            <Input
              id={id}
              type="number"
              value={value.numMin ?? ''}
              onChange={(event) => onChange({ numMin: num(event.target.value) })}
              placeholder="최소"
              className="w-24"
            />
            <span className="text-muted-foreground text-sm">~</span>
            <Input
              type="number"
              value={value.numMax ?? ''}
              onChange={(event) => onChange({ numMax: num(event.target.value) })}
              placeholder="최대"
              aria-label={`${definition.label} 최대`}
              className="w-24"
            />
          </>
        )}
        <span className="text-muted-foreground w-12 text-sm">{definition.unit}</span>
        <Input
          value={value.note}
          onChange={(event) => onChange({ note: event.target.value })}
          placeholder="비고 — 숫자로 못 적는 것 (상온 · 규격에 따름)"
          aria-label={`${definition.label} 비고`}
          className="min-w-40 flex-1"
          maxLength={2000}
        />
        <button
          type="button"
          aria-label={`${definition.label} 제거`}
          className="text-muted-foreground hover:text-foreground"
          onClick={onRemove}
        >
          <X className="size-4" />
        </button>
      </div>
      {/**
       * **원문과 환산 전 값은 비고와 다른 칸이다.**
       *
       * 비고는 옮겨 적은 사람의 *해석*이고 원문은 *증거*다. 한 칸에 섞이면 검토하는 사람이
       * 「이게 문서에 있는 말인가 옮긴 사람의 말인가」 를 못 가르고, 값 하나를 확인하려고
       * 원본을 다시 연다 — 그것이 검토 한 건의 시간을 늘린다.
       */}
      <div className="mt-1 flex flex-wrap items-center gap-2 pl-30">
        <Input
          value={value.sourceText}
          onChange={(event) => onChange({ sourceText: event.target.value })}
          placeholder="문서 원문 — 적힌 그대로"
          aria-label={`${definition.label} 원문`}
          className="min-w-48 flex-1"
          maxLength={4000}
        />
        <span className="text-muted-foreground text-xs">환산 전</span>
        <Input
          value={value.originalValue}
          onChange={(event) => onChange({ originalValue: event.target.value })}
          placeholder="158"
          aria-label={`${definition.label} 환산 전 값`}
          className="w-24"
          maxLength={100}
        />
        <Input
          value={value.originalUnit}
          onChange={(event) => onChange({ originalUnit: event.target.value })}
          placeholder="degF"
          aria-label={`${definition.label} 환산 전 단위`}
          className="w-24"
          maxLength={40}
        />
      </div>
      <p className="text-muted-foreground mt-1 pl-30 text-xs">
        {describeRange(value, definition.unit)}
      </p>
      {attachments && (
        <div className="mt-1 pl-30">
          <FieldAttachments definition={definition} bag={attachments} />
        </div>
      )}
    </div>
  )
}

/** 지금 적힌 것이 무슨 뜻인지 한 줄로 — 한쪽만 적은 것이 실수인지 뜻인지 사람이 본다. */
function describeRange(value: StandardValue, unit: string): string {
  const suffix = unit ? ` ${unit}` : ''
  const where = value.setLabel
    ? `「${value.setLabel}」${value.stepOrder === null ? '' : ` ${value.stepOrder}번째`} · `
    : ''
  // 점은 폭이 없다 — 그 값에서만 한다는 뜻이고, 사이 온도로 읽히면 안 된다.
  if (value.numValue !== null) return `${where}${value.numValue}${suffix} 한 점 (폭 없음)`
  if (value.numMin !== null && value.numMax !== null) {
    return `${where}${value.numMin} ~ ${value.numMax}${suffix} 사이`
  }
  if (value.numMin !== null) return `${where}${value.numMin}${suffix} 이상 (최대는 제한 없음)`
  if (value.numMax !== null) return `${where}${value.numMax}${suffix} 이하 (최소는 제한 없음)`
  if (value.note.trim()) return '숫자가 없어 장비 판정에는 안 쓰입니다 — 사람이 읽는 줄입니다.'
  return '최소·최대 중 하나만 적어도 됩니다.'
}

/** 이 칸에 붙은 그림. **한 장도 없고 넣을 수도 없으면 아무것도 안 그린다** — 빈 자리가
 *  칸마다 서면 카드가 그만큼 길어진다. */
function FieldAttachments({
  definition,
  bag,
}: {
  definition: AttributeDefinition
  bag: {
    rows: Attachment[]
    canEdit: boolean
    objectId: string | null
    onChanged: () => void
  }
}) {
  const mine = bag.rows.filter((one) => one.definition_id === definition.id)
  const [open, setOpen] = useState(false)
  if (mine.length === 0 && !bag.canEdit) return null
  if (mine.length === 0 && !open) {
    return (
      <button
        type="button"
        className="text-muted-foreground hover:text-foreground text-xs underline decoration-dotted underline-offset-2"
        onClick={() => setOpen(true)}
      >
        이미지 첨부
      </button>
    )
  }
  return (
    <AttachmentStrip
      target="reliability_test"
      objectId={bag.objectId}
      definitionId={definition.id}
      rows={mine}
      canEdit={bag.canEdit}
      onChanged={bag.onChanged}
      label="이 항목의 이미지"
    />
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
      placeholder={options.length > 0 ? '선택' : '값이 아직 없습니다'}
      detailTitle={definition.label}
      detailHint="온톨로지에서 고릅니다 — 없으면 관리자가 값을 더합니다."
    />
  )
}

/** 사내 규격서 고르기 — **공개 규격과 다른 사전이다.** 부서가 만든 문서고 파일이 붙는다. */
function DocumentField({
  id,
  value,
  onChange,
}: {
  id: string
  value: string | null
  onChange: (next: string | null) => void
}) {
  const found = useResource(() => specDocumentApi.list(), [])
  const options = (found.data ?? []).map((one) => ({
    id: one.id,
    label: `${one.code} ${one.title}`.trim(),
    // **파일이 없으면 그 사실을 고르는 자리에서 말한다** — 번호만 있는 문서를 걸어 두면
    // 읽는 사람이 원본을 찾아 헤맨다.
    detail: [one.revision, one.workspace_name, one.file_count === 0 ? '파일 없음' : null]
      .filter(Boolean)
      .join(' · '),
  }))
  return (
    <SearchablePicker
      id={id}
      options={options}
      value={value ?? ''}
      onChange={(next) => onChange(next || null)}
      placeholder="규격서 선택"
      searchPlaceholder="문서 번호의 일부 (MX-REL)"
      detailTitle="사내 규격서"
      detailHint="「사내 규격서」 화면에서 등록하고 원본 파일을 올립니다."
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
  // 목록을 한 번 받고 **피커가 제자리에서 거른다** — 글자마다 서버를 부르면 고르는 손이
  // 결과가 요동치는 사이에 미끄러진다(SearchablePicker 는 제 안에서 거르는 칸을 갖는다).
  const found = useResource(() => methodApi.list({}), [])
  const options = (found.data?.items ?? []).map((one) => ({
    id: one.id,
    label: `${one.code} ${one.title}`.trim(),
    detail: one.edition ?? null,
  }))
  return (
    <SearchablePicker
      id={id}
      options={options}
      value={value ?? ''}
      onChange={(next) => onChange(next || null)}
      placeholder="규격 선택"
      searchPlaceholder="규격 번호의 일부 (ISO 6892)"
      detailTitle="규격"
      detailHint="규격 사전에서 고릅니다 — 글자로 적으면 같은 규격이 둘로 갈립니다."
    />
  )
}

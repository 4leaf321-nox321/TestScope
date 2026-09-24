/**
 * 항목 값 편집 — **이름은 목록에서 고르고, 없을 때만 새로 적는다.**
 *
 * 이름이 갈리는 것(온도 · 시험온도 · Temp)이 초안의 가장 큰 병이다. 그래서 이름 칸은 글자
 * 입력이 아니라 고르기다 — 정식 항목이 먼저, 누가 이미 쓴 초안이 건수와 함께 다음, 정말
 * 없을 때만 「새 항목」. 초안을 고르면 그 종류·단위를 물려받아 단위가 갈리는 것도 함께 줄인다.
 *
 * 값 칸은 **친 글자의 모양으로 종류를 알아맞힌다**(kinds.ts). 종류를 고르라고 하면 전부
 * 문장으로 넣기 때문이다. 사람은 제안된 종류를 확인하거나 바꾼다.
 *
 * 이 컴포넌트는 값을 저장하지 않는다 — 줄 목록을 들고 있다가 부모가 `toPayload` 로 바꿔 대상의
 * API 에 함께 보낸다. 초안 정의는 그때 서버가 만든다.
 */

import { useEffect, useMemo, useState } from 'react'
import { X } from 'lucide-react'

import { SearchablePicker } from '@/shared/components/SearchablePicker'
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
import { attributeApi } from '@/modules/attributes/api'
import type {
  AttributeDefinition,
  AttributeTarget,
  AttributeValue,
  AttributeValueIn,
} from '@/modules/attributes/api'
import {
  COMMON_UNITS,
  DRAFT_KINDS,
  KIND_LABEL,
  detect,
  isNumeric,
  normalizeUnitInput,
} from '@/modules/attributes/kinds'
import type { AttributeKind } from '@/modules/attributes/kinds'
import { methodApi } from '@/modules/methods/api'
import { vocabularyApi } from '@/modules/vocabulary/api'

/** 편집 중인 한 줄. 서버로 갈 때 `toPayload` 가 종류에 맞는 칸만 골라 담는다. */
export interface AttributeRow {
  key: string
  definitionId: string | null
  /** definitionId 가 없을 때의 새 이름. */
  newLabel: string
  kind: AttributeKind
  /** 사람이 종류를 직접 골랐으면 알아맞히기가 덮지 않는다. */
  kindLocked: boolean
  /** 수치·구간·날짜·문장이 공유하는 입력 글자. 저장은 아래 칸으로 나눠서. */
  raw: string
  numValue: number | null
  numMin: number | null
  numMax: number | null
  unit: string
  textValue: string
  boolValue: boolean | null
  dateValue: string
  termId: string | null
  termLabel: string
  methodId: string | null
  methodLabel: string
  note: string
}

let counter = 0
function nextKey(): string {
  counter += 1
  return `row-${counter}`
}

function blank(partial: Partial<AttributeRow>): AttributeRow {
  return {
    key: nextKey(),
    definitionId: null,
    newLabel: '',
    kind: 'text',
    kindLocked: false,
    raw: '',
    numValue: null,
    numMin: null,
    numMax: null,
    unit: '',
    textValue: '',
    boolValue: null,
    dateValue: '',
    termId: null,
    termLabel: '',
    methodId: null,
    methodLabel: '',
    note: '',
    ...partial,
  }
}

function fmt(value: number | null): string {
  return value === null ? '' : String(value)
}

/** 서버가 준 값을 편집 줄로. 수정 창이 열릴 때 쓴다. */
export function fromValues(values: AttributeValue[]): AttributeRow[] {
  return values.map((one) => {
    const kind = one.kind as AttributeKind
    let raw = ''
    if (kind === 'number') raw = `${fmt(one.num_value)}${one.unit ? ` ${one.unit}` : ''}`
    if (kind === 'range' || kind === 'condition') {
      raw = `${fmt(one.num_min)} ~ ${fmt(one.num_max)}${one.unit ? ` ${one.unit}` : ''}`
    }
    if (kind === 'date') raw = one.date_value ?? ''
    if (kind === 'text') raw = one.text_value ?? ''
    return blank({
      definitionId: one.definition_id,
      kind,
      kindLocked: true,
      raw,
      numValue: one.num_value,
      numMin: one.num_min,
      numMax: one.num_max,
      unit: one.unit,
      textValue: one.text_value ?? '',
      boolValue: one.bool_value,
      dateValue: one.date_value ?? '',
      termId: one.term_id,
      termLabel: one.term_value ?? '',
      methodId: one.method_id,
      methodLabel: one.method_code ?? '',
      note: one.note ?? '',
    })
  })
}

/** 값이 적혔나 — 종류마다 보는 칸이 다르다. */
export function hasValue(row: AttributeRow): boolean {
  switch (row.kind) {
    case 'number':
      return row.numValue !== null
    case 'range':
    case 'condition':
      return row.numMin !== null || row.numMax !== null
    case 'boolean':
      return row.boolValue !== null
    case 'date':
      return row.dateValue !== ''
    case 'term':
      return row.termId !== null
    case 'method':
      return row.methodId !== null
    default:
      return row.textValue.trim() !== ''
  }
}

/**
 * 편집 줄을 서버 요청으로. **비어 있는 줄은 뺀다** — 필수 항목이 미리 줄로 서 있다가 안 채워져도
 * 저장은 된다(화면이 「비어 있는 필수 항목」 으로 말한다). 막으면 사람은 아무 값이나 넣는다.
 */
export function toPayload(rows: AttributeRow[]): AttributeValueIn[] {
  return rows
    .filter((row) => (row.definitionId || row.newLabel.trim()) && hasValue(row))
    .map((row) => ({
      definition_id: row.definitionId,
      new_label: row.definitionId ? null : row.newLabel.trim(),
      new_kind: row.kind,
      num_value: row.numValue,
      num_min: row.numMin,
      num_max: row.numMax,
      unit: normalizeUnitInput(row.unit),
      text_value: row.textValue || null,
      bool_value: row.boolValue,
      date_value: row.dateValue || null,
      term_id: row.termId,
      method_id: row.methodId,
      note: row.note.trim() || null,
    }))
}

/** 친 글자를 종류에 맞는 칸으로. 종류가 잠기지 않았으면 모양을 보고 종류도 바꾼다. */
function applyRaw(row: AttributeRow, raw: string): AttributeRow {
  const found = detect(raw)
  const kind: AttributeKind = row.kindLocked ? row.kind : found.kind
  const next: AttributeRow = { ...row, raw, kind }
  if (kind === 'number') {
    next.numValue = found.kind === 'number' ? (found.numValue ?? null) : null
    next.unit = found.kind === 'number' ? (found.unit ?? '') : row.unit
    next.numMin = next.numMax = null
  } else if (kind === 'range' || kind === 'condition') {
    if (found.kind === 'range') {
      next.numMin = found.numMin ?? null
      next.numMax = found.numMax ?? null
      next.unit = found.unit || row.unit
    } else if (found.kind === 'number') {
      // 「85」 하나만 치면 최소=최대 — 「85 이상」 은 「85 ~」 로.
      next.numMin = next.numMax = found.numValue ?? null
      next.unit = found.unit || row.unit
    } else {
      next.numMin = next.numMax = null
    }
    next.numValue = null
  } else if (kind === 'date') {
    next.dateValue = found.kind === 'date' ? (found.text ?? '') : ''
  } else if (kind === 'text') {
    next.textValue = raw
  }
  return next
}

function TermPicker({
  slug,
  row,
  onPick,
}: {
  slug: string
  row: AttributeRow
  onPick: (id: string, label: string) => void
}) {
  const terms = useResource(() => vocabularyApi.terms(slug), [slug])
  const options = useMemo(
    () => (terms.data ?? []).map((one) => ({ id: one.id, label: one.value })),
    [terms.data],
  )
  return (
    <SearchablePicker
      options={options}
      value={row.termId ?? ''}
      onChange={(id) => onPick(id, options.find((one) => one.id === id)?.label ?? '')}
      placeholder="기준정보 값 선택"
      className="w-full"
    />
  )
}

function MethodPicker({
  row,
  onPick,
}: {
  row: AttributeRow
  onPick: (id: string, label: string) => void
}) {
  const [query, setQuery] = useState('')
  const found = useResource(
    () =>
      query.trim().length >= 2 ? methodApi.list({ q: query.trim() }) : Promise.resolve(null),
    [query],
  )
  const items = found.data?.items ?? []
  return (
    <div className="space-y-1">
      {row.methodId ? (
        <div className="flex items-center gap-2 text-sm">
          <span className="font-medium">{row.methodLabel}</span>
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground text-xs underline"
            onClick={() => onPick('', '')}
          >
            변경
          </button>
        </div>
      ) : (
        <>
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="규격 코드로 찾기 (두 글자 이상)"
            aria-label="규격 찾기"
          />
          {items.length > 0 && (
            <ul className="max-h-40 overflow-y-auto rounded-md border text-sm">
              {items.slice(0, 20).map((one) => (
                <li key={one.id}>
                  <button
                    type="button"
                    className="hover:bg-muted w-full px-2 py-1 text-left"
                    onClick={() => onPick(one.id, one.code)}
                  >
                    <span className="font-medium">{one.code}</span>{' '}
                    <span className="text-muted-foreground text-xs">{one.title}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}

function ValueInput({
  row,
  definition,
  onChange,
}: {
  row: AttributeRow
  definition: AttributeDefinition | undefined
  onChange: (next: AttributeRow) => void
}) {
  const kind = row.kind
  const unitHint = definition?.unit ? ` (${definition.unit})` : ''
  if (kind === 'boolean') {
    return (
      <Select
        value={row.boolValue === null ? '' : row.boolValue ? 'yes' : 'no'}
        onValueChange={(next) => onChange({ ...row, boolValue: next === 'yes' })}
      >
        <SelectTrigger aria-label={`${labelOf(row, definition)} 값`}>
          <SelectValue placeholder="있음 / 없음" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="yes">있음</SelectItem>
          <SelectItem value="no">없음</SelectItem>
        </SelectContent>
      </Select>
    )
  }
  if (kind === 'choice') {
    return (
      <Select
        value={row.textValue}
        onValueChange={(next) => onChange({ ...row, textValue: next })}
      >
        <SelectTrigger aria-label={`${labelOf(row, definition)} 값`}>
          <SelectValue placeholder="선택" />
        </SelectTrigger>
        <SelectContent>
          {(definition?.choices ?? []).map((one) => (
            <SelectItem key={one} value={one}>
              {one}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    )
  }
  if (kind === 'term' && definition?.vocabulary_slug) {
    return (
      <TermPicker
        slug={definition.vocabulary_slug}
        row={row}
        onPick={(id, label) => onChange({ ...row, termId: id || null, termLabel: label })}
      />
    )
  }
  if (kind === 'method') {
    return (
      <MethodPicker
        row={row}
        onPick={(id, label) => onChange({ ...row, methodId: id || null, methodLabel: label })}
      />
    )
  }
  const placeholder =
    kind === 'number'
      ? `85 degC · 5 개${unitHint}`
      : kind === 'range' || kind === 'condition'
        ? `-40 ~ 125 degC${unitHint}`
        : kind === 'date'
          ? '2026-03-01'
          : '글자'
  return (
    <Input
      value={row.raw}
      onChange={(event) => onChange(applyRaw(row, event.target.value))}
      placeholder={placeholder}
      aria-label={`${labelOf(row, definition)} 값`}
      list={isNumeric(kind) ? 'attribute-units' : undefined}
    />
  )
}

function labelOf(row: AttributeRow, definition: AttributeDefinition | undefined): string {
  return definition?.label ?? row.newLabel ?? '속성'
}

export function AttributeValuesEditor({
  target,
  rows,
  onChange,
}: {
  target: AttributeTarget
  rows: AttributeRow[]
  onChange: (rows: AttributeRow[]) => void
}) {
  const definitions = useResource(() => attributeApi.definitions(target), [target])
  const [newLabel, setNewLabel] = useState('')
  const byId = useMemo(
    () => new Map((definitions.data ?? []).map((one) => [one.id, one])),
    [definitions.data],
  )
  const used = new Set(rows.map((row) => row.definitionId).filter(Boolean))

  // 정식이 먼저, 초안은 건수와 함께. 이미 고른 것은 뺀다.
  const options = useMemo(
    () =>
      (definitions.data ?? [])
        .filter((one) => !used.has(one.id))
        .map((one) => ({
          id: one.id,
          label: one.label,
          detail: `${KIND_LABEL[one.kind as AttributeKind] ?? one.kind}${one.unit ? ` · ${one.unit}` : ''}${one.help ? ` · ${one.help}` : ''}`,
          badge:
            one.status === 'standard'
              ? one.is_required
                ? '정식 · 필수'
                : '정식'
              : `초안 · ${one.value_count}건`,
        })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [definitions.data, rows],
  )

  // **필수 항목이 비면 말한다 — 막지는 않는다.** 막으면 사람은 아무 값이나 넣는다.
  const filled = new Set(rows.filter(hasValue).map((row) => row.definitionId))
  const missing = (definitions.data ?? []).filter(
    (one) => one.status === 'standard' && one.is_required && !filled.has(one.id),
  )

  // 정의 목록이 오면 처음 여는 등록 창에 필수 항목 줄을 미리 세운다.
  useEffect(() => {
    if (!definitions.data || rows.length > 0) return
    const required = definitions.data.filter(
      (one) => one.status === 'standard' && one.is_required,
    )
    if (required.length > 0) onChange(required.map((one) => rowFor(one)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [definitions.data])

  function rowFor(definition: AttributeDefinition): AttributeRow {
    return blank({
      definitionId: definition.id,
      kind: definition.kind as AttributeKind,
      kindLocked: true,
      unit: definition.unit,
    })
  }

  function update(key: string, next: AttributeRow) {
    onChange(rows.map((row) => (row.key === key ? next : row)))
  }

  function addNew() {
    const label = newLabel.trim()
    if (!label) return
    // 같은 이름이 있으면 새로 만들지 않고 그것을 고른다 — 이름이 갈리지 않게.
    const existing = (definitions.data ?? []).find(
      (one) => one.label.toLowerCase() === label.toLowerCase(),
    )
    onChange([...rows, existing ? rowFor(existing) : blank({ newLabel: label })])
    setNewLabel('')
  }

  return (
    <div className="space-y-2">
      <datalist id="attribute-units">
        {COMMON_UNITS.map((one) => (
          <option key={one} value={one} />
        ))}
      </datalist>

      {rows.length > 0 && (
        <ul className="space-y-2">
          {rows.map((row) => {
            const definition = row.definitionId ? byId.get(row.definitionId) : undefined
            const isDraft = !definition || definition.status === 'draft'
            return (
              <li key={row.key} className="rounded-md border p-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="min-w-32 text-sm font-medium">
                    {labelOf(row, definition)}
                    {isDraft && (
                      <span
                        className="text-muted-foreground ml-1 text-xs"
                        title="정식 속성이 아닙니다. 표시·수집만 되고 검색 판정에는 안 쓰입니다."
                      >
                        초안
                      </span>
                    )}
                  </span>
                  {!definition && (
                    <Select
                      value={row.kind}
                      onValueChange={(next) =>
                        update(
                          row.key,
                          applyRaw(
                            { ...row, kind: next as AttributeKind, kindLocked: true },
                            row.raw,
                          ),
                        )
                      }
                    >
                      <SelectTrigger className="w-32" aria-label={`${row.newLabel} 종류`}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {DRAFT_KINDS.map((one) => (
                          <SelectItem key={one} value={one}>
                            {KIND_LABEL[one]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                  <div className="min-w-48 flex-1">
                    <ValueInput
                      row={row}
                      definition={definition}
                      onChange={(next) => update(row.key, next)}
                    />
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={`${labelOf(row, definition)} 제거`}
                    onClick={() => onChange(rows.filter((one) => one.key !== row.key))}
                  >
                    <X className="size-4" />
                  </Button>
                </div>
                {isNumeric(row.kind) && !row.kindLocked && row.raw && (
                  <p className="text-muted-foreground mt-1 text-xs">
                    {KIND_LABEL[row.kind]}로 읽었습니다
                    {row.unit ? ` · 단위 ${row.unit}` : ''}. 아니면 종류를 바꾸십시오.
                  </p>
                )}
              </li>
            )
          })}
        </ul>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <SearchablePicker
          options={options}
          value=""
          onChange={(id) => {
            const definition = byId.get(id)
            if (definition) onChange([...rows, rowFor(definition)])
          }}
          placeholder="속성 선택"
          detailTitle="속성 전부"
          detailHint="정식 속성이 먼저, 누가 이미 쓴 초안이 건수와 함께 다음입니다."
          className="w-56"
        />
        <span className="text-muted-foreground text-xs">없으면</span>
        <Input
          value={newLabel}
          onChange={(event) => setNewLabel(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              addNew()
            }
          }}
          placeholder="새 속성 이름"
          aria-label="새 속성 이름"
          className="w-40"
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={addNew}
          disabled={!newLabel.trim()}
        >
          새 속성
        </Button>
      </div>

      {missing.length > 0 && (
        <p className="text-xs text-amber-700">
          비어 있는 필수 속성: {missing.map((one) => one.label).join(' · ')}
        </p>
      )}
      <p className="text-muted-foreground text-xs">
        새 속성은 초안으로 남고, 시스템 관리자가 「공통」 의 속성 정의에서 정식으로 올립니다.
        값은 「85 degC」 「-40 ~ 125 degC」 「2026-03-01」 처럼 치면 종류를 알아봅니다.
      </p>
    </div>
  )
}

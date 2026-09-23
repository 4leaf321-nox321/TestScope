/**
 * 이름마다 숫자가 붙는 칸 — 「A등급 4 · B등급 4」.
 *
 * 글자 한 줄로 받으면 사람은 읽어도 **기계는 못 읽는다.** 그래서 이름 칸과 숫자 칸을
 * 갈라 받는다. 줄은 필요한 만큼 늘린다 — 등급이 셋인 시험도 있고 단계가 다섯인 것도 있다.
 *
 * `matrix` 는 이것이 사양마다 한 벌인 것이다(사양 → 등급 → 값).
 */

import { Plus, X } from 'lucide-react'

import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import type { MatrixRow, Pair } from '@/modules/attributes/kinds'

function emptyPair(): Pair {
  return { label: '', value: null }
}

function PairRows({
  rows,
  unit,
  labelPlaceholder,
  onChange,
}: {
  rows: Pair[]
  unit: string
  labelPlaceholder: string
  onChange: (next: Pair[]) => void
}) {
  return (
    <div className="space-y-1.5">
      {rows.map((row, index) => (
        <div key={index} className="flex items-center gap-2">
          <Input
            value={row.label}
            onChange={(event) => {
              const next = [...rows]
              next[index] = { ...row, label: event.target.value }
              onChange(next)
            }}
            placeholder={labelPlaceholder}
            aria-label={`${labelPlaceholder} ${index + 1}`}
            maxLength={100}
            className="flex-1"
          />
          <Input
            type="number"
            value={row.value ?? ''}
            onChange={(event) => {
              const raw = event.target.value
              const next = [...rows]
              next[index] = { ...row, value: raw === '' ? null : Number(raw) }
              onChange(next)
            }}
            placeholder="수량"
            aria-label={`${row.label || labelPlaceholder} 수량`}
            className="w-24"
          />
          {unit && <span className="text-muted-foreground w-6 text-sm">{unit}</span>}
          <button
            type="button"
            aria-label={`${row.label || `${index + 1}번째`} 줄 빼기`}
            className="text-muted-foreground hover:text-foreground"
            onClick={() => onChange(rows.filter((_, at) => at !== index))}
          >
            <X className="size-4" />
          </button>
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => onChange([...rows, emptyPair()])}
      >
        <Plus className="size-3" /> 줄 추가
      </Button>
    </div>
  )
}

export function PairsEditor({
  rows,
  unit,
  onChange,
}: {
  rows: Pair[]
  unit: string
  onChange: (next: Pair[]) => void
}) {
  return (
    <PairRows
      rows={rows.length > 0 ? rows : [emptyPair()]}
      unit={unit}
      labelPlaceholder="등급·단계 이름"
      onChange={onChange}
    />
  )
}

export function MatrixEditor({
  rows,
  unit,
  onChange,
}: {
  rows: MatrixRow[]
  unit: string
  onChange: (next: MatrixRow[]) => void
}) {
  const shown = rows.length > 0 ? rows : [{ label: '', entries: [emptyPair()] }]
  return (
    <div className="space-y-3">
      {shown.map((row, index) => (
        <div key={index} className="space-y-2 rounded-md border p-3">
          <div className="flex items-center gap-2">
            <Input
              value={row.label}
              onChange={(event) => {
                const next = [...shown]
                next[index] = { ...row, label: event.target.value }
                onChange(next)
              }}
              placeholder="사양 이름"
              aria-label={`사양 ${index + 1}`}
              maxLength={100}
            />
            <button
              type="button"
              aria-label={`${row.label || `${index + 1}번째`} 사양 빼기`}
              className="text-muted-foreground hover:text-foreground"
              onClick={() => onChange(shown.filter((_, at) => at !== index))}
            >
              <X className="size-4" />
            </button>
          </div>
          <PairRows
            rows={row.entries.length > 0 ? row.entries : [emptyPair()]}
            unit={unit}
            labelPlaceholder="등급·단계 이름"
            onChange={(entries) => {
              const next = [...shown]
              next[index] = { ...row, entries }
              onChange(next)
            }}
          />
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => onChange([...shown, { label: '', entries: [emptyPair()] }])}
      >
        <Plus className="size-3" /> 사양 추가
      </Button>
    </div>
  )
}

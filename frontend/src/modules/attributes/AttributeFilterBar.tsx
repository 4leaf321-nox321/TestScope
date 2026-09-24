/**
 * 속성으로 거르기 — **적어 둔 것을 되찾는 칸.**
 *
 * 속성은 「열이 아니라 행」 이라 유연한 대신, 값이 상세 화면에만 뜨면 쌓아 둔 것을 되찾을 길이
 * 없다. 「투자 연도 2020 이후 장비」 를 못 물으면 사람은 목록을 내려받아 엑셀에서 거르고, 그
 * 순간 이 시스템은 입력 창구일 뿐이다.
 *
 * 조건은 서버 문법 그대로(`<키><연산><값>`)이고 **거르기는 서버가 한다** — 화면이 한 쪽을
 * 받아 놓고 거르면 상한을 넘는 순간 나머지가 조용히 빠지고, 그때 목록은 「그 조건에 맞는 것이
 * 이것뿐」 이라고 거짓말한다.
 *
 * 고르는 칸은 **정의 목록**이다(자유 입력이 아니라): 키를 외우게 하면 아무도 안 쓰고, 오타는
 * 400 으로 돌아온다. 종류마다 쓸 수 있는 연산이 다르므로 그것도 종류에서 정한다 — 수치에
 * 「포함」 을 보여 주면 눌러 본 사람이 오류를 본다.
 */

import { useEffect, useMemo, useState } from 'react'
import { Plus, X } from 'lucide-react'

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
import type { AttributeDefinition, AttributeTarget } from '@/modules/attributes/api'

/** 연산자와 그 우리말. 글자(`>=`)는 서버 문법이고, 이름은 사람이 고를 말이다. */
const OPERATORS = [
  { op: '=', label: '같다' },
  { op: '!=', label: '다르다' },
  { op: '>=', label: '이상' },
  { op: '<=', label: '이하' },
  { op: '>', label: '초과' },
  { op: '<', label: '미만' },
  { op: '~', label: '포함' },
  { op: '*', label: '값이 있다' },
] as const

const NUMERIC = new Set(['number', 'range', 'condition'])

function operatorsFor(kind: string): readonly { op: string; label: string }[] {
  if (NUMERIC.has(kind) || kind === 'date') {
    return OPERATORS.filter((one) => one.op !== '~')
  }
  if (kind === 'boolean') return OPERATORS.filter((one) => one.op === '=' || one.op === '*')
  return OPERATORS.filter(
    (one) => one.op !== '>' && one.op !== '<' && one.op !== '>=' && one.op !== '<=',
  )
}

/** 「temp_x>=100」 을 「시험 온도 이상 100 degC」 로. 못 읽는 것은 그대로 보여 준다. */
export function describe(raw: string, definitions: AttributeDefinition[]): string {
  const matched = /^([A-Za-z0-9_\-.]+)(\*|<=|>=|!=|<|>|=|~)(.*)$/.exec(raw)
  if (!matched) return raw
  const [, key, op, value] = matched
  const definition = definitions.find((one) => one.key === key)
  const label = definition?.label ?? key
  const word = OPERATORS.find((one) => one.op === op)?.label ?? op
  if (op === '*') return `${label} ${word}`
  const unit = definition && NUMERIC.has(definition.kind) ? ` ${definition.unit}` : ''
  return `${label} ${value}${unit} ${word}`
}

interface Props {
  target: AttributeTarget
  /** 지금 걸린 조건들 — 서버 문법 그대로. 주소에 그대로 실어 공유할 수 있다. */
  value: string[]
  onChange: (next: string[]) => void
  /** 목록이 **0건으로 끝났나.** 참이고 조건이 걸려 있으면 조건마다 「왜 0건인가」 를 서버에
   *  묻는다 — 빈 표만 보여 주면 사람은 「그런 것 없다」 로 읽는데, 가장 흔한 실제는 「아무도
   *  안 적었다」 다. */
  empty?: boolean
}

/** 0건일 때 조건마다 한 줄 — 서버가 세고 서버가 말한다(MCP 도 같은 것을 받는다). */
function EmptyDiagnosis({ target, attrs }: { target: AttributeTarget; attrs: string[] }) {
  const key = attrs.join('\u0000')
  const rows = useResource(() => attributeApi.diagnose(target, attrs), [target, key])
  if (!rows.data || rows.data.length === 0) return null
  return (
    <ul className="space-y-0.5 rounded-md border border-dashed p-2 text-xs">
      {rows.data.map((one) => (
        <li key={one.key}>
          <span className="font-medium">{one.label}</span>{' '}
          <span className="text-muted-foreground">{one.hint}</span>
        </li>
      ))}
    </ul>
  )
}

export function AttributeFilterBar({ target, value, onChange, empty = false }: Props) {
  const definitions = useResource(() => attributeApi.definitions(target), [target])
  const rows = useMemo(
    () => (definitions.data ?? []).filter((one) => one.is_active),
    [definitions.data],
  )
  const [key, setKey] = useState('')
  const [op, setOp] = useState('=')
  const [text, setText] = useState('')

  const picked = rows.find((one) => one.key === key)
  const allowed = operatorsFor(picked?.kind ?? 'text')

  // 종류가 바뀌면 그 종류에 없는 연산이 남아 있을 수 있다 — 남겨 두면 눌렀을 때 400 이다.
  useEffect(() => {
    if (picked && !allowed.some((one) => one.op === op)) setOp(allowed[0]?.op ?? '=')
  }, [picked, allowed, op])

  if (rows.length === 0) return null

  const add = () => {
    if (!picked) return
    if (op !== '*' && !text.trim()) return
    const next = `${picked.key}${op}${op === '*' ? '' : text.trim()}`
    if (!value.includes(next)) onChange([...value, next])
    setText('')
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-end gap-2">
        <label className="space-y-1">
          <span className="text-muted-foreground text-xs">속성</span>
          <Select value={key} onValueChange={setKey}>
            <SelectTrigger size="sm" className="w-48">
              <SelectValue placeholder="속성으로 거르기" />
            </SelectTrigger>
            <SelectContent>
              {rows.map((one) => (
                <SelectItem key={one.id} value={one.key}>
                  {one.label}
                  {one.unit ? ` (${one.unit})` : ''}
                  {one.status === 'draft' ? ' · 초안' : ''}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </label>
        <label className="space-y-1">
          <span className="text-muted-foreground text-xs">조건</span>
          <Select value={op} onValueChange={setOp} disabled={!picked}>
            <SelectTrigger size="sm" className="w-28">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {allowed.map((one) => (
                <SelectItem key={one.op} value={one.op}>
                  {one.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </label>
        {op !== '*' && (
          <label className="space-y-1">
            <span className="text-muted-foreground text-xs">
              값{picked?.unit ? ` (${picked.unit})` : ''}
            </span>
            <Input
              value={text}
              disabled={!picked}
              className="h-8 w-40"
              placeholder={picked && NUMERIC.has(picked.kind) ? '숫자' : '값'}
              onChange={(event) => setText(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') add()
              }}
            />
          </label>
        )}
        <Button size="sm" variant="outline" disabled={!picked} onClick={add}>
          <Plus className="mr-1 size-3.5" />
          조건 추가
        </Button>
      </div>

      {value.length > 0 && (
        <ul className="flex flex-wrap items-center gap-1 text-xs">
          {value.map((one) => (
            <li
              key={one}
              className="bg-muted flex items-center gap-1 rounded-full py-0.5 pr-1 pl-2"
            >
              {describe(one, rows)}
              <button
                type="button"
                aria-label={`${describe(one, rows)} 제거`}
                className="hover:bg-background rounded-full p-0.5"
                onClick={() => onChange(value.filter((row) => row !== one))}
              >
                <X className="size-3" />
              </button>
            </li>
          ))}
          {/* 여러 조건은 **모두** 만족해야 한다 — 「또는」 으로 읽으면 결과 수를 오해한다. */}
          <li className="text-muted-foreground ml-1">조건 모두 만족</li>
        </ul>
      )}
      {empty && value.length > 0 && <EmptyDiagnosis target={target} attrs={value} />}
    </div>
  )
}

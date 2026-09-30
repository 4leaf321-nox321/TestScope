/**
 * 속성을 **열로 세우고, 열마다 거른다.**
 *
 * 속성은 「열이 아니라 행」 이라 유연한 대신, 표에서는 한 칸에 「시험 온도: 85 ℃ / 시험 시간:
 * 1000 h / …」 를 줄줄이 쌓은 덩어리로 보였다. 그 꼴로는 **세로로 못 읽는다** — 「온도를
 * 적은 시험이 몇 건인가」 「이 줄만 습도가 비었나」 는 한 열을 위아래로 훑어야 보이는 것인데,
 * 덩어리 안에서는 같은 속성이 줄마다 다른 높이에 있다.
 *
 * 그래서 정의마다 열을 하나씩 세운다. 대신 열이 서른 개를 넘으므로 셋을 함께 둔다:
 *
 *   * **열마다 거르기** — 머리글의 깔때기. 서버 문법(`키<연산>값`)을 그대로 만들어 붙인다.
 *   * **「값 없음」** — `!*`. 채워야 할 칸을 찾는 물음이라 실제로 가장 자주 쓰인다.
 *     `!=` 와 다르다: `!=` 는 *적혀 있는데* 그 값이 아닌 것이고, `!*` 는 **줄 자체가 없는
 *     것**이다. 이것이 없으면 「안 적힌 것」 은 목록을 받아 사람이 세는 수밖에 없다.
 *   * **열 고르기** — 서른여섯 개를 늘 펼쳐 둘 수는 없다. 고른 것은 브라우저에 남는다.
 *
 * **거르기는 서버가 한다.** 화면이 한 쪽을 받아 놓고 거르면 상한을 넘는 순간 나머지가
 * 조용히 빠지고, 그때 표는 「그 조건에 맞는 것이 이것뿐」 이라고 거짓말한다.
 */

import { useCallback, useMemo, useState } from 'react'
import { Columns3, Filter } from 'lucide-react'

import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover'
import { TableCell, TableHead } from '@/shared/components/ui/table'
import { useResource } from '@/shared/hooks/useResource'
import { attributeApi } from '@/modules/attributes/api'
import {
  NO_VALUE_OPS,
  operatorsFor,
  parseFilter,
} from '@/modules/attributes/AttributeFilterBar'
import type { AttributeDefinition, AttributeTarget } from '@/modules/attributes/api'

/** 줄에 딸려 오는 값 한 개 — 어느 표에서 왔든 이만큼이면 열에 그릴 수 있다. */
export interface ColumnValue {
  definition_id: string
  set_label?: string | null
  step_label?: string | null
  is_current?: boolean
  status?: string
  display: string
  note?: string | null
}

const STORE = 'testscope.attribute-columns'

/** 숨긴 열은 브라우저에 남는다 — 들어올 때마다 서른여섯 개를 다시 접게 할 수는 없다. */
function readHidden(target: AttributeTarget): string[] {
  try {
    const saved = JSON.parse(window.localStorage.getItem(STORE) ?? '{}') as Record<
      string,
      string[]
    >
    return Array.isArray(saved[target]) ? saved[target] : []
  } catch {
    // 사생활 모드·지운 저장소에서는 읽기 자체가 던진다. 기본값으로 그린다.
    return []
  }
}

function writeHidden(target: AttributeTarget, keys: string[]): void {
  try {
    const saved = JSON.parse(window.localStorage.getItem(STORE) ?? '{}') as Record<
      string,
      string[]
    >
    window.localStorage.setItem(STORE, JSON.stringify({ ...saved, [target]: keys }))
  } catch {
    // 못 적어도 이번 화면은 그대로 동작한다 — 다음에 올 때 기본값으로 돌아갈 뿐이다.
  }
}

export interface AttributeColumns {
  /** 켤 수 있는 정의 전부(꺼진 정의는 뺀다). */
  all: AttributeDefinition[]
  /** 지금 열로 선 정의 — 정의 순서 그대로. */
  shown: AttributeDefinition[]
  hidden: string[]
  toggle: (key: string) => void
  /** `'all'` 전부 · `'used'` 값이 한 건이라도 있는 것만 · `'none'` 없음. */
  preset: (which: 'all' | 'used' | 'none') => void
}

/**
 * 열로 세울 속성. **기본은 전부**다 — 「어느 속성이 비었나」 가 이 표를 보는 이유이고,
 * 값이 없는 열을 처음부터 숨기면 그 물음이 화면에서 사라진다.
 */
export function useAttributeColumns(target: AttributeTarget): AttributeColumns {
  const definitions = useResource(() => attributeApi.definitions(target), [target])
  const all = useMemo(
    () => (definitions.data ?? []).filter((one) => one.is_active),
    [definitions.data],
  )
  const [hidden, setHidden] = useState<string[]>(() => readHidden(target))

  const keep = useCallback(
    (next: string[]) => {
      setHidden(next)
      writeHidden(target, next)
    },
    [target],
  )

  return {
    all,
    shown: useMemo(() => all.filter((one) => !hidden.includes(one.key)), [all, hidden]),
    hidden,
    toggle: (key) =>
      keep(hidden.includes(key) ? hidden.filter((one) => one !== key) : [...hidden, key]),
    preset: (which) =>
      keep(
        which === 'all'
          ? []
          : which === 'none'
            ? all.map((one) => one.key)
            : all.filter((one) => one.value_count === 0).map((one) => one.key),
      ),
  }
}

/** 어느 열을 세울까 — 서른여섯 개를 늘 펼쳐 둘 수는 없다. */
export function AttributeColumnPicker({ columns }: { columns: AttributeColumns }) {
  if (columns.all.length === 0) return null
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button size="sm" variant="outline">
          <Columns3 className="mr-1 size-3.5" />
          속성 열 {columns.shown.length}/{columns.all.length}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 p-2">
        <div className="mb-2 flex gap-1">
          <Button size="sm" variant="ghost" onClick={() => columns.preset('all')}>
            전체 선택
          </Button>
          {/* 값이 한 건도 없는 속성은 서른 개가 넘는다 — 한 번에 접는 길이 없으면 아무도 안 쓴다. */}
          <Button size="sm" variant="ghost" onClick={() => columns.preset('used')}>
            값 보유 항목
          </Button>
          <Button size="sm" variant="ghost" onClick={() => columns.preset('none')}>
            전체 해제
          </Button>
        </div>
        <ul className="max-h-80 space-y-0.5 overflow-y-auto text-sm">
          {columns.all.map((one) => (
            <li key={one.id}>
              <label className="hover:bg-muted flex items-center gap-2 rounded px-1 py-0.5">
                <input
                  type="checkbox"
                  className="size-3.5"
                  checked={!columns.hidden.includes(one.key)}
                  onChange={() => columns.toggle(one.key)}
                />
                <span className="flex-1 truncate" title={one.label}>
                  {one.label}
                  {one.unit ? ` (${one.unit})` : ''}
                </span>
                <span className="text-muted-foreground text-xs">{one.value_count}</span>
              </label>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  )
}

/** 이 열에 걸린 조건들 — 묶음을 가리는 조건(`키@묶음`)도 이 열의 것이다. */
function minePlusRest(value: string[], key: string) {
  const mine: string[] = []
  const rest: string[] = []
  for (const one of value) (parseFilter(one)?.key === key ? mine : rest).push(one)
  return { mine, rest }
}

function ColumnFilter({
  definition,
  value,
  onChange,
}: {
  definition: AttributeDefinition
  value: string[]
  onChange: (next: string[]) => void
}) {
  const { mine, rest } = minePlusRest(value, definition.key)
  const allowed = operatorsFor(definition.kind)
  const [open, setOpen] = useState(false)
  const [op, setOp] = useState(allowed[0]?.op ?? '=')
  const [text, setText] = useState('')
  const blank = NO_VALUE_OPS.includes(op)

  const add = () => {
    if (!blank && !text.trim()) return
    const next = `${definition.key}${op}${blank ? '' : text.trim()}`
    // **같은 열에 여러 조건을 걸 수 있다**(80 이상이면서 120 이하) — 갈아 끼우면
    // 범위를 못 묻는다. 똑같은 조건만 안 쌓는다.
    if (!value.includes(next)) onChange([...value, next])
    setText('')
    setOpen(false)
  }

  return (
    <div className="flex items-center gap-1">
      <span className="truncate" title={definition.help ?? definition.label}>
        {definition.label}
      </span>
      {definition.unit && (
        <span className="text-muted-foreground text-xs font-normal">{definition.unit}</span>
      )}
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-label={`${definition.label} 필터`}
            // 걸린 열은 **눈에 띈다** — 안 그러면 왜 스무 건만 보이는지 못 찾는다.
            className={`rounded p-0.5 ${
              mine.length > 0 ? 'text-primary' : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <Filter className={`size-3.5 ${mine.length > 0 ? 'fill-current' : ''}`} />
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-64 space-y-2 p-2">
          <p className="text-sm font-medium">{definition.label}</p>
          {/**
           * **필터의 방향을 적는다.** 「값 없음」 을 걸었는데 아무것도 안 줄어들면 사람은
           * 고장으로 읽는다 — 실제로는 그 속성에 값을 적은 항목이 한 건도 없어서 전부가
           * 조건에 맞은 것이다. 그 수를 함께 적어 두면 그 자리에서 알 수 있다.
           */}
          <p className="text-muted-foreground text-xs">
            조건에 맞는 항목만 표시됩니다. 이 속성에 값이 입력된 항목은 전사 기준{' '}
            {definition.value_count}건입니다.
          </p>
          <div className="flex items-end gap-1">
            {/* 창 안의 창은 열고 닫는 길이 얽힌다 — 연산 고르기는 **제 것**으로 둔다. */}
            <select
              aria-label={`${definition.label} 연산자`}
              className="bg-background h-8 rounded-md border px-1 text-sm"
              value={op}
              onChange={(event) => setOp(event.target.value)}
            >
              {allowed.map((one) => (
                <option key={one.op} value={one.op}>
                  {one.label}
                </option>
              ))}
            </select>
            {!blank && (
              <Input
                autoFocus
                value={text}
                className="h-8 flex-1"
                placeholder={definition.unit || '값'}
                onChange={(event) => setText(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') add()
                }}
              />
            )}
          </div>
          <div className="flex justify-between gap-1">
            <Button size="sm" onClick={add}>
              필터 적용
            </Button>
            {mine.length > 0 && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  onChange(rest)
                  setOpen(false)
                }}
              >
                이 열 필터 해제
              </Button>
            )}
          </div>
        </PopoverContent>
      </Popover>
    </div>
  )
}

/** 머리글 칸들 — `<tr>` 안에 그대로 편다. */
export function AttributeHeadCells({
  columns,
  value,
  onChange,
}: {
  columns: AttributeDefinition[]
  value: string[]
  onChange: (next: string[]) => void
}) {
  return (
    <>
      {columns.map((one) => (
        <TableHead key={one.id} className="max-w-56 min-w-36">
          <ColumnFilter definition={one} value={value} onChange={onChange} />
        </TableHead>
      ))}
    </>
  )
}

/** 한 줄의 값 칸들 — 열 순서는 머리글과 **같은 배열**에서 온다. */
export function AttributeBodyCells({
  columns,
  values,
}: {
  columns: AttributeDefinition[]
  values: ColumnValue[]
}) {
  // 한 정의에 값이 여럿일 수 있다 — 조건 묶음(주 조건 70 ℃ · 불량 시 90 ℃)과 차례가 그렇다.
  // 정의마다 모아 두지 않으면 묶음이 둘인 시험에서 한쪽이 조용히 안 보인다.
  const byDefinition = useMemo(() => {
    const out = new Map<string, ColumnValue[]>()
    for (const one of values) {
      // 과거 판의 값은 이 자리의 「지금 값」 이 아니다 — 이력은 카드 안에서 본다.
      if (one.is_current === false) continue
      const got = out.get(one.definition_id)
      if (got) got.push(one)
      else out.set(one.definition_id, [one])
    }
    return out
  }, [values])

  return (
    <>
      {columns.map((one) => {
        // **빈 값은 값이 아니다.** 숫자를 못 옮겨 비고에만 적은 줄이 있다(기타 조건이
        // 대개 그렇다). 그 줄을 그냥 그리면 칸이 **아무 글자 없이 비어** 보이는데, 사람은
        // 그것을 「값 없음」 으로 읽고 그렇게 거른다 — 그래서 비고를 대신 보여 준다.
        const mine = (byDefinition.get(one.id) ?? []).filter(
          (item) => item.display || item.note,
        )
        return (
          <TableCell key={one.id} className="max-w-56 min-w-36 align-top text-sm">
            {mine.length === 0 ? (
              // **빈 칸을 「—」 로 적는다** — 아무것도 안 그리면 열이 밀린 것인지 값이
              // 없는 것인지 구별이 안 된다.
              <span className="text-muted-foreground">—</span>
            ) : (
              <ul className="space-y-0.5">
                {mine.map((item, at) => (
                  <li key={`${item.set_label ?? ''}/${item.step_label ?? ''}/${at}`}>
                    {(item.set_label || item.step_label) && (
                      <span className="text-muted-foreground mr-1 text-xs">
                        {[item.set_label, item.step_label].filter(Boolean).join(' · ')}
                      </span>
                    )}
                    {item.display ? (
                      <span className="break-words whitespace-pre-line">{item.display}</span>
                    ) : (
                      // 값 없이 비고만 — **값으로 안 센다**(「값 없음」 에 걸린다).
                      <span
                        className="text-muted-foreground break-words whitespace-pre-line italic"
                        title="값 없이 비고만 적힌 항목입니다"
                      >
                        {item.note}
                      </span>
                    )}
                    {item.status === 'draft' && (
                      // 초안은 표시·수집만 — 검색 판정에 안 쓰인다는 것을 읽는 사람이 알아야 한다.
                      <span
                        className="text-muted-foreground ml-1 text-xs"
                        title="초안 속성 — 시스템 관리자가 정식으로 올리기 전입니다"
                      >
                        초안
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </TableCell>
        )
      })}
    </>
  )
}

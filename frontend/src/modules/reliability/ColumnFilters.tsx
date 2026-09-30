/**
 * 속성 **아닌** 열로 거르기 — 이름 · 목적 · 시험 항목 · 보유 장비.
 *
 * 속성에는 조건 문법(`키<연산>값`)이 있는데 이 넷에는 없었다. 그래서 1784건에서 「목적을
 * 안 적은 줄」 을 찾으려면 서른여섯 쪽을 눈으로 훑어야 했고, 그러면 아무도 안 찾는다 —
 * **화면이 열로 보여 주는 것은 열로 거를 수 있어야 한다.**
 *
 * 생김새는 속성 열과 **같다**(머리글의 깔때기, 걸리면 색이 찬다). 같은 표에서 어떤 열은
 * 깔때기로 거르고 어떤 열은 못 거르면, 사람은 못 거르는 열을 눌러 보고 나서야 안다.
 *
 * 「없음」 을 묻는 자리가 셋이다 — 목적 안 적음 · 시험 항목 미지정 · **돌릴 장비 없음.**
 * 마지막 것은 목록이 이미 노란 「0대」 로 적고 있는 바로 그 줄인데, 그것으로 좁힐 길이
 * 없었다. 「미지정」 과는 다르다: 앞은 항목을 아직 안 이은 것이고, 뒤는 이었는데 그 항목이
 * 되는 장비가 그 사업부에 없는 것이다. 해야 할 일이 다르다.
 *
 * **거르기는 서버가 한다.** 화면이 한 쪽을 받아 놓고 거르면 상한을 넘는 순간 나머지가
 * 조용히 빠지고, 그때 표는 「그 조건에 맞는 것이 이것뿐」 이라고 거짓말한다.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Filter, X } from 'lucide-react'

import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover'

/** 서버가 받는 이름 그대로 — 주소에 그대로 실려 링크가 된다. */
export const ROW_KEYS = ['name', 'purpose', 'test_item', 'equipment'] as const
export type RowKey = (typeof ROW_KEYS)[number]
export type RowFilters = Partial<Record<RowKey, string>>

/** 「안 적힘」 을 묻는 말 — 목록 API 가 이미 `test_item=none` 으로 쓰고 있다. */
export const NONE = 'none'

const SAID: Record<RowKey, string> = {
  name: '시험명',
  purpose: '목적',
  test_item: '시험 항목',
  equipment: '보유 장비',
}

/** 「purpose=none」 을 「목적 안 적음」 으로. 칩이 조건을 사람 말로 적어야 뺄 수 있다. */
export function describeRow(key: RowKey, value: string): string {
  if (key === 'equipment') return '보유 장비 없음'
  if (value === NONE) return key === 'purpose' ? '목적 미입력' : '시험 항목 미지정'
  return `${SAID[key]} 포함: ${value}`
}

export interface RowFilterState {
  value: RowFilters
  set: (key: RowKey, next: string) => void
  clear: (key: RowKey) => void
  count: number
}

/**
 * 조건을 **주소에 싣는다.** 좁혀 놓은 화면을 옆 사람에게 링크로 건넬 수 있어야 하고,
 * 「목적을 안 적은 시험」 같은 물음은 한 번 만들면 계속 쓴다 — 화면 안에만 두면 매번 다시 건다.
 */
export function useRowFilters(): RowFilterState {
  const [params, setParams] = useSearchParams()
  const value = useMemo(() => {
    const out: RowFilters = {}
    for (const key of ROW_KEYS) {
      const got = params.get(key)
      if (got) out[key] = got
    }
    return out
  }, [params])

  const set = useCallback(
    (key: RowKey, next: string) => {
      setParams(
        (before) => {
          const moved = new URLSearchParams(before)
          if (next) moved.set(key, next)
          else moved.delete(key)
          return moved
        },
        // 거르기는 **되돌아갈 자리가 아니다** — 뒤로 가기가 조건 하나씩 풀리면 못 나간다.
        { replace: true },
      )
    },
    [setParams],
  )

  return {
    value,
    set,
    clear: (key) => set(key, ''),
    count: Object.keys(value).length,
  }
}

/** 머리글 한 칸 — 이름과 깔때기. 팝오버 안은 열마다 다르므로 부르는 쪽이 채운다. */
export function HeadFilter({
  label,
  active,
  onClear,
  children,
}: {
  label: string
  active: boolean
  onClear: () => void
  children: (close: () => void) => React.ReactNode
}) {
  const [open, setOpen] = useState(false)
  return (
    <div className="flex items-center gap-1">
      <span className="truncate">{label}</span>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-label={`${label} 필터`}
            // 걸린 열은 **눈에 띈다** — 안 그러면 왜 스무 건만 보이는지 못 찾는다.
            className={`rounded p-0.5 ${
              active ? 'text-primary' : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <Filter className={`size-3.5 ${active ? 'fill-current' : ''}`} />
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-64 space-y-2 p-2">
          <p className="text-sm font-medium">{label}</p>
          {/* **필터의 방향을 적는다** — 「미입력」 을 걸었는데 목록이 그대로면 사람은
              고장으로 읽는다. 실제로는 전부가 미입력이라 전부가 조건에 맞은 것이다. */}
          <p className="text-muted-foreground text-xs">조건에 맞는 항목만 표시됩니다.</p>
          {children(() => setOpen(false))}
          {active && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                onClear()
                setOpen(false)
              }}
            >
              이 열 필터 해제
            </Button>
          )}
        </PopoverContent>
      </Popover>
    </div>
  )
}

/** 글자로 거르는 칸 — 치고 엔터, 또는 단추. */
export function FilterText({
  value,
  placeholder,
  onApply,
}: {
  value: string
  placeholder: string
  onApply: (next: string) => void
}) {
  const [text, setText] = useState(value)
  // 밖에서 조건이 바뀌면(칩을 뺐다) 칸도 따라간다 — 안 그러면 지운 글자가 남아 있다.
  useEffect(() => setText(value), [value])
  return (
    <div className="flex gap-1">
      <Input
        autoFocus
        value={text}
        className="h-8 flex-1"
        placeholder={placeholder}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter') onApply(text.trim())
        }}
      />
      <Button size="sm" onClick={() => onApply(text.trim())}>
        필터 적용
      </Button>
    </div>
  )
}

/** 「없음」 하나 — 무엇을 묻는 것인지 한 줄로 적는다. 안 적으면 둘을 헷갈린다. */
export function FilterBlank({
  label,
  hint,
  on,
  onChange,
}: {
  label: string
  hint: string
  on: boolean
  onChange: (next: boolean) => void
}) {
  return (
    <label className="hover:bg-muted flex items-start gap-2 rounded p-1 text-sm">
      <input
        type="checkbox"
        className="mt-1 size-3.5"
        checked={on}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span>
        {label}
        <span className="text-muted-foreground block text-xs">{hint}</span>
      </span>
    </label>
  )
}

/** 걸린 조건을 칩으로 — 열 머리글에서 걸었든 **푸는 자리는 한 곳**이다. */
export function RowFilterChips({ rows }: { rows: RowFilterState }) {
  if (rows.count === 0) return null
  return (
    <ul className="flex flex-wrap items-center gap-1 text-xs">
      {ROW_KEYS.filter((key) => rows.value[key]).map((key) => {
        const said = describeRow(key, rows.value[key] as string)
        return (
          <li
            key={key}
            className="bg-muted flex items-center gap-1 rounded-full py-0.5 pr-1 pl-2"
          >
            {said}
            <button
              type="button"
              aria-label={`${said} 필터 해제`}
              className="hover:bg-background rounded-full p-0.5"
              onClick={() => rows.clear(key)}
            >
              <X className="size-3" />
            </button>
          </li>
        )
      })}
    </ul>
  )
}

/** 「신뢰성 시험」 열 — 이름에 든 글자. */
export function NameHead({ rows }: { rows: RowFilterState }) {
  return (
    <HeadFilter
      label="신뢰성 시험"
      active={Boolean(rows.value.name)}
      onClear={() => rows.clear('name')}
    >
      {(close) => (
        <FilterText
          value={rows.value.name ?? ''}
          placeholder="시험명 검색어"
          onApply={(next) => {
            rows.set('name', next)
            close()
          }}
        />
      )}
    </HeadFilter>
  )
}

/** 「목적」 열 — 든 글자, 또는 **안 적은 줄.** */
export function PurposeHead({ rows }: { rows: RowFilterState }) {
  const blank = rows.value.purpose === NONE
  return (
    <HeadFilter
      label="목적"
      active={Boolean(rows.value.purpose)}
      onClear={() => rows.clear('purpose')}
    >
      {(close) => (
        <>
          {!blank && (
            <FilterText
              value={rows.value.purpose ?? ''}
              placeholder="목적 검색어"
              onApply={(next) => {
                rows.set('purpose', next)
                close()
              }}
            />
          )}
          <FilterBlank
            label="목적 미입력"
            hint="AI 가 등록한 항목은 목적이 비어 있는 경우가 많습니다."
            on={blank}
            onChange={(on) => {
              rows.set('purpose', on ? NONE : '')
              close()
            }}
          />
        </>
      )}
    </HeadFilter>
  )
}

/** 「적용 시험 항목 · 보유 장비」 열 — 한 머리글이 **두 물음**을 받는다. */
export function TestItemHead({ rows }: { rows: RowFilterState }) {
  const blank = rows.value.test_item === NONE
  return (
    <HeadFilter
      label="적용 시험 항목 · 보유 장비"
      active={Boolean(rows.value.test_item || rows.value.equipment)}
      onClear={() => {
        rows.clear('test_item')
        rows.clear('equipment')
      }}
    >
      {(close) => (
        <>
          {!blank && (
            <FilterText
              value={rows.value.test_item ?? ''}
              placeholder="시험 항목명"
              onApply={(next) => {
                rows.set('test_item', next)
                close()
              }}
            />
          )}
          <FilterBlank
            label="시험 항목 미지정"
            hint="시험 항목이 하나도 연결되지 않은 항목 — 장비로 이어지는 연결이 없습니다."
            on={blank}
            onChange={(on) => rows.set('test_item', on ? NONE : '')}
          />
          <FilterBlank
            label="보유 장비 없음"
            hint="시험 항목은 연결했으나 해당 항목을 수행할 장비가 이 사업부에 없는 항목 — 목록의 「0대」 표시입니다."
            on={rows.value.equipment === NONE}
            onChange={(on) => rows.set('equipment', on ? NONE : '')}
          />
        </>
      )}
    </HeadFilter>
  )
}

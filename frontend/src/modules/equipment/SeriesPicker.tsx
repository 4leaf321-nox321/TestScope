/**
 * 계열 고르기 — **서버가 거른다.**
 *
 * 기종 등록 창이 계열 목록을 200개씩 받아 `<Select>` 에 넣고 있었다. 계열은 265개라
 * **65개가 조용히 안 보였다** — 못 찾은 사람은 「계열이 없구나」 하고 새로 만들고, 그러면
 * 같은 계열이 둘이 된다(AGENTS.md: 스물을 넘으면 Select 를 쓰지 않는다). 그래서
 * `ModelPicker` 와 같은 모양으로 타이핑을 서버로 보낸다.
 *
 * 줄마다 제조사·분류·종류(본체/부속)와 **기종 수**를 보인다 — 「6800 Series」 가 둘 뜨면
 * 어느 것이 본체이고 어느 것이 부속 계열인지가 이름만으로는 안 갈린다.
 */

import { useEffect, useState } from 'react'
import { Check, ChevronsUpDown } from 'lucide-react'

import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover'
import { useResource } from '@/shared/hooks/useResource'
import { seriesApi } from '@/modules/equipment/api'
import type { EquipmentSeriesRow } from '@/modules/equipment/api'

const KIND_LABEL: Record<string, string> = {
  main: '본체',
  accessory: '부속',
  sensor: '센서',
  software: '소프트웨어',
}

export function SeriesPicker({
  value,
  onChange,
  id,
}: {
  value: string
  onChange: (seriesId: string, series: EquipmentSeriesRow | null) => void
  id?: string
}) {
  const [open, setOpen] = useState(false)
  const [typed, setTyped] = useState('')
  const [query, setQuery] = useState('')
  const [picked, setPicked] = useState<EquipmentSeriesRow | null>(null)

  // 글자마다 조회하지 않는다 — 타이핑 중에 결과가 요동치면 고르는 손이 미끄러진다.
  useEffect(() => {
    const timer = setTimeout(() => setQuery(typed.trim()), 250)
    return () => clearTimeout(timer)
  }, [typed])

  const page = useResource(() => seriesApi.list({ q: query || undefined, limit: 50 }), [query])
  const rows = page.data?.items ?? []
  const total = page.data?.total ?? 0

  useEffect(() => {
    if (!value) setPicked(null)
  }, [value])

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          // 고른 뒤 두 줄이 되므로 처음부터 그 키로 서 있게 한다 — 고르는 순간 폼이
          // 밀려 내려가지 않게.
          className="h-auto min-h-13 w-full justify-between py-2 font-normal"
        >
          {picked ? (
            <span className="min-w-0 text-left">
              <span className="block truncate">{picked.name_ko || picked.name}</span>
              <span className="text-muted-foreground block truncate text-xs font-normal">
                {[picked.maker, picked.category, KIND_LABEL[picked.kind] ?? picked.kind]
                  .filter(Boolean)
                  .join(' · ')}
              </span>
            </span>
          ) : (
            <span className="text-muted-foreground">계열 고르기</span>
          )}
          <ChevronsUpDown className="size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
        <div className="border-b p-2">
          <Input
            autoFocus
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            placeholder="계열명·한글명 또는 제조사"
          />
        </div>

        {/* **키를 고정한다.** 줄 수에 따라 늘었다 줄면 누르려던 줄이 손가락 아래에서 옮겨 간다. */}
        <ul className="h-72 overflow-y-auto py-1">
          {rows.map((one) => (
            <li key={one.id}>
              <button
                type="button"
                className="hover:bg-muted flex w-full items-start gap-2 px-3 py-2 text-left text-sm"
                onClick={() => {
                  setPicked(one)
                  onChange(one.id, one)
                  setOpen(false)
                }}
              >
                <Check
                  className={`mt-0.5 size-4 shrink-0 ${value === one.id ? 'opacity-100' : 'opacity-0'}`}
                />
                <span className="min-w-0 flex-1">
                  <span className="font-medium">{one.name_ko || one.name}</span>
                  <span className="text-muted-foreground block truncate text-xs">
                    {[one.maker, one.category, KIND_LABEL[one.kind] ?? one.kind]
                      .filter(Boolean)
                      .join(' · ') || '—'}
                  </span>
                </span>
                <span className="text-muted-foreground shrink-0 text-xs">
                  {one.model_count === 0 ? '기종 없음' : `기종 ${one.model_count}`}
                </span>
              </button>
            </li>
          ))}
          {rows.length === 0 && (
            <li className="text-muted-foreground px-3 py-6 text-center text-sm">
              {query
                ? '찾는 계열이 없습니다. 없으면 계열을 먼저 만듭니다.'
                : '이름의 일부를 입력하세요.'}
            </li>
          )}
        </ul>

        {/* **자리를 늘 차지한다.** 나타났다 사라지면 창 키가 그만큼 뛴다. */}
        <p className="text-muted-foreground h-9 border-t px-3 py-2 text-xs">
          {total === 0
            ? ' '
            : total > rows.length
              ? `${total}건 중 ${rows.length}건. 더 자세히 입력하세요.`
              : `계열 ${total}건`}
        </p>
      </PopoverContent>
    </Popover>
  )
}

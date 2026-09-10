/**
 * 기종 고르기 — **서버가 거른다. 계열로 좁힐 수 있다.**
 *
 * ## 목록을 통째로 받아 두지 않는다
 *
 * 카탈로그가 563기종이고 서버 상한은 한 번에 200이라, 받아 두는 방식은 **363기종을
 * 조용히 안 보여 준다** — 못 찾은 사람은 「카탈로그에 없구나」 하고 빈 칸으로
 * 저장한다. 실제로 그랬다. 그래서 타이핑을 서버로 보낸다.
 *
 * ## 계열로 한 번 좁힌다
 *
 * 사람이 아는 것은 대개 **계열까지**다 — 「인스트론 6800 시리즈」 는 알아도
 * `68FM-300` 은 라벨을 봐야 안다. 검색 결과에서 계열을 누르면 그 계열의 기종이
 * **전부** 뜬다: 검색어와 안 맞는 기종까지 보여야 라벨과 대조할 수 있다.
 *
 * 반대로 기종명을 아는 사람은 그냥 치면 된다 — 두 길을 다 열어 둔다.
 */

import { useEffect, useState } from 'react'
import { Check, ChevronRight, ChevronsUpDown, X } from 'lucide-react'

import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover'
import { useResource } from '@/shared/hooks/useResource'
import { catalogApi, seriesApi } from '@/modules/equipment/api'
import type { EquipmentModelRow } from '@/modules/equipment/api'

export function ModelPicker({
  value,
  onChange,
  id,
}: {
  value: string
  onChange: (modelId: string, model: EquipmentModelRow | null) => void
  id?: string
}) {
  const [open, setOpen] = useState(false)
  const [typed, setTyped] = useState('')
  const [query, setQuery] = useState('')
  const [picked, setPicked] = useState<EquipmentModelRow | null>(null)
  /** 좁혀 둔 계열. 정해지면 **그 계열의 기종이 전부** 뜬다. */
  const [series, setSeries] = useState<{ id: string; name: string } | null>(null)
  /** 무엇을 훑고 있나 — 기종이냐 계열이냐.
   *
   * **두 길을 다 열어 둔다.** 라벨의 기종명을 아는 사람은 그것을 치면 되고,
   * 「인스트론 6800 시리즈」 까지만 아는 사람은 계열부터 고른다. 실무에서는
   * 뒤쪽이 더 흔하다 — 기종명은 장비 앞에 가야 읽을 수 있다. */
  const [mode, setMode] = useState<'model' | 'series'>('model')

  // 글자마다 조회하지 않는다 — 타이핑 중에 결과가 요동치면 고르는 손이 미끄러진다.
  useEffect(() => {
    const timer = setTimeout(() => setQuery(typed.trim()), 250)
    return () => clearTimeout(timer)
  }, [typed])

  const page = useResource(
    () =>
      catalogApi.list({
        q: query || undefined,
        seriesId: series?.id,
        limit: 50,
      }),
    [query, series?.id],
  )
  const seriesPage = useResource(
    () =>
      mode === 'series'
        ? seriesApi.list({ q: query || undefined, kind: 'main', limit: 50 })
        : Promise.resolve(null),
    [query, mode],
  )
  const rows = page.data?.items ?? []
  const total = page.data?.total ?? 0
  const seriesRows = seriesPage.data?.items ?? []

  function narrow(id: string, name: string) {
    setSeries({ id, name })
    setMode('model')
    // **검색어를 비운다.** 「6800」 으로 찾아 들어왔는데 그 글자가 기종명에 없다고
    // 목록이 비면, 사람은 계열을 잘못 골랐다고 읽는다.
    setTyped('')
    setQuery('')
  }

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
          // 고른 뒤에는 두 줄이 되므로 키를 고정하지 않는다 — 대신 **처음부터
          // 그 키**로 서 있게 해서, 고르는 순간 폼이 밀려 내려가지 않게 한다.
          className="h-auto min-h-13 w-full justify-between py-2 font-normal"
        >
          {picked ? (
            // **고른 것이 무엇인지 두 줄로 보인다.** 제조사·계열·기종을 한 줄에
            // 이어 붙이면 잘리고, 잘리는 쪽은 늘 뒤 — 즉 기종명이다.
            <span className="min-w-0 text-left">
              <span className="block truncate">{picked.name}</span>
              <span className="text-muted-foreground block truncate text-xs font-normal">
                {[picked.maker, picked.series_name].filter(Boolean).join(' · ')}
              </span>
            </span>
          ) : (
            <span className="text-muted-foreground">카탈로그에서 찾기</span>
          )}
          <ChevronsUpDown className="size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
        {series ? (
          // 좁혀 둔 계열. **무엇으로 좁혔는지 보이고, 한 번에 풀린다** — 안 보이면
          // 목록이 짧은 것을 「카탈로그에 없다」 로 읽는다.
          <div className="bg-muted/50 flex h-11 items-center justify-between gap-2 border-b px-2">
            <span className="truncate text-sm">
              <span className="text-muted-foreground">계열 </span>
              <span className="font-medium">{series.name}</span>
            </span>
            <Button type="button" size="sm" variant="ghost" onClick={() => setSeries(null)}>
              <X className="size-4" />
              해제
            </Button>
          </div>
        ) : (
          // **두 길을 다 열어 둔다.** 기종명을 아는 사람과 계열까지만 아는 사람이
          // 둘 다 있고, 실무에서는 뒤쪽이 더 흔하다.
          <div className="flex h-11 items-center gap-1 border-b p-1">
            {(
              [
                ['model', '기종으로 찾기'],
                ['series', '계열부터 고르기'],
              ] as const
            ).map(([value, label]) => (
              <Button
                key={value}
                type="button"
                size="sm"
                variant={mode === value ? 'secondary' : 'ghost'}
                className="flex-1"
                onClick={() => setMode(value)}
              >
                {label}
              </Button>
            ))}
          </div>
        )}

        {/* 계열을 좁힌 뒤에도 입력은 남는다 — 열두 기종짜리 계열에서는 그 안에서
            한 번 더 좁히는 편이 빠르다. */}
        <div className="border-b p-2">
          <Input
            autoFocus
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            placeholder={
              series
                ? '이 계열 안에서 찾기'
                : mode === 'series'
                  ? '계열명·한글명 또는 제조사'
                  : '기종명·계열명 또는 제조사'
            }
          />
        </div>

        {/* **키를 고정한다.** 줄 수에 따라 늘었다 줄면 창이 통째로 뛰고, 그때
            누르려던 줄이 손가락 아래에서 옮겨 간다. */}
        <ul className="h-72 overflow-y-auto py-1">
          {mode === 'series' && !series
            ? seriesRows.map((one) => (
                <li key={one.id}>
                  <button
                    type="button"
                    className="hover:bg-muted flex w-full items-start justify-between gap-2 px-3 py-2 text-left text-sm"
                    onClick={() => narrow(one.id, one.name)}
                  >
                    <span className="min-w-0">
                      <span className="font-medium">{one.name_ko || one.name}</span>
                      <span className="text-muted-foreground block truncate text-xs">
                        {[one.maker, one.category].filter(Boolean).join(' · ') || '—'}
                      </span>
                    </span>
                    {/* **기종이 0 이면 고를 것이 없다.** 눌러 들어간 뒤에 알면
                        되돌아 나와야 한다. */}
                    <span
                      className={`shrink-0 text-xs ${
                        one.model_count === 0 ? 'text-amber-600' : 'text-muted-foreground'
                      }`}
                    >
                      {one.model_count === 0 ? '기종 없음' : `기종 ${one.model_count}`}
                      <ChevronRight className="ml-0.5 inline size-3" />
                    </span>
                  </button>
                </li>
              ))
            : rows.map((one) => (
                <li key={one.id} className="flex items-start">
                  <button
                    type="button"
                    className="hover:bg-muted flex min-w-0 flex-1 items-start gap-2 px-3 py-2 text-left text-sm"
                    onClick={() => {
                      setPicked(one)
                      onChange(one.id, one)
                      setOpen(false)
                    }}
                  >
                    <Check
                      className={`mt-0.5 size-4 shrink-0 ${
                        value === one.id ? 'opacity-100' : 'opacity-0'
                      }`}
                    />
                    <span className="min-w-0">
                      <span className="font-medium">{one.name}</span>
                      <span className="text-muted-foreground block truncate text-xs">
                        {[one.maker, one.form_factor].filter(Boolean).join(' · ') || '—'}
                      </span>
                    </span>
                  </button>
                  {/* **계열을 눌러 좁힌다.** 그 안의 어느 기종인지는 라벨을 봐야
                      아는데, 그때 계열의 기종이 전부 떠야 대조할 수 있다. */}
                  {!series && (
                    <button
                      type="button"
                      className="text-muted-foreground hover:bg-muted hover:text-foreground shrink-0 px-2 py-2 text-xs"
                      title={`${one.series_name} 의 기종만 보기`}
                      onClick={() => narrow(one.series_id, one.series_name)}
                    >
                      {one.series_name}
                      <ChevronRight className="ml-0.5 inline size-3" />
                    </button>
                  )}
                </li>
              ))}

          {(mode === 'series' && !series ? seriesRows : rows).length === 0 && (
            <li className="text-muted-foreground px-3 py-6 text-center text-sm">
              {series && !query
                ? '이 계열에 기종이 없습니다. 계열 화면에서 먼저 기종을 만드세요.'
                : query
                  ? '찾는 것이 없습니다. 카탈로그에 없으면 비워 두고 나중에 이을 수 있습니다.'
                  : '이름의 일부를 입력하세요.'}
            </li>
          )}
        </ul>

        {/* **자리를 늘 차지한다.** 나타났다 사라지면 창 키가 그만큼 뛴다. */}
        <p className="text-muted-foreground h-9 border-t px-3 py-2 text-xs">
          {(() => {
            const browsing = mode === 'series' && !series
            const shown = browsing ? seriesRows.length : rows.length
            const all = browsing ? (seriesPage.data?.total ?? 0) : total
            if (all === 0) return ' '
            if (all > shown) return `${all}건 중 ${shown}건. 더 자세히 입력하세요.`
            return browsing ? `계열 ${all}건` : `기종 ${all}건`
          })()}
        </p>
      </PopoverContent>
    </Popover>
  )
}

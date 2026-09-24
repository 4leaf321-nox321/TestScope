/**
 * 검색형 고르기 — **목록이 길어지면 드롭다운으로는 못 찾는다.**
 *
 * 시험 항목 87종, 사양 정의 209종, 장비 분류 108종. 평범한 `<Select>` 는 그것을
 * 통째로 펼쳐 놓고 사람에게 눈으로 찾으라고 한다 — 스물이 넘으면 그 일은 실패한다.
 * 못 찾은 사람은 **없다고 결론 내리고 새로 만든다**, 그러면 같은 값이 둘로 갈린다.
 *
 * ## 두 가지 길
 *
 *     피커    이름의 일부를 알 때. 치면 좁혀진다
 *     상세    무엇이 있는지 모를 때. 큰 창에서 **전부** 훑는다
 *
 * 앞의 것만 두면 「무엇을 칠지」 를 모르는 사람이 막힌다. 뒤의 것만 두면 아는
 * 사람이 매번 큰 창을 연다.
 */

import { useEffect, useMemo, useState } from 'react'
import { Check, ChevronsUpDown, List, Search } from 'lucide-react'

import { Button } from '@/shared/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
import { Input } from '@/shared/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover'

/** 고를 수 있는 한 줄. 화면이 무엇을 그릴지 여기서 정해진다. */
export interface PickerOption {
  id: string
  label: string
  /** 아래 줄에 흐리게. 무엇으로 구별하는지 — 제조사·그룹·단위 같은 것. */
  detail?: string | null
  /** 오른쪽 끝에. 「이미 있음」 이나 쓰임 수처럼 **고르기 전에 알아야 할 것.** */
  badge?: string | null
  /** 고를 수 없는 줄. 이유를 badge 에 적는다 — 비활성만 시키고 말 안 하면 버그로 읽힌다. */
  disabled?: boolean
}

/** 검색어로 거른다. **비교키로 본다** — 「UTM」 과 「utm」 이 다르면 안 된다. */
function matches(option: PickerOption, query: string): boolean {
  if (!query) return true
  const needle = query.trim().toLowerCase()
  return (
    option.label.toLowerCase().includes(needle) ||
    (option.detail ?? '').toLowerCase().includes(needle)
  )
}

function Row({
  option,
  picked,
  onPick,
}: {
  option: PickerOption
  picked: boolean
  onPick: () => void
}) {
  return (
    <button
      type="button"
      disabled={option.disabled}
      className="hover:bg-muted flex w-full items-start gap-2 px-3 py-2 text-left text-sm disabled:opacity-50"
      onClick={onPick}
    >
      <Check className={`mt-0.5 size-4 shrink-0 ${picked ? 'opacity-100' : 'opacity-0'}`} />
      <span className="min-w-0 flex-1">
        <span className="block truncate font-medium">{option.label}</span>
        {option.detail && (
          <span className="text-muted-foreground block truncate text-xs">{option.detail}</span>
        )}
      </span>
      {option.badge && (
        <span className="text-muted-foreground shrink-0 text-xs">{option.badge}</span>
      )}
    </button>
  )
}

export function SearchablePicker({
  options,
  value,
  onChange,
  placeholder = '선택',
  searchPlaceholder = '이름의 일부를 입력하십시오',
  detailTitle,
  detailHint,
  id,
  className,
}: {
  options: PickerOption[]
  value: string
  onChange: (id: string) => void
  placeholder?: string
  searchPlaceholder?: string
  /** 「상세」 창의 제목. 없으면 상세 단추를 안 단다. */
  detailTitle?: string
  detailHint?: string
  id?: string
  className?: string
}) {
  const [open, setOpen] = useState(false)
  const [detail, setDetail] = useState(false)
  const [query, setQuery] = useState('')
  const [detailQuery, setDetailQuery] = useState('')

  const picked = options.find((one) => one.id === value) ?? null
  const shown = useMemo(() => options.filter((one) => matches(one, query)), [options, query])
  const inDetail = useMemo(
    () => options.filter((one) => matches(one, detailQuery)),
    [options, detailQuery],
  )

  // 창을 닫으면 검색어를 비운다 — 다시 열었을 때 지난 검색이 남아 있으면,
  // 짧은 목록을 「없다」 로 읽는다.
  useEffect(() => {
    if (!open) setQuery('')
  }, [open])
  useEffect(() => {
    if (!detail) setDetailQuery('')
  }, [detail])

  function choose(next: string) {
    onChange(next)
    setOpen(false)
    setDetail(false)
  }

  return (
    <div className={`flex items-center gap-1 ${className ?? ''}`}>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            id={id}
            type="button"
            variant="outline"
            className="min-w-0 flex-1 justify-between font-normal"
          >
            <span className={`truncate ${picked ? '' : 'text-muted-foreground'}`}>
              {picked ? picked.label : placeholder}
            </span>
            <ChevronsUpDown className="size-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
          <div className="border-b p-2">
            <Input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={searchPlaceholder}
            />
          </div>
          {/* **키를 고정한다.** 줄 수에 따라 늘었다 줄면 누르려던 줄이 손가락
              아래에서 옮겨 간다. */}
          <ul className="h-64 overflow-y-auto py-1">
            {shown.length === 0 && (
              <li className="text-muted-foreground px-3 py-6 text-center text-sm">
                검색 결과가 없습니다.
              </li>
            )}
            {shown.map((one) => (
              <li key={one.id}>
                <Row option={one} picked={one.id === value} onPick={() => choose(one.id)} />
              </li>
            ))}
          </ul>
          <p className="text-muted-foreground h-9 border-t px-3 py-2 text-xs">
            {options.length}개 중 {shown.length}개
          </p>
        </PopoverContent>
      </Popover>

      {detailTitle && (
        // **무엇이 있는지 모를 때 여는 자리.** 치는 것만 두면 「무엇을 칠지」 를
        // 모르는 사람이 막힌다.
        <Button
          type="button"
          variant="outline"
          size="icon"
          title={`${detailTitle} 전체 보기`}
          onClick={() => setDetail(true)}
        >
          <List className="size-4" />
        </Button>
      )}

      {detailTitle && (
        <Dialog open={detail} onOpenChange={setDetail}>
          {/* **크게 연다.** 전부 훑는 것이 목적인 창이라, 좁으면 그 목적이 안 선다. */}
          <DialogContent className="sm:max-w-4xl">
            <DialogHeader>
              <DialogTitle>{detailTitle}</DialogTitle>
              <DialogDescription>
                {detailHint ?? '전체 목록입니다. 골라서 닫으면 위 칸에 들어갑니다.'}
              </DialogDescription>
            </DialogHeader>

            <div className="relative">
              <Search className="text-muted-foreground absolute top-2.5 left-2.5 size-4" />
              <Input
                value={detailQuery}
                onChange={(event) => setDetailQuery(event.target.value)}
                placeholder={searchPlaceholder}
                className="pl-8"
              />
            </div>

            {/* 두 칸으로 벌린다 — 209종을 한 줄씩 세우면 굴리는 거리가 너무 멀다. */}
            <ul className="grid max-h-[52vh] grid-cols-1 gap-x-4 overflow-y-auto sm:grid-cols-2">
              {inDetail.length === 0 && (
                <li className="text-muted-foreground col-span-full py-10 text-center text-sm">
                  검색 결과가 없습니다.
                </li>
              )}
              {inDetail.map((one) => (
                <li key={one.id} className="border-b last:border-b-0">
                  <Row option={one} picked={one.id === value} onPick={() => choose(one.id)} />
                </li>
              ))}
            </ul>

            <DialogFooter>
              <span className="text-muted-foreground mr-auto self-center text-xs">
                {options.length}개 중 {inDetail.length}개
              </span>
              <Button type="button" variant="outline" onClick={() => setDetail(false)}>
                닫기
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}

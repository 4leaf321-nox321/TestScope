/**
 * 카탈로그 목록(계열·기종)의 **열마다 거르기.**
 *
 * 머리글 바로 아래에 한 줄로 둔다 — 어느 열을 거르고 있는지가 그 열 밑에 보여야
 * 한다. 위에 따로 모아 두면 「이 목록이 왜 짧지」 를 사람이 되짚어야 하고, 되짚기는
 * 대개 실패한다. 보유 장비 목록과 같은 자리, 같은 방식이다.
 *
 * ## 고를 수 있는 것은 **카탈로그에 있는 값뿐**이다
 *
 * 온톨로지 전체를 펼치면 제조사 축 수백 종 중 79종만 계열이 가리키고, 나머지는
 * 골라도 0 건인 선택지가 된다 — 한 번 겪으면 사람은 거르기를 안 믿는다. 그래서
 * 서버가 「지금 카탈로그에 있는 값과 그 수」 를 준다(`/filter-options`).
 *
 * ## 스물을 넘으면 드롭다운을 안 쓴다
 *
 * 제조사 79 · 분류 87 · 계열 198 이다. 접어 두면 그날 못 찾고, 못 찾은 사람은
 * 없다고 결론 내린다(AGENTS.md). 손에 꼽는 것(종류 넷 · 상태 둘)만 드롭다운이다.
 *
 * ## 거르는 것은 서버다
 *
 * 한 쪽을 받아 놓고 화면이 거르면, 상한을 넘는 순간 나머지가 조용히 빠진다 — 그리고
 * 그때 목록은 「그 조건에 맞는 것이 이것뿐」 이라고 거짓말한다.
 */

import { SearchablePicker } from '@/shared/components/SearchablePicker'
import { Input } from '@/shared/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import type { CatalogFilterOptions } from '@/modules/equipment/api'

/** 계열 목록이 들고 있는 거르기. 빈 문자열은 **안 거른다**는 뜻이다. */
export interface SeriesFilterState {
  name: string
  kind: string
  makerTermId: string
  categoryTermId: string
  status: string
  /** `none` 이면 기종이 없는 계열만. */
  models: string
  /** `none` 이면 시험 항목이 없는 계열만. */
  testItem: string
  /** `owned` 면 보유한 것만. */
  owned: string
}

export const EMPTY_SERIES_FILTERS: SeriesFilterState = {
  name: '',
  kind: '',
  makerTermId: '',
  categoryTermId: '',
  status: '',
  models: '',
  testItem: '',
  owned: '',
}

/** 기종 목록이 들고 있는 거르기. */
export interface ModelFilterState {
  name: string
  seriesId: string
  makerTermId: string
  categoryTermId: string
  /** `none` 사양이 빈 것 · `uncertain` 원본 확인이 필요한 것. */
  spec: string
  testItem: string
  owned: string
}

export const EMPTY_MODEL_FILTERS: ModelFilterState = {
  name: '',
  seriesId: '',
  makerTermId: '',
  categoryTermId: '',
  spec: '',
  testItem: '',
  owned: '',
}

/** 몇 개 조건으로 걸렀나. 계열과 기종이 같은 셈을 쓴다 — 빈 문자열이 「안 거른다」 다. */
export function activeCount(filters: SeriesFilterState | ModelFilterState): number {
  return Object.values(filters).filter((one) => one !== '').length
}

/** 「보유」 열의 선택지. 카탈로그 714기종 중 우리가 가진 것은 손에 꼽는다 —
 *  **그 손잡이가 없으면 「우리 것」 을 볼 방법이 없다.** */
const OWNED_OPTIONS = [{ value: 'owned', label: '보유한 것만' }]

/** 드롭다운 한 칸. 빈 값을 고르면 거르기가 풀린다 — 푸는 자리가 목록 안에 있어야 한다. */
function Pick({
  value,
  onChange,
  placeholder,
  options,
}: {
  value: string
  onChange: (next: string) => void
  placeholder: string
  options: { value: string; label: string }[]
}) {
  return (
    <Select
      value={value || '전체'}
      onValueChange={(next) => onChange(next === '전체' ? '' : next)}
    >
      <SelectTrigger className="h-8 w-full text-xs">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="전체">{placeholder}</SelectItem>
        {options.map((one) => (
          <SelectItem key={one.value} value={one.value}>
            {one.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

/** 서버가 준 선택지를 피커가 읽는 모양으로. 수를 함께 적는다 — 골라도 0 건인
 *  선택지가 섞이면 사람은 거르기를 안 믿는다. */
function asOptions(rows: CatalogFilterOptions['makers'] | undefined, unit: string) {
  return (rows ?? []).map((one) => ({
    id: one.value,
    label: one.label,
    // 분류라면 어느 군인지, 군이라면 「묶음 · N개 분류」 — 군을 고르면 아래가 다 걸린다.
    detail: one.detail ?? null,
    badge: `${one.count}${unit}`,
  }))
}

export function SeriesFilters({
  value,
  onChange,
  options,
}: {
  value: SeriesFilterState
  onChange: (next: SeriesFilterState) => void
  options: CatalogFilterOptions | null
}) {
  const set = (patch: Partial<SeriesFilterState>) => onChange({ ...value, ...patch })

  return (
    <>
      {/* 이름과 종류를 한 칸에 둔다 — 종류는 이 열 안에 배지로 붙는 값이라,
          열을 따로 만들면 본체가 186줄 같은 글자를 반복한다. */}
      <td className="p-1">
        <div className="flex gap-1">
          <Input
            value={value.name}
            onChange={(event) => set({ name: event.target.value })}
            placeholder="계열명"
            className="h-8 flex-1 text-xs"
          />
          <div className="w-24 shrink-0">
            <Pick
              value={value.kind}
              onChange={(next) => set({ kind: next })}
              placeholder="종류"
              options={(options?.kinds ?? []).map((one) => ({
                value: one.value,
                label: `${one.label} ${one.count}`,
              }))}
            />
          </div>
        </div>
      </td>
      <td className="p-1">
        {/* 79종. 치면서 찾는다. */}
        <SearchablePicker
          value={value.makerTermId}
          onChange={(next) => set({ makerTermId: next })}
          options={asOptions(options?.makers, '계열')}
          placeholder="제조사 전체"
          detailTitle="제조사"
          detailHint="카탈로그에 계열이 있는 제조사만 나옵니다."
          className="w-full"
        />
      </td>
      <td className="p-1">
        {/* 87종. */}
        <SearchablePicker
          value={value.categoryTermId}
          onChange={(next) => set({ categoryTermId: next })}
          options={asOptions(options?.categories, '계열')}
          placeholder="분류 전체"
          detailTitle="장비 분류"
          detailHint="카탈로그에 계열이 있는 분류만 나옵니다. 묶음을 고르면 그 아래 분류가 다 걸립니다."
          className="w-full"
        />
      </td>
      <td className="p-1">
        {/* **0 이면 아무도 이 계열을 가리킬 수 없다** — 보유 장비가 가리키는 것은
            계열이 아니라 기종이다. 그래서 「없음만」 이 손잡이가 된다. */}
        <Pick
          value={value.models}
          onChange={(next) => set({ models: next })}
          placeholder="기종 전체"
          options={[{ value: 'none', label: '기종 없음만' }]}
        />
      </td>
      <td className="p-1">
        {/* 시험 항목이 0 이면 이 계열의 기종으로 등록한 장비가 **검색에 안 걸린다.** */}
        <Pick
          value={value.testItem}
          onChange={(next) => set({ testItem: next })}
          placeholder="시험 항목 전체"
          options={[{ value: 'none', label: '미등록만' }]}
        />
      </td>
      <td className="p-1">
        <Pick
          value={value.owned}
          onChange={(next) => set({ owned: next })}
          placeholder="보유 전체"
          options={OWNED_OPTIONS}
        />
      </td>
      <td className="p-1">
        <Pick
          value={value.status}
          onChange={(next) => set({ status: next })}
          placeholder="상태 전체"
          options={(options?.statuses ?? []).map((one) => ({
            value: one.value,
            label: `${one.label} ${one.count}`,
          }))}
        />
      </td>
    </>
  )
}

export function ModelFilters({
  value,
  onChange,
  options,
}: {
  value: ModelFilterState
  onChange: (next: ModelFilterState) => void
  options: CatalogFilterOptions | null
}) {
  const set = (patch: Partial<ModelFilterState>) => onChange({ ...value, ...patch })

  return (
    <>
      {/* 계열은 이 열 안에 부제로 붙는 값이라 같은 칸에서 거른다. */}
      <td className="p-1">
        <div className="flex gap-1">
          <Input
            value={value.name}
            onChange={(event) => set({ name: event.target.value })}
            placeholder="기종명"
            className="h-8 flex-1 text-xs"
          />
          <div className="w-32 shrink-0">
            {/* 198종. 드롭다운으로 두면 그날 못 찾는다. */}
            <SearchablePicker
              value={value.seriesId}
              onChange={(next) => set({ seriesId: next })}
              options={asOptions(options?.series, '기종')}
              placeholder="계열 전체"
              detailTitle="장비 계열"
              detailHint="기종이 있는 계열만 나옵니다."
              className="w-full"
            />
          </div>
        </div>
      </td>
      <td className="p-1">
        <SearchablePicker
          value={value.categoryTermId}
          onChange={(next) => set({ categoryTermId: next })}
          options={asOptions(options?.categories, '기종')}
          placeholder="분류 전체"
          detailTitle="장비 분류"
          detailHint="카탈로그에 기종이 있는 분류만 나옵니다. 묶음을 고르면 그 아래 분류가 다 걸립니다."
          className="w-full"
        />
      </td>
      <td className="p-1">
        <SearchablePicker
          value={value.makerTermId}
          onChange={(next) => set({ makerTermId: next })}
          options={asOptions(options?.makers, '기종')}
          placeholder="제조사 전체"
          detailTitle="제조사"
          detailHint="카탈로그에 기종이 있는 제조사만 나옵니다."
          className="w-full"
        />
      </td>
      <td className="p-1">
        {/* **사양 없음과 원본 확인 필요는 할 일이 다르다.** 앞엣것은 채우는 일이고,
            뒤엣것은 원본을 열어 맞는지 보는 일이다 — 뭉치면 둘 다 안 된다. */}
        <Pick
          value={value.spec}
          onChange={(next) => set({ spec: next })}
          placeholder="사양 전체"
          options={[
            { value: 'none', label: '사양 없음만' },
            { value: 'uncertain', label: '원본 확인 필요' },
          ]}
        />
      </td>
      <td className="p-1">
        <Pick
          value={value.testItem}
          onChange={(next) => set({ testItem: next })}
          placeholder="시험 항목 전체"
          options={[{ value: 'none', label: '미등록만' }]}
        />
      </td>
      <td className="p-1">
        <Pick
          value={value.owned}
          onChange={(next) => set({ owned: next })}
          placeholder="보유 전체"
          options={OWNED_OPTIONS}
        />
      </td>
    </>
  )
}

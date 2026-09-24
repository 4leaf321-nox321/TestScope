/**
 * 보유 장비 목록의 **열마다 거르기.**
 *
 * 머리글 바로 아래에 한 줄로 둔다 — 어느 열을 거르고 있는지가 그 열 밑에 보여야
 * 한다. 위에 따로 모아 두면 「이 목록이 왜 짧지」 를 사람이 되짚어야 하고, 되짚기는
 * 대개 실패한다.
 *
 * ## 고를 수 있는 것은 **목록에 있는 값뿐**이다
 *
 * 기준정보 전체를 펼치면 분류 108종 중 100종이 골라도 0 건인 선택지가 된다 — 한 번
 * 겪으면 사람은 거르기를 안 믿는다. 그래서 서버가 「지금 목록에 있는 값과 그 수」 를
 * 준다(`/equipment/filter-options`).
 *
 * 부서도 거기서 받는다. `/workspaces` 는 **내 소속만** 주는데 목록에는 열린 부서의
 * 장비가 함께 보이므로, 그것으로 거르게 두면 보이는데 못 거르는 부서가 생긴다.
 *
 * ## 고르는 칸은 **거의 다 피커**다
 *
 * 분류 108종·시험 항목 87종은 물론이고, 부서와 거점도 조직이 커지면 수백이 된다 —
 * 드롭다운으로 두면 그날 못 찾는다(AGENTS.md). 손에 꼽는 것(상태 여섯·교정 넷)만
 * 드롭다운이다.
 *
 * 자산번호와 이름은 **각자 친다.** 한 칸으로 합치면 번호를 치는 사람이 이름에 걸린
 * 줄을 함께 보게 되고, 그 줄들이 찾는 것을 가린다.
 *
 * ## 거르는 것은 서버다
 *
 * 한 쪽을 받아 놓고 화면이 거르면, 상한을 넘는 순간 나머지가 조용히 빠진다 — 그리고
 * 그때 목록은 「그 조건에 맞는 장비가 이것뿐」 이라고 거짓말한다.
 */

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
import { equipmentApi } from '@/modules/equipment/api'
import { EQUIPMENT_STATUS_OPTIONS } from '@/modules/equipment/status'

/** 화면이 들고 있는 거르기 상태. 빈 문자열은 **안 거른다**는 뜻이다. */
export interface EquipmentFilterState {
  assetNo: string
  name: string
  categoryTermId: string
  workspace: string
  siteTermId: string
  status: string
  testItemTermId: string
  /** `none` 이면 **시험 항목이 하나도 없는 장비**만. 홈의 「남은 일」 이 이걸로 온다. */
  testItem: string
  /** `unlinked` 면 **기종을 안 고른 장비**만. 카탈로그를 채울 자리를 찾는 손잡이다. */
  catalog: string
  calibration: string
}

export const EMPTY_FILTERS: EquipmentFilterState = {
  assetNo: '',
  name: '',
  categoryTermId: '',
  workspace: '',
  siteTermId: '',
  status: '',
  testItemTermId: '',
  testItem: '',
  catalog: '',
  calibration: '',
}

export function activeCount(filters: EquipmentFilterState): number {
  return Object.values(filters).filter((one) => one !== '').length
}

/** 교정으로 거르는 넷. **「대상 아님」 과 「이력 없음」 을 나눠 둔다** — 뭉치면
 *  빠뜨린 장비가 대상 아닌 장비 뒤에 숨는다. */
const CALIBRATION_OPTIONS = [
  { value: 'required', label: '대상 전부' },
  { value: 'missing', label: '이력 없음' },
  { value: 'overdue', label: '기한 초과' },
  { value: 'exempt', label: '대상 아님' },
]

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

export function EquipmentFilters({
  value,
  onChange,
}: {
  value: EquipmentFilterState
  onChange: (next: EquipmentFilterState) => void
}) {
  // **한 번만 받는다.** 거를 때마다 다시 받으면 고르는 사이에 선택지가 흔들린다.
  const options = useResource(() => equipmentApi.filterOptions(), [])
  const set = (patch: Partial<EquipmentFilterState>) => onChange({ ...value, ...patch })

  /** 상태는 **생애 순서**로 보여 준다(입고 → 가동 → … → 폐기). 서버는 있는 것만 알려
   *  주고, 그 순서는 화면이 안다. */
  const statuses = EQUIPMENT_STATUS_OPTIONS.filter((one) =>
    (options.data?.statuses ?? []).some((row) => row.value === one.value),
  ).map((one) => {
    const found = (options.data?.statuses ?? []).find((row) => row.value === one.value)
    return { value: one.value, label: `${one.label} ${found?.count ?? 0}` }
  })

  return (
    <>
      {/* **자산번호와 이름을 따로 친다.** 현장에서는 라벨의 번호를 치고, 회의에서는
          이름을 친다 — 한 칸으로 합치면 번호를 치는 사람이 이름에 걸린 줄을 함께 보게
          되고, 그 줄들이 찾는 것을 가린다. */}
      <td className="p-1">
        <Input
          value={value.assetNo}
          onChange={(event) => set({ assetNo: event.target.value })}
          placeholder="자산번호"
          className="h-8 text-xs"
        />
      </td>
      <td className="p-1">
        <Input
          value={value.name}
          onChange={(event) => set({ name: event.target.value })}
          placeholder="이름"
          className="h-8 text-xs"
        />
      </td>
      <td className="p-1">
        {/* **카탈로그에 안 이어진 장비만.** 「미연결」 표시가 이 열에 붙으므로 거르기도
            여기 둔다. 기종이 없으면 시험 항목이 0 건이고, 0 건이면 검색에 안 걸린다. */}
        {value.catalog === 'unlinked' ? (
          <Button
            size="sm"
            variant="secondary"
            className="h-8 w-full text-xs"
            onClick={() => set({ catalog: '' })}
          >
            카탈로그 미연결만 ✕
          </Button>
        ) : (
          <SearchablePicker
            value={value.categoryTermId}
            onChange={(next) => set({ categoryTermId: next })}
            options={(options.data?.categories ?? []).map((one) => ({
              id: one.value,
              label: one.label,
              detail: one.detail ?? null,
              badge: `${one.count}대`,
            }))}
            placeholder="분류 전체"
            detailTitle="장비 분류"
            detailHint="지금 목록에 있는 분류만 나옵니다. 묶음을 고르면 그 아래 분류가 다 걸립니다."
            className="w-full"
          />
        )}
      </td>
      <td className="p-1">
        {/* **부서도 수백이 된다.** 조직도를 통째로 들이면 드롭다운으로는 못 찾는다. */}
        <SearchablePicker
          value={value.workspace}
          onChange={(next) => set({ workspace: next })}
          options={(options.data?.workspaces ?? []).map((one) => ({
            id: one.value,
            label: one.label,
            badge: `${one.count}대`,
          }))}
          placeholder="부서 전체"
          detailTitle="보유 부서"
          detailHint="지금 목록에 장비가 있는 부서만 나옵니다."
          className="w-full"
        />
      </td>
      <td className="p-1">
        {/* 거점도 마찬가지다 — 공장·연구소·현장이 늘면 금세 수십을 넘는다. */}
        <SearchablePicker
          value={value.siteTermId}
          onChange={(next) => set({ siteTermId: next })}
          options={(options.data?.sites ?? []).map((one) => ({
            id: one.value,
            label: one.label,
            badge: `${one.count}대`,
          }))}
          placeholder="거점 전체"
          detailTitle="보유 거점"
          detailHint="지금 목록에 장비가 있는 거점만 나옵니다."
          className="w-full"
        />
      </td>
      <td className="p-1">
        <Pick
          value={value.status}
          onChange={(next) => set({ status: next })}
          placeholder="상태 전체"
          options={statuses}
        />
      </td>
      <td className="p-1">
        {/* 87종. 여기도 치면서 찾는다. */}
        {/* 시험 항목이 **없는** 장비만 보는 중이면 그 사실을 먼저 말한다 — 피커에는
            고를 값이 없어서, 안 적어 두면 빈 목록의 이유가 화면에 없다. */}
        {value.testItem === 'none' ? (
          <Button
            size="sm"
            variant="secondary"
            className="h-8 w-full text-xs"
            onClick={() => set({ testItem: '' })}
          >
            시험 항목 없음만 ✕
          </Button>
        ) : (
          <SearchablePicker
            value={value.testItemTermId}
            onChange={(next) => set({ testItemTermId: next })}
            options={(options.data?.test_items ?? []).map((one) => ({
              id: one.value,
              label: one.label,
              badge: `${one.count}대`,
            }))}
            placeholder="시험 항목 전체"
            detailTitle="시험 항목"
            detailHint="우리 장비에 적혀 있는 항목만 나옵니다."
            className="w-full"
          />
        )}
      </td>
      <td className="p-1">
        <Pick
          value={value.calibration}
          onChange={(next) => set({ calibration: next })}
          placeholder="교정 전체"
          options={CALIBRATION_OPTIONS}
        />
      </td>
    </>
  )
}

/**
 * 이 장비로 무엇을 어디까지 할 수 있나.
 *
 * ## 조건은 SI 로 보낸다
 *
 * 화면이 조건 정의의 si_unit 을 보고 환산한다. 여기서는 표시 단위와 저장 단위가
 * 같은 축(온도 degC, 하중 kN)만 쓰므로 그대로 보내지만, **다른 단위를 쓰는 조건이
 * 생기면 환산은 여기 한 곳에서** 한다 — 두 곳에서 하면 언젠가 한쪽만 고쳐지고,
 * 그때 저장된 숫자가 조용히 세 자릿수 틀린다.
 */

import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'

import { ApiError } from '@/shared/api/client'
import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { StatusBadge } from '@/shared/components/StatusBadge'
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
import { AXIS, vocabularyApi } from '@/modules/vocabulary/api'
import { capabilityApi } from '@/modules/equipment/api'
import type { Capability } from '@/modules/equipment/api'

/** "제한 없음" 을 0 으로 적지 않는다 — 하한이 0 인 장비와 구별되지 않는다. */
function shownRange(min: number | null, max: number | null, unit: string): string {
  const low = min === null ? '제한 없음' : `${min} ${unit}`.trim()
  const high = max === null ? '제한 없음' : `${max} ${unit}`.trim()
  return `${low} ~ ${high}`
}

export function CapabilityPanel({
  equipmentId,
  canEdit,
}: {
  equipmentId: string
  canEdit: boolean
}) {
  const list = useResource(() => capabilityApi.forEquipment(equipmentId), [equipmentId])
  const items = useResource(() => vocabularyApi.terms(AXIS.testItem), [])
  const conditions = useResource(() => vocabularyApi.conditions(), [])
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [newItem, setNewItem] = useState('')

  async function addCapability() {
    if (!newItem) return
    setError(null)
    try {
      await capabilityApi.create({ equipment_id: equipmentId, test_item_term_id: newItem })
      setNewItem('')
      list.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

  return (
    <div className="space-y-4">
      {canEdit && (
        <div className="flex flex-wrap items-center gap-2">
          <Select value={newItem} onValueChange={setNewItem}>
            <SelectTrigger className="w-56">
              <SelectValue placeholder="시험 항목" />
            </SelectTrigger>
            <SelectContent>
              {(items.data ?? []).map((one) => (
                <SelectItem key={one.id} value={one.id}>
                  {one.value}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button onClick={addCapability} disabled={!newItem}>
            <Plus className="size-4" />
            역량 추가
          </Button>
        </div>
      )}

      <ErrorNotice error={error ?? list.error} />

      {list.data && list.data.length === 0 ? (
        <EmptyState
          title="등록된 역량이 없습니다"
          hint="역량이 없으면 이 장비는 검색에 걸리지 않습니다. 할 수 있는 시험 항목부터 적어 주세요."
        />
      ) : (
        <ul className="space-y-3">
          {(list.data ?? []).map((capability) => (
            <CapabilityCard
              key={capability.id}
              capability={capability}
              conditions={conditions.data ?? []}
              onChanged={list.reload}
            />
          ))}
        </ul>
      )}
    </div>
  )
}

function CapabilityCard({
  capability,
  conditions,
  onChanged,
}: {
  capability: Capability
  conditions: { id: string; label: string; si_unit: string; display_unit: string }[]
  onChanged: () => void
}) {
  const [conditionKey, setConditionKey] = useState('')
  const [min, setMin] = useState('')
  const [max, setMax] = useState('')
  const [error, setError] = useState<ApiError | Error | null>(null)

  async function addLimit() {
    if (!conditionKey) return
    setError(null)
    try {
      await capabilityApi.putLimit(capability.id, {
        condition_key_id: conditionKey,
        // **빈 칸은 null 로 보낸다.** 0 으로 채우면 "제한 없음" 이 "0 까지" 가 된다.
        min_value: min.trim() === '' ? null : Number(min),
        max_value: max.trim() === '' ? null : Number(max),
      })
      setConditionKey('')
      setMin('')
      setMax('')
      onChanged()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

  return (
    <li className="rounded-md border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{capability.test_item}</span>
          {capability.method_code && (
            <span className="text-muted-foreground text-sm">{capability.method_code}</span>
          )}
          <StatusBadge kind="confidence" value={capability.confidence} />
        </div>
        {capability.can_edit && (
          <Button
            variant="ghost"
            size="sm"
            onClick={async () => {
              await capabilityApi.remove(capability.id)
              onChanged()
            }}
          >
            <Trash2 className="size-4" />
            삭제
          </Button>
        )}
      </div>

      {capability.note && <p className="mt-2 text-sm">{capability.note}</p>}

      <ul className="mt-3 space-y-1 text-sm">
        {capability.limits.map((limit) => (
          <li key={limit.id} className="flex items-center gap-2">
            <span className="text-muted-foreground w-32 shrink-0">{limit.condition_label}</span>
            <span>
              {limit.text_value ??
                shownRange(limit.min_value, limit.max_value, limit.display_unit || limit.si_unit)}
            </span>
            {capability.can_edit && (
              <Button
                variant="ghost"
                size="sm"
                onClick={async () => {
                  await capabilityApi.removeLimit(capability.id, limit.id)
                  onChanged()
                }}
              >
                빼기
              </Button>
            )}
          </li>
        ))}
      </ul>

      {capability.can_edit && (
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t pt-3">
          <Select value={conditionKey} onValueChange={setConditionKey}>
            <SelectTrigger className="w-44">
              <SelectValue placeholder="조건 추가" />
            </SelectTrigger>
            <SelectContent>
              {conditions.map((one) => (
                <SelectItem key={one.id} value={one.id}>
                  {one.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {/* **비워 두는 것이 "제한 없음" 이다.** placeholder 가 그것을 말한다. */}
          <Input
            type="number"
            value={min}
            onChange={(event) => setMin(event.target.value)}
            placeholder="최소 (비우면 제한 없음)"
            className="w-52"
          />
          <Input
            type="number"
            value={max}
            onChange={(event) => setMax(event.target.value)}
            placeholder="최대 (비우면 제한 없음)"
            className="w-52"
          />
          <Button variant="outline" onClick={addLimit} disabled={!conditionKey}>
            저장
          </Button>
        </div>
      )}

      <ErrorNotice error={error} className="mt-3" />
    </li>
  )
}

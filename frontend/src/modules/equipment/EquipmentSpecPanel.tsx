/**
 * 이 장비의 사양 — **카탈로그 값 위에 실측을 덮는다.**
 *
 * 한 줄에 둘을 함께 그린다: 「300 kN · 사양서 250 kN」. 하나만 보여 주면 사람은 그
 * 수치가 잰 값인지 사양서 값인지 알 수 없고, 그 둘은 믿는 정도가 다르다.
 *
 * **기종 사양표(`ModelSpecPanel`)와 다른 화면이다.** 저기는 그 기종을 쓰는 모든
 * 장비의 기준이고, 여기는 이 한 대의 값이다 — 섞으면 한 대의 실측이 열 대의 기준이 된다.
 */

import { useState } from 'react'
import { Pencil, RotateCcw } from 'lucide-react'

import { ApiError } from '@/shared/api/client'
import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { Badge } from '@/shared/components/ui/badge'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import { useResource } from '@/shared/hooks/useResource'
import { shownDate } from '@/shared/lib/datetime'
import { equipmentSpecApi } from '@/modules/equipment/api'
import type { EquipmentSpecItem } from '@/modules/equipment/api'
import { shownSpecValue } from '@/modules/equipment/specValue'

/** 값 칸 하나를 그 정의의 종류에 맞게 읽는다. 정의의 계약은 item 이 함께 갖고 있다. */
function shown(item: EquipmentSpecItem, side: 'catalog' | 'measured'): string | null {
  const value = side === 'catalog' ? item.catalog : item.measured
  if (!value) return null
  return shownSpecValue({
    kind: item.kind,
    si_unit: item.si_unit,
    display_unit: item.display_unit,
    num_value: value.num_value,
    num_min: value.num_min,
    num_max: value.num_max,
    text_value: value.text_value,
    bool_value: value.bool_value,
  })
}

/** 종류에 맞는 칸만 보낸다. 나머지는 서버가 비운다 — 틀린 칸에 담긴 값은 조용히 사라진다. */
function toBody(item: EquipmentSpecItem, draft: Record<string, string>) {
  const number = (raw: string | undefined) =>
    raw === undefined || raw.trim() === '' ? null : Number(raw)
  return {
    definition_id: item.definition_id,
    num_value: item.kind === 'number' ? number(draft.num_value) : null,
    num_min: item.kind === 'range' ? number(draft.num_min) : null,
    num_max: item.kind === 'range' ? number(draft.num_max) : null,
    text_value:
      item.kind === 'text' || item.kind === 'choice' ? (draft.text_value ?? null) : null,
    bool_value: item.kind === 'boolean' ? draft.bool_value === 'yes' : null,
    measured_on: draft.measured_on || null,
    note: draft.note || null,
  }
}

export function EquipmentSpecPanel({
  equipmentId,
  canEdit,
}: {
  equipmentId: string
  canEdit: boolean
}) {
  const sheet = useResource(() => equipmentSpecApi.sheet(equipmentId), [equipmentId])
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [busy, setBusy] = useState(false)
  /** 마지막 저장이 시험 조건에 반영됐나. **안 말하면 사람은 반영된 줄 안다.** */
  const [reflected, setReflected] = useState<string | null>(null)

  function start(item: EquipmentSpecItem) {
    const value = item.measured ?? item.catalog
    setEditing(item.definition_id)
    setReflected(null)
    setDraft({
      num_value: value?.num_value?.toString() ?? '',
      num_min: value?.num_min?.toString() ?? '',
      num_max: value?.num_max?.toString() ?? '',
      text_value: value?.text_value ?? '',
      bool_value: value?.bool_value ? 'yes' : 'no',
      measured_on: item.measured?.measured_on ?? '',
      note: item.measured?.note ?? '',
    })
  }

  async function save(item: EquipmentSpecItem) {
    setBusy(true)
    setError(null)
    try {
      const result = await equipmentSpecApi.put(equipmentId, toBody(item, draft))
      setEditing(null)
      setReflected(
        result.condition_label
          ? result.reflected
            ? `${result.condition_label} 조건을 이 장비의 시험 항목에 반영했습니다.`
            : `${result.condition_label} 조건은 손으로 적어 둔 값이 있어 그대로 두었습니다.`
          : null,
      )
      sheet.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  async function revert(item: EquipmentSpecItem) {
    setBusy(true)
    setError(null)
    try {
      await equipmentSpecApi.remove(equipmentId, item.definition_id)
      sheet.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  if (sheet.error) return <ErrorNotice error={sheet.error} />
  const data = sheet.data
  if (!data) return null

  if (data.groups.length === 0) {
    return (
      <EmptyState
        title="적힌 사양이 없습니다"
        hint={
          data.model_id
            ? '이 기종에 아직 사양이 안 적혔습니다. 기종 화면에서 사양서 값을 채우거나, 여기서 실측을 적으십시오.'
            : '카탈로그에 연결되지 않은 장비입니다. 기종을 연결하면 사양서 값이 따라옵니다.'
        }
      />
    )
  }

  return (
    <div className="space-y-6">
      <p className="text-muted-foreground text-sm">
        사양서 값 위에 <strong>이 장비의 실측값</strong>을 덮습니다. 덮은 칸은 둘 다 보이고,
        검색 조건에 이어진 사양은 이 장비의 시험 조건이 됩니다.
        {data.override_count > 0 && ` 지금 ${data.override_count}칸이 실측입니다.`}
      </p>

      <ErrorNotice error={error} />
      {reflected && <p className="text-sm">{reflected}</p>}

      {data.groups.map((group) => (
        <section key={group.group_id} className="space-y-2">
          <h3 className="text-base font-semibold">{group.label}</h3>
          <div className="divide-y rounded-md border">
            {group.items.map((item) => {
              const catalogValue = shown(item, 'catalog')
              const measuredValue = shown(item, 'measured')
              const open = editing === item.definition_id
              return (
                <div key={item.definition_id} className="space-y-2 p-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium">
                        {item.label}
                        {item.condition_key_id && (
                          <Badge variant="outline" className="ml-2">
                            검색 조건
                          </Badge>
                        )}
                      </p>
                      <p className="text-sm">
                        {/* **실측이 이긴다.** 사양서 값은 괄호로 함께 남긴다 —
                            지워 버리면 무엇과 달랐는지 알 수 없다. */}
                        {measuredValue ? (
                          <>
                            <span className="font-medium">{measuredValue}</span>
                            <span className="text-muted-foreground">
                              {' '}
                              실측
                              {item.measured?.measured_on
                                ? ` · ${shownDate(item.measured.measured_on)}`
                                : ' · 날짜 없음'}
                              {catalogValue ? ` · 사양서 ${catalogValue}` : ''}
                            </span>
                          </>
                        ) : (
                          <>
                            <span>{catalogValue ?? '—'}</span>
                            <span className="text-muted-foreground"> 사양서</span>
                          </>
                        )}
                      </p>
                      {item.measured?.note && (
                        <p className="text-muted-foreground text-xs">{item.measured.note}</p>
                      )}
                    </div>
                    {canEdit && !open && (
                      <div className="flex shrink-0 gap-2">
                        <Button size="sm" variant="outline" onClick={() => start(item)}>
                          <Pencil className="size-4" />
                          실측값 입력
                        </Button>
                        {item.measured && (
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={busy}
                            onClick={() => revert(item)}
                          >
                            <RotateCcw className="size-4" />
                            사양서로
                          </Button>
                        )}
                      </div>
                    )}
                  </div>

                  {open && (
                    <div className="bg-muted/40 space-y-3 rounded-md p-3">
                      <div className="grid gap-3 sm:grid-cols-3">
                        {item.kind === 'range' ? (
                          <>
                            <div className="space-y-1">
                              <Label htmlFor={`min-${item.definition_id}`}>최소</Label>
                              <Input
                                id={`min-${item.definition_id}`}
                                value={draft.num_min ?? ''}
                                onChange={(event) =>
                                  setDraft({ ...draft, num_min: event.target.value })
                                }
                                placeholder="비우면 제한 없음"
                              />
                            </div>
                            <div className="space-y-1">
                              <Label htmlFor={`max-${item.definition_id}`}>최대</Label>
                              <Input
                                id={`max-${item.definition_id}`}
                                value={draft.num_max ?? ''}
                                onChange={(event) =>
                                  setDraft({ ...draft, num_max: event.target.value })
                                }
                                placeholder="비우면 제한 없음"
                              />
                            </div>
                          </>
                        ) : item.kind === 'number' ? (
                          <div className="space-y-1">
                            <Label htmlFor={`value-${item.definition_id}`}>
                              값 {item.display_unit || item.si_unit}
                            </Label>
                            <Input
                              id={`value-${item.definition_id}`}
                              value={draft.num_value ?? ''}
                              onChange={(event) =>
                                setDraft({ ...draft, num_value: event.target.value })
                              }
                            />
                          </div>
                        ) : (
                          <div className="space-y-1 sm:col-span-2">
                            <Label htmlFor={`text-${item.definition_id}`}>값</Label>
                            <Input
                              id={`text-${item.definition_id}`}
                              value={draft.text_value ?? ''}
                              onChange={(event) =>
                                setDraft({ ...draft, text_value: event.target.value })
                              }
                            />
                          </div>
                        )}
                        <div className="space-y-1">
                          <Label htmlFor={`when-${item.definition_id}`}>잰 날</Label>
                          {/* **날짜를 묻는다.** 3년 전 실측은 사양서보다 나을 것이
                              없고, 날짜가 없으면 그것을 판단할 수 없다. */}
                          <Input
                            id={`when-${item.definition_id}`}
                            type="date"
                            value={draft.measured_on ?? ''}
                            onChange={(event) =>
                              setDraft({ ...draft, measured_on: event.target.value })
                            }
                          />
                        </div>
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor={`note-${item.definition_id}`}>비고</Label>
                        <Input
                          id={`note-${item.definition_id}`}
                          value={draft.note ?? ''}
                          onChange={(event) =>
                            setDraft({ ...draft, note: event.target.value })
                          }
                          placeholder="어떻게 쟀는지 · 어떤 조건에서인지"
                        />
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" disabled={busy} onClick={() => save(item)}>
                          저장
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => setEditing(null)}>
                          취소
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </section>
      ))}
    </div>
  )
}

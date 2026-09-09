/**
 * 시험법 상세 — 요구 조건이 본문이다.
 *
 * **요구 조건이 곧 검색 물음이 된다.** 여기 적힌 숫자를 검색 화면이 그대로 물어
 * 주므로, 사람이 규격서를 펴 놓고 숫자를 옮겨 적을 필요가 없다 — 그 옮겨 적기에서
 * 자릿수가 틀린다.
 */

import { useState } from 'react'
import { Trash2 } from 'lucide-react'
import { useParams } from 'react-router-dom'

import { ApiError } from '@/shared/api/client'
import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table'
import { useResource } from '@/shared/hooks/useResource'
import { vocabularyApi } from '@/modules/vocabulary/api'
import { methodApi } from '@/modules/methods/api'

/** "제한 없음" 을 0 으로 적지 않는다 — 하한이 0 인 요구와 구별되지 않는다. */
function shownBound(value: number | null, unit: string): string {
  return value === null ? '—' : `${value} ${unit}`.trim()
}

export default function MethodDetailPage() {
  const { id = '' } = useParams<{ id: string }>()
  const method = useResource(() => methodApi.read(id), [id])
  const conditions = useResource(() => vocabularyApi.conditions(), [])

  const [conditionKey, setConditionKey] = useState('')
  const [min, setMin] = useState('')
  const [max, setMax] = useState('')
  const [error, setError] = useState<ApiError | Error | null>(null)

  if (method.error) return <ErrorNotice error={method.error} />
  if (!method.data) return null

  const one = method.data

  async function addRequirement() {
    if (!conditionKey) return
    setError(null)
    try {
      await methodApi.putRequirement(id, {
        condition_key_id: conditionKey,
        // **빈 칸은 null 이다.** 20 kN 이상은 min 만 있고 max 가 없다.
        min_value: min.trim() === '' ? null : Number(min),
        max_value: max.trim() === '' ? null : Number(max),
      })
      setConditionKey('')
      setMin('')
      setMax('')
      method.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        back={{ to: '/methods', label: '시험법·규격' }}
        title={`${one.code}${one.edition ? ` ${one.edition}` : ''}`}
        description={one.title}
      />

      <dl className="grid grid-cols-2 gap-4 rounded-md border p-4 sm:grid-cols-4">
        <div>
          <dt className="text-muted-foreground text-xs">시험 항목</dt>
          <dd className="text-sm">{one.test_item ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">제정 기관</dt>
          <dd className="text-sm">{one.body ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">상태</dt>
          <dd className="text-sm">
            {one.status === 'superseded'
              ? `대체됨${one.superseded_by_code ? ` (${one.superseded_by_code})` : ''}`
              : one.status === 'draft'
                ? '초안'
                : '현행'}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">가능 장비</dt>
          <dd className="text-sm">
            {one.equipment_count === 0 ? (
              <span className="text-amber-600">없음 — 지금은 못 하는 시험입니다</span>
            ) : (
              `${one.equipment_count}대`
            )}
          </dd>
        </div>
      </dl>

      {one.summary && <p className="text-sm">{one.summary}</p>}

      <section className="space-y-3">
        <h2 className="text-base font-semibold">요구 조건</h2>

        {one.requirements.length === 0 ? (
          <EmptyState
            title="요구 조건이 없습니다"
            hint="조건을 적어 두면 검색이 이 숫자를 그대로 물어 줍니다. 규격서를 펴 놓고 옮겨 적을 필요가 없어집니다."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>조건</TableHead>
                <TableHead>최소</TableHead>
                <TableHead>최대</TableHead>
                <TableHead>필수</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {one.requirements.map((requirement) => (
                <TableRow key={requirement.id}>
                  <TableCell>{requirement.condition_label}</TableCell>
                  <TableCell>
                    {shownBound(
                      requirement.min_value,
                      requirement.display_unit || requirement.si_unit,
                    )}
                  </TableCell>
                  <TableCell>
                    {shownBound(
                      requirement.max_value,
                      requirement.display_unit || requirement.si_unit,
                    )}
                  </TableCell>
                  <TableCell>{requirement.is_mandatory ? '필수' : '권고'}</TableCell>
                  <TableCell className="text-right">
                    {one.can_edit && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={async () => {
                          await methodApi.removeRequirement(id, requirement.id)
                          method.reload()
                        }}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {one.can_edit && (
          <div className="flex flex-wrap items-center gap-2 border-t pt-3">
            <Select value={conditionKey} onValueChange={setConditionKey}>
              <SelectTrigger className="w-44">
                <SelectValue placeholder="조건 추가" />
              </SelectTrigger>
              <SelectContent>
                {(conditions.data ?? []).map((condition) => (
                  <SelectItem key={condition.id} value={condition.id}>
                    {condition.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              type="number"
              value={min}
              onChange={(event) => setMin(event.target.value)}
              placeholder="최소 (비우면 없음)"
              className="w-48"
            />
            <Input
              type="number"
              value={max}
              onChange={(event) => setMax(event.target.value)}
              placeholder="최대 (비우면 없음)"
              className="w-48"
            />
            <Button variant="outline" onClick={addRequirement} disabled={!conditionKey}>
              저장
            </Button>
          </div>
        )}

        <ErrorNotice error={error} />
      </section>
    </div>
  )
}

/**
 * 시험법 상세 — 요구 조건이 본문이다.
 *
 * **요구 조건이 곧 검색 물음이 된다.** 여기 적힌 숫자를 검색 화면이 그대로 물어
 * 주므로, 사람이 규격서를 펴 놓고 숫자를 옮겨 적을 필요가 없다 — 그 옮겨 적기에서
 * 자릿수가 틀린다.
 *
 * **시험 항목은 여기서 정한다.** 카탈로그가 인용했는데 어느 시험의 것인지 안 정해진 규격이
 * 172 건 있다 — 정하는 순간 인용한 계열의 그 시험 항목에 붙는다. 그래서 인용한 계열 목록이
 * 이 화면에 함께 있다: 무엇이 붙을지 보고 정한다.
 */

import { useState } from 'react'
import { Trash2 } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

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
import { useAuth } from '@/shared/auth/AuthContext'
import { useResource } from '@/shared/hooks/useResource'
import { AttachmentStrip } from '@/modules/attachments/AttachmentStrip'
import { attachmentApi } from '@/modules/attachments/api'
import { AXIS, vocabularyApi } from '@/modules/vocabulary/api'
import { AttributeValuesPanel } from '@/modules/attributes/AttributeValuesPanel'
import { GraphPanel } from '@/modules/graph/GraphPanel'
import { methodApi } from '@/modules/methods/api'

/** "제한 없음" 을 0 으로 적지 않는다 — 하한이 0 인 요구와 구별되지 않는다. */
function shownBound(value: number | null, unit: string): string {
  return value === null ? '—' : `${value} ${unit}`.trim()
}

export default function MethodDetailPage() {
  const { id = '' } = useParams<{ id: string }>()
  const { user } = useAuth()
  const method = useResource(() => methodApi.read(id), [id])
  /** 규격서 원문 — 목록과 따로 받는다. 상세를 열 때마다 파일 목록이 필요하다. */
  const documents = useResource(() => attachmentApi.list('method', id), [id])
  const conditions = useResource(() => vocabularyApi.conditions(), [])
  const items = useResource(() => vocabularyApi.terms(AXIS.testItem), [])
  const [pickingItem, setPickingItem] = useState('')

  const [conditionKey, setConditionKey] = useState('')
  const [min, setMin] = useState('')
  const [max, setMax] = useState('')
  const [error, setError] = useState<ApiError | Error | null>(null)

  if (method.error) return <ErrorNotice error={method.error} />
  if (!method.data) return null

  const one = method.data

  async function decideTestItem() {
    if (!pickingItem) return
    setError(null)
    try {
      // **더한다.** 통째로 바뀌는 칸이라, 이미 정해진 것을 안 실으면 조용히 끊긴다 —
      // 규격 하나가 시험 항목 여럿을 덮으므로 실제로 일어나는 일이다.
      await methodApi.update(id, {
        test_item_term_ids: [
          ...(one?.test_items ?? []).map((item) => item.term_id),
          pickingItem,
        ],
      })
      setPickingItem('')
      method.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

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
          {/* **여럿일 수 있다** — IEC 60529 는 방진과 방수를 한 문서가 정의한다. */}
          <dd className="text-sm">
            {one.test_items.length === 0 ? (
              <span className="text-amber-600">안 정해짐</span>
            ) : (
              one.test_items.map((item) => item.value).join(' · ')
            )}
          </dd>
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
          <dt className="text-muted-foreground text-xs">수행 가능 장비</dt>
          <dd className="text-sm">
            {one.equipment_count === 0 ? (
              <span className="text-amber-600">없음 — 현재 수행 불가한 시험입니다</span>
            ) : (
              `${one.equipment_count}대`
            )}
          </dd>
        </div>
      </dl>

      {one.summary && <p className="text-sm">{one.summary}</p>}

      {one.test_items.length === 0 && one.can_edit && (
        <div className="space-y-2 rounded-md border border-amber-300 bg-amber-50 p-4 dark:bg-amber-950/30">
          <p className="text-sm">
            <strong>이 규격이 어느 시험의 것인지 정해 주십시오.</strong>
            {one.pending_series_count > 0
              ? ` 인용한 계열 ${one.pending_series_count}개가 정하는 순간 이 규격에 붙습니다.`
              : ' 정해 두면 계열의 시험 항목에 이 규격을 걸 수 있습니다.'}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Select value={pickingItem} onValueChange={setPickingItem}>
              <SelectTrigger className="w-56" aria-label="시험 항목 선택">
                <SelectValue placeholder="시험 항목" />
              </SelectTrigger>
              <SelectContent>
                {(items.data ?? []).map((term) => (
                  <SelectItem key={term.id} value={term.id}>
                    {term.value}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button onClick={decideTestItem} disabled={!pickingItem}>
              적용 규격으로 지정
            </Button>
          </div>
        </div>
      )}

      <GraphPanel objectId={`method:${one.id}`} />

      {/* **규격서 원문.** 번호만 있고 문서가 없으면 읽을 수가 없고, 요구 조건을 채울
          재료도 없다(601건 중 원문을 가진 것이 19건이었다). 사내 규격서도 여기 붙는다 —
          여러 신뢰성 시험이 한 문서를 인용하므로 시험마다 복사하지 않는다.

          **올리고 지우는 것은 시스템 관리자만**이다. 규격은 전사 공용이라 한 부서가 올린
          판이 전사의 근거가 되면 안 된다 — 판정은 서버가 하고 여기는 표시일 뿐이다. */}
      <section className="space-y-3">
        <h2 className="text-base font-semibold">
          규격서
          {(documents.data ?? []).length > 0 && ` · ${(documents.data ?? []).length}`}
        </h2>
        <ErrorNotice error={documents.error} />
        <AttachmentStrip
          target="method"
          objectId={one.id}
          rows={documents.data ?? []}
          canEdit={Boolean(user?.is_system_admin)}
          size="lg"
          label="규격서 올리기"
          onChanged={() => documents.reload()}
        />
        {(documents.data ?? []).length === 0 && !user?.is_system_admin && (
          <p className="text-muted-foreground text-sm">
            올라온 규격서가 없습니다. 시스템 관리자가 올립니다.
          </p>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-base font-semibold">속성</h2>
        <AttributeValuesPanel
          target="method"
          values={one.attributes ?? []}
          canEdit={one.can_edit}
          onSave={async (attributes) => {
            await methodApi.update(one.id, { attributes })
            method.reload()
          }}
        />
      </section>

      <section className="space-y-3">
        <h2 className="text-base font-semibold">인용한 계열</h2>
        {one.cited_series.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            이 규격을 인용한 카탈로그 계열이 없습니다 — 카탈로그에 이 시험을 하는 계열이
            없거나, 아직 반입하지 않은 것입니다.
          </p>
        ) : (
          <ul className="flex flex-wrap gap-2 text-sm">
            {one.cited_series.map((row) => (
              <li key={row.series_id}>
                <Link
                  to={`/catalog/equipment-series/${row.series_id}`}
                  className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 hover:underline ${row.pending ? 'border-dashed text-muted-foreground' : ''}`}
                >
                  {row.series_name}
                  {/* 미정은 점선 — 인용은 했는데 어느 시험 항목 밑에 둘지 못 정한 것. */}
                  <span className="text-muted-foreground text-xs">
                    {row.pending ? '시험 항목 미지정' : row.test_item}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

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

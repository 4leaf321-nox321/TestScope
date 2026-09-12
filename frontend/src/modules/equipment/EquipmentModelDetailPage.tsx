/**
 * 장비 기종 상세 — **수치가 갈리는 자리.**
 *
 * 무슨 시험이 되나는 계열이 정하고 여기서는 읽기만 한다. 여기서 적는 것은 사양이고,
 * 검색축에 이어진 사양은 이 기종으로 **보유 장비를 등록할 때 시험 조건이 된다**
 * (ADR 0006). 이미 등록된 장비는 안 바뀐다 — 상속이 아니라 복사다(ADR 0004).
 *
 * ## 사양이 빈 기종은 이 화면에서 채운다
 *
 * 891 중 224 에 사양값이 하나도 없다. 검색은 그 기종을 「모름」 으로 답하고, 사람은 되는지
 * 안 되는지를 못 본다. 그중 205 는 **원문은 들어와 있다** — 정의가 없는 키라 사양표에 못
 * 세운 것뿐이다. 그래서 사양이 비면 원문을 **펼친 채로** 두고 그 위에 「채우세요」 라고
 * 말한다: 옮겨 적을 것이 바로 아래 있는데 접혀 있으면 아무도 안 연다.
 */

import { Link, useParams } from 'react-router-dom'

import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table'
import { useResource } from '@/shared/hooks/useResource'
import { catalogApi, equipmentApi } from '@/modules/equipment/api'
import { ModelSpecPanel } from '@/modules/equipment/ModelSpecPanel'
import { FreeSpecsPanel } from '@/modules/equipment/FreeSpecsPanel'
import { RawSpecs } from '@/modules/equipment/RawSpecs'
import { RecordListPanel } from '@/modules/equipment/RecordListPanel'

/** "제한 없음" 을 0 으로 적지 않는다 — 하한이 0 인 기종과 구별되지 않는다. */
function shownRange(min: number | null, max: number | null, unit: string): string {
  const low = min === null ? '제한 없음' : `${min} ${unit}`.trim()
  const high = max === null ? '제한 없음' : `${max} ${unit}`.trim()
  return `${low} ~ ${high}`
}

export default function EquipmentModelDetailPage() {
  const { id = '' } = useParams<{ id: string }>()
  const model = useResource(() => catalogApi.read(id), [id])
  // 이 기종으로 만든 장비들. **카탈로그가 답해야 하는 물음**이라 상세에도 둔다.
  const units = useResource(() => equipmentApi.list({ modelId: id, limit: 200 }), [id])

  if (model.error) return <ErrorNotice error={model.error} />
  if (!model.data) return null
  const one = model.data
  const mine = units.data?.items ?? []

  return (
    <div className="space-y-6">
      {/* 옆 기종으로 뒤로 가지 않고 건너뛴다 — 같은 계열의 기종을 견주는 일이 흔하다. */}
      <RecordListPanel kind="model" currentId={one.id} />

      <PageHeader
        back={{ to: `/catalog/equipment-series/${one.series_id}`, label: one.series_name }}
        title={one.name}
        description={
          [one.maker, one.category].filter(Boolean).join(' · ') || '제조사·분류 미지정'
        }
      />

      <dl className="grid grid-cols-2 gap-4 rounded-md border p-4 sm:grid-cols-4">
        <div>
          <dt className="text-muted-foreground text-xs">계열</dt>
          <dd className="text-sm">
            <Link
              to={`/catalog/equipment-series/${one.series_id}`}
              className="hover:underline"
            >
              {one.series_name}
            </Link>
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">상태</dt>
          <dd className="text-sm">{one.status === 'active' ? '현행' : '단종'}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">보유</dt>
          <dd className="text-sm">
            {one.unit_count === 0
              ? '없음'
              : `${one.unit_count}대 (가동 ${one.operational_count})`}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">생김새</dt>
          <dd className="text-sm">{one.form_factor || '—'}</dd>
        </div>
        {one.summary && (
          <div className="sm:col-span-4">
            <dt className="text-muted-foreground text-xs">설명</dt>
            <dd className="text-sm whitespace-pre-wrap">{one.summary}</dd>
          </div>
        )}
      </dl>

      {one.spec_note && <p className="text-sm whitespace-pre-wrap">{one.spec_note}</p>}

      <ModelSpecPanel
        // 「정의로 세우기」 가 값을 이쪽으로 옮기면 사양표를 다시 읽어야 한다 — 수가 바뀌면
        // 다시 그린다.
        key={`${one.id}:${one.spec_count}`}
        modelId={one.id}
        categoryTermId={one.category_term_id}
        canEdit={one.can_edit}
        onSaved={() => model.reload()}
      />

      {/* 정의 있는 사양 → 이 기종만의 사양 → 원문. 위로 갈수록 정제된 것이다. */}
      <FreeSpecsPanel
        modelId={one.id}
        rows={one.free_specs}
        canEdit={one.can_edit}
        onChanged={() => model.reload()}
      />

      <RawSpecs
        raw={one.raw_specs}
        empty={one.spec_count === 0 && one.free_specs.length === 0}
      />

      <section className="space-y-3">
        <div>
          <h2 className="text-base font-semibold">계열의 시험 항목</h2>
          <p className="text-muted-foreground mt-1 text-sm">
            <strong>무슨 시험이 되는지는 계열이 정합니다.</strong> 고치려면{' '}
            <Link
              to={`/catalog/equipment-series/${one.series_id}`}
              className="underline underline-offset-2"
            >
              {one.series_name}
            </Link>{' '}
            에서 하세요. 위 사양의 값이 조건을 좁힙니다.
          </p>
        </div>
        {one.test_items.length === 0 ? (
          <EmptyState
            title="계열에 시험 항목이 없습니다"
            hint="비워 두면 이 기종으로 장비를 등록해도 복사될 것이 없어, 매번 손으로 적게 됩니다."
          />
        ) : (
          <ul className="space-y-2 text-sm">
            {one.test_items.map((test_item) => (
              <li key={test_item.id} className="rounded-md border p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{test_item.test_item}</span>
                  {test_item.method_code && (
                    <span className="text-muted-foreground">{test_item.method_code}</span>
                  )}
                </div>
                {test_item.limits.length > 0 && (
                  <ul className="text-muted-foreground mt-2 space-y-1 text-xs">
                    {test_item.limits.map((limit) => (
                      <li key={limit.id}>
                        {limit.condition_label}{' '}
                        {limit.text_value ??
                          shownRange(
                            limit.min_value,
                            limit.max_value,
                            limit.display_unit || limit.si_unit,
                          )}
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-base font-semibold">이 기종의 보유 장비</h2>
        {mine.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            아직 이 기종으로 등록된 장비가 없습니다.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>자산번호</TableHead>
                <TableHead>이름</TableHead>
                <TableHead>위치</TableHead>
                <TableHead>상태</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mine.map((unit) => (
                <TableRow key={unit.id}>
                  <TableCell className="font-mono text-xs">
                    <Link to={`/equipment/${unit.id}`} className="hover:underline">
                      {unit.asset_no}
                    </Link>
                  </TableCell>
                  <TableCell>{unit.name}</TableCell>
                  <TableCell>
                    {[unit.workspace_name, unit.site, unit.location]
                      .filter(Boolean)
                      .join(' · ') || '—'}
                  </TableCell>
                  <TableCell>{unit.status}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>
    </div>
  )
}

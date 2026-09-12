/**
 * 장비 기종 상세 — **수치가 갈리는 자리.**
 *
 * 무슨 시험이 되나는 계열이 정하고 여기서는 읽기만 한다. 여기서 적는 것은 사양이고,
 * 검색축에 이어진 사양은 이 기종으로 **보유 장비를 등록할 때 시험 조건이 된다**
 * (ADR 0006). 이미 등록된 장비는 안 바뀐다 — 상속이 아니라 복사다(ADR 0004).
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
        modelId={one.id}
        categoryTermId={one.category_term_id}
        canEdit={one.can_edit}
        onSaved={() => model.reload()}
      />

      {Object.keys(one.raw_specs).length > 0 && (
        <details className="rounded-md border p-4">
          <summary className="cursor-pointer text-base font-semibold">
            카탈로그 원문
            <span className="text-muted-foreground ml-2 text-sm font-normal">
              {Object.keys(one.raw_specs).length}개 항목
            </span>
          </summary>
          <p className="text-muted-foreground mt-2 text-sm">
            제조사 카탈로그에 적힌 그대로입니다. <strong>위 사양표는 정의가 있는 칸만</strong>
            담고, 여기에는 정의가 없는 것까지 전부 있습니다 — 원본에 950종 넘는 키가 있고
            대부분이 한 카탈로그에만 나옵니다. 정의로 세우면 목록이 못 쓰게 되고, 안 세우면
            사라지므로 둘 다 합니다.
          </p>
          <dl className="mt-3 space-y-1 text-sm">
            {Object.entries(one.raw_specs).map(([key, value]) => (
              <div key={key} className="flex flex-wrap items-baseline gap-2">
                <dt className="text-muted-foreground w-56 shrink-0 font-mono text-xs">
                  {key}
                </dt>
                <dd className="min-w-0 break-all">
                  {typeof value === 'object' && value !== null
                    ? JSON.stringify(value)
                    : String(value)}
                </dd>
              </div>
            ))}
          </dl>
        </details>
      )}

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

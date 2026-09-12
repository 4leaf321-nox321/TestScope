/**
 * 장비 계열 상세 — 무슨 시험이 되나, 어느 부속이 붙나, 어떤 기종이 있나.
 *
 * **수치는 여기 없다.** 하중·공간·무게는 기종마다 갈리므로 기종 상세가 갖는다.
 * 여기 적은 시험 항목은 이 계열의 기종으로 **보유 장비를 등록할 때 복사된다** — 상속이
 * 아니라 복사라, 이 값을 나중에 고쳐도 이미 만든 장비는 안 바뀐다(ADR 0004·0006).
 */

import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { ApiError } from '@/shared/api/client'
import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { Badge } from '@/shared/components/ui/badge'
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
import { AXIS, vocabularyApi } from '@/modules/vocabulary/api'
import type { ConditionKey } from '@/modules/vocabulary/api'
import { SearchablePicker } from '@/shared/components/SearchablePicker'
import { catalogApi, seriesApi } from '@/modules/equipment/api'
import type { EquipmentSeries } from '@/modules/equipment/api'
import { propertyApi } from '@/modules/properties/api'
import type { TestItemProperty } from '@/modules/properties/api'
import { NewEquipmentModelDialog } from '@/modules/equipment/NewEquipmentModelDialog'

/** "제한 없음" 을 0 으로 적지 않는다 — 하한이 0 인 계열과 구별되지 않는다. */
function shownRange(min: number | null, max: number | null, unit: string): string {
  const low = min === null ? '제한 없음' : `${min} ${unit}`.trim()
  const high = max === null ? '제한 없음' : `${max} ${unit}`.trim()
  return `${low} ~ ${high}`
}

/** 원본 카탈로그가 쓰는 관계 이름을 화면 말로 바꾼다. */
const RELATION_LABEL: Record<string, string> = {
  compatible_accessory: '붙는 부속',
  fits_on: '장착 대상',
  requires: '필요 장비',
  controlled_by: '제어 장비',
  extends_temperature: '온도 범위를 넓힘',
  simulates_environment: '환경 재현',
  successor_of: '이전 기종',
  same_family_as: '같은 계통',
  variant_of: '상위 계열',
}

/** 조건 한 칸을 넣는 줄. 개체 쪽(TestItemPanel)과 **같은 규칙**이다. */
function LimitForm({
  conditions,
  onSubmit,
}: {
  conditions: ConditionKey[]
  onSubmit: (body: Record<string, unknown>) => void
}) {
  const [key, setKey] = useState('')
  const [min, setMin] = useState('')
  const [max, setMax] = useState('')

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 border-t pt-3">
      <Select value={key} onValueChange={setKey}>
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
      {/* **비워 두는 것이 "제한 없음" 이다.** 0 이 아니다. */}
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
      <Button
        variant="outline"
        disabled={!key}
        onClick={() => {
          onSubmit({
            condition_key_id: key,
            min_value: min.trim() === '' ? null : Number(min),
            max_value: max.trim() === '' ? null : Number(max),
          })
          setKey('')
          setMin('')
          setMax('')
        }}
      >
        저장
      </Button>
    </div>
  )
}

export default function EquipmentSeriesDetailPage() {
  const { id = '' } = useParams<{ id: string }>()
  const series = useResource(() => seriesApi.read(id), [id])
  const models = useResource(() => catalogApi.list({ seriesId: id, limit: 200 }), [id])
  const items = useResource(() => vocabularyApi.terms(AXIS.testItem), [])
  const conditions = useResource(() => vocabularyApi.conditions(), [])
  // **얻는 물성.** 시험 항목 줄만 보면 「이 계열로 영률을 잴 수 있나」 에 답이 안 된다 —
  // 물성 ↔ 시험 항목 표는 전사 공통이라 한 번 받아 시험 항목마다 나눠 붙인다(ADR 0007).
  const links = useResource(() => propertyApi.links(), [])

  const [newItem, setNewItem] = useState('')
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState<ApiError | Error | null>(null)

  if (series.error) return <ErrorNotice error={series.error} />
  if (!series.data) return null
  const one = series.data

  async function act(run: () => Promise<unknown>) {
    setError(null)
    try {
      await run()
      series.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        back={{ to: '/catalog/equipment-series', label: '장비 계열' }}
        title={one.name_ko || one.name}
        description={
          [one.maker, one.brand, one.category].filter(Boolean).join(' · ') ||
          '제조사·분류 미지정'
        }
        actions={
          one.can_edit ? (
            <Button onClick={() => setAdding(true)}>
              <Plus className="size-4" />
              기종 추가
            </Button>
          ) : undefined
        }
      />

      <dl className="grid grid-cols-2 gap-4 rounded-md border p-4 sm:grid-cols-4">
        <div>
          <dt className="text-muted-foreground text-xs">정식 명칭</dt>
          <dd className="text-sm">{one.name}</dd>
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
          <dt className="text-muted-foreground text-xs">구동·형태</dt>
          <dd className="text-sm">
            {[one.drive, one.form_factor].filter(Boolean).join(' · ') || '—'}
          </dd>
        </div>
        {one.summary && (
          <div className="sm:col-span-4">
            <dt className="text-muted-foreground text-xs">설명</dt>
            <dd className="text-sm whitespace-pre-wrap">{one.summary}</dd>
          </div>
        )}
        {one.source_path && (
          <div className="sm:col-span-4">
            <dt className="text-muted-foreground text-xs">출처 문서</dt>
            <dd className="font-mono text-xs">{one.source_path}</dd>
          </div>
        )}
      </dl>

      {one.spec_note && (
        <p className="text-muted-foreground text-sm whitespace-pre-wrap">{one.spec_note}</p>
      )}

      <ErrorNotice error={error} />

      <SeriesTestItems
        series={one}
        items={items.data ?? []}
        conditions={conditions.data ?? []}
        links={links.data ?? []}
        newItem={newItem}
        setNewItem={setNewItem}
        act={act}
      />

      <section className="space-y-3">
        <div>
          <h2 className="text-base font-semibold">기종</h2>
          <p className="text-muted-foreground mt-1 text-sm">
            <strong>보유 장비는 계열이 아니라 기종을 가리킵니다.</strong> 한 계열 안에서 하중이
            수백 배 갈리기 때문입니다 — 수치 사양은 각 기종에 적습니다.
          </p>
        </div>
        {(models.data?.items ?? []).length === 0 ? (
          <EmptyState
            title="기종이 없습니다"
            hint="기종이 없으면 이 계열을 가리키는 보유 장비를 만들 수 없습니다."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>기종</TableHead>
                <TableHead>생김새</TableHead>
                <TableHead className="text-right">보유</TableHead>
                <TableHead>상태</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(models.data?.items ?? []).map((model) => (
                <TableRow key={model.id}>
                  <TableCell className="font-medium">
                    <Link
                      to={`/catalog/equipment-models/${model.id}`}
                      className="hover:underline"
                    >
                      {model.name}
                    </Link>
                  </TableCell>
                  <TableCell>{model.form_factor || '—'}</TableCell>
                  <TableCell className="text-right">
                    {model.unit_count === 0
                      ? '—'
                      : `${model.unit_count}대 (가동 ${model.operational_count})`}
                  </TableCell>
                  <TableCell>{model.status === 'active' ? '현행' : '단종'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      <SeriesRelations series={one} act={act} />

      <NewEquipmentModelDialog
        open={adding}
        seriesId={one.id}
        onClose={() => setAdding(false)}
        onCreated={() => {
          setAdding(false)
          models.reload()
          series.reload()
        }}
      />
    </div>
  )
}

/** 시험 항목 절. 본문에서 떼어 낸 이유는 한 화면 함수가 너무 길어지기 때문이다. */
function SeriesTestItems({
  series,
  items,
  conditions,
  links,
  newItem,
  setNewItem,
  act,
}: {
  series: EquipmentSeries
  items: { id: string; value: string }[]
  conditions: ConditionKey[]
  /** 물성 ↔ 시험 항목 연결 전부. 시험 항목마다 「얻는 물성」 으로 나뉘어 붙는다. */
  links: TestItemProperty[]
  newItem: string
  setNewItem: (value: string) => void
  act: (run: () => Promise<unknown>) => void
}) {
  // **이미 적은 것은 고르기 전에 보여 준다.** 눌러 보고 409 를 받는 것은 답이지만,
  // 답을 받으려고 누르게 하는 것은 화면의 일이 아니다.
  const taken = new Set(series.test_items.map((one) => one.test_item))
  const options = items.map((item) => ({
    id: item.id,
    label: item.value,
    badge: taken.has(item.value) ? '이미 있음' : null,
    disabled: taken.has(item.value),
  }))

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-base font-semibold">시험 항목</h2>
        <p className="text-muted-foreground mt-1 text-sm">
          여기 적은 값은 이 계열의 기종으로 <strong>보유 장비를 등록할 때 복사됩니다.</strong>{' '}
          조건은 <strong>계열 전체가 만족하는 것만</strong> 적습니다 — 기종마다 갈리는 수치는
          그 기종의 사양에 적으면 등록할 때 합쳐집니다.
        </p>
      </div>

      {series.test_items.length === 0 ? (
        <EmptyState
          title="시험 항목이 없습니다"
          hint="비워 두면 이 계열의 기종으로 장비를 등록해도 복사될 것이 없어, 매번 손으로 적게 됩니다."
        />
      ) : (
        <ul className="space-y-3">
          {series.test_items.map((test_item) => (
            <li key={test_item.id} className="rounded-md border p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{test_item.test_item}</span>
                  {test_item.method_code && (
                    <span className="text-muted-foreground text-sm">
                      {test_item.method_code}
                    </span>
                  )}
                </div>
                {series.can_edit && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      act(() => seriesApi.removeTestItem(series.id, test_item.id))
                    }
                  >
                    <Trash2 className="size-4" />
                  </Button>
                )}
              </div>

              {test_item.note && <p className="mt-2 text-sm">{test_item.note}</p>}

              {/* **이 시험으로 얻는 물성.** 전사 공통 표에서 온다 — 계열마다 다르게 적는
                  자리는 아직 없다(신율계가 없어 영률은 안 되는 대는 보유 장비 쪽에서).
                  제안(점선)은 아직 사람이 확인하지 않은 것이다. */}
              {(() => {
                const mine = links.filter(
                  (link) => link.test_item_term_id === test_item.test_item_term_id,
                )
                if (mine.length === 0) return null
                return (
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <span className="text-muted-foreground text-xs">얻는 물성</span>
                    {mine.map((link) => (
                      <Link
                        key={link.id}
                        to="/properties"
                        title={
                          link.note ??
                          (link.status === 'suggested' ? '기계가 제안한 연결' : '')
                        }
                        className={`rounded-full border px-2 py-0.5 text-xs hover:underline ${
                          link.status === 'suggested'
                            ? 'border-dashed text-muted-foreground'
                            : 'bg-muted'
                        }`}
                      >
                        {link.property}
                      </Link>
                    ))}
                  </div>
                )
              })()}

              {/* **카탈로그가 인용한 규격.** 전에는 비고에 글자로만 있어서 시험법
                  453건이 아무것도 가리키지 않는 목록이었다 — 이제 눌러서 그 규격으로
                  간다. 요구 조건이 없는 규격은 **검색이 조건으로 좁히지 못하므로**
                  그 사실을 함께 적는다. */}
              {test_item.methods.length > 0 && (
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <span className="text-muted-foreground text-xs">인용 규격</span>
                  {test_item.methods.map((method) => (
                    <Link
                      key={method.id}
                      to={`/methods/${method.id}`}
                      title={method.title}
                      className="hover:underline"
                    >
                      <Badge variant={method.has_requirements ? 'secondary' : 'outline'}>
                        {[method.code, method.edition].filter(Boolean).join(' ')}
                        {!method.has_requirements && (
                          <span className="text-muted-foreground"> 조건 없음</span>
                        )}
                      </Badge>
                    </Link>
                  ))}
                </div>
              )}

              <ul className="mt-3 space-y-1 text-sm">
                {test_item.limits.map((limit) => (
                  <li key={limit.id} className="flex items-center gap-2">
                    <span className="text-muted-foreground w-32 shrink-0">
                      {limit.condition_label}
                    </span>
                    <span>
                      {limit.text_value ??
                        shownRange(
                          limit.min_value,
                          limit.max_value,
                          limit.display_unit || limit.si_unit,
                        )}
                    </span>
                    {limit.requires_accessory && (
                      <span
                        className="rounded bg-amber-500/10 px-1.5 py-0.5 text-xs text-amber-700"
                        title="옵션 부속(챔버·노)이 있어야 나오는 범위"
                      >
                        부속 필요
                      </span>
                    )}
                    {series.can_edit && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          act(() => seriesApi.removeLimit(series.id, test_item.id, limit.id))
                        }
                      >
                        빼기
                      </Button>
                    )}
                  </li>
                ))}
              </ul>

              {series.can_edit && (
                <LimitForm
                  conditions={conditions}
                  onSubmit={(body) =>
                    act(() => seriesApi.putLimit(series.id, test_item.id, body))
                  }
                />
              )}
            </li>
          ))}
        </ul>
      )}

      {series.can_edit && (
        <div className="flex flex-wrap items-center gap-2 border-t pt-3">
          {/* **드롭다운으로는 못 찾는다.** 시험 항목이 87종이고, 스물이 넘으면 눈으로
              찾는 일은 실패한다 — 못 찾은 사람은 없다고 결론 내리고 새로 만들고,
              그러면 같은 항목이 둘로 갈린다. 시험 항목은 닫힌 축이라 특히 나쁘다. */}
          <SearchablePicker
            className="w-72"
            options={options}
            value={newItem}
            onChange={setNewItem}
            placeholder="시험 항목"
            searchPlaceholder="인장 · 경도 · 충격 …"
            detailTitle="시험 항목"
            detailHint="이 계열이 무슨 시험을 하는지 고릅니다. 이미 적은 항목은 흐리게 보입니다."
          />
          <Button
            onClick={() =>
              act(async () => {
                await seriesApi.addTestItem(series.id, { test_item_term_id: newItem })
                setNewItem('')
              })
            }
            disabled={!newItem}
          >
            시험 항목 추가
          </Button>
        </div>
      )}
    </section>
  )
}

/** 부속·계보. **양방향으로 보인다** — 한쪽만 보여 주면 챔버 화면이 늘 비어 있다. */
function SeriesRelations({
  series,
  act,
}: {
  series: EquipmentSeries
  act: (run: () => Promise<unknown>) => void
}) {
  if (series.relations.length === 0) return null
  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold">부속·계보</h2>
      <ul className="space-y-1 text-sm">
        {series.relations.map((one) => (
          <li key={one.id} className="flex flex-wrap items-center gap-2">
            <span className="text-muted-foreground w-36 shrink-0">
              {RELATION_LABEL[one.relation] ?? one.relation}
              {/* 이 계열이 관계의 대상 쪽이면 방향을 뒤집어 읽어야 한다. */}
              {one.inbound && <span className="ml-1 text-xs">(받는 쪽)</span>}
            </span>
            <Link
              to={`/catalog/equipment-series/${one.other_series_id}`}
              className="font-medium hover:underline"
            >
              {one.other_name}
            </Link>
            {one.other_maker && (
              <span className="text-muted-foreground text-xs">{one.other_maker}</span>
            )}
            {one.note && <span className="text-muted-foreground text-xs">{one.note}</span>}
            {series.can_edit && !one.inbound && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => act(() => seriesApi.removeRelation(series.id, one.id))}
              >
                <Trash2 className="size-4" />
              </Button>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}

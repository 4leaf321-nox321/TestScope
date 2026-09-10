/**
 * 장비 찾기 — **이 시스템의 첫 화면이다.**
 *
 *     시험 항목  ->  요구 조건  ->  시험법  ->  가능한 장비  ->  보유 위치
 *
 * 나머지 화면은 전부 이 한 물음에 답하기 위해 있다.
 *
 * ## 모름을 됨과 섞지 않는다
 *
 * 장비에 그 조건이 안 적혀 있는 것과 적혀 있는데 안 되는 것은 다르다. 둘을 같게
 * 답하면 사람은 헛걸음을 하고, 그 한 번으로 시스템 전체가 안 믿긴다.
 *
 * ## 시험 항목은 드롭다운이 아니라 펼쳐 둔다
 *
 * 87종이다. 접어 두면 **무엇을 물을 수 있는지 자체를 모른다** — 이 화면에 처음 온
 * 사람에게 그 목록이 곧 「이 시스템에 무엇을 물을 수 있나」 다. 스물이 넘으면
 * `<Select>` 를 쓰지 않는다는 규칙(AGENTS.md)이 여기에도 그대로 걸린다.
 *
 * 대신 **쓰이는 것을 앞에 둔다.** 카탈로그에서 아무도 안 하는 항목을 골라 봐야
 * 빈 결과만 나오고, 사람은 그것을 시스템 탓으로 읽는다.
 */

import { useMemo, useState } from 'react'
import { Search as SearchIcon } from 'lucide-react'
import { Link } from 'react-router-dom'

import { ApiError } from '@/shared/api/client'
import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { StatusBadge } from '@/shared/components/StatusBadge'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import { useResource } from '@/shared/hooks/useResource'
import { AXIS, vocabularyApi } from '@/modules/vocabulary/api'
import type { ConditionKey } from '@/modules/vocabulary/api'
import { searchApi } from '@/modules/search/api'
import type { ConditionQuery, SearchResponse } from '@/modules/search/api'

/** 조건 한 줄의 입력 상태. **비어 있는 칸은 안 묻는다** — 0 과 다르다. */
interface ConditionRow {
  key: ConditionKey
  mode: 'at' | 'at_least' | 'at_most'
  value: string
}

const MODE_LABEL: Record<ConditionRow['mode'], string> = {
  at: '그 값에서',
  at_least: '그 값 이상',
  at_most: '그 값 이하',
}

/** 토글 한 알의 모양. **안 쓰이는 항목은 흐리게** — 지우지는 않는다: 카탈로그에
 *  없을 뿐이지 우리 장비에 손으로 적어 둔 것이 있을 수 있다. */
function chipClass(picked: boolean, unused = false): string {
  const base =
    'rounded-full border px-2.5 py-1 text-sm transition-colors focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none'
  if (picked) return `${base} bg-primary text-primary-foreground border-primary`
  return `${base} hover:bg-muted ${unused ? 'text-muted-foreground/60' : ''}`
}

function toQuery(row: ConditionRow): ConditionQuery | null {
  const value = Number(row.value)
  if (row.value.trim() === '' || Number.isNaN(value)) return null
  return { condition_key_id: row.key.id, [row.mode]: value }
}

export default function SearchPage() {
  const items = useResource(() => vocabularyApi.terms(AXIS.testItem), [])
  const conditions = useResource(() => vocabularyApi.conditions(), [])

  const [testItem, setTestItem] = useState<string>('')
  /** 항목이 87종이라 **치는 길도 함께** 낸다. 눈으로 훑는 길만 두면 아는 이름을
   *  가진 사람이 매번 전체를 훑어야 한다. */
  const [itemFilter, setItemFilter] = useState('')
  const [rows, setRows] = useState<ConditionRow[]>([])
  const [includeUnavailable, setIncludeUnavailable] = useState(false)
  const [result, setResult] = useState<SearchResponse | null>(null)
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [busy, setBusy] = useState(false)

  /** 쓰이는 것 먼저, 그 안에서는 가나다순. **한 번만 계산한다** — 타이핑마다
   *  87개를 다시 정렬하면 입력이 끊긴다. */
  const sortedItems = useMemo(
    () =>
      [...(items.data ?? [])].sort(
        (a, b) => b.usage_count - a.usage_count || a.value.localeCompare(b.value, 'ko'),
      ),
    [items.data],
  )
  const shownItems = useMemo(() => {
    const needle = itemFilter.trim().toLowerCase()
    if (!needle) return sortedItems
    return sortedItems.filter((one) => one.value.toLowerCase().includes(needle))
  }, [sortedItems, itemFilter])

  function addCondition(keyId: string) {
    const key = (conditions.data ?? []).find((one) => one.id === keyId)
    if (!key || rows.some((row) => row.key.id === keyId)) return
    // 하중처럼 "얼마까지 되나" 를 묻는 조건은 대개 이상으로, 온도는 그 값에서.
    const mode: ConditionRow['mode'] = key.dimension === 'force' ? 'at_least' : 'at'
    setRows((current) => [...current, { key, mode, value: '' }])
  }

  async function run() {
    setBusy(true)
    setError(null)
    try {
      setResult(
        await searchApi.test_items({
          test_item_term_id: testItem || null,
          conditions: rows.map(toQuery).filter((one): one is ConditionQuery => one !== null),
          include_unavailable: includeUnavailable,
        }),
      )
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="장비 찾기"
        description="시험 항목과 조건을 주면, 그것이 가능한 장비와 보유 위치를 찾습니다."
      />

      <div className="space-y-4 rounded-md border p-4">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Label htmlFor="item-filter">
              시험 항목
              <span className="text-muted-foreground ml-2 font-normal">
                {sortedItems.length}종 · 하나를 고르거나 비워 두면 전체
              </span>
            </Label>
            <Input
              id="item-filter"
              value={itemFilter}
              onChange={(event) => setItemFilter(event.target.value)}
              placeholder="이름의 일부"
              className="h-8 w-40"
            />
          </div>

          {/* **펼쳐 둔다.** 접으면 무엇을 물을 수 있는지 자체를 모른다 — 이 목록이
              곧 「이 시스템에 무엇을 물을 수 있나」 다. */}
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => setTestItem('')}
              className={chipClass(testItem === '')}
            >
              전체
            </button>
            {shownItems.map((one) => (
              <button
                key={one.id}
                type="button"
                // 다시 누르면 풀린다 — 고른 것을 지우려고 「전체」 를 찾아가지 않게.
                onClick={() => setTestItem((current) => (current === one.id ? '' : one.id))}
                className={chipClass(testItem === one.id, one.usage_count === 0)}
                title={
                  one.usage_count === 0
                    ? '이 항목을 하는 계열이 카탈로그에 없습니다 — 결과가 비어 있을 수 있습니다'
                    : `${one.usage_count}군데서 쓰입니다`
                }
              >
                {one.value}
              </button>
            ))}
            {shownItems.length === 0 && (
              <p className="text-muted-foreground text-sm">
                그 말과 맞는 시험 항목이 없습니다.
              </p>
            )}
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="add-condition">조건 추가</Label>
            <Select value="" onValueChange={addCondition}>
              <SelectTrigger id="add-condition">
                <SelectValue placeholder="온도 · 하중 · 주파수 …" />
              </SelectTrigger>
              <SelectContent>
                {(conditions.data ?? []).map((one) => (
                  <SelectItem key={one.id} value={one.id}>
                    {one.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {rows.map((row, index) => (
          <div key={row.key.id} className="flex flex-wrap items-end gap-2">
            <div className="w-40 shrink-0">
              <Label className="text-xs">{row.key.label}</Label>
            </div>
            <Select
              value={row.mode}
              onValueChange={(mode) =>
                setRows((current) =>
                  current.map((one, i) =>
                    i === index ? { ...one, mode: mode as ConditionRow['mode'] } : one,
                  ),
                )
              }
            >
              <SelectTrigger className="w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(MODE_LABEL).map(([mode, label]) => (
                  <SelectItem key={mode} value={mode}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              type="number"
              value={row.value}
              onChange={(event) =>
                setRows((current) =>
                  current.map((one, i) =>
                    i === index ? { ...one, value: event.target.value } : one,
                  ),
                )
              }
              className="w-32"
              placeholder="값"
            />
            {/* **단위를 적어 준다.** 숫자만 받으면 20 이 N 인지 kN 인지 알 수 없고,
                그 둘은 자릿수가 셋 다르다. */}
            <span className="text-muted-foreground pb-2 text-sm">
              {row.key.display_unit || row.key.si_unit}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setRows((current) => current.filter((_, i) => i !== index))}
            >
              빼기
            </Button>
          </div>
        ))}

        <div className="flex items-center gap-3">
          <Button onClick={run} disabled={busy}>
            <SearchIcon className="size-4" />
            {busy ? '찾는 중…' : '찾기'}
          </Button>
          <label className="text-muted-foreground flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={includeUnavailable}
              onChange={(event) => setIncludeUnavailable(event.target.checked)}
            />
            {/* 기본은 뺀다 — 오늘 시험을 잡을 수 없는 장비를 가능하다고 답하면,
                그 답을 믿고 일정을 짠 사람이 막힌다. */}
            점검·고장·폐기 장비도 보기
          </label>
        </div>
      </div>

      <ErrorNotice error={error ?? items.error ?? conditions.error} />

      {result && <SearchResult result={result} />}
    </div>
  )
}

function SearchResult({ result }: { result: SearchResponse }) {
  if (result.hits.length === 0) {
    return (
      <EmptyState
        title="조건에 맞는 장비가 없습니다"
        hint={
          <>
            {/* **왜 비었는지 말한다.** 조건에 걸려 빠진 것과 애초에 안 적힌 것은
                할 일이 다르다 — 앞은 조건을 넓히는 일이고, 뒤는 채우는 일이다. */}
            조건에 걸려 빠진 시험 항목이 {result.unmet_count}건 있습니다.
            {result.unregistered_equipment > 0 && (
              <>
                {' '}
                그리고 시험 항목이 아직 안 적힌 장비가 {result.unregistered_equipment}대 있어
                검색에 걸리지 않습니다.
              </>
            )}
          </>
        }
        action={
          <Button asChild variant="outline">
            <Link to="/equipment">장비 목록 보기</Link>
          </Button>
        }
      />
    )
  }

  return (
    <div className="space-y-3">
      <p className="text-muted-foreground text-sm">
        {result.total}건. 조건에 걸려 빠진 시험 항목 {result.unmet_count}건.
        {result.unregistered_equipment > 0 && (
          <> 시험 항목 미등록 장비 {result.unregistered_equipment}대는 검색에 안 걸립니다.</>
        )}
      </p>

      <ul className="space-y-3">
        {result.hits.map((hit) => (
          <li key={hit.equipment_test_item_id} className="rounded-md border p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    to={`/equipment/${hit.equipment_id}`}
                    className="font-medium hover:underline"
                  >
                    {hit.asset_no} · {hit.equipment_name}
                  </Link>
                  <StatusBadge kind="verdict" value={hit.verdict} />
                  <StatusBadge kind="equipment" value={hit.status} />
                  <StatusBadge kind="confidence" value={hit.confidence} />
                </div>
                <p className="text-muted-foreground mt-1 text-sm">
                  {hit.test_item}
                  {hit.method_code ? ` · ${hit.method_code}` : ''}
                </p>
                {/* **찾은 다음에 연락할 사람이 없으면 검색은 절반만 한 것이다.** */}
                <p className="text-muted-foreground mt-1 text-sm">
                  {[hit.workspace_name, hit.site, hit.location].filter(Boolean).join(' · ') ||
                    '위치 미등록'}
                  {hit.contact_name ? ` · 담당 ${hit.contact_name}` : ''}
                </p>
                {hit.note && <p className="mt-2 text-sm">{hit.note}</p>}
              </div>
            </div>

            {hit.conditions.length > 0 && (
              <ul className="mt-3 space-y-1 border-t pt-3 text-sm">
                {hit.conditions.map((one) => (
                  <li key={one.condition_key_id} className="flex flex-wrap gap-x-2">
                    <span className="text-muted-foreground w-32 shrink-0">
                      {one.condition_label}
                    </span>
                    <span>{one.asked}</span>
                    <span className="text-muted-foreground">
                      {/* **모른다고 말한다.** 빈 칸으로 두면 된다는 뜻으로 읽힌다. */}
                      {one.condition_range
                        ? `장비 ${one.condition_range}`
                        : '장비에 이 조건이 안 적혀 있습니다'}
                    </span>
                  </li>
                ))}
              </ul>
            )}

            {hit.calibration_due_on && (
              <p className="text-muted-foreground mt-2 text-xs">
                교정 예정일 {hit.calibration_due_on}
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

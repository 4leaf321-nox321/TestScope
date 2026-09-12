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
 *
 * ## 어디서 찾나 — 보유 장비, 또는 카탈로그
 *
 * 장비 검색은 **우리가 가진 것**을 답한다. 가진 것이 없을 때 다음 물음은 늘 「그러면 무엇을
 * 사나」 이고, 그 답은 카탈로그에 있다 — 같은 물음을 계열·기종에 던진다. 기종 단위로
 * 판정하고(계열 봉투는 0.5~600 kN 이라 답이 못 된다), 기종마다 **보유 대수**를 단다 — 사기
 * 전에 있는 것을 본다.
 *
 * ## 조건은 시험 항목이 정한다
 *
 * 인장에 습도를 묻는 것은 뜻이 없다. 시험 항목마다 뜻이 있는 조건 축(검색축)이 카탈로그의
 * 「시험 항목」 에 적혀 있고, 여기서는 고른 시험 항목의 축만 조건 칸에 낸다 — 물성으로 물으면
 * 그 물성을 내는 시험 항목들의 축을 합친다. 축이 안 정해진 항목이면 전부를 내되 **그렇다고
 * 말한다**: 조용히 일곱 개를 다 내면 사람은 뭘 채워야 하는지 모른다.
 *
 * ## 물성으로도 묻는다
 *
 * 「인장강도 재는 장비」 가 사람의 말이다. 물성을 고르면 서버가 그것을 내는 시험 항목
 * 전부로 펼쳐 찾고(N:M — Tg 는 DSC·DMA·TMA 셋), 응답이 **무엇으로 펼쳤는지** 를 돌려준다.
 * 펼친 것이 없으면 「장비가 없다」 가 아니라 「연결이 없다」 라고 말해야 한다 — 그 둘은
 * 할 일이 다르다.
 */

import { useMemo, useState } from 'react'
import { Search as SearchIcon } from 'lucide-react'
import { Link } from 'react-router-dom'

import { ApiError } from '@/shared/api/client'
import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { SearchablePicker } from '@/shared/components/SearchablePicker'
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
import { propertyApi } from '@/modules/properties/api'
import { searchApi } from '@/modules/search/api'
import { testItemCatalogApi } from '@/modules/test_items/api'
import type {
  CatalogSearchResponse,
  ConditionQuery,
  SearchResponse,
} from '@/modules/search/api'

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

/** `unknown` 의 이유를 사람 말로. **어디를 채우면 되는지**까지 — 「모른다」 만 말하면 사람은
 *  채울 자리를 못 찾는다. 장비 쪽은 그 장비의 조건, 카탈로그 쪽은 그 기종의 사양이다. */
function whyUnknown(reason: string | null | undefined, scope: 'owned' | 'catalog'): string {
  const where = scope === 'owned' ? '장비 조건에' : '기종 사양에'
  switch (reason) {
    case 'missing':
      return `${where} 이 조건이 안 적혀 있습니다 — 적으면 판정됩니다`
    case 'no_range':
      return `${where} 범위가 비어 있습니다`
    case 'no_max':
      return `${where} 상한이 없어 「이상」 을 판정할 수 없습니다 — 상한을 적으세요`
    case 'no_min':
      return `${where} 하한이 없어 「이하」 를 판정할 수 없습니다 — 하한을 적으세요`
    default:
      return ''
  }
}

function toQuery(row: ConditionRow): ConditionQuery | null {
  const value = Number(row.value)
  if (row.value.trim() === '' || Number.isNaN(value)) return null
  return { condition_key_id: row.key.id, [row.mode]: value }
}

export default function SearchPage() {
  const items = useResource(() => vocabularyApi.terms(AXIS.testItem), [])
  const conditions = useResource(() => vocabularyApi.conditions(), [])
  // **이어진 것만** 고르게 한다 — 연결 없는 물성을 골라 봐야 결과가 늘 비고, 사람은
  // 그것을 「우리 장비가 없다」 로 읽는다.
  const properties = useResource(() => propertyApi.list({ linkedOnly: true }), [])
  // 시험 항목마다의 검색축 — 96 줄이라 한 번에 받아 둔다.
  const axes = useResource(() => testItemCatalogApi.list(), [])

  const [testItem, setTestItem] = useState<string>('')
  const [property, setProperty] = useState<string>('')
  /** 항목이 87종이라 **치는 길도 함께** 낸다. 눈으로 훑는 길만 두면 아는 이름을
   *  가진 사람이 매번 전체를 훑어야 한다. */
  const [itemFilter, setItemFilter] = useState('')
  const [rows, setRows] = useState<ConditionRow[]>([])
  const [includeUnavailable, setIncludeUnavailable] = useState(false)
  /** 어디서 찾나. `owned` 는 보유 장비, `catalog` 는 계열·기종. */
  const [scope, setScope] = useState<'owned' | 'catalog'>('owned')
  const [result, setResult] = useState<SearchResponse | null>(null)
  const [catalog, setCatalog] = useState<CatalogSearchResponse | null>(null)
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

  /** 지금 물음에 뜻이 있는 조건 축. `null` 이면 「정해진 것이 없다」 — 전부를 낸다. */
  const relevantKeyIds = useMemo<Set<string> | null>(() => {
    const byItem = new Map((axes.data ?? []).map((row) => [row.id, row.condition_key_ids]))
    let itemIds: string[] = []
    if (testItem) itemIds = [testItem]
    else if (property) {
      const picked = (properties.data ?? []).find((one) => one.id === property)
      itemIds = picked ? picked.links.map((link) => link.test_item_term_id) : []
    }
    if (itemIds.length === 0) return null
    const union = new Set<string>()
    for (const id of itemIds) for (const keyId of byItem.get(id) ?? []) union.add(keyId)
    // 고른 항목 전부에 축이 없으면 정해진 것이 없는 것이다.
    return union.size === 0 ? null : union
  }, [axes.data, testItem, property, properties.data])
  /** 축이 정해진 항목을 골랐나 — 아니면 「안 정해졌다」 고 말한다. */
  const axesUndecided = (testItem !== '' || property !== '') && relevantKeyIds === null
  const shownConditions = useMemo(() => {
    const all = conditions.data ?? []
    if (!relevantKeyIds) return all
    // 뜻이 있는 축이 먼저, 나머지는 뒤에 — 숨기지는 않는다. 「전에는 됐는데」 가 안 생기게.
    return [
      ...all.filter((one) => relevantKeyIds.has(one.id)),
      ...all.filter((one) => !relevantKeyIds.has(one.id)),
    ]
  }, [conditions.data, relevantKeyIds])

  function rowFor(key: ConditionKey): ConditionRow {
    // 하중처럼 "얼마까지 되나" 를 묻는 조건은 대개 이상으로, 온도는 그 값에서.
    const mode: ConditionRow['mode'] = key.dimension === 'force' ? 'at_least' : 'at'
    return { key, mode, value: '' }
  }

  function addCondition(keyId: string) {
    const key = (conditions.data ?? []).find((one) => one.id === keyId)
    if (!key || rows.some((row) => row.key.id === keyId)) return
    setRows((current) => [...current, rowFor(key)])
  }

  /** 시험 항목을 고르면 그 항목의 축을 **조건 칸에 미리 깐다** — 무엇을 채우면 되는지가
   *  보이게. 이미 값을 적은 줄은 남기고, 다른 시험의 축이던 빈 줄은 걷는다. */
  function pickTestItem(next: string) {
    setTestItem(next)
    const row = (axes.data ?? []).find((one) => one.id === next)
    const wanted = new Set(row?.condition_key_ids ?? [])
    setRows((current) => {
      const kept = current.filter((one) => one.value.trim() !== '' || wanted.has(one.key.id))
      const have = new Set(kept.map((one) => one.key.id))
      const added = (conditions.data ?? [])
        .filter((key) => wanted.has(key.id) && !have.has(key.id))
        .map(rowFor)
      return [...kept, ...added]
    })
  }

  async function run() {
    setBusy(true)
    setError(null)
    const body = {
      test_item_term_id: testItem || null,
      property_term_id: property || null,
      conditions: rows.map(toQuery).filter((one): one is ConditionQuery => one !== null),
      include_unavailable: includeUnavailable,
    }
    try {
      if (scope === 'catalog') {
        setResult(null)
        setCatalog(await searchApi.catalog(body))
      } else {
        setCatalog(null)
        setResult(await searchApi.test_items(body))
      }
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
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <Label htmlFor="property">
              물성으로 묻기
              <span className="text-muted-foreground ml-2 font-normal">
                「인장강도」 처럼 — 그것을 내는 시험 항목 전부로 찾습니다
              </span>
            </Label>
            <SearchablePicker
              id="property"
              options={(properties.data ?? []).map((one) => ({
                id: one.id,
                label: one.value,
                detail: one.links.map((link) => link.test_item).join(' · '),
              }))}
              value={property}
              onChange={setProperty}
              placeholder="물성 (선택)"
              detailTitle="물성 항목"
              detailHint="시험 항목이 이어진 물성만 — 나머지는 「물성 항목」 화면에서 잇습니다"
              className="w-72"
            />
          </div>
          {property && (
            <Button variant="ghost" size="sm" onClick={() => setProperty('')}>
              물성 풀기
            </Button>
          )}
        </div>

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
              onClick={() => pickTestItem('')}
              className={chipClass(testItem === '')}
            >
              전체
            </button>
            {shownItems.map((one) => (
              <button
                key={one.id}
                type="button"
                // 다시 누르면 풀린다 — 고른 것을 지우려고 「전체」 를 찾아가지 않게.
                onClick={() => pickTestItem(testItem === one.id ? '' : one.id)}
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
            <Label htmlFor="add-condition">
              조건 추가
              {relevantKeyIds && (
                <span className="text-muted-foreground ml-2 font-normal">
                  이 시험의 축이 위에, 나머지는 아래
                </span>
              )}
            </Label>
            <Select value="" onValueChange={addCondition}>
              <SelectTrigger id="add-condition">
                <SelectValue placeholder="온도 · 하중 · 주파수 …" />
              </SelectTrigger>
              <SelectContent>
                {shownConditions.map((one) => (
                  <SelectItem key={one.id} value={one.id}>
                    {one.label}
                    {relevantKeyIds && !relevantKeyIds.has(one.id)
                      ? ' (이 시험의 축 아님)'
                      : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {axesUndecided && (
              // **말한다.** 조용히 일곱 개를 다 내면 사람은 뭘 채워야 하는지 모른다.
              <p className="text-muted-foreground text-xs">
                이 시험의 검색축이 아직 안 정해져 조건을 전부 보입니다 —{' '}
                <Link
                  to={
                    testItem
                      ? `/catalog/test-items/${testItem}`
                      : '/catalog/test-items?gap=axes'
                  }
                  className="underline"
                >
                  시험 항목에서 정하기
                </Link>
              </p>
            )}
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

        <div className="flex flex-wrap items-center gap-3">
          {/* **어디서 찾나.** 가진 것과 세상에 있는 것은 다른 물음이라 갈라 둔다 — 한
              목록에 섞으면 「우리한테 있다」 로 읽힌다. */}
          <div
            className="inline-flex rounded-md border"
            role="tablist"
            aria-label="어디서 찾나"
          >
            {(
              [
                ['owned', '보유 장비에서'],
                ['catalog', '카탈로그에서'],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={scope === key}
                onClick={() => setScope(key)}
                className={`px-3 py-1.5 text-sm ${scope === key ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}
              >
                {label}
              </button>
            ))}
          </div>
          <Button onClick={run} disabled={busy}>
            <SearchIcon className="size-4" />
            {busy ? '찾는 중…' : '찾기'}
          </Button>
          {scope === 'owned' && (
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
          )}
        </div>
      </div>

      <ErrorNotice error={error ?? items.error ?? conditions.error ?? properties.error} />

      {result && <SearchResult result={result} />}
      {catalog && <CatalogResult result={catalog} />}
    </div>
  )
}

/** 「없습니다」 를 왜로 — 세 수가 세 가지 할 일을 가른다. */
function Diagnosis({ result }: { result: SearchResponse }) {
  const d = result.diagnosis
  return (
    <ul className="mt-1 list-disc space-y-0.5 pl-5 text-left">
      {d && d.equipment_with_item === 0 ? (
        <li>
          이 시험 항목이 적힌 보유 장비가 <strong>0대</strong>입니다 — 조건이 좁은 것이 아니라
          아무도 이 시험을 등록하지 않았습니다.
        </li>
      ) : (
        <li>
          조건에 걸려 빠진 시험 항목이 <strong>{result.unmet_count}건</strong> 있습니다
          {d && ` (이 시험을 적은 장비 ${d.equipment_with_item}대 중)`}. 조건을 넓혀 보세요.
        </li>
      )}
      {d && d.catalog_series_with_item > 0 && (
        <li>
          카탈로그에는 이 시험을 하는 계열이 <strong>{d.catalog_series_with_item}개</strong>{' '}
          있습니다 — 위의 「카탈로그에서」 로 찾으면 어떤 기종이 되는지 나옵니다.
        </li>
      )}
      {d && d.unlinked_equipment > 0 && (
        <li>
          기종에 안 이어진 장비가 <strong>{d.unlinked_equipment}대</strong> 있습니다 — 그
          장비들은 카탈로그의 시험 항목을 못 받아 검색에 안 걸립니다.{' '}
          <Link to="/equipment?catalog=unlinked" className="underline">
            이어 주기
          </Link>
        </li>
      )}
      {result.unregistered_equipment > 0 && (
        <li>
          시험 항목이 하나도 안 적힌 장비가 <strong>{result.unregistered_equipment}대</strong>{' '}
          있습니다.{' '}
          <Link to="/equipment?test_item=none" className="underline">
            적으러 가기
          </Link>
        </li>
      )}
    </ul>
  )
}

/** 카탈로그 답 — 계열 한 장에 기종이 줄줄이. **기종 단위 판정**이고 보유 대수가 붙는다. */
function CatalogResult({ result }: { result: CatalogSearchResponse }) {
  const expanded =
    result.expanded_test_items.length > 0 ? (
      <p className="text-muted-foreground text-sm">
        물성을 시험 항목 <strong>{result.expanded_test_items.join(' · ')}</strong> 으로 펼쳐
        찾았습니다.
      </p>
    ) : null

  if (result.hits.length === 0) {
    return (
      <EmptyState
        title="조건에 맞는 기종이 카탈로그에 없습니다"
        hint={
          <>
            {expanded}
            조건에 걸려 빠진 기종이 {result.unmet_models}종 있습니다.
            {result.unmet_models === 0 &&
              ' 이 시험 항목을 하는 계열이 카탈로그에 없거나, 기종에 사양이 안 적혀 있습니다.'}
          </>
        }
        action={
          <Button asChild variant="outline">
            <Link to="/catalog/equipment-series">계열 목록 보기</Link>
          </Button>
        }
      />
    )
  }

  return (
    <div className="space-y-3">
      {expanded}
      <p className="text-muted-foreground text-sm">
        계열 {result.total_series} · 기종 {result.total_models}. 조건에 걸려 빠진 기종{' '}
        {result.unmet_models}종.
      </p>
      <ul className="space-y-3">
        {result.hits.map((hit) => (
          <li key={hit.series_id} className="rounded-md border p-4">
            <div className="flex flex-wrap items-center gap-2">
              <Link
                to={`/catalog/equipment-series/${hit.series_id}`}
                className="font-medium hover:underline"
              >
                {hit.series_name}
              </Link>
              <span className="text-muted-foreground text-sm">
                {[hit.maker, hit.category].filter(Boolean).join(' · ')}
              </span>
            </div>
            <p className="text-muted-foreground mt-1 text-sm">
              {hit.test_item}
              {hit.methods.length > 0 && ` · ${hit.methods.join(' · ')}`}
            </p>
            {hit.note && <p className="mt-1 text-sm">{hit.note}</p>}
            <ul className="mt-3 divide-y border-t text-sm">
              {hit.models.map((model) => (
                <li key={model.model_id} className="flex flex-wrap items-center gap-2 py-1.5">
                  <Link
                    to={`/catalog/equipment-models/${model.model_id}`}
                    className="w-48 truncate hover:underline"
                  >
                    {model.model_name}
                  </Link>
                  <StatusBadge kind="verdict" value={model.verdict} />
                  {/* **사기 전에 있는 것을 본다.** 0 이면 그냥 비운다 — 「없음」 을 붉게 칠하면
                      살 것이 아니라 없는 것으로 읽힌다. */}
                  {model.owned_units > 0 && (
                    <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-xs text-emerald-700">
                      보유 {model.owned_units}대
                    </span>
                  )}
                  <span className="text-muted-foreground flex flex-wrap gap-x-3 text-xs">
                    {model.conditions.map((one) => (
                      <span key={one.condition_key_id}>
                        {one.condition_label} {one.condition_range ?? '안 적힘'}
                        {one.verdict === 'accessory' && ' (부속)'}
                        {one.verdict === 'unknown' &&
                          ` — ${whyUnknown(one.reason, 'catalog')}`}
                      </span>
                    ))}
                  </span>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </div>
  )
}

function SearchResult({ result }: { result: SearchResponse }) {
  const expanded =
    result.expanded_test_items.length > 0 ? (
      <p className="text-muted-foreground text-sm">
        물성을 시험 항목 <strong>{result.expanded_test_items.join(' · ')}</strong> 으로 펼쳐
        찾았습니다.
      </p>
    ) : null

  if (result.hits.length === 0) {
    return (
      <EmptyState
        title={
          result.diagnosis && result.diagnosis.equipment_with_item === 0
            ? '이 시험을 하는 장비가 등록된 적이 없습니다'
            : '조건에 맞는 장비가 없습니다'
        }
        hint={
          <>
            {expanded}
            {/* **왜 비었는지 말한다.** 조건에 걸려 빠진 것, 애초에 안 적힌 것, 카탈로그에만
                있는 것은 할 일이 다르다 — 앞은 조건을 넓히는 일, 가운데는 채우는 일, 뒤는
                사는 일이다. 수는 서버가 세고, 말은 여기서 한다. */}
            <Diagnosis result={result} />
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
      {expanded}
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
                      {one.condition_range ? `장비 ${one.condition_range}` : null}
                    </span>
                    {one.verdict === 'unknown' && (
                      <span className="text-muted-foreground">
                        {whyUnknown(one.reason, 'owned')}{' '}
                        <Link
                          to={`/equipment/${hit.equipment_id}`}
                          className="underline decoration-dotted underline-offset-2"
                        >
                          채우기
                        </Link>
                      </span>
                    )}
                    {one.verdict === 'accessory' && (
                      <span className="text-amber-700">
                        옵션 부속(챔버·노)이 있어야 되는 범위
                      </span>
                    )}
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

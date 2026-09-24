/**
 * 물성 항목 — **어떤 시험으로 어떤 물성을 얻나, 양쪽에서.**
 *
 *     물성  ⇄  시험 항목  ->  요구 조건  ->  시험법  ->  가능한 장비  ->  보유 위치
 *      N:M
 *
 * 사람이 묻는 말은 「인장 되는 장비」 보다 「**인장강도** 알고 싶은데 어디서 하나」 에 가깝다.
 * 이 화면이 그 두 말 사이의 다리다.
 *
 * ## 두 방향이 다 있어야 한다
 *
 * 물성에서 보면 「Tg 는 DSC·DMA·TMA 셋에서 나온다」(N:1)가 보이고, 시험 항목에서 보면
 * 「인장은 강도·항복·영률·연신율을 낸다」(1:N)가 보인다. 한쪽만 두면 반대 물음은 표를 전부
 * 훑어야 한다. 알마다 **반대편 수**를 달아 둔다 — 「DSC ×6」 은 DSC 가 여섯 물성을 낸다는
 * 뜻이고, 그 알을 누르면 그쪽 줄로 간다.
 *
 * ## 제안과 확인을 다르게 그린다
 *
 * 첫 채움은 기계가 했다(온톨로지·MaterialTwin). 그것은 **제안**이고 점선으로 선다. 사람이
 * 보고 ✓ 를 누르면 확인이 된다. 둘을 같은 얼굴로 그리면 아무도 되짚지 않고, 「굽힘으로
 * 인장강도」 같은 오답이 확인된 것과 나란히 앉는다.
 *
 * ## 확인은 줄 단위로 묶는다
 *
 * 제안 254건을 알 하나씩 누르게 두면 아무도 끝내지 못한다 — 실제로 확인이 0 인 채로 남아
 * 있었다. 사람이 실제로 판단하는 단위는 줄이다: 「인장이 내는 것은 이 다섯 개, 맞다」.
 * 그래서 줄마다 「N개 다 확인」 을 두고, 거른 목록 전체에도 같은 단추를 둔다.
 *
 * **되돌릴 길을 같이 둔다.** 묶음은 빠른 만큼 잘못 누르면 크게 잘못되는데, 되돌리기가 없으면
 * 사람은 아예 안 누른다 — 그러면 한 줄씩 누르는 것과 같아진다.
 *
 * ## 이어진 것이 없는 줄도 보인다
 *
 * 271 물성 중 시험이 이어진 것은 174 다. 나머지를 숨기면 「우리는 이 물성을 못 잰다」 와
 * 「아직 아무도 안 이었다」 가 같아진다. 시험 항목 쪽도 같다 — 물성을 안 내는 시험(EMC·
 * 낙하)은 그 사실이 보여야 한다.
 */

import { useMemo, useState } from 'react'
import { Check, CheckCheck, Plus, Trash2, Undo2 } from 'lucide-react'

import { ApiError } from '@/shared/api/client'
import { useAuth } from '@/shared/auth/AuthContext'
import { NewTermButton } from '@/modules/vocabulary/NewTermButton'
import { isSystemAdmin } from '@/shared/auth/roles'
import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
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
import { useBackFromReference } from '@/shared/hooks/useBackFromReference'
import { AXIS, vocabularyApi } from '@/modules/vocabulary/api'
import type { Term } from '@/modules/vocabulary/api'
import { DOMAIN_LABEL, propertyApi } from '@/modules/properties/api'
import type { Property, TestItemProperty } from '@/modules/properties/api'

type View = 'property' | 'item'

/**
 * 이 연결을 누가 적었나.
 *
 * **「카탈로그 원본」 이라고 밝힌다.** 화면 하나가 「온톨로지」 라는 이름을 갖게 됐으므로
 * (관리 → 온톨로지), 여기서 그냥 「온톨로지」 라고 쓰면 「저 화면에서 누가 적었나」 로
 * 읽힌다 — 실제로는 반입이 카탈로그 원본(`source/catalog/ontology`)에서 가져온 것이다.
 */
const SOURCE_LABEL: Record<string, string> = {
  ontology: '카탈로그 원본',
  materialtwin: 'MaterialTwin',
  manual: '손으로',
}

/** 알 하나 — 연결 한 줄. 제안은 점선, 확인은 칠. `count` 는 반대편에 몇이 이어졌나. */
function LinkChip({
  label,
  link,
  count,
  admin,
  onOpen,
  onConfirm,
  onRemove,
}: {
  label: string
  link: TestItemProperty
  count: number
  admin: boolean
  onOpen: () => void
  onConfirm: () => void
  onRemove: () => void
}) {
  const suggested = link.status === 'suggested'
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs ${
        suggested ? 'border-dashed text-muted-foreground' : 'bg-muted'
      }`}
      title={[
        suggested ? '자동 제안 연결 — 아직 사람이 확인하지 않았습니다' : '확인된 연결',
        `출처: ${SOURCE_LABEL[link.source] ?? link.source}`,
        link.note ?? '',
      ]
        .filter(Boolean)
        .join('\n')}
    >
      <button type="button" onClick={onOpen} className="hover:underline">
        {label}
      </button>
      {/* **반대편 수.** ×3 이면 이것이 다른 둘과도 이어져 있다 — N:1 이 여기서 보인다. */}
      {count > 1 && <span className="text-muted-foreground">×{count}</span>}
      {link.note && <span className="text-muted-foreground">· {link.note}</span>}
      {admin && suggested && (
        <button
          type="button"
          onClick={onConfirm}
          className="hover:text-foreground ml-0.5"
          aria-label={`${label} 연결 확인`}
        >
          <Check className="size-3" />
        </button>
      )}
      {admin && (
        <button
          type="button"
          onClick={onRemove}
          className="hover:text-destructive ml-0.5"
          aria-label={`${label} 연결 지우기`}
        >
          <Trash2 className="size-3" />
        </button>
      )}
    </span>
  )
}

/** 줄 하나를 통째로 확인 — **사람이 실제로 판단하는 단위**다. 「인장이 내는 것은 이
 *  다섯 개, 맞다」 를 한 번에 말하게 한다. 제안이 없으면 안 보인다. */
function RowConfirm({
  admin,
  busy,
  label,
  ids,
  onConfirm,
}: {
  admin: boolean
  busy: boolean
  label: string
  ids: string[]
  onConfirm: (ids: string[]) => void
}) {
  if (!admin || ids.length === 0) return null
  return (
    <Button
      size="sm"
      variant="ghost"
      className="h-6 px-1.5 text-xs"
      disabled={busy}
      aria-label={`${label} 제안 ${ids.length}개 다 확인`}
      onClick={() => onConfirm(ids)}
    >
      <Check className="mr-1 size-3" />
      {ids.length}개 다 확인
    </Button>
  )
}

/** 시험 항목 한 줄 — 시험에서 보는 눈. */
interface ItemRow {
  id: string
  value: string
  links: { link: TestItemProperty; property: Property }[]
}

export default function PropertiesPage() {
  const { user } = useAuth()
  const admin = isSystemAdmin(user)
  const [view, setView] = useState<View>('property')
  const [query, setQuery] = useState('')
  const [domain, setDomain] = useState('')
  const [linkedOnly, setLinkedOnly] = useState(false)
  /** 확인 안 한 것만 — **검토하는 사람의 눈**이다. 다 확인하면 목록이 비고, 그것이 끝났다는
   *  표시가 된다. 확인된 것까지 섞여 있으면 어디까지 봤는지 매번 다시 찾는다. */
  const [suggestedOnly, setSuggestedOnly] = useState(false)
  /** 여럿에 이어진 것만 — 물성 쪽은 「여러 시험에서 나오는 물성」(N:1), 시험 쪽은
   *  「여러 물성을 내는 시험」(1:N). 갈림이 있는 곳이 사람이 봐야 하는 곳이다. */
  const [manyOnly, setManyOnly] = useState(false)
  /** 알을 눌러 건너온 줄 하나. 있으면 그 줄만 보인다. */
  const [focus, setFocus] = useState<{ view: View; id: string } | null>(null)
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [adding, setAdding] = useState<string | null>(null)
  const [picked, setPicked] = useState('')
  /** 방금 묶음으로 확인한 것 — 되돌릴 수 있게 id 를 들고 있는다. */
  const [undoable, setUndoable] = useState<{ ids: string[]; count: number } | null>(null)
  const [busy, setBusy] = useState(false)

  // **전부 받아 둔다** — 271 물성 · 254 연결이라 한 번이면 되고, 두 방향과 반대편
  // 수를 화면이 셀 수 있다. 서버 거르기는 안 쓴다: 반대편 수는 전체를 알아야 맞다.
  const properties = useResource(() => propertyApi.list(), [])
  const items = useResource(() => vocabularyApi.terms(AXIS.testItem), [])

  const allProps = useMemo(() => properties.data ?? [], [properties.data])

  /** 시험 항목마다 물성 몇 개. */
  const perItem = useMemo(() => {
    const out = new Map<string, number>()
    for (const one of allProps)
      for (const link of one.links)
        out.set(link.test_item_term_id, (out.get(link.test_item_term_id) ?? 0) + 1)
    return out
  }, [allProps])

  const itemRows = useMemo<ItemRow[]>(() => {
    const byId = new Map<string, ItemRow>()
    for (const term of (items.data ?? []) as Term[])
      byId.set(term.id, { id: term.id, value: term.value, links: [] })
    for (const property of allProps)
      for (const link of property.links) {
        const row = byId.get(link.test_item_term_id)
        if (row) row.links.push({ link, property })
      }
    return [...byId.values()].sort((a, b) => a.value.localeCompare(b.value, 'ko'))
  }, [items.data, allProps])

  const needle = query.trim().toLowerCase()
  const shownProps = allProps.filter((one) => {
    if (focus?.view === 'property') return one.id === focus.id
    if (domain && one.domain !== domain) return false
    if (linkedOnly && one.links.length === 0) return false
    if (suggestedOnly && !one.links.some((link) => link.status === 'suggested')) return false
    if (manyOnly && one.links.length < 2) return false
    if (!needle) return true
    return [
      one.value,
      one.code ?? '',
      ...one.aliases,
      ...one.links.map((l) => l.test_item),
    ].some((text) => text.toLowerCase().includes(needle))
  })
  const shownItems = itemRows.filter((one) => {
    if (focus?.view === 'item') return one.id === focus.id
    if (linkedOnly && one.links.length === 0) return false
    if (suggestedOnly && !one.links.some(({ link }) => link.status === 'suggested'))
      return false
    if (manyOnly && one.links.length < 2) return false
    if (domain && !one.links.some((l) => l.property.domain === domain)) return false
    if (!needle) return true
    return [one.value, ...one.links.map((l) => l.property.value)].some((text) =>
      text.toLowerCase().includes(needle),
    )
  })

  /** 도메인별로 묶는다 — 271 줄을 한 표로 두면 「열」 과 「기계」 가 섞여 훑을 수 없다. */
  const grouped = useMemo(() => {
    const out = new Map<string, Property[]>()
    for (const one of shownProps) {
      const key = one.domain ?? ''
      out.set(key, [...(out.get(key) ?? []), one])
    }
    return [...out.entries()]
  }, [shownProps])

  async function run(work: () => Promise<unknown>) {
    setError(null)
    try {
      await work()
      properties.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

  /** 제안 여럿을 한 번에 확인한다. **되돌릴 수 있게** 무엇을 바꿨는지 들고 있는다. */
  async function confirmMany(ids: string[]) {
    if (ids.length === 0) return
    setBusy(true)
    await run(async () => {
      const got = await propertyApi.bulk(ids, 'confirmed')
      setUndoable(got.changed > 0 ? { ids, count: got.changed } : null)
    })
    setBusy(false)
  }

  /** 거른 목록에서 아직 확인 안 한 연결 전부. 화면에 보이는 것만 — 안 보이는 것을 함께
   *  바꾸면 사람이 무엇을 확인한 것인지 알 수 없다. */
  const shownSuggested = useMemo(() => {
    if (view === 'property')
      return shownProps.flatMap((one) =>
        one.links.filter((link) => link.status === 'suggested').map((link) => link.id),
      )
    return shownItems.flatMap((row) =>
      row.links.filter(({ link }) => link.status === 'suggested').map(({ link }) => link.id),
    )
  }, [view, shownProps, shownItems])

  function jump(to: View, id: string) {
    setFocus({ view: to, id })
    setView(to)
    setAdding(null)
  }

  const linkedProps = allProps.filter((one) => one.links.length > 0).length
  const linkedItems = itemRows.filter((one) => one.links.length > 0).length
  const suggested = allProps.reduce(
    (sum, one) => sum + one.links.filter((link) => link.status === 'suggested').length,
    0,
  )

  function adder(kind: View, rowId: string, taken: Set<string>) {
    if (!admin) return null
    if (adding !== rowId) {
      return (
        <Button
          size="sm"
          variant="ghost"
          className="h-6 px-1.5 text-xs"
          onClick={() => {
            setAdding(rowId)
            setPicked('')
          }}
        >
          <Plus className="mr-1 size-3" />
          {kind === 'property' ? '시험 연결' : '물성 연결'}
        </Button>
      )
    }
    const options =
      kind === 'property'
        ? itemRows
            .filter((one) => !taken.has(one.id))
            .map((one) => ({ id: one.id, label: one.value }))
        : allProps
            .filter((one) => !taken.has(one.id))
            .map((one) => ({ id: one.id, label: one.value, detail: one.code }))
    return (
      <div className="mt-1 flex flex-wrap items-center gap-2">
        <SearchablePicker
          options={options}
          value={picked}
          onChange={setPicked}
          placeholder={kind === 'property' ? '시험 항목' : '물성'}
          detailTitle={kind === 'property' ? '시험 항목' : '물성 항목'}
          className="w-72"
        />
        <Button
          size="sm"
          disabled={!picked}
          onClick={() =>
            void run(async () => {
              await propertyApi.link(
                kind === 'property'
                  ? { test_item_term_id: picked, property_term_id: rowId }
                  : { test_item_term_id: rowId, property_term_id: picked },
              )
              setAdding(null)
            })
          }
        >
          연결
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setAdding(null)}>
          취소
        </Button>
      </div>
    )
  }

  const empty = view === 'property' ? shownProps.length === 0 : shownItems.length === 0

  return (
    <div className="space-y-6">
      <PageHeader
        back={useBackFromReference()}
        title="물성 항목"
        description="어떤 시험으로 어떤 물성을 얻는지. 검색이 「인장강도 재는 장비」 를 이 표로 시험 항목으로 바꿉니다."
        actions={<NewTermButton slug="property" onCreated={() => properties.reload()} />}
      />

      <div className="flex flex-wrap items-center gap-3">
        {/* **두 방향.** 한쪽만 두면 반대 물음은 표를 전부 훑어야 한다. */}
        <div className="inline-flex rounded-md border" role="tablist" aria-label="표시 방향">
          {(
            [
              ['property', '물성에서'],
              ['item', '시험 항목에서'],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={view === key}
              onClick={() => {
                setView(key)
                setFocus(null)
              }}
              className={`px-3 py-1.5 text-sm ${view === key ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}
            >
              {label}
            </button>
          ))}
        </div>
        <Input
          value={query}
          onChange={(event) => {
            setQuery(event.target.value)
            setFocus(null)
          }}
          placeholder={
            view === 'property' ? '물성 이름 · 키 · 별칭 · 시험' : '시험 항목 · 물성'
          }
          className="max-w-xs"
        />
        <Select
          value={domain || 'all'}
          onValueChange={(value) => {
            setDomain(value === 'all' ? '' : value)
            setFocus(null)
          }}
        >
          <SelectTrigger className="w-40">
            <SelectValue placeholder="분야 전체" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">분야 전체</SelectItem>
            {Object.keys(DOMAIN_LABEL).map((one) => (
              <SelectItem key={one} value={one}>
                {DOMAIN_LABEL[one]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <label className="text-muted-foreground flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={linkedOnly}
            onChange={(event) => setLinkedOnly(event.target.checked)}
          />
          연결된 것만
        </label>
        <label className="text-muted-foreground flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={manyOnly}
            onChange={(event) => setManyOnly(event.target.checked)}
          />
          {view === 'property' ? '여러 시험에서 나오는 물성만' : '여러 물성을 내는 시험만'}
        </label>
        <label className="text-muted-foreground flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={suggestedOnly}
            onChange={(event) => {
              setSuggestedOnly(event.target.checked)
              setFocus(null)
            }}
          />
          {/* 검토하는 사람의 눈 — 다 확인하면 목록이 비고, 그것이 끝났다는 표시가 된다. */}
          확인 안 한 것만
        </label>
      </div>

      {admin && suggested > 0 && (
        <div className="flex flex-wrap items-center gap-3 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm dark:bg-amber-950/30">
          <p>
            자동 제안 연결 <strong>{suggested}건</strong>을 아직 아무도 확인하지 않았습니다.
            확인된 연결만이 「이 물성은 이 시험으로 나온다」 의 근거가 되고, 내보내기가
            카탈로그에 싣는 값입니다.
          </p>
          {shownSuggested.length > 0 && (
            <Button size="sm" disabled={busy} onClick={() => void confirmMany(shownSuggested)}>
              <CheckCheck className="size-4" />
              {/* **보이는 것만.** 안 보이는 것까지 바꾸면 사람이 무엇을 확인한 것인지 모른다. */}
              지금 보이는 {shownSuggested.length}건 다 확인
            </Button>
          )}
        </div>
      )}

      {undoable && (
        <div className="flex flex-wrap items-center gap-3 rounded-md border p-3 text-sm">
          <span>
            <strong>{undoable.count}건</strong>을 확인으로 올렸습니다.
          </span>
          {/* 되돌릴 길이 없으면 사람은 묶음 단추를 아예 안 누른다. */}
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() =>
              void run(async () => {
                await propertyApi.bulk(undoable.ids, 'suggested')
                setUndoable(null)
              })
            }
          >
            <Undo2 className="size-4" />
            되돌리기
          </Button>
        </div>
      )}

      {properties.data && (
        <p className="text-muted-foreground text-sm">
          물성 {allProps.length}종 중 이어진 것 {linkedProps} · 시험 항목 {itemRows.length}종
          중 이어진 것 {linkedItems}
          {suggested > 0 && (
            <>
              {' '}
              · <span className="text-amber-700">확인 안 한 제안 {suggested}</span>
            </>
          )}
          {focus && (
            <>
              {' '}
              ·{' '}
              <button type="button" className="underline" onClick={() => setFocus(null)}>
                전체 보기
              </button>
            </>
          )}
        </p>
      )}

      <ErrorNotice error={properties.error ?? items.error ?? error} />

      {properties.data && empty ? (
        <EmptyState
          title={view === 'property' ? '물성이 없습니다' : '시험 항목이 없습니다'}
          hint={
            linkedOnly || manyOnly
              ? '필터를 해제해 보십시오.'
              : '카탈로그 반입(import_catalog.py)이 MaterialTwin 물성 271종과 연결을 심습니다.'
          }
        />
      ) : view === 'property' ? (
        <div className="space-y-6">
          {grouped.map(([key, rows]) => (
            <section key={key} className="space-y-2">
              <h2 className="text-muted-foreground text-sm font-medium">
                {(DOMAIN_LABEL[key] ?? key) || '분야 없음'}{' '}
                <span className="font-normal">{rows.length}</span>
              </h2>
              <table className="w-full border-collapse text-sm">
                <tbody>
                  {rows.map((one) => (
                    <tr key={one.id} className="border-b align-top">
                      <td className="w-64 py-1.5 pr-3">
                        <div className="font-medium">{one.value}</div>
                        <div className="text-muted-foreground font-mono text-xs">
                          {one.code}
                          {one.symbol && (
                            <span className="ml-1 font-sans">· {one.symbol}</span>
                          )}
                          {one.si_unit && (
                            <span className="ml-1 font-sans">[{one.si_unit}]</span>
                          )}
                        </div>
                      </td>
                      <td className="py-1.5">
                        <div className="flex flex-wrap items-center gap-1">
                          {one.links.map((link) => (
                            <LinkChip
                              key={link.id}
                              label={link.test_item}
                              link={link}
                              count={perItem.get(link.test_item_term_id) ?? 0}
                              admin={admin}
                              onOpen={() => jump('item', link.test_item_term_id)}
                              onConfirm={() =>
                                void run(() =>
                                  propertyApi.update(link.id, { status: 'confirmed' }),
                                )
                              }
                              onRemove={() => void run(() => propertyApi.unlink(link.id))}
                            />
                          ))}
                          {one.links.length === 0 && (
                            <span className="text-muted-foreground text-xs">
                              이어진 시험 없음 — 이 물성으로는 아직 검색이 안 됩니다
                            </span>
                          )}
                          {adder(
                            'property',
                            one.id,
                            new Set(one.links.map((l) => l.test_item_term_id)),
                          )}
                          <RowConfirm
                            admin={admin}
                            busy={busy}
                            label={one.value}
                            ids={one.links
                              .filter((link) => link.status === 'suggested')
                              .map((link) => link.id)}
                            onConfirm={confirmMany}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ))}
        </div>
      ) : (
        <table className="w-full border-collapse text-sm">
          <tbody>
            {shownItems.map((row) => (
              <tr key={row.id} className="border-b align-top">
                <td className="w-64 py-1.5 pr-3 font-medium">{row.value}</td>
                <td className="py-1.5">
                  <div className="flex flex-wrap items-center gap-1">
                    {row.links
                      .slice()
                      .sort((a, b) => a.property.value.localeCompare(b.property.value, 'ko'))
                      .map(({ link, property }) => (
                        <LinkChip
                          key={link.id}
                          label={property.value}
                          link={link}
                          count={property.links.length}
                          admin={admin}
                          onOpen={() => jump('property', property.id)}
                          onConfirm={() =>
                            void run(() =>
                              propertyApi.update(link.id, { status: 'confirmed' }),
                            )
                          }
                          onRemove={() => void run(() => propertyApi.unlink(link.id))}
                        />
                      ))}
                    {row.links.length === 0 && (
                      <span className="text-muted-foreground text-xs">
                        내는 물성 없음 — 판정·곡선으로 끝나는 시험이거나 아직 안 이었습니다
                      </span>
                    )}
                    {adder('item', row.id, new Set(row.links.map((l) => l.property.id)))}
                    <RowConfirm
                      admin={admin}
                      busy={busy}
                      label={row.value}
                      ids={row.links
                        .filter(({ link }) => link.status === 'suggested')
                        .map(({ link }) => link.id)}
                      onConfirm={confirmMany}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

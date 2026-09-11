/**
 * 물성 항목 — **어떤 시험으로 어떤 물성을 얻나.**
 *
 *     물성  ⇄  시험 항목  ->  요구 조건  ->  시험법  ->  가능한 장비  ->  보유 위치
 *      N:M
 *
 * 사람이 묻는 말은 「인장 되는 장비」 보다 「**인장강도** 알고 싶은데 어디서 하나」 에 가깝다.
 * 이 화면이 그 두 말 사이의 다리다. 물성 하나에 시험 여럿(Tg ← DSC·DMA·TMA), 시험 하나에
 * 물성 여럿(인장 → 강도·항복·영률·연신율)이라 표는 물성 한 줄에 시험 항목이 여러 알로 선다.
 *
 * ## 제안과 확인을 다르게 그린다
 *
 * 첫 채움은 기계가 했다(온톨로지·MaterialTwin). 그것은 **제안**이고 흐리게 선다. 사람이
 * 보고 「맞다」 를 누르면 확인이 된다. 둘을 같은 얼굴로 그리면 아무도 되짚지 않고, 「굽힘으로
 * 인장강도」 같은 오답이 확인된 것과 나란히 앉는다.
 *
 * ## 이어진 것이 없는 물성도 보인다
 *
 * 271 물성 중 시험이 이어진 것은 절반이다. 나머지를 숨기면 「우리는 이 물성을 못 잰다」 와
 * 「아직 아무도 안 이었다」 가 같아진다. 기본은 전부 보이고, 「이어진 것만」 으로 좁힌다.
 */

import { useMemo, useState } from 'react'
import { Check, Plus, Trash2 } from 'lucide-react'

import { ApiError } from '@/shared/api/client'
import { useAuth } from '@/shared/auth/AuthContext'
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
import { AXIS, vocabularyApi } from '@/modules/vocabulary/api'
import { DOMAIN_LABEL, propertyApi } from '@/modules/properties/api'
import type { Property, TestItemProperty } from '@/modules/properties/api'

/** 한 알 — 시험 항목 하나. 제안은 흐리고, 확인은 또렷하다. */
function LinkChip({
  link,
  admin,
  onConfirm,
  onRemove,
}: {
  link: TestItemProperty
  admin: boolean
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
        suggested ? '기계가 제안한 연결 — 아직 사람이 확인하지 않았습니다' : '확인된 연결',
        `출처: ${{ ontology: '온톨로지', materialtwin: 'MaterialTwin', manual: '손으로' }[link.source] ?? link.source}`,
        link.note ?? '',
      ]
        .filter(Boolean)
        .join('\n')}
    >
      {link.test_item}
      {link.note && <span className="text-muted-foreground">· {link.note}</span>}
      {admin && suggested && (
        <button
          type="button"
          onClick={onConfirm}
          className="hover:text-foreground ml-0.5"
          aria-label={`${link.test_item} 연결 확인`}
        >
          <Check className="size-3" />
        </button>
      )}
      {admin && (
        <button
          type="button"
          onClick={onRemove}
          className="hover:text-destructive ml-0.5"
          aria-label={`${link.test_item} 연결 지우기`}
        >
          <Trash2 className="size-3" />
        </button>
      )}
    </span>
  )
}

export default function PropertiesPage() {
  const { user } = useAuth()
  const admin = isSystemAdmin(user)
  const [query, setQuery] = useState('')
  const [domain, setDomain] = useState('')
  const [linkedOnly, setLinkedOnly] = useState(false)
  const [error, setError] = useState<ApiError | Error | null>(null)
  /** 어느 물성에 시험을 더하는 중인가. 한 번에 하나 — 표 전체에 피커를 깔면 271개가 뜬다. */
  const [adding, setAdding] = useState<string | null>(null)
  const [pickedItem, setPickedItem] = useState('')

  const properties = useResource(
    () => propertyApi.list({ q: query || undefined, domain: domain || undefined, linkedOnly }),
    [query, domain, linkedOnly],
  )
  const items = useResource(
    () => (admin ? vocabularyApi.terms(AXIS.testItem) : Promise.resolve([])),
    [admin],
  )

  /** 도메인별로 묶는다 — 271 줄을 한 표로 두면 「열」 과 「기계」 가 섞여 훑을 수 없다. */
  const grouped = useMemo(() => {
    const out = new Map<string, Property[]>()
    for (const one of properties.data ?? []) {
      const key = one.domain ?? ''
      out.set(key, [...(out.get(key) ?? []), one])
    }
    return [...out.entries()]
  }, [properties.data])

  async function run(work: () => Promise<unknown>) {
    setError(null)
    try {
      await work()
      properties.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

  const linked = (properties.data ?? []).filter((one) => one.links.length > 0).length
  const suggested = (properties.data ?? []).reduce(
    (sum, one) => sum + one.links.filter((link) => link.status === 'suggested').length,
    0,
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="물성 항목"
        description="어떤 시험으로 어떤 물성을 얻는지. 검색이 「인장강도 재는 장비」 를 이 표로 시험 항목으로 바꿉니다."
      />

      <div className="flex flex-wrap items-center gap-3">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="물성 이름 · 키 · 별칭"
          className="max-w-xs"
        />
        <Select
          value={domain || 'all'}
          onValueChange={(value) => setDomain(value === 'all' ? '' : value)}
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
          시험이 이어진 것만
        </label>
        {properties.data && (
          <span className="text-muted-foreground text-sm">
            {properties.data.length}종 · 이어진 것 {linked}
            {suggested > 0 && (
              <>
                {' '}
                · <span className="text-amber-700">확인 안 한 제안 {suggested}</span>
              </>
            )}
          </span>
        )}
      </div>

      <ErrorNotice error={properties.error ?? error} />

      {properties.data && properties.data.length === 0 ? (
        <EmptyState
          title="물성이 없습니다"
          hint={
            linkedOnly
              ? '이어진 시험이 있는 물성이 없습니다. 「시험이 이어진 것만」 을 풀어 보세요.'
              : '카탈로그 반입(import_catalog.py)이 MaterialTwin 물성 271종을 심습니다.'
          }
        />
      ) : (
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
                              link={link}
                              admin={admin}
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
                          {admin && adding !== one.id && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 px-1.5 text-xs"
                              onClick={() => {
                                setAdding(one.id)
                                setPickedItem('')
                              }}
                            >
                              <Plus className="mr-1 size-3" />
                              시험 잇기
                            </Button>
                          )}
                        </div>
                        {admin && adding === one.id && (
                          <div className="mt-1 flex flex-wrap items-center gap-2">
                            <SearchablePicker
                              options={(items.data ?? [])
                                .filter(
                                  (item) =>
                                    !one.links.some(
                                      (link) => link.test_item_term_id === item.id,
                                    ),
                                )
                                .map((item) => ({ id: item.id, label: item.value }))}
                              value={pickedItem}
                              onChange={setPickedItem}
                              placeholder="시험 항목"
                              detailTitle="시험 항목"
                              className="w-64"
                            />
                            <Button
                              size="sm"
                              disabled={!pickedItem}
                              onClick={() =>
                                void run(async () => {
                                  await propertyApi.link({
                                    test_item_term_id: pickedItem,
                                    property_term_id: one.id,
                                  })
                                  setAdding(null)
                                })
                              }
                            >
                              잇기
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => setAdding(null)}>
                              취소
                            </Button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * 검색 결과 그리기 — 보유 장비의 판정(SearchResult)과 카탈로그의 판정(CatalogResult), 그리고
 * 「왜 모르는지 / 왜 없는지」(Diagnosis·whyUnknown).
 *
 * `SearchPage.tsx` 에서 갈라 나온 것(2026-09-13). 글자는 그대로, 자리만 옮겼다 — 페이지는
 * 물음을 만들고, 여기는 답을 그린다.
 */

import { Link } from 'react-router-dom'

import { EmptyState } from '@/shared/components/EmptyState'
import { StatusBadge } from '@/shared/components/StatusBadge'
import { Button } from '@/shared/components/ui/button'
import type { CatalogSearchResponse, SearchResponse } from '@/modules/search/api'
import type { components } from '@/shared/api/schema'

type AccessoryOffer = components['schemas']['AccessoryOffer']

/** **부속을 붙이면 된다** — 무엇을, 어디까지, 우리가 갖고 있나.
 *
 *  「부속 필요」 만 적으면 사람은 어느 부속인지 찾으러 카탈로그를 뒤져야 하고 대개 거기서
 *  멈춘다. 보유 대수가 0 이 아니면 **살 것이 아니라 옆에서 가져오면 되는 것**이라, 그
 *  숫자를 같은 줄에 둔다. */
function Accessory({ offer }: { offer: AccessoryOffer }) {
  return (
    <span className="text-amber-700">
      <Link
        to={`/catalog/equipment-models/${offer.model_id}`}
        className="underline decoration-dotted underline-offset-2"
      >
        {offer.model_name}
      </Link>
      {` (${offer.series_name}) ${offer.condition_range}: 장착 시 가능`}
      {offer.owned_units > 0 && (
        <strong className="text-emerald-700"> · 보유 {offer.owned_units}대</strong>
      )}
    </span>
  )
}

/** `unknown` 의 이유를 사람 말로. **어디를 채우면 되는지**까지 — 「모른다」 만 말하면 사람은
 *  채울 자리를 못 찾는다. 장비 쪽은 그 장비의 조건, 카탈로그 쪽은 그 기종의 사양이다. */
function whyUnknown(reason: string | null | undefined, scope: 'owned' | 'catalog'): string {
  const where = scope === 'owned' ? '장비 조건에' : '기종 사양에'
  switch (reason) {
    case 'missing':
      return `${where} 이 조건 미기재. 입력 시 판정 가능`
    case 'no_range':
      return `${where} 범위 미기재`
    case 'no_max':
      return `${where} 상한이 없어 ‘이상’ 판정 불가. 상한 입력 필요`
    case 'no_min':
      return `${where} 하한이 없어 ‘이하’ 판정 불가. 하한 입력 필요`
    default:
      return ''
  }
}

/** 「없습니다」 를 왜로 — 세 수가 세 가지 할 일을 가른다. */
function Diagnosis({ result }: { result: SearchResponse }) {
  const d = result.diagnosis
  return (
    <ul className="mt-1 list-disc space-y-0.5 pl-5 text-left">
      {d && d.equipment_with_item === 0 ? (
        <li>
          이 시험 항목이 등록된 보유 장비 <strong>0대</strong>. 조건 문제가 아닌 시험 미등록
          상태.
        </li>
      ) : (
        <li>
          조건에 걸려 빠진 시험 항목 <strong>{result.unmet_count}건</strong>
          {d && ` (이 시험을 등록한 장비 ${d.equipment_with_item}대 중)`}. 조건 범위 확대 필요.
        </li>
      )}
      {d && d.catalog_series_with_item > 0 && (
        <li>
          카탈로그에는 이 시험을 하는 계열 <strong>{d.catalog_series_with_item}개</strong>{' '}
          있음. 위의 ‘카탈로그에서’ 검색으로 가능 기종 확인 가능.
        </li>
      )}
      {d && d.unlinked_equipment > 0 && (
        <li>
          기종 미연결 장비 <strong>{d.unlinked_equipment}대</strong>. 카탈로그의 시험 항목을
          받지 못해 검색에서 제외됨.{' '}
          <Link to="/equipment?catalog=unlinked" className="underline">
            기종 연결
          </Link>
        </li>
      )}
      {result.unregistered_equipment > 0 && (
        <li>
          시험 항목 미등록 장비 <strong>{result.unregistered_equipment}대</strong>.{' '}
          <Link to="/equipment?test_item=none" className="underline">
            시험 항목 입력
          </Link>
        </li>
      )}
    </ul>
  )
}

/** 카탈로그 답 — 계열 한 장에 기종이 줄줄이. **기종 단위 판정**이고 보유 대수가 붙는다. */
export function CatalogResult({ result }: { result: CatalogSearchResponse }) {
  const expanded =
    result.expanded_test_items.length > 0 ? (
      <p className="text-muted-foreground text-sm">
        물성을 시험 항목으로 펼쳐 검색:{' '}
        <strong>{result.expanded_test_items.join(' · ')}</strong>
      </p>
    ) : null

  if (result.hits.length === 0) {
    return (
      <EmptyState
        title="조건에 맞는 카탈로그 기종 없음"
        hint={
          <>
            {expanded}
            조건에 걸려 빠진 기종 {result.unmet_models}종.
            {result.unmet_models === 0 &&
              ' 이 시험 항목을 하는 계열이 카탈로그에 없거나 기종 사양 미기재 상태.'}
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
                        {one.condition_label} {one.condition_range ?? '미기재'}
                        {one.verdict === 'accessory' && !one.accessory && ' (부속)'}
                        {one.accessory && (
                          <>
                            {': '}
                            <Accessory offer={one.accessory} />
                          </>
                        )}
                        {one.verdict === 'unknown' && `: ${whyUnknown(one.reason, 'catalog')}`}
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

export function SearchResult({ result }: { result: SearchResponse }) {
  const expanded =
    result.expanded_test_items.length > 0 ? (
      <p className="text-muted-foreground text-sm">
        물성을 시험 항목으로 펼쳐 검색:{' '}
        <strong>{result.expanded_test_items.join(' · ')}</strong>
      </p>
    ) : null

  if (result.hits.length === 0) {
    return (
      <EmptyState
        title={
          result.diagnosis && result.diagnosis.equipment_with_item === 0
            ? '이 시험을 하는 등록 장비 없음'
            : '조건에 맞는 장비 없음'
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
          <> 시험 항목 미등록 장비 {result.unregistered_equipment}대는 검색에서 제외됨.</>
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
                          값 입력
                        </Link>
                      </span>
                    )}
                    {one.accessory ? (
                      <Accessory offer={one.accessory} />
                    ) : (
                      one.verdict === 'accessory' && (
                        <span className="text-amber-700">옵션 부속(챔버·노) 기준 범위</span>
                      )
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

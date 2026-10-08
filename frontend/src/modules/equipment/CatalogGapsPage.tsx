/**
 * 카탈로그 보강 — **미연결 장비를 왜 미연결인지로 가른다**(시스템 관리자).
 *
 * 운영에서 미연결 장비가 분류마다 남았는데(2026-10-08) 이유가 여럿이었다: 모델명이 없어
 * 대조할 수 없음 · 카탈로그에 기종이 없음 · 비슷하지만 다른 기종 · 계열은 있지만 기종이 없음.
 * 한 목록에 섞여 있으면 관리자는 줄마다 같은 추리를 되풀이한다. 그래서 서버가 가르고
 * (`catalog_gaps.py`), 이 화면은 경우마다 할 일을 단추로 둔다.
 *
 * - 같은 기종 있음 → 그 기종에 연결
 * - 비슷한 기종 있음 → 같은 기종인지 보고 연결하거나, 후보 계열에 기종 등록
 * - 계열만 있음 → 그 계열에 기종 등록
 * - 카탈로그에 없음 → CSV 로 내려받아 제조사 사양서 조사(정본 `source/catalog` → 반입)
 * - 모델명 없음 → 장비 화면에서 모델명 입력
 *
 * **고치는 길은 기종 등록 요청과 같다** — 연결·등록·아니오가 요청을 만든 뒤 바로 정하므로,
 * 누가 언제 무엇으로 정했는지가 요청 줄과 감사에 남는다. 후보는 후보일 뿐이라 연결 전에
 * 확인 창을 띄운다: 비슷한 기종을 고르면 그 장비의 하중·온도가 남의 것이 된다.
 */

import { useState } from 'react'
import { Link } from 'react-router-dom'

import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { ConfirmDialog } from '@/shared/components/ConfirmDialog'
import { PageHeader } from '@/shared/components/PageHeader'
import { Badge } from '@/shared/components/ui/badge'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { useResource } from '@/shared/hooks/useResource'
import {
  catalogGapApi,
  type CatalogGapCase,
  type CatalogGapGroup,
} from '@/modules/equipment/api'

/** 경우마다 할 일 — 요약 칩 아래 한 줄로 보인다. */
const WHAT_TO_DO: Record<CatalogGapCase, string> = {
  exact: '같은 이름의 기종이 카탈로그에 있음. 확인 후 연결.',
  similar: '이름이 비슷한 기종이 있음. 다른 기종일 수 있으므로 확인 후 연결 또는 계열에 등록.',
  series_only: '계열은 있으나 해당 기종이 없음. 계열에 기종 등록.',
  not_in_catalog:
    '제조사 또는 계열부터 카탈로그에 없음. CSV 내려받아 제조사 사양서 조사 필요.',
  no_model: '모델명이 비어 대조 불가. 장비 화면에서 모델명 입력 필요.',
  excluded: '카탈로그 대상 아님으로 결정된 장비(자작 장비 등). 조치 불필요.',
}

const CASE_ORDER: CatalogGapCase[] = [
  'exact',
  'similar',
  'series_only',
  'not_in_catalog',
  'no_model',
  'excluded',
]

/** 한 묶음에 보이는 장비 수. 나머지는 「외 N대」 와 CSV. */
const UNITS_SHOWN = 5

type Pending =
  | { kind: 'link'; group: CatalogGapGroup; modelId: string; modelLabel: string }
  | {
      kind: 'create'
      group: CatalogGapGroup
      seriesId: string
      seriesLabel: string
      name: string
    }
  | { kind: 'reject'; group: CatalogGapGroup }

export default function CatalogGapsPage() {
  const [gapCase, setGapCase] = useState<CatalogGapCase | ''>('')
  const [category, setCategory] = useState('')
  const [query, setQuery] = useState('')
  const [typed, setTyped] = useState('')
  const gaps = useResource(
    () => catalogGapApi.list({ case: gapCase, category_term_id: category, q: query }),
    [gapCase, category, query],
  )
  const [error, setError] = useState<Error | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [pending, setPending] = useState<Pending | null>(null)
  const [seriesPicked, setSeriesPicked] = useState<Record<string, string>>({})
  const [names, setNames] = useState<Record<string, string>>({})

  const data = gaps.data
  const groups = data?.groups ?? []
  const labels = data?.case_labels ?? {}

  async function run(label: string, work: () => Promise<string>) {
    setBusy(label)
    setError(null)
    setNotice(null)
    try {
      setNotice(await work())
      gaps.reload()
    } catch (failed) {
      setError(failed as Error)
    } finally {
      setBusy(null)
    }
  }

  function request(keys: string[]) {
    return run('request', async () => {
      const done = await catalogGapApi.request(keys)
      const skipped = done.skipped.length
        ? ` · 모델명 없는 묶음 ${done.skipped.length}건 제외`
        : ''
      return `기종 등록 요청 ${done.requested}건 등록${skipped}`
    })
  }

  async function confirm() {
    if (!pending) return
    const { group } = pending
    const body =
      pending.kind === 'link'
        ? { key: group.key, model_id: pending.modelId }
        : pending.kind === 'create'
          ? { key: group.key, series_id: pending.seriesId, name: pending.name }
          : { key: group.key, reject: true }
    const done = await catalogGapApi.resolve(body)
    const failed = Array.isArray(done.failed) ? done.failed.length : 0
    setNotice(
      pending.kind === 'reject'
        ? `${group.count}대를 카탈로그 대상 아님으로 결정`
        : `${String(done.linked ?? 0)}대 연결${failed ? ` · ${failed}대 실패` : ''}`,
    )
    gaps.reload()
  }

  const requestable = groups.filter((one) => one.model_text && one.case !== 'excluded')

  return (
    <div className="space-y-6">
      <PageHeader
        title="카탈로그 보강"
        description="카탈로그 기종에 연결되지 않은 장비를 사유별로 분류. 같은 제조사·모델명 표기는 한 묶음이며, 연결·등록 시 묶음의 장비 전체에 일괄 반영."
      />

      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          onClick={() =>
            void run('export', async () => {
              await catalogGapApi.export()
              return 'CSV 내려받기 시작'
            })
          }
          disabled={busy === 'export'}
        >
          CSV 내려받기
        </Button>
        <Button asChild size="sm" variant="ghost">
          <Link to="/admin/model-proposals">기종 등록 요청 보기</Link>
        </Button>
      </div>

      <ErrorNotice error={error ?? gaps.error} />
      {notice && <p className="text-sm">{notice}</p>}

      {data && (
        <section className="space-y-2" aria-label="사유별 요약">
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant={gapCase === '' ? 'default' : 'outline'}
              onClick={() => setGapCase('')}
            >
              전체 {data.units}대
            </Button>
            {CASE_ORDER.map((one) => (
              <Button
                key={one}
                size="sm"
                variant={gapCase === one ? 'default' : 'outline'}
                onClick={() => setGapCase(one)}
              >
                {labels[one] ?? one} {data.by_case[one] ?? 0}대
              </Button>
            ))}
          </div>
          {gapCase && <p className="text-muted-foreground text-sm">{WHAT_TO_DO[gapCase]}</p>}
        </section>
      )}

      {data && data.by_category.length > 0 && (
        <details className="rounded-md border p-3">
          <summary className="cursor-pointer text-sm font-medium">
            분류별 현황 ({data.by_category.length}개 분류)
          </summary>
          <p className="text-muted-foreground mt-2 text-xs">
            ‘정본에 분류 없음’은 운영에서 직접 만든 분류로, 카탈로그 정본(source/catalog)에
            해당 분류가 없음. 기종 조사 전에 정본에 분류 추가 필요.
          </p>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-muted-foreground text-left">
                  <th className="py-1 pr-3 font-normal">분류</th>
                  <th className="py-1 pr-3 text-right font-normal">합계</th>
                  {CASE_ORDER.map((one) => (
                    <th key={one} className="py-1 pr-3 text-right font-normal">
                      {labels[one] ?? one}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.by_category.map((row) => (
                  <tr key={row.category} className="border-t">
                    <td className="py-1 pr-3">
                      {row.category_term_id ? (
                        <button
                          type="button"
                          className="text-left underline-offset-2 hover:underline"
                          onClick={() => setCategory(row.category_term_id ?? '')}
                        >
                          {row.category}
                        </button>
                      ) : (
                        row.category
                      )}
                      {!row.in_catalog && row.category_term_id && (
                        <Badge variant="outline" className="ml-2">
                          정본에 분류 없음
                        </Badge>
                      )}
                    </td>
                    <td className="py-1 pr-3 text-right">{row.total}</td>
                    {CASE_ORDER.map((one) => (
                      <td key={one} className="text-muted-foreground py-1 pr-3 text-right">
                        {row.by_case[one] || ''}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}

      <form
        className="flex flex-wrap items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          setQuery(typed.trim())
        }}
      >
        <Input
          value={typed}
          onChange={(event) => setTyped(event.target.value)}
          placeholder="제조사·모델명 검색"
          aria-label="제조사·모델명 검색"
          className="w-64"
          maxLength={200}
        />
        <Button type="submit" size="sm" variant="outline">
          검색
        </Button>
        {(category || query) && (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => {
              setCategory('')
              setQuery('')
              setTyped('')
            }}
          >
            분류·검색 해제
          </Button>
        )}
        {requestable.length > 0 && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="ml-auto"
            disabled={busy === 'request'}
            onClick={() => void request(requestable.map((one) => one.key))}
          >
            표시된 묶음 {requestable.length}건 요청으로 올리기
          </Button>
        )}
      </form>

      {data && groups.length === 0 ? (
        <EmptyState
          title={data.units === 0 ? '미연결 장비 없음' : '조건에 맞는 묶음 없음'}
          hint={
            data.units === 0
              ? '모든 장비가 카탈로그 기종에 연결됨.'
              : '사유·분류·검색 조건 변경 필요.'
          }
        />
      ) : (
        <ul className="space-y-3">
          {groups.map((group) => (
            <li key={group.key} className="space-y-2 rounded-md border p-3">
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="text-base font-medium">
                  {[group.maker_text, group.model_text].filter(Boolean).join(' ') ||
                    '제조사·모델명 없음'}
                  {!group.model_text && group.maker_text && ' (모델명 없음)'}
                </span>
                <Badge variant={group.case === 'exact' ? 'default' : 'secondary'}>
                  {group.case_label}
                </Badge>
                <span className="text-muted-foreground text-sm">
                  {group.count}대
                  {group.departments.length > 0 && ` · ${group.departments.join(', ')}`}
                  {group.categories.length > 0 && ` · ${group.categories.join(', ')}`}
                </span>
                {group.maker_text && !group.maker_known && (
                  <span className="text-muted-foreground text-xs">제조사 카탈로그 미등록</span>
                )}
                {group.open_requests > 0 && (
                  <span className="text-muted-foreground text-xs">
                    요청 대기 {group.open_requests}건
                  </span>
                )}
              </div>

              <ul className="text-muted-foreground space-y-0.5 text-sm">
                {group.units.slice(0, UNITS_SHOWN).map((unit) => (
                  <li key={unit.id}>
                    <Link
                      to={`/equipment/${unit.id}`}
                      className="underline-offset-2 hover:underline"
                    >
                      {unit.asset_no}
                    </Link>{' '}
                    {unit.name}
                    {unit.workspace && ` · ${unit.workspace}`}
                    {group.case === 'no_model' && ' · 모델명 입력 필요'}
                  </li>
                ))}
                {group.count > UNITS_SHOWN && (
                  <li>외 {group.count - UNITS_SHOWN}대(전체는 CSV)</li>
                )}
              </ul>

              {group.models.length > 0 && (
                <div className="space-y-1">
                  <p className="text-sm font-medium">
                    {group.case === 'exact' ? '같은 기종' : '비슷한 기종(다른 기종일 수 있음)'}
                  </p>
                  <ul className="space-y-1">
                    {group.models.map((model) => (
                      <li key={model.id} className="flex flex-wrap items-center gap-2 text-sm">
                        <span>{model.label}</span>
                        {model.detail && (
                          <span className="text-muted-foreground text-xs">{model.detail}</span>
                        )}
                        {model.score != null && model.score < 1 && (
                          <span className="text-muted-foreground text-xs">
                            유사도 {Math.round(model.score * 100)}%
                          </span>
                        )}
                        <Button
                          size="sm"
                          variant={group.case === 'exact' ? 'default' : 'outline'}
                          onClick={() =>
                            setPending({
                              kind: 'link',
                              group,
                              modelId: model.id,
                              modelLabel: model.label,
                            })
                          }
                        >
                          이 기종에 연결
                        </Button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {group.series.length > 0 && group.model_text && group.case !== 'exact' && (
                <div className="flex flex-wrap items-center gap-2">
                  <select
                    className="border-input h-8 max-w-md rounded-md border bg-transparent px-2 text-sm"
                    aria-label={`${group.model_text} 등록할 계열`}
                    value={seriesPicked[group.key] ?? group.series[0].id}
                    onChange={(event) =>
                      setSeriesPicked((before) => ({
                        ...before,
                        [group.key]: event.target.value,
                      }))
                    }
                  >
                    {group.series.map((one) => (
                      <option key={one.id} value={one.id}>
                        {one.label}
                        {one.detail ? ` (${one.detail})` : ''}
                      </option>
                    ))}
                  </select>
                  <Input
                    value={names[group.key] ?? group.model_text}
                    onChange={(event) =>
                      setNames((before) => ({ ...before, [group.key]: event.target.value }))
                    }
                    aria-label={`${group.model_text} 기종 이름`}
                    className="w-48"
                    maxLength={150}
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      const seriesId = seriesPicked[group.key] ?? group.series[0].id
                      setPending({
                        kind: 'create',
                        group,
                        seriesId,
                        seriesLabel:
                          group.series.find((one) => one.id === seriesId)?.label ?? '',
                        name: (names[group.key] ?? group.model_text ?? '').trim(),
                      })
                    }}
                  >
                    계열에 기종 등록
                  </Button>
                </div>
              )}

              {group.model_text && group.case !== 'excluded' && (
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={busy === 'request' || group.open_requests >= group.count}
                    onClick={() => void request([group.key])}
                  >
                    요청으로 올리기
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setPending({ kind: 'reject', group })}
                  >
                    카탈로그 대상 아님
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {data && data.groups_total > groups.length && groups.length > 0 && (
        <p className="text-muted-foreground text-xs">
          전체 {data.groups_total}묶음 중 {groups.length}묶음 표시(사유·분류·검색 조건 적용).
        </p>
      )}

      <ConfirmDialog
        open={pending !== null}
        title={
          pending?.kind === 'link'
            ? '기종에 연결하시겠습니까?'
            : pending?.kind === 'create'
              ? '계열에 기종을 등록하시겠습니까?'
              : '카탈로그 대상 아님으로 결정하시겠습니까?'
        }
        description={
          pending && (
            <span className="space-y-1">
              <span className="block">
                대상:{' '}
                {[pending.group.maker_text, pending.group.model_text]
                  .filter(Boolean)
                  .join(' ')}{' '}
                · 장비 {pending.group.count}대
              </span>
              {pending.kind === 'link' && (
                <span className="block">
                  연결 기종: {pending.modelLabel}. 해당 계열의 시험 항목이 장비에 복사되고,
                  조건 판정에 이 기종의 사양이 쓰임.
                  {pending.group.case !== 'exact' && ' 비슷한 이름일 뿐 다른 기종일 수 있음.'}
                </span>
              )}
              {pending.kind === 'create' && (
                <span className="block">
                  계열: {pending.seriesLabel} · 기종 이름: {pending.name}. 기종 이름에 계열
                  이름 포함 금지.
                </span>
              )}
              {pending.kind === 'reject' && (
                <span className="block">장비는 미연결로 유지되며 보강 일감에서 제외됨.</span>
              )}
            </span>
          )
        }
        confirmLabel={
          pending?.kind === 'link' ? '연결' : pending?.kind === 'create' ? '등록' : '결정'
        }
        onConfirm={confirm}
        onClose={() => setPending(null)}
      />
    </div>
  )
}

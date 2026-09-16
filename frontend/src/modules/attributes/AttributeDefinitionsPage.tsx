/**
 * 항목 정의 — **신뢰성 시험(뒤에는 보유 장비)에 붙는 칸의 목록.**
 *
 * 열을 미리 뚫지 않고 이름을 데이터로 둔 자리다. 두 층이 한 화면에 선다:
 *
 *     정식    관리자가 확정한 항목. 필수 표시·검색축 연결·의미 색인에 들어간다
 *     초안    누가 값을 적으며 새 이름을 쓴 것. 건수순으로 보면 무엇을 올릴지 보인다
 *
 * 초안 목록은 **곧 정리 화면이다** — 「시험온도 12건 · 온도 7건 · Temp 3건」 이 나란히 보이면
 * 하나로 합쳐 정식으로 올린다. 값은 따라오고 원래 항목은 꺼진다.
 *
 * 시험 조건 정의·장비 사양 정의와 같은 성격(칸의 계약)이지만 대상이 다르다 — 저쪽은
 * 카탈로그(기종), 여기는 사내 운영 데이터(부서가 적는 것).
 */

import { useState } from 'react'
import { useParams } from 'react-router-dom'

import { ApiError } from '@/shared/api/client'
import { useAuth } from '@/shared/auth/AuthContext'
import { isSystemAdmin } from '@/shared/auth/roles'
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
import { attributeApi } from '@/modules/attributes/api'
import type { AttributeDefinition, AttributeTarget } from '@/modules/attributes/api'
import { KIND_LABEL } from '@/modules/attributes/kinds'
import type { AttributeKind } from '@/modules/attributes/kinds'
import { vocabularyApi } from '@/modules/vocabulary/api'

/** 주소의 마지막 조각 → 대상. 대상마다 메뉴가 따로 선다 — 신뢰성 시험의 「판정 기준」 과 보유
 *  장비의 「담당 구역」 이 한 표에 섞이면 어느 쪽인지 매번 확인해야 한다. */
export const TARGET_BY_PATH: Record<string, AttributeTarget> = {
  'reliability-test': 'reliability_test',
  equipment: 'equipment',
}

const TARGET_LABEL: Record<AttributeTarget, string> = {
  reliability_test: '신뢰성 시험',
  equipment: '보유 장비',
}

/** 관리자가 새로 만들 수 있는 종류 — 초안이 못 만드는 축·선택지 종류가 여기 있다. */
const ADMIN_KINDS: AttributeKind[] = [
  'number',
  'range',
  'text',
  'boolean',
  'date',
  'choice',
  'condition',
  'term',
  'method',
]

export default function AttributeDefinitionsPage() {
  const { user } = useAuth()
  const canEdit = isSystemAdmin(user)
  const { target: targetPath = 'reliability-test' } = useParams<{ target: string }>()
  const target: AttributeTarget = TARGET_BY_PATH[targetPath] ?? 'reliability_test'
  const list = useResource(() => attributeApi.definitions(target, true), [target])
  const conditions = useResource(() => vocabularyApi.conditions(), [])
  const axes = useResource(() => vocabularyApi.list(), [])

  const [label, setLabel] = useState('')
  const [kind, setKind] = useState<AttributeKind>('text')
  const [unit, setUnit] = useState('')
  const [choices, setChoices] = useState('')
  const [conditionKey, setConditionKey] = useState('')
  const [vocabulary, setVocabulary] = useState('')
  const [asDraft, setAsDraft] = useState(false)
  const [merging, setMerging] = useState<AttributeDefinition | null>(null)
  const [mergeTarget, setMergeTarget] = useState('')
  const [error, setError] = useState<ApiError | Error | null>(null)

  async function act(run: () => Promise<unknown>) {
    setError(null)
    try {
      await run()
      list.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

  const rows = list.data ?? []
  const standard = rows.filter((one) => one.status === 'standard' && one.is_active)
  // 초안은 **건수 많은 것부터** — 많이 쓰인 이름이 정식으로 올릴 첫 후보다.
  const drafts = rows
    .filter((one) => one.status === 'draft' && one.is_active)
    .sort((a, b) => b.value_count - a.value_count || a.label.localeCompare(b.label))
  const inactive = rows.filter((one) => !one.is_active)
  const byId = new Map(rows.map((one) => [one.id, one]))

  function kindOf(row: AttributeDefinition): string {
    return KIND_LABEL[row.kind as AttributeKind] ?? row.kind
  }

  function detail(row: AttributeDefinition): string {
    const parts: string[] = []
    if (row.unit) parts.push(row.unit)
    if (row.condition_key_label) parts.push(`축 ${row.condition_key_label}`)
    if (row.vocabulary_slug) parts.push(`축 ${row.vocabulary_slug}`)
    if (row.choices.length) parts.push(row.choices.join(' | '))
    return parts.join(' · ')
  }

  function renderRow(row: AttributeDefinition) {
    return (
      <TableRow key={row.id}>
        <TableCell className="font-medium">
          {row.label}
          {row.is_required && (
            <Badge variant="secondary" className="ml-2 text-[10px]">
              필수
            </Badge>
          )}
          {row.merged_into_id && (
            <span className="text-muted-foreground ml-2 text-xs">
              → {byId.get(row.merged_into_id)?.label ?? '합쳐짐'}
            </span>
          )}
        </TableCell>
        <TableCell className="text-sm">{kindOf(row)}</TableCell>
        <TableCell className="text-muted-foreground text-sm">{detail(row) || '—'}</TableCell>
        <TableCell className="text-right text-sm">{row.value_count}</TableCell>
        <TableCell className="text-muted-foreground font-mono text-xs">{row.key}</TableCell>
        {canEdit && (
          <TableCell className="space-x-1 text-right whitespace-nowrap">
            {row.is_active && row.status === 'draft' && (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    act(() => attributeApi.update(row.id, { status: 'standard' }))
                  }
                >
                  정식으로
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setMerging(row)
                    setMergeTarget('')
                  }}
                >
                  합치기
                </Button>
              </>
            )}
            {row.is_active && row.status === 'standard' && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() =>
                  act(() => attributeApi.update(row.id, { is_required: !row.is_required }))
                }
              >
                {row.is_required ? '필수 해제' : '필수로'}
              </Button>
            )}
            {row.is_active && !row.merged_into_id && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => act(() => attributeApi.update(row.id, { is_active: false }))}
              >
                끄기
              </Button>
            )}
            {!row.is_active && !row.merged_into_id && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => act(() => attributeApi.update(row.id, { is_active: true }))}
              >
                켜기
              </Button>
            )}
            {row.value_count === 0 && !row.merged_into_id && (
              // **값이 없을 때만 지운다.** 값이 있는 항목을 지우면 그 값이 무엇이었는지 알 수
              // 없어진다 — 그때는 끄거나 합친다. 단추를 숨기는 것이 곧 그 규칙의 설명이다.
              <Button
                size="sm"
                variant="ghost"
                className="text-destructive"
                onClick={() => act(() => attributeApi.remove(row.id))}
              >
                삭제
              </Button>
            )}
          </TableCell>
        )}
      </TableRow>
    )
  }

  const header = (
    <TableHeader>
      <TableRow>
        <TableHead>속성</TableHead>
        <TableHead>종류</TableHead>
        <TableHead>단위 · 축 · 선택지</TableHead>
        <TableHead className="text-right">값</TableHead>
        <TableHead>키</TableHead>
        {canEdit && <TableHead className="w-64" />}
      </TableRow>
    </TableHeader>
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title={`${TARGET_LABEL[target]} 속성 정의`}
        description={`${TARGET_LABEL[target]}에 붙는 속성(고정 칸이 아닌 정보)입니다. 정식 속성은 검색·색인에 쓰이고, 초안은 값을 적은 사람이 새 이름을 쓴 것 — 건수를 보고 정식으로 올리거나 합칩니다.`}
      />

      {canEdit && (
        <form
          className="flex flex-wrap items-end gap-2 rounded-md border p-4"
          onSubmit={(event) => {
            event.preventDefault()
            act(async () => {
              await attributeApi.create({
                target,
                label,
                kind,
                unit,
                choices: choices
                  .split('|')
                  .map((one) => one.trim())
                  .filter(Boolean),
                condition_key_id: kind === 'condition' ? conditionKey || null : null,
                vocabulary_id: kind === 'term' ? vocabulary || null : null,
                status: asDraft ? 'draft' : 'standard',
              })
              setLabel('')
              setUnit('')
              setChoices('')
            })
          }}
        >
          <div className="space-y-1">
            <label className="text-xs" htmlFor="attr-label">
              이름
            </label>
            <Input
              id="attr-label"
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              placeholder="시험 온도"
              required
            />
          </div>
          <div className="space-y-1">
            <span className="block text-xs">종류</span>
            <Select value={kind} onValueChange={(next) => setKind(next as AttributeKind)}>
              <SelectTrigger className="w-32" aria-label="종류">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ADMIN_KINDS.map((one) => (
                  <SelectItem key={one} value={one}>
                    {KIND_LABEL[one]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {(kind === 'number' || kind === 'range' || kind === 'condition') && (
            <div className="space-y-1">
              <label className="text-xs" htmlFor="attr-unit">
                읽는 단위
              </label>
              <Input
                id="attr-unit"
                value={unit}
                onChange={(event) => setUnit(event.target.value)}
                placeholder="degC"
                className="w-24"
              />
            </div>
          )}
          {kind === 'choice' && (
            <div className="space-y-1">
              <label className="text-xs" htmlFor="attr-choices">
                선택지 (| 로 나눔)
              </label>
              <Input
                id="attr-choices"
                value={choices}
                onChange={(event) => setChoices(event.target.value)}
                placeholder="시편 | 완제품"
                required
              />
            </div>
          )}
          {kind === 'condition' && (
            <div className="space-y-1">
              <span className="block text-xs">검색 조건 축</span>
              <Select value={conditionKey} onValueChange={setConditionKey}>
                <SelectTrigger className="w-40" aria-label="검색 조건 축">
                  <SelectValue placeholder="선택" />
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
          )}
          {kind === 'term' && (
            <div className="space-y-1">
              <span className="block text-xs">기준정보 축</span>
              <Select value={vocabulary} onValueChange={setVocabulary}>
                <SelectTrigger className="w-40" aria-label="기준정보 축">
                  <SelectValue placeholder="선택" />
                </SelectTrigger>
                <SelectContent>
                  {(axes.data ?? []).map((one) => (
                    <SelectItem key={one.id} value={one.id}>
                      {one.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          <label className="flex items-center gap-1 pb-2 text-xs">
            <input
              type="checkbox"
              checked={asDraft}
              onChange={(event) => setAsDraft(event.target.checked)}
            />
            초안으로 (조사 중인 후보를 미리 세움)
          </label>
          <Button type="submit">추가</Button>
        </form>
      )}

      <ErrorNotice error={error ?? list.error} />

      <section className="space-y-2">
        <h2 className="text-sm font-semibold">정식 {standard.length}</h2>
        {standard.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            아직 정식 속성이 없습니다. 초안을 올리거나 위에서 새로 만듭니다.
          </p>
        ) : (
          <Table>
            {header}
            <TableBody>{standard.map(renderRow)}</TableBody>
          </Table>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold">초안 {drafts.length}</h2>
        <p className="text-muted-foreground text-xs">
          값을 적은 사람이 새 이름으로 쓴 속성입니다. 표시·수집만 되고 검색 판정·색인에는 안
          쓰입니다. 같은 뜻이 여럿이면 하나로 합치고, 쓸 것이면 정식으로 올립니다.
        </p>
        {drafts.length === 0 ? (
          <p className="text-muted-foreground text-sm">초안이 없습니다.</p>
        ) : (
          <Table>
            {header}
            <TableBody>{drafts.map(renderRow)}</TableBody>
          </Table>
        )}
      </section>

      {inactive.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-muted-foreground text-sm font-semibold">
            꺼짐 {inactive.length}
          </h2>
          <Table>
            {header}
            <TableBody>{inactive.map(renderRow)}</TableBody>
          </Table>
        </section>
      )}

      {merging && (
        <div className="flex flex-wrap items-center gap-2 rounded-md border p-4">
          <span className="text-sm">
            <b>{merging.label}</b> ({merging.value_count}건) 을 어디로 합칠까요? 종류가 같은
            것만 — {kindOf(merging)}.
          </span>
          <Select value={mergeTarget} onValueChange={setMergeTarget}>
            <SelectTrigger className="w-56" aria-label="합칠 속성">
              <SelectValue placeholder="남는 속성" />
            </SelectTrigger>
            <SelectContent>
              {rows
                .filter(
                  (one) => one.is_active && one.id !== merging.id && one.kind === merging.kind,
                )
                .map((one) => (
                  <SelectItem key={one.id} value={one.id}>
                    {one.label} ·{' '}
                    {one.status === 'standard' ? '정식' : `초안 ${one.value_count}건`}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
          <Button
            size="sm"
            disabled={!mergeTarget}
            onClick={() =>
              act(async () => {
                await attributeApi.merge(merging.id, mergeTarget)
                setMerging(null)
              })
            }
          >
            합치기
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setMerging(null)}>
            취소
          </Button>
        </div>
      )}
    </div>
  )
}

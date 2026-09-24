/**
 * 장비 기종 사양.
 *
 * 시험 항목 검색 조건와 **같은 성격**이다 — 둘 다 값이 아니라 칸의 계약이다. 다른 것은
 * 쓰임이다:
 *
 *     시험 조건   검색이 묻는 축. 일곱 개. 범위 비교가 되어야 한다
 *     장비 사양   사양서에 적힌 모든 것. 수백 개. 대부분 검색 안 한다
 *
 * 한 표로 합치지 않은 이유는 화면을 보면 안다 — 프레임 강성과 외형 치수가 검색
 * 폼에 뜨면 그 화면은 못 쓰게 된다(ADR 0005).
 *
 * ## 붙는 분류가 비어 있으면 공통이다
 *
 * "아직 안 정했음" 이 아니다. 전원·무게처럼 분류를 가리지 않는 것이 실제로 많고,
 * 그것이 기본값이라야 설치 직후에도 사양표가 빈 화면이 아니다.
 */

import { useState } from 'react'

import { ApiError } from '@/shared/api/client'
import { useAuth } from '@/shared/auth/AuthContext'
import { isSystemAdmin } from '@/shared/auth/roles'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
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
import { vocabularyApi } from '@/modules/vocabulary/api'
import { convertValue, isError } from '@/shared/units'

/** 화면이 쓰는 말. 코드의 kind 를 그대로 보여 주면 읽는 사람이 번역을 한다. */
const KIND_LABEL: Record<string, string> = {
  number: '수치',
  range: '구간',
  choice: '선택',
  boolean: '있음/없음',
  text: '문장',
}

export default function SpecDefinitionsPage() {
  const { user } = useAuth()
  const canEdit = isSystemAdmin(user)
  const groups = useResource(() => vocabularyApi.specGroups(), [])
  const list = useResource(() => vocabularyApi.specDefinitions({ includeInactive: true }), [])
  const conditions = useResource(() => vocabularyApi.conditions(), [])

  const [key, setKey] = useState('')
  const [label, setLabel] = useState('')
  const [group, setGroup] = useState('')
  const [kind, setKind] = useState('number')
  const [unit, setUnit] = useState('')
  const [error, setError] = useState<ApiError | Error | null>(null)

  async function act(run: () => Promise<unknown>) {
    setError(null)
    try {
      await run()
      list.reload()
      groups.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        back={{ to: '/reference?kind=model', label: '기준정보' }}
        title="장비 기종 사양"
        description="장비 모델에 적을 수 있는 칸입니다. 적용 분류를 비워 두면 모든 장비에 뜹니다 — 전원·무게처럼 분류를 가리지 않는 것이 실제로 많습니다."
      />

      {canEdit && (
        <form
          className="flex flex-wrap items-end gap-2 rounded-md border p-4"
          onSubmit={(event) => {
            event.preventDefault()
            act(async () => {
              await vocabularyApi.createSpecDefinition({
                key,
                label,
                group_id: group,
                kind,
                si_unit: unit,
                display_unit: unit,
              })
              setKey('')
              setLabel('')
              setUnit('')
            })
          }}
        >
          <div className="space-y-1">
            {/* **코드와 반입 스크립트가 거는 이름이다.** 만든 뒤에는 못 바꾼다. */}
            <label className="text-xs" htmlFor="spec-key">
              키
            </label>
            <Input
              id="spec-key"
              value={key}
              onChange={(event) => setKey(event.target.value)}
              placeholder="oil_capacity"
              pattern="[a-z][a-z0-9_]{1,59}"
              required
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs" htmlFor="spec-label">
              화면 이름
            </label>
            <Input
              id="spec-label"
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              placeholder="유압 유닛 용량"
              required
            />
          </div>
          <div className="space-y-1">
            <span className="block text-xs">그룹</span>
            <Select value={group} onValueChange={setGroup}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="선택" />
              </SelectTrigger>
              <SelectContent>
                {(groups.data ?? []).map((one) => (
                  <SelectItem key={one.id} value={one.id}>
                    {one.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            {/* **종류는 만든 뒤에 못 바꾼다** — 값이 어느 칸에 담겼는지를 정한다. */}
            <span className="block text-xs">종류</span>
            <Select value={kind} onValueChange={setKind}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(KIND_LABEL).map(([value, text]) => (
                  <SelectItem key={value} value={value}>
                    {text}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <label className="text-xs" htmlFor="spec-unit">
              단위
            </label>
            <Input
              id="spec-unit"
              value={unit}
              onChange={(event) => setUnit(event.target.value)}
              placeholder="L"
              className="w-24"
            />
          </div>
          <Button type="submit" disabled={!group}>
            사양 등록
          </Button>
        </form>
      )}

      <ErrorNotice error={error ?? list.error} />

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>화면 이름</TableHead>
            <TableHead>키</TableHead>
            <TableHead>그룹</TableHead>
            <TableHead>종류</TableHead>
            <TableHead>단위</TableHead>
            <TableHead>적용 분류</TableHead>
            <TableHead>검색 조건</TableHead>
            <TableHead className="text-right">참조</TableHead>
            <TableHead className="text-right">사용</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(list.data ?? []).map((one) => (
            <TableRow key={one.id} className={one.is_active ? undefined : 'opacity-60'}>
              <TableCell>
                {one.label}
                {one.help && (
                  <p className="text-muted-foreground mt-0.5 text-xs">{one.help}</p>
                )}
              </TableCell>
              <TableCell className="font-mono text-xs">{one.key}</TableCell>
              <TableCell>{one.group_label}</TableCell>
              <TableCell>{KIND_LABEL[one.kind] ?? one.kind}</TableCell>
              <TableCell>{one.display_unit || one.si_unit || '—'}</TableCell>
              {/* **비어 있으면 공통이다.** 「미지정」 이라고 적으면 덜 채운 것으로 읽힌다. */}
              <TableCell>
                {one.categories.length === 0 ? (
                  <span className="text-muted-foreground">공통</span>
                ) : (
                  one.categories.join(', ')
                )}
              </TableCell>
              {/* 이어져 있으면 이 사양의 값이 기종의 시험 항목으로 따라 들어간다.
                  **단위가 다르면 곱해서 옮기고, 못 곱하는 짝은 안 옮긴다** — 그 사실을
                  여기서 말한다(쇼어 경도 ↔ kN). 끊는 길은 일부러 없다: 조용히 끊기면 그
                  사양이 왜 검색에서 사라졌는지 아무도 못 찾는다. */}
              <TableCell>
                {canEdit ? (
                  <Select
                    value={one.condition_key_id ?? ''}
                    onValueChange={(value) =>
                      act(() =>
                        vocabularyApi.updateSpecDefinition(one.id, {
                          condition_key_id: value,
                        }),
                      )
                    }
                  >
                    <SelectTrigger className="h-8 w-40" aria-label={`${one.label} 검색 조건`}>
                      <SelectValue placeholder="—" />
                    </SelectTrigger>
                    <SelectContent>
                      {(conditions.data ?? []).map((key) => (
                        <SelectItem key={key.id} value={key.id}>
                          {key.label}
                          {(key.display_unit || key.si_unit) &&
                            ` [${key.display_unit || key.si_unit}]`}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  (one.condition_label ?? <span className="text-muted-foreground">—</span>)
                )}
                {(() => {
                  const axis = (conditions.data ?? []).find(
                    (key) => key.id === one.condition_key_id,
                  )
                  if (!axis) return null
                  const mine = one.display_unit || one.si_unit
                  const theirs = axis.display_unit || axis.si_unit
                  const probe = convertValue(`1 ${mine || theirs}`, theirs)
                  if (mine === theirs || (probe !== null && !isError(probe))) return null
                  return (
                    <p className="text-destructive mt-1 text-xs">
                      단위 {mine || '없음'} ↔ {theirs || '없음'} 을 못 맞춥니다 — 이 사양은
                      검색에 안 실립니다
                    </p>
                  )
                })()}
              </TableCell>
              {/* **쓰임 수를 끄기 전에 보여 준다.** 단위를 고치면 이 숫자만큼의
                  값이 한꺼번에 다른 뜻이 된다. */}
              <TableCell className="text-right">{one.usage_count}</TableCell>
              <TableCell className="text-right">
                {canEdit && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      act(() =>
                        vocabularyApi.updateSpecDefinition(one.id, {
                          is_active: !one.is_active,
                        }),
                      )
                    }
                  >
                    {one.is_active ? '비활성화' : '활성화'}
                  </Button>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {/* 조건 정의를 못 찾은 사람이 여기서 헤매지 않게 길을 적어 둔다. */}
      <p className="text-muted-foreground text-xs">
        검색 조건에 잇는 것은 지금 {conditions.data?.length ?? 0}개 조건 중에서 고릅니다. 새
        축이 필요하면 「시험 항목 검색 조건」 에서 먼저 만드십시오.
      </p>
    </div>
  )
}

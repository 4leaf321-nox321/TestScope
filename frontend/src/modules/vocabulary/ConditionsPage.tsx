/**
 * 시험 항목 검색 조건.
 *
 * 온톨로지가 **값의 목록**이라면 이것은 **칸의 계약**이다. 조건에는 차원·단위처럼
 * 값이 아닌 것이 붙고, 그래서 표가 다르다.
 *
 * ## 단위를 고치는 것은 되돌릴 수 없다
 *
 * kN 을 N 으로 바꾸는 순간 이미 저장된 숫자 전부가 다른 값이 된다. 화면이 그것을
 * 말해 주고, 서버는 감사에 남긴다.
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table'
import { useResource } from '@/shared/hooks/useResource'
import { vocabularyApi } from '@/modules/vocabulary/api'

export default function ConditionsPage() {
  const { user } = useAuth()
  const canEdit = isSystemAdmin(user)
  const list = useResource(() => vocabularyApi.conditions(true), [])
  const [key, setKey] = useState('')
  const [label, setLabel] = useState('')
  const [unit, setUnit] = useState('')
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

  return (
    <div className="space-y-6">
      <PageHeader
        back={{ to: '/admin/ontology?kind=axis:test_item', label: '온톨로지' }}
        title="시험 항목 검색 조건"
        description="온도·하중·주파수처럼 장비의 시험 조건과 규격의 요구 조건이 함께 쓰는 칸입니다. 값은 언제나 저장 단위로 담깁니다."
      />

      {canEdit && (
        <form
          className="flex flex-wrap items-end gap-2 rounded-md border p-4"
          onSubmit={(event) => {
            event.preventDefault()
            act(async () => {
              await vocabularyApi.createCondition({
                key,
                label,
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
            {/* **코드가 거는 이름이다.** 소문자와 밑줄만 — 화면 이름은 옆 칸이 갖는다. */}
            <label className="text-xs" htmlFor="condition-key">
              키
            </label>
            <Input
              id="condition-key"
              value={key}
              onChange={(event) => setKey(event.target.value)}
              placeholder="impact_energy"
              pattern="[a-z][a-z0-9_]{1,49}"
              required
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs" htmlFor="condition-label">
              화면 이름
            </label>
            <Input
              id="condition-label"
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              placeholder="충격 에너지"
              required
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs" htmlFor="condition-unit">
              단위
            </label>
            <Input
              id="condition-unit"
              value={unit}
              onChange={(event) => setUnit(event.target.value)}
              placeholder="J"
            />
          </div>
          <Button type="submit">검색 조건 등록</Button>
        </form>
      )}

      <ErrorNotice error={error ?? list.error} />

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>화면 이름</TableHead>
            <TableHead>키</TableHead>
            <TableHead>종류</TableHead>
            <TableHead>저장 단위</TableHead>
            <TableHead>표시 단위</TableHead>
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
              <TableCell>
                {one.kind === 'range' ? '범위' : one.kind === 'choice' ? '선택' : '있음/없음'}
              </TableCell>
              <TableCell>{one.si_unit || '—'}</TableCell>
              <TableCell>{one.display_unit || '—'}</TableCell>
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
                        vocabularyApi.updateCondition(one.id, { is_active: !one.is_active }),
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
    </div>
  )
}

/**
 * 시험법·규격 목록.
 *
 * **가능 장비 수를 한 칸으로 보여 준다.** 0 인 규격은 지금 우리가 못 하는 시험이고,
 * 그 사실이 목록에 보여야 "이건 외주" 라는 판단이 선다.
 *
 * **못 하는 시험과 끊긴 연결을 가른다.** 「인용 계열」 이 0 인데 「시험 항목 미지정」 이 있으면
 * 그 규격은 카탈로그가 인용했는데 어느 시험의 것인지 안 정해져 못 이어진 것이다 — 시험
 * 항목을 정하면 붙는다. 그 둘을 한 칸에 섞으면 464 중 287 이 「없음」 으로 서고, 사람은
 * 카탈로그가 비었다고 읽는다.
 *
 * 기본은 현행만 보여 준다 — 대체된 판이 섞여 있으면 사람이 옛 규격을 고르고, 그
 * 사실은 시험이 끝난 뒤에야 드러난다.
 */

import { useState } from 'react'
import { Plus, Upload } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'

import { useAuth } from '@/shared/auth/AuthContext'
import { isAnyManager } from '@/shared/auth/roles'
import { EmptyState } from '@/shared/components/EmptyState'
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
import { AttributeFilterBar } from '@/modules/attributes/AttributeFilterBar'
import { useBackFromReference } from '@/shared/hooks/useBackFromReference'
import { methodApi } from '@/modules/methods/api'
import { NewMethodDialog } from '@/modules/methods/NewMethodDialog'
import { RequirementImportDialog } from '@/modules/methods/RequirementImportDialog'

export default function MethodsPage() {
  const { user } = useAuth()
  // **홈의 「남은 일」 이 `?requirement=none` 으로 온다.** 안 읽으면 눌러도 전체
  // 목록이 떠서, 사람은 「왜 안 걸러졌지」 를 겪고 그 목록을 안 믿게 된다.
  const [params, setParams] = useSearchParams()
  const requirement = params.get('requirement') ?? undefined
  const testItem = params.get('test_item') ?? undefined
  const cited = params.get('cited') ?? undefined
  const used = params.get('used') ?? undefined
  const [query, setQuery] = useState('')
  const [includeSuperseded, setIncludeSuperseded] = useState(false)
  // 속성 조건은 주소에 실린다 — 물은 화면을 그대로 보낼 수 있다.
  const [attrs, setAttrs] = useState<string[]>(() => params.getAll('attr'))
  const [creating, setCreating] = useState(false)
  const [importing, setImporting] = useState(false)
  const page = useResource(
    () =>
      methodApi.list({
        q: query || undefined,
        requirement,
        testItem,
        cited,
        used,
        includeSuperseded,
        attrs,
      }),
    [query, requirement, testItem, cited, used, includeSuperseded, attrs],
  )
  const filtered =
    requirement === 'none' || testItem === 'none' || cited === 'none' || used === 'owned'

  /** 거르기 하나를 켜고 끈다. 다른 거르기는 그대로 — 「보유 장비가 쓰는 것 중 조건 없는 것」
   *  처럼 겹쳐 쓰는 것이 이 목록의 쓸모다. */
  function toggle(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (next.get(key) === value) next.delete(key)
    else next.set(key, value)
    setParams(next)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        back={useBackFromReference()}
        title="시험법·규격"
        description="규격이 요구하는 조건을 적어 두면, 검색이 그 숫자를 그대로 물어 줍니다."
        actions={
          isAnyManager(user) ? (
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => setImporting(true)}>
                <Upload className="size-4" />
                요구 조건 표로 넣기
              </Button>
              <Button onClick={() => setCreating(true)}>
                <Plus className="size-4" />
                시험법 등록
              </Button>
            </div>
          ) : undefined
        }
      />

      {/* 속성 값으로 거르기 — 규격에 붙인 관리자 정의 칸을 되찾는 길. */}
      <AttributeFilterBar target="method" value={attrs} onChange={setAttrs} />

      <div className="flex flex-wrap items-center gap-3">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="규격 번호 또는 제목"
          className="max-w-sm"
        />
        <label className="text-muted-foreground flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={includeSuperseded}
            onChange={(event) => setIncludeSuperseded(event.target.checked)}
          />
          대체된 판도 보기
        </label>
        {/* 거르기는 주소에 산다 — 홈의 「남은 일」 과 같은 조건이라 링크로 올 수 있다. */}
        <div className="flex flex-wrap gap-1 text-sm">
          <Button
            size="sm"
            variant={used === 'owned' ? 'default' : 'outline'}
            onClick={() => toggle('used', 'owned')}
          >
            보유 장비가 쓰는 것
          </Button>
          <Button
            size="sm"
            variant={requirement === 'none' ? 'default' : 'outline'}
            onClick={() => toggle('requirement', 'none')}
          >
            요구 조건 없는 것
          </Button>
          <Button
            size="sm"
            variant={testItem === 'none' ? 'default' : 'outline'}
            onClick={() => toggle('test_item', 'none')}
          >
            시험 항목 안 정해진 것
          </Button>
          <Button
            size="sm"
            variant={cited === 'none' ? 'default' : 'outline'}
            onClick={() => toggle('cited', 'none')}
          >
            어느 계열에도 안 이어진 것
          </Button>
        </div>
      </div>

      {filtered && (
        <div className="bg-muted/50 flex flex-wrap items-center gap-3 rounded-md border p-3">
          <p className="text-sm">
            {used === 'owned' && (
              <>
                <strong>보유 장비의 시험 항목이 실제로 가리키는 규격만</strong> 보고 있습니다.
                464 는 카탈로그가 인용한 수이고, 우리가 하는 시험의 규격은 이것입니다 — 요구
                조건은 여기부터 채웁니다.{' '}
              </>
            )}
            {requirement === 'none' && (
              <>
                <strong>요구 조건이 안 적힌 규격만</strong> 보고 있습니다. 조건이 없으면 검색이
                그 규격으로 장비를 좁히지 못하고, 사람이 매번 직접 입력해야 합니다.
              </>
            )}
            {testItem === 'none' && (
              <>
                <strong>어느 시험의 규격인지 안 정해진 것만</strong> 보고 있습니다. 카탈로그가
                인용했는데 시험이 여럿인 계열이라 반입이 못 정한 것입니다 — 상세에서 시험
                항목을 정하면 인용한 계열에 바로 붙습니다.
              </>
            )}
            {cited === 'none' && (
              <>
                <strong>어느 계열의 시험 항목에도 안 이어진 규격만</strong> 보고 있습니다.
                「시험 항목 미지정」 이 있으면 끊긴 연결이고, 없으면 카탈로그에 이 시험을 하는
                계열이 없는 것입니다.
              </>
            )}
          </p>
          <Button size="sm" variant="outline" onClick={() => setParams({})}>
            필터 해제
          </Button>
        </div>
      )}

      <ErrorNotice error={page.error} />

      {page.data && page.data.items.length === 0 ? (
        <EmptyState
          title="시험법이 없습니다"
          hint="규격을 등록해 두면 장비 시험 항목에 그 규격을 걸 수 있고, 검색이 규격의 요구 조건을 자동으로 채웁니다."
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>규격</TableHead>
              <TableHead>판</TableHead>
              <TableHead>제목</TableHead>
              <TableHead>시험 항목</TableHead>
              <TableHead className="text-right">요구 조건</TableHead>
              <TableHead className="text-right">인용 계열</TableHead>
              <TableHead className="text-right">가능 장비</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(page.data?.items ?? []).map((one) => (
              <TableRow
                key={one.id}
                className={one.status === 'superseded' ? 'opacity-60' : undefined}
              >
                <TableCell className="font-medium">
                  <Link to={`/methods/${one.id}`} className="hover:underline">
                    {one.code}
                  </Link>
                </TableCell>
                <TableCell>{one.edition ?? '—'}</TableCell>
                <TableCell className="max-w-md truncate">{one.title}</TableCell>
                <TableCell>
                  {one.test_item ?? (
                    <Link
                      to={`/methods/${one.id}`}
                      className="text-amber-600 underline decoration-dotted underline-offset-2"
                    >
                      안 정해짐
                    </Link>
                  )}
                </TableCell>
                <TableCell className="text-right">{one.requirements.length}</TableCell>
                <TableCell className="text-right">
                  {/* 이어진 계열 수. 미정 인용이 있으면 따로 말한다 — 「0」 만 보면 카탈로그에
                      없는 것으로 읽힌다. */}
                  {one.series_count === 0 && one.pending_series_count === 0 ? (
                    <span className="text-muted-foreground">—</span>
                  ) : (
                    one.series_count
                  )}
                  {one.pending_series_count > 0 && (
                    <span className="text-muted-foreground ml-1 text-xs">
                      (미정 {one.pending_series_count})
                    </span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  {/* **0 을 그냥 0 으로 두지 않는다.** 그것이 이 표에서 가장 중요한 칸이다. */}
                  {one.equipment_count === 0 ? (
                    <span className="text-amber-600">없음</span>
                  ) : (
                    one.equipment_count
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <RequirementImportDialog
        open={importing}
        onClose={() => setImporting(false)}
        onImported={() => page.reload()}
      />
      <NewMethodDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={() => {
          setCreating(false)
          page.reload()
        }}
      />
    </div>
  )
}

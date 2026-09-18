/**
 * 신뢰성 시험 전체 — **「누가 무슨 시험을 하나」 를 부서를 가로질러 한 표로.**
 *
 * 사이드바 「신뢰성 시험」 아래에는 부서마다 화면이 하나씩 서는데(부서 관리자가 거기서 등록·
 * 수정), 이 화면은 그 전부를 한 번에 본다: 다른 부서가 이미 같은 절차를 하는지, 어느 시험
 * 항목이 어느 부서에 몰려 있는지. 고치는 문은 부서 화면이다 — 줄의 부서 이름을 누르면 간다.
 *
 * 찾기는 이름·목적·부서·시험 항목·속성 값을 한 칸으로 거른다 — 「85 degC」 로 치면 그 조건을
 * 적은 절차가 걸린다(속성 값은 서버가 만든 display 글자).
 */

import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Wrench } from 'lucide-react'

import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { Input } from '@/shared/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table'
import { useBackFromReference } from '@/shared/hooks/useBackFromReference'
import { useResource } from '@/shared/hooks/useResource'
import { Button } from '@/shared/components/ui/button'
import { AttributeFilterBar } from '@/modules/attributes/AttributeFilterBar'
import { CapabilityDialog } from '@/modules/reliability/CapabilityDialog'
import { reliabilityApi } from '@/modules/reliability/api'
import type { ReliabilityTest } from '@/modules/reliability/api'

function haystack(row: ReliabilityTest): string {
  return [
    row.name,
    row.purpose,
    row.workspace_name,
    ...row.test_items.map((one) => one.value),
    ...row.attributes.map((one) => `${one.label} ${one.display}`),
  ]
    .join(' ')
    .toLowerCase()
}

export default function ReliabilityTestsPage() {
  // 속성 조건은 **서버가** 거른다 — 아래 찾기 칸은 받은 쪽 안에서만 훑는다.
  const [attrs, setAttrs] = useState<string[]>([])
  const tests = useResource(() => reliabilityApi.listAll(attrs), [attrs])
  const [query, setQuery] = useState('')
  const [asking, setAsking] = useState<ReliabilityTest | null>(null)
  const rows = tests.data ?? []
  const needle = query.trim().toLowerCase()
  const shown = useMemo(
    () => (needle ? rows.filter((row) => haystack(row).includes(needle)) : rows),
    [rows, needle],
  )
  const workspaces = new Set(rows.map((row) => row.workspace_slug)).size

  return (
    <div className="space-y-6">
      <PageHeader
        back={useBackFromReference()}
        title="신뢰성 시험"
        description="부서가 제품 개발·검증을 위해 수행하는 시험 전부 — 부서를 가로질러 한 표로. 등록·수정은 그 부서의 화면(사이드바 아래 부서 이름)에서 합니다."
      />

      {/* 조건 속성으로 거르기 — 「-40 °C 이하로 내려가는 시험」 을 물을 수 있어야 조건을 적는다. */}
      <AttributeFilterBar target="reliability_test" value={attrs} onChange={setAttrs} />

      <div className="flex flex-wrap items-center gap-3">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="찾기 — 시험 · 목적 · 부서 · 시험 항목 · 속성 값"
          className="w-80"
        />
        {tests.data && (
          <p className="text-muted-foreground text-sm">
            신뢰성 시험 {rows.length}종 · 부서 {workspaces}곳
            {needle && ` · 걸린 것 ${shown.length}종`}
          </p>
        )}
      </div>

      <ErrorNotice error={tests.error} />

      {tests.data && rows.length === 0 ? (
        <EmptyState
          title="등록된 신뢰성 시험이 없습니다"
          hint="사이드바 「신뢰성 시험」 아래의 부서 화면에서 그 부서의 관리자가 등록합니다. 부서가 안 보이면 「관리 → 부서 정보」 의 「신뢰성 시험」 표시를 켭니다."
        />
      ) : tests.data && shown.length === 0 ? (
        <EmptyState title="걸리는 신뢰성 시험이 없습니다" hint="찾는 말을 줄여 보세요." />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>부서</TableHead>
              <TableHead>신뢰성 시험</TableHead>
              <TableHead>목적</TableHead>
              <TableHead>구성 시험 항목 · 그 부서 장비</TableHead>
              <TableHead>속성</TableHead>
              <TableHead className="w-32" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {shown.map((row) => (
              <TableRow key={row.id}>
                <TableCell className="whitespace-nowrap">
                  {/* 고치는 문 — 부서 화면. 여기서는 읽기만. */}
                  <Link
                    to={`/reliability-tests/${row.workspace_slug}`}
                    className="hover:underline"
                  >
                    {row.workspace_name}
                  </Link>
                </TableCell>
                <TableCell className="font-medium">{row.name}</TableCell>
                <TableCell className="text-muted-foreground max-w-xs text-sm whitespace-pre-line">
                  {row.purpose || '—'}
                </TableCell>
                <TableCell>
                  {row.test_items.length === 0 ? (
                    <span className="text-muted-foreground text-sm">시험 항목 미지정</span>
                  ) : (
                    <ul className="flex flex-wrap gap-x-3 gap-y-1 text-sm">
                      {row.test_items.map((item) => (
                        <li key={item.term_id} className="flex items-center gap-1">
                          <Link
                            to={`/catalog/test-items/${item.term_id}`}
                            className="hover:underline"
                          >
                            {item.value}
                          </Link>
                          <span
                            className={`text-xs ${item.equipment_count === 0 ? 'text-amber-600' : 'text-muted-foreground'}`}
                            title={
                              item.equipment_count === 0
                                ? '이 항목이 되는 장비가 그 부서에 없습니다'
                                : undefined
                            }
                          >
                            {item.equipment_count}대
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </TableCell>
                <TableCell>
                  {row.attributes.length === 0 ? (
                    <span className="text-muted-foreground text-sm">—</span>
                  ) : (
                    <ul className="space-y-0.5 text-sm">
                      {row.attributes.map((item) => (
                        <li key={item.definition_id} className="flex flex-wrap gap-x-1">
                          <span className="text-muted-foreground">{item.label}</span>
                          <span>{item.display}</span>
                          {item.status === 'draft' && (
                            <span className="text-muted-foreground text-xs">초안</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </TableCell>
                <TableCell className="text-right whitespace-nowrap">
                  {/* **이 시험, 어느 장비로 돌리나.** 조건 속성이 그대로 검색 조건이 된다 —
                      시험 항목까지만 이으면 답이 「인장 되는 장비 N대」 라서, 사람이 다시
                      장비를 하나씩 열어 봐야 한다. */}
                  <Button size="sm" variant="outline" onClick={() => setAsking(row)}>
                    <Wrench className="mr-1 size-3.5" />
                    가능한 장비
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {asking && <CapabilityDialog test={asking} onClose={() => setAsking(null)} />}
    </div>
  )
}

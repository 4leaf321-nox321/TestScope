/**
 * 기준정보 보기 — **고르는 사람이 목록을 볼 수 있어야 한다.**
 *
 * 이 값을 매일 드롭다운에서 고르는 것은 멤버다. 못 보면 찾는 값이 없을 때
 * "아직 없다" 인지 "이름이 다르다" 인지 구별할 수 없다. 고치는 자리는 관리 화면이다.
 */

import { useState } from 'react'

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
import { useResource } from '@/shared/hooks/useResource'
import { cn } from '@/shared/lib/utils'
import { vocabularyApi } from '@/modules/vocabulary/api'

export default function VocabularyPage() {
  const axes = useResource(() => vocabularyApi.list(), [])
  const [slug, setSlug] = useState<string | null>(null)
  const [query, setQuery] = useState('')

  const current = slug ?? axes.data?.[0]?.slug ?? null
  const terms = useResource(
    () => (current ? vocabularyApi.terms(current, query || undefined) : Promise.resolve([])),
    [current, query],
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="기준정보"
        description="폼에서 고르는 값들의 목록입니다. 값을 더하거나 고치는 것은 관리자가 합니다."
      />

      <ErrorNotice error={axes.error ?? terms.error} />

      <div className="flex gap-6">
        {/* 축 목록. **값 수를 함께 보여 준다** — 비어 있는 축과 채워진 축이 같아
            보이면 어디를 채워야 하는지 알 수 없다. */}
        <ul className="w-56 shrink-0 space-y-1">
          {(axes.data ?? []).map((axis) => (
            <li key={axis.slug}>
              <button
                type="button"
                onClick={() => setSlug(axis.slug)}
                className={cn(
                  'flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm',
                  axis.slug === current
                    ? 'bg-accent text-accent-foreground font-medium'
                    : 'text-muted-foreground hover:bg-accent/60',
                )}
              >
                <span className="truncate">{axis.label}</span>
                <span className="text-xs">{axis.term_count}</span>
              </button>
            </li>
          ))}
        </ul>

        <div className="min-w-0 flex-1 space-y-3">
          {/* 축 설명을 보여 준다 — 고르는 사람이 축의 뜻을 모르면 비슷한 축 둘 중
              아무 데나 값을 넣는다. */}
          {(() => {
            const axis = (axes.data ?? []).find((one) => one.slug === current)
            return axis?.description ? (
              <p className="text-muted-foreground text-sm">{axis.description}</p>
            ) : null
          })()}

          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="값 찾기"
            className="max-w-sm"
          />

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>값</TableHead>
                <TableHead>코드</TableHead>
                <TableHead>상위</TableHead>
                <TableHead>다른 표기</TableHead>
                <TableHead className="text-right">쓰임</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(terms.data ?? []).map((term) => (
                <TableRow key={term.id}>
                  <TableCell>{term.value}</TableCell>
                  <TableCell className="font-mono text-xs">{term.code ?? '—'}</TableCell>
                  <TableCell>{term.parent_value ?? '—'}</TableCell>
                  {/* **별칭을 보여 준다.** 찾는 값이 별칭으로 이미 묶여 있는지를
                      알 수 있어야 사람이 같은 값을 또 만들지 않는다. */}
                  <TableCell className="text-muted-foreground text-sm">
                    {term.aliases.join(', ') || '—'}
                  </TableCell>
                  <TableCell className="text-right">{term.usage_count}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  )
}

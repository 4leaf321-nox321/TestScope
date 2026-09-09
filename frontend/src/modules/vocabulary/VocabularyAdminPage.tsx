/**
 * 기준정보 편집.
 *
 * **켜 두고 고칠 데가 없으면 절반만 한 것이다.** 오타가 값이 되면 그것을 고르는
 * 다음 사람이 생기고, 오염이 자기 강화된다.
 *
 * 합치기는 원본을 **별칭으로 남긴다** — 지우면 같은 오타가 또 들어오고, 그때는
 * 아무도 그것이 예전에 합쳐졌던 값이라는 것을 모른다.
 */

import { useState } from 'react'

import { ApiError } from '@/shared/api/client'
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

export default function VocabularyAdminPage() {
  const axes = useResource(() => vocabularyApi.list(), [])
  const [slug, setSlug] = useState('')
  const current = slug || axes.data?.[0]?.slug || ''
  const terms = useResource(
    () => (current ? vocabularyApi.terms(current) : Promise.resolve([])),
    [current],
  )
  const [value, setValue] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState<ApiError | Error | null>(null)

  async function act(run: () => Promise<unknown>) {
    setError(null)
    try {
      await run()
      terms.reload()
      axes.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="기준정보 편집"
        description="값을 더하고, 이름을 고치고, 중복을 합칩니다. 이름 변경은 변경 이력에 남습니다."
      />

      <div className="flex flex-wrap items-end gap-2">
        <Select value={current} onValueChange={setSlug}>
          <SelectTrigger className="w-56">
            <SelectValue placeholder="축" />
          </SelectTrigger>
          <SelectContent>
            {(axes.data ?? []).map((axis) => (
              <SelectItem key={axis.slug} value={axis.slug}>
                {axis.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="새 값"
          className="w-56"
        />
        <Input
          value={code}
          onChange={(event) => setCode(event.target.value)}
          placeholder="코드 (선택)"
          className="w-40"
        />
        <Button
          onClick={() =>
            act(async () => {
              await vocabularyApi.createTerm(current, { value, code: code || null })
              setValue('')
              setCode('')
            })
          }
          disabled={!value || !current}
        >
          추가
        </Button>
      </div>

      {/* 서버가 중복을 잡으면 **어느 값과 겹치는지**까지 말해 준다. 그 메시지를
          그대로 보여 준다 — 다시 쓰면 표현이 갈린다. */}
      <ErrorNotice error={error ?? terms.error} />

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>값</TableHead>
            <TableHead>코드</TableHead>
            <TableHead>다른 표기</TableHead>
            <TableHead>상태</TableHead>
            <TableHead className="text-right">쓰임</TableHead>
            <TableHead className="text-right">편집</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(terms.data ?? []).map((term) => (
            <TableRow key={term.id}>
              <TableCell>{term.value}</TableCell>
              <TableCell className="font-mono text-xs">{term.code ?? '—'}</TableCell>
              <TableCell className="text-muted-foreground text-sm">
                {term.aliases.join(', ') || '—'}
              </TableCell>
              <TableCell>{term.status === 'active' ? '사용' : '폐기'}</TableCell>
              <TableCell className="text-right">{term.usage_count}</TableCell>
              <TableCell className="space-x-1 text-right">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    const next = window.prompt('새 이름', term.value)
                    if (next) act(() => vocabularyApi.updateTerm(term.id, { value: next }))
                  }}
                >
                  이름
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    const alias = window.prompt('이 값의 다른 표기')
                    if (alias) act(() => vocabularyApi.addAlias(term.id, alias))
                  }}
                >
                  표기 추가
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    act(() =>
                      vocabularyApi.updateTerm(term.id, {
                        // **지우지 않고 폐기한다.** 지우면 그 값을 가리키던 장비가
                        // 무엇이었는지 알 수 없게 된다.
                        status: term.status === 'active' ? 'deprecated' : 'active',
                      }),
                    )
                  }
                >
                  {term.status === 'active' ? '폐기' : '되살리기'}
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

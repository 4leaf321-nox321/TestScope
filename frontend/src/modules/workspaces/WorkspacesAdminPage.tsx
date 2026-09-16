/**
 * 부서 정보 — 전사 조직도.
 *
 * **트리 순서는 서버가 정한다.** 화면이 평면 목록을 받아 스스로 세우면, 부서
 * 선택기와 이 화면의 순서가 달라진다 — 같은 목록이 화면마다 다르게 보인다.
 *
 * **부서를 지우는 것은 예외다.** 기본은 보관(is_active=false)이고, 삭제는 잘못
 * 만든 부서처럼 자료가 아예 없는 경우를 위한 것이다.
 */

import { useState } from 'react'
import { ChevronDown, ChevronUp, Download, FileInput, Plus } from 'lucide-react'

import { ApiError } from '@/shared/api/client'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table'
import { useResource } from '@/shared/hooks/useResource'
import { ImportWorkspacesDialog } from '@/modules/workspaces/ImportWorkspacesDialog'
import { workspaceApi } from '@/modules/workspaces/api'

export default function WorkspacesAdminPage() {
  const list = useResource(() => workspaceApi.list(true), [])
  const [slug, setSlug] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [importing, setImporting] = useState(false)

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
        title="부서 정보"
        description="조직도를 만들고 고칩니다. 부서를 옮겨도 장비는 하나도 움직이지 않습니다."
        actions={
          // ReportArchive 의 「부서 정보 내보내기」 와 컬럼·순서가 같다 — 양쪽으로
          // 오간다. 한쪽으로만 들어가는 것은 호환이 아니라 이사다.
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setImporting(true)}>
              <FileInput className="size-4" />
              가져오기
            </Button>
            <Button
              variant="outline"
              onClick={() =>
                act(async () => {
                  await workspaceApi.exportCsv()
                })
              }
            >
              <Download className="size-4" />
              CSV 내보내기
            </Button>
          </div>
        }
      />

      <ImportWorkspacesDialog
        open={importing}
        onClose={() => setImporting(false)}
        onDone={() => list.reload()}
      />

      <form
        className="flex flex-wrap items-end gap-2 rounded-md border p-4"
        onSubmit={(event) => {
          event.preventDefault()
          act(async () => {
            await workspaceApi.create({ slug, name })
            setSlug('')
            setName('')
          })
        }}
      >
        <div className="space-y-2">
          <Label htmlFor="slug">주소 이름</Label>
          {/* URL 에 들어가므로 소문자·숫자·하이픈만. 한글 이름은 옆 칸이 갖는다. */}
          <Input
            id="slug"
            value={slug}
            onChange={(event) => setSlug(event.target.value)}
            placeholder="material-lab"
            pattern="[a-z0-9][a-z0-9-]{1,49}"
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="name">부서 이름</Label>
          <Input
            id="name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="재료시험팀"
            required
          />
        </div>
        <Button type="submit">
          <Plus className="size-4" />
          부서 추가
        </Button>
      </form>

      <ErrorNotice error={error ?? list.error} />

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>부서</TableHead>
            <TableHead>주소</TableHead>
            <TableHead className="text-right">멤버</TableHead>
            <TableHead className="text-right">장비</TableHead>
            <TableHead>공개</TableHead>
            <TableHead>신뢰성 시험</TableHead>
            <TableHead>상태</TableHead>
            <TableHead className="text-right">순서</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(list.data ?? []).map((one) => (
            <TableRow key={one.id}>
              <TableCell>
                {/* 깊이만큼 들여쓴다 — 경로 문자열을 그대로 쓰면 줄이 길어져 표가 접힌다. */}
                <span style={{ paddingLeft: `${one.depth * 16}px` }}>{one.name}</span>
              </TableCell>
              <TableCell className="font-mono text-xs">{one.slug}</TableCell>
              <TableCell className="text-right">{one.member_count}</TableCell>
              <TableCell className="text-right">{one.equipment_count}</TableCell>
              <TableCell>
                {/* **가리는 쪽이 예외다.** 기본은 전원 공개 — 이 시스템의 물음이
                    부서를 가로지르기 때문이다. */}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    act(() => workspaceApi.update(one.slug, { restricted: !one.restricted }))
                  }
                >
                  {one.restricted ? '멤버만' : '전원'}
                </Button>
              </TableCell>
              <TableCell>
                {/* 체크한 부서가 사이드바 「신뢰성 시험」 아래에 선다 — 부서마다 그
                    부서의 신뢰성 시험 화면 하나. 조직도를 통째로 메뉴에 펼치지 않는다. */}
                <label className="flex cursor-pointer items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={one.reliability_listed}
                    aria-label={`${one.name} 신뢰성 시험 메뉴 표시`}
                    onChange={(event) =>
                      act(() =>
                        workspaceApi.update(one.slug, {
                          reliability_listed: event.target.checked,
                        }),
                      )
                    }
                  />
                  <span className="text-muted-foreground text-xs">
                    {one.reliability_listed ? '메뉴 표시' : '—'}
                  </span>
                </label>
              </TableCell>
              <TableCell>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    act(() => workspaceApi.update(one.slug, { is_active: !one.is_active }))
                  }
                >
                  {one.is_active ? '사용' : '보관'}
                </Button>
              </TableCell>
              <TableCell className="text-right">
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="위로"
                  onClick={() => act(() => workspaceApi.reorder(one.slug, 'up'))}
                >
                  <ChevronUp className="size-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="아래로"
                  onClick={() => act(() => workspaceApi.reorder(one.slug, 'down'))}
                >
                  <ChevronDown className="size-4" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

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
import { Download, FileInput, Plus, Trash2 } from 'lucide-react'

import { ApiError } from '@/shared/api/client'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import { reliabilityApi } from '@/modules/reliability/api'
import { useResource } from '@/shared/hooks/useResource'
import { useBackFromReference } from '@/shared/hooks/useBackFromReference'
import { DeleteWorkspaceDialog } from '@/modules/workspaces/DeleteWorkspaceDialog'
import { WorkspaceTree } from '@/modules/workspaces/WorkspaceTree'
import { ImportWorkspacesDialog } from '@/modules/workspaces/ImportWorkspacesDialog'
import { workspaceApi } from '@/modules/workspaces/api'
import type { Workspace } from '@/modules/workspaces/api'

export default function WorkspacesAdminPage() {
  const list = useResource(() => workspaceApi.list(true), [])
  // 고를 수 있는 사업부. 값을 더하는 자리는 「관리 → 온톨로지」 의 사업부 축이다 —
  // 여기서 만들게 두면 오타가 그대로 사업부가 된다(닫힌 축인 이유).
  const divisions = useResource(() => reliabilityApi.divisions(), [])
  const [slug, setSlug] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [importing, setImporting] = useState(false)
  /** 지우려고 연 부서. 창이 확인과 이관을 맡는다. */
  const [removing, setRemoving] = useState<Workspace | null>(null)

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
        back={useBackFromReference()}
        title="부서 정보"
        description="조직도 생성 및 수정. 부서를 이동해도 장비는 그대로 유지됨."
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
          부서 등록
        </Button>
      </form>

      <ErrorNotice error={error ?? list.error} />

      {/* **표가 아니라 트리다.** 열이 여섯이나 서 있으면 들여쓰기가 묻혀 상하 관계가
          없는 것처럼 보인다 — 실제로 그렇게 보인다는 말을 들었다(2026-09-28). 줄기를
          그리고, 줄마다 「↳ 상위」 를 적고, 끌어다 놓아 옮길 수 있게 한다. */}
      <p className="text-muted-foreground text-xs">
        손잡이를 끌어 이동. <strong>줄 위의 얇은 띠</strong>에 놓으면 그 부서의 앞 형제,{' '}
        <strong>줄 자체</strong>에 놓으면 그 부서의 마지막 자식으로 배치됨.
      </p>

      <div className="rounded-md border">
        <WorkspaceTree
          rows={list.data ?? []}
          onMove={(plan) => act(() => workspaceApi.applyTree(plan))}
          renderActions={(one) => (
            <div className="flex shrink-0 items-center gap-1">
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
              {/* **사업부.** 붙이면 그 아래 부서가 모두 물려받는다 — 사업부에 한 번
                  붙이면 수십 개 팀에 다시 붙일 일이 없고, 팀이 옮겨 가면 부모만 바뀌어도
                  따라간다. 신뢰성 시험은 부서가 아니라 이 사업부에 속한다.

                  **물려받은 것은 흐리게** 보인다 — 「여기 안 붙었네」 하고 또 붙이면
                  그 팀만 조직 개편에서 떨어져 나간다. */}
              <select
                className="bg-background h-7 rounded-md border px-1 text-xs"
                aria-label={`${one.name} 사업부`}
                title={
                  one.division_own
                    ? '이 부서에 직접 지정된 사업부'
                    : one.division_name
                      ? `상위 부서에서 상속: ${one.division_name}`
                      : '사업부 없음'
                }
                value={one.division_own ? (one.division_code ?? '') : ''}
                onChange={(event) =>
                  act(() =>
                    workspaceApi.update(one.slug, { division_code: event.target.value }),
                  )
                }
              >
                <option value="">
                  {one.division_name && !one.division_own
                    ? `(물려받음: ${one.division_name})`
                    : '(사업부 없음)'}
                </option>
                {(divisions.data ?? []).map((division) => (
                  <option key={division.code} value={division.code}>
                    {division.name}
                  </option>
                ))}
              </select>
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  act(() => workspaceApi.update(one.slug, { is_active: !one.is_active }))
                }
              >
                {one.is_active ? '사용' : '보관'}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label={`${one.name} 지우기`}
                onClick={() => setRemoving(one)}
              >
                <Trash2 className="text-destructive size-4" />
              </Button>
            </div>
          )}
        />
      </div>

      <DeleteWorkspaceDialog
        target={removing}
        all={list.data ?? []}
        onClose={() => setRemoving(null)}
        onDeleted={() => {
          setRemoving(null)
          list.reload()
        }}
      />
    </div>
  )
}

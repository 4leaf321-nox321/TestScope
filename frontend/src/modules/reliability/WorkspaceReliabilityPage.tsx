/**
 * 부서 하나의 신뢰성 시험 — **「저 부서는 무슨 시험을 하나」 의 답.**
 *
 * 신뢰성 시험은 부서가 제품 개발·검증을 위해 수행하는 시험이고(고온고습 1000h · 열충격
 * 500 cycle), 「시험 항목」(장비가 할 수 있는 측정 — 인장·경도·열충격)과 다른 층이다.
 * 신뢰성 시험 하나가 시험 항목 하나 이상을 써서 돌고, 그 항목이 장비로 이어진다:
 *
 *     신뢰성 시험  →  시험 항목  →  장비
 *
 * 사이드바 「신뢰성 시험」 아래에 「부서 정보」 에서 고른 부서가 서고, 누르면 이 화면이다.
 * 등록은 그 부서의 관리자와 시스템 관리자. 등록 단추는 roles.ts 가, 줄마다의 수정 단추는
 * 서버의 `can_edit` 가 정한다 — 둘 다 표시일 뿐이고 권한은 서버가 판정한다.
 */

import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Pencil, Plus, Trash2 } from 'lucide-react'

import { useAuth } from '@/shared/auth/AuthContext'
import { isManagerOf } from '@/shared/auth/roles'
import { ConfirmDialog } from '@/shared/components/ConfirmDialog'
import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { Button } from '@/shared/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table'
import { useResource } from '@/shared/hooks/useResource'
import { ReliabilityTestDialog } from '@/modules/reliability/ReliabilityTestDialog'
import { reliabilityApi } from '@/modules/reliability/api'
import type { ReliabilityTest } from '@/modules/reliability/api'
import { workspaceApi } from '@/modules/workspaces/api'

export default function WorkspaceReliabilityPage() {
  const { slug = '' } = useParams<{ slug: string }>()
  const { user } = useAuth()
  // 부서 이름은 메뉴와 같은 목록에서 받는다 — 여기 없으면 메뉴에도 없는 부서다.
  const listed = useResource(() => workspaceApi.reliabilityListed(), [])
  const tests = useResource(() => reliabilityApi.list(slug), [slug])
  const [editing, setEditing] = useState<ReliabilityTest | null>(null)
  const [creating, setCreating] = useState(false)
  const [removing, setRemoving] = useState<ReliabilityTest | null>(null)

  const workspace = listed.data?.find((one) => one.slug === slug)
  const rows = tests.data ?? []
  // **표시일 뿐 권한이 아니다.** 등록 단추는 roles.ts 가, 줄마다의 수정은 서버의 can_edit 가
  // 정한다 — 눌러야 403 을 아는 단추는 「할 수 있는 일」 을 알려 주지 못한다.
  const canEdit = isManagerOf(user, slug)

  if (listed.data && !workspace) {
    return (
      <div className="space-y-6">
        <PageHeader title="신뢰성 시험" />
        <EmptyState
          title="이 부서는 신뢰성 시험 메뉴에 없습니다"
          hint="시스템 관리자가 「관리 → 부서 정보」 에서 체크한 부서만 여기 섭니다. 보관한 부서도 빠집니다."
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={workspace ? `${workspace.name} · 신뢰성 시험` : '신뢰성 시험'}
        description={
          workspace
            ? `${workspace.path} 가 제품 개발·검증을 위해 수행하는 시험. 쓰는 시험 항목 옆의 수가 이 부서 장비 중 그 항목이 되는 대수입니다.`
            : undefined
        }
        actions={
          canEdit && (
            <Button onClick={() => setCreating(true)}>
              <Plus className="size-4" />
              신뢰성 시험 등록
            </Button>
          )
        }
      />

      {tests.data && (
        <p className="text-muted-foreground text-sm">신뢰성 시험 {rows.length}종</p>
      )}

      <ErrorNotice error={tests.error ?? listed.error} />

      {tests.data && rows.length === 0 ? (
        <EmptyState
          title="등록된 신뢰성 시험이 없습니다"
          hint={
            canEdit
              ? '위의 「신뢰성 시험 등록」 으로 첫 시험을 적으세요.'
              : '이 부서의 관리자 또는 시스템 관리자가 등록합니다.'
          }
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>신뢰성 시험</TableHead>
              <TableHead>목적</TableHead>
              <TableHead>쓰는 시험 항목 · 이 부서 장비</TableHead>
              {canEdit && <TableHead className="w-24" />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell className="font-medium">{row.name}</TableCell>
                <TableCell className="text-muted-foreground max-w-md text-sm whitespace-pre-line">
                  {row.purpose || '—'}
                </TableCell>
                <TableCell>
                  {row.test_items.length === 0 ? (
                    // 「장비 없음」 이 아니라 「안 정함」 — 둘은 해야 할 일이 다르다.
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
                          {item.equipment_count === 0 ? (
                            <span
                              className="text-amber-600 text-xs"
                              title="이 항목이 되는 장비가 이 부서에 없습니다"
                            >
                              0대
                            </span>
                          ) : (
                            <Link
                              to={`/equipment?workspace=${slug}&test_item_term_id=${item.term_id}`}
                              className="text-muted-foreground text-xs hover:underline"
                            >
                              {item.equipment_count}대
                            </Link>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </TableCell>
                {canEdit && (
                  <TableCell className="text-right whitespace-nowrap">
                    {row.can_edit && (
                      <>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`${row.name} 수정`}
                          onClick={() => setEditing(row)}
                        >
                          <Pencil className="size-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`${row.name} 삭제`}
                          onClick={() => setRemoving(row)}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      </>
                    )}
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <ReliabilityTestDialog
        open={creating || editing !== null}
        workspace={slug}
        editing={editing}
        onClose={() => {
          setCreating(false)
          setEditing(null)
        }}
        onSaved={() => {
          setCreating(false)
          setEditing(null)
          tests.reload()
        }}
      />

      <ConfirmDialog
        open={removing !== null}
        title="신뢰성 시험을 삭제합니다"
        description={
          <>
            <strong>{removing?.name}</strong> 을 목록에서 삭제합니다. 데이터는 보존되며 변경
            이력에 남습니다.
          </>
        }
        confirmLabel="삭제"
        destructive
        onConfirm={async () => {
          if (removing) await reliabilityApi.remove(removing.id)
          setRemoving(null)
          tests.reload()
        }}
        onClose={() => setRemoving(null)}
      />
    </div>
  )
}

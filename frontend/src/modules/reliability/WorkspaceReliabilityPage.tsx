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
 *
 * **후보를 검토하는 자리가 여기다.** AI 가 MCP 로 올린 시험은 확인 전까지 전사 목록에
 * 안 나오고 이 화면에만 선다 — 그래서 맨 위에 몇 건인지 적고, 줄에 배지를 단다. 목록
 * 아래쪽에 섞여 있으면 아무도 안 본다.
 *
 * **줄을 누르면 보기 창, 연필을 누르면 수정 창이다.** 읽으려고 수정 창을 여는 것은
 * 위험하고(읽다가 글자를 건드린다), 고칠 권한이 없는 사람은 연필이 없어 카드를 열 길이
 * 아예 없었다.
 *
 * 좁은 창에서는 **덜 급한 열을 접는다**(속성 → 목적 → 시험 항목 순). 시험 항목·속성은
 * 줄바꿈이 안 되는 덩어리라 폭을 안 내놓고, 그러면 목적 열만 혼자 찌그러져 글자 한 자
 * 폭이 되면서 가로 스크롤까지 생긴다 — 전사 목록과 같은 규칙이다. 목적 열은 `w-` 가
 * 아니라 **`min-w-`** 라야 한다: `w-` 는 표가 눌리면 브라우저가 무시한다.
 */

import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Pencil, Plus, Trash2, Wrench } from 'lucide-react'

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
import { isPlainRowClick } from '@/shared/lib/rowClick'
import { useBackFromReference } from '@/shared/hooks/useBackFromReference'
import { CandidateBadge, isCandidate } from '@/modules/reliability/CandidateReview'
import { CapabilityDialog } from '@/modules/reliability/CapabilityDialog'
import { ReliabilityTestDialog } from '@/modules/reliability/ReliabilityTestDialog'
import {
  ReliabilityTestViewDialog,
  RowOpener,
} from '@/modules/reliability/ReliabilityTestViewDialog'
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
  const [asking, setAsking] = useState<ReliabilityTest | null>(null)
  /** 읽기만 하는 창 — 줄을 누르면 이것. */
  const [viewing, setViewing] = useState<ReliabilityTest | null>(null)

  const workspace = listed.data?.find((one) => one.slug === slug)
  const rows = tests.data ?? []
  // 서버가 후보를 앞으로 보내 준다 — 여기서는 세기만 한다.
  const pending = rows.filter(isCandidate).length
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
        back={useBackFromReference()}
        title={workspace ? `${workspace.name} · 신뢰성 시험` : '신뢰성 시험'}
        description={
          workspace
            ? `${workspace.path} 가 제품 개발·검증을 위해 수행하는 시험. 적용 시험 항목 옆의 수가 이 부서 장비 중 그 항목이 되는 대수입니다.`
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
        <p className="text-muted-foreground text-sm">
          신뢰성 시험 {rows.length}종
          {pending > 0 && (
            // **숫자를 눈에 띄게 둔다.** 「확인 전 3건」 이 안 보이면 아무도 안 연다.
            <span className="text-destructive ml-2 font-medium">
              확인 전 {pending}건 — 내용을 읽고 확인해 주십시오
            </span>
          )}
        </p>
      )}

      <ErrorNotice error={tests.error ?? listed.error} />

      {tests.data && rows.length === 0 ? (
        <EmptyState
          title="등록된 신뢰성 시험이 없습니다"
          hint={
            canEdit
              ? '위의 「신뢰성 시험 등록」 으로 첫 시험을 적으십시오.'
              : '이 부서의 관리자 또는 시스템 관리자가 등록합니다.'
          }
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>신뢰성 시험</TableHead>
              <TableHead className="hidden w-full min-w-96 lg:table-cell">목적</TableHead>
              <TableHead className="hidden min-w-48 md:table-cell">
                적용 시험 항목 · 보유 장비
              </TableHead>
              <TableHead className="hidden min-w-56 xl:table-cell">속성</TableHead>
              <TableHead className="w-32" />
              {canEdit && <TableHead className="w-24" />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow
                key={row.id}
                className="hover:bg-muted/50 cursor-pointer"
                // 줄 어디를 눌러도 열되 **링크·단추 위에서는 안 연다** — 시험 항목 링크를
                // 누른 사람은 그 항목으로 가려던 것이다.
                onClick={(event) => isPlainRowClick(event) && setViewing(row)}
              >
                <TableCell>
                  <RowOpener name={row.name} onOpen={() => setViewing(row)}>
                    <CandidateBadge row={row} />
                  </RowOpener>
                </TableCell>
                {/* **줄 수를 묶는다.** 전문은 줄을 눌러 보기 창에서 읽는다. */}
                <TableCell className="text-muted-foreground hidden w-full min-w-96 align-top text-sm lg:table-cell">
                  <p className="line-clamp-3 whitespace-pre-line" title={row.purpose}>
                    {row.purpose || '—'}
                  </p>
                </TableCell>
                <TableCell className="hidden align-top md:table-cell">
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
                <TableCell className="hidden align-top xl:table-cell">
                  {row.attributes.length === 0 ? (
                    <span className="text-muted-foreground text-sm">—</span>
                  ) : (
                    <ul className="space-y-0.5 text-sm">
                      {row.attributes.map((item) => (
                        <li key={item.definition_id} className="flex flex-wrap gap-x-1">
                          <span className="text-muted-foreground">{item.label}</span>
                          <span>{item.display}</span>
                          {item.status === 'draft' && (
                            // 초안은 표시·수집만 — 검색 판정에 안 쓰인다는 것을 읽는 사람이 알아야 한다.
                            <span
                              className="text-muted-foreground text-xs"
                              title="초안 속성 — 시스템 관리자가 정식으로 올리기 전입니다"
                            >
                              초안
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </TableCell>
                {/* **이 시험, 어느 장비로 돌리나.** 조건 속성이 그대로 검색 조건이 된다 —
                    「이 부서 장비 N대」 는 조건을 안 본 수라, 그 N 대를 사람이 다시 하나씩
                    열어 봐야 했다. 읽기는 누구나 — 빌릴 곳을 찾는 것이 이 화면의 쓸모다. */}
                <TableCell className="text-right whitespace-nowrap">
                  <Button size="sm" variant="outline" onClick={() => setAsking(row)}>
                    <Wrench className="mr-1 size-3.5" />
                    수행 가능 장비
                  </Button>
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

      {asking && <CapabilityDialog test={asking} onClose={() => setAsking(null)} />}

      <ReliabilityTestViewDialog
        test={viewing}
        onClose={() => setViewing(null)}
        onEdit={(row) => {
          setViewing(null)
          setEditing(row)
        }}
        onChanged={(next) => {
          setViewing(next)
          tests.reload()
        }}
      />

      <ReliabilityTestDialog
        open={creating || editing !== null}
        workspace={slug}
        editing={editing}
        onReviewed={(next) => {
          // 창은 열어 둔다 — 확인한 뒤에 이어서 고칠 수 있어야 한다.
          setEditing(next)
          tests.reload()
        }}
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

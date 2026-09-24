/**
 * 사내 규격서 — **부서가 만든 시험 문서의 원본이 사는 곳.**
 *
 * 공개 규격(「시험법·규격」, ASTM·ISO·KS 601건)과 **다른 화면이다.** 출처도 권한도 개정
 * 주기도 다르고, 한 목록에 섞으면 「우리가 인용하는 공개 규격」 을 세는 숫자가 틀어진다.
 *
 * 신뢰성 시험의 「규격서」 칸이 여기 줄을 드롭다운으로 가리킨다 — 같은 문서를 여러 시험이
 * 인용하므로 시험마다 문서 설명을 다시 적지 않는다.
 *
 * **판은 줄을 나누지 않는다.** MX-REL-012 는 줄 하나고 「판」 칸을 고치며 개정본 파일을
 * 더한다 — 판마다 새 줄을 만들면 개정될 때마다 걸어 둔 시험 수십 건의 링크를 사람이
 * 옮겨야 하고, 그러면 아무도 안 옮긴다.
 */

import { useMemo, useState } from 'react'
import { FileText, Pencil, Plus, Trash2 } from 'lucide-react'

import { useAuth } from '@/shared/auth/AuthContext'
import { ConfirmDialog } from '@/shared/components/ConfirmDialog'
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
import { isPlainRowClick } from '@/shared/lib/rowClick'
import { SpecDocumentDialog } from '@/modules/documents/SpecDocumentDialog'
import { SpecDocumentViewDialog } from '@/modules/documents/SpecDocumentViewDialog'
import { specDocumentApi } from '@/modules/documents/api'
import type { SpecDocument } from '@/modules/documents/api'

export default function SpecDocumentsPage() {
  const { user } = useAuth()
  const documents = useResource(() => specDocumentApi.list(), [])
  const [query, setQuery] = useState('')
  const [editing, setEditing] = useState<SpecDocument | null>(null)
  const [creating, setCreating] = useState(false)
  const [viewing, setViewing] = useState<SpecDocument | null>(null)
  const [removing, setRemoving] = useState<SpecDocument | null>(null)
  const [error, setError] = useState<Error | null>(null)

  const rows = documents.data ?? []
  const needle = query.trim().toLowerCase()
  const shown = useMemo(
    () =>
      needle
        ? rows.filter((row) =>
            [row.code, row.title, row.workspace_name, row.revision ?? '']
              .join(' ')
              .toLowerCase()
              .includes(needle),
          )
        : rows,
    [rows, needle],
  )
  // 등록 단추는 **어느 부서든 관리자면** 보인다. 판정은 서버가 한다.
  const canAdd = Boolean(
    user?.is_system_admin || (user?.memberships ?? []).some((one) => one.role === 'manager'),
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="사내 규격서"
        description="부서가 만든 시험 문서입니다. 공개 규격(ASTM·ISO·KS)은 「시험법·규격」 에 있습니다. 신뢰성 시험의 「규격서」 칸이 여기 문서를 가리킵니다."
        actions={
          canAdd && (
            <Button onClick={() => setCreating(true)}>
              <Plus className="size-4" />
              규격서 등록
            </Button>
          )
        }
      />

      <div className="flex flex-wrap items-center gap-3">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="찾기 — 번호 · 제목 · 부서"
          className="w-80"
        />
        {documents.data && (
          <p className="text-muted-foreground text-sm">
            규격서 {rows.length}건{needle && ` · 걸린 것 ${shown.length}건`}
          </p>
        )}
      </div>

      <ErrorNotice error={documents.error ?? error} />

      {documents.data && rows.length === 0 ? (
        <EmptyState
          title="등록된 사내 규격서가 없습니다"
          hint={
            canAdd
              ? '위의 「규격서 등록」 으로 문서 번호를 만들고, 그 안에 원본 파일을 올립니다.'
              : '부서 관리자 또는 시스템 관리자가 등록합니다.'
          }
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>번호</TableHead>
              <TableHead className="hidden w-full min-w-80 lg:table-cell">제목</TableHead>
              <TableHead>판</TableHead>
              <TableHead>부서</TableHead>
              <TableHead className="hidden md:table-cell">파일</TableHead>
              <TableHead className="hidden md:table-cell">거는 시험</TableHead>
              <TableHead className="w-24" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {shown.map((row) => (
              <TableRow
                key={row.id}
                className="hover:bg-muted/50 cursor-pointer"
                onClick={(event) => isPlainRowClick(event) && setViewing(row)}
              >
                <TableCell className="font-medium">
                  <button
                    type="button"
                    className="text-left font-medium hover:underline"
                    aria-label={`${row.code} 보기`}
                    onClick={() => setViewing(row)}
                  >
                    {row.code}
                  </button>
                </TableCell>
                <TableCell className="text-muted-foreground hidden w-full min-w-80 align-top text-sm lg:table-cell">
                  <p className="line-clamp-2" title={row.title}>
                    {row.title}
                  </p>
                </TableCell>
                <TableCell className="whitespace-nowrap">{row.revision ?? '—'}</TableCell>
                <TableCell className="whitespace-nowrap">{row.workspace_name}</TableCell>
                <TableCell className="hidden md:table-cell">
                  {row.file_count === 0 ? (
                    // **파일 없는 규격서는 번호일 뿐이다.** 그 사실이 목록에 보여야 한다.
                    <span className="text-amber-600 text-sm">없음</span>
                  ) : (
                    <span className="flex items-center gap-1 text-sm">
                      <FileText className="size-3.5" />
                      {row.file_count}
                    </span>
                  )}
                </TableCell>
                <TableCell className="text-muted-foreground hidden text-sm md:table-cell">
                  {row.linked_test_count === 0 ? '—' : `${row.linked_test_count}건`}
                </TableCell>
                <TableCell className="text-right whitespace-nowrap">
                  {row.can_edit && (
                    <>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`${row.code} 수정`}
                        onClick={() => setEditing(row)}
                      >
                        <Pencil className="size-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`${row.code} 삭제`}
                        onClick={() => setRemoving(row)}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <SpecDocumentViewDialog
        document={viewing}
        onClose={() => setViewing(null)}
        onEdit={(row) => {
          setViewing(null)
          setEditing(row)
        }}
        onChanged={() => documents.reload()}
      />

      <SpecDocumentDialog
        open={creating || editing !== null}
        editing={editing}
        onClose={() => {
          setCreating(false)
          setEditing(null)
        }}
        onSaved={() => {
          setCreating(false)
          setEditing(null)
          documents.reload()
        }}
      />

      <ConfirmDialog
        open={removing !== null}
        title="사내 규격서를 삭제합니다"
        description={
          <>
            <strong>{removing?.code}</strong> 을 목록에서 삭제합니다. 데이터는 보존되며 변경
            이력에 남습니다. 거는 신뢰성 시험이 있으면 삭제되지 않습니다.
          </>
        }
        confirmLabel="삭제"
        destructive
        onConfirm={async () => {
          if (!removing) return
          setError(null)
          try {
            await specDocumentApi.remove(removing.id)
            setRemoving(null)
            documents.reload()
          } catch (caught) {
            setRemoving(null)
            setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
          }
        }}
        onClose={() => setRemoving(null)}
      />
    </div>
  )
}

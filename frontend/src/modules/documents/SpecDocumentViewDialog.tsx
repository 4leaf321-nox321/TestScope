/**
 * 사내 규격서 보기 — **원본 파일이 여기 있다.**
 *
 * 줄을 누르면 열린다. 읽는 자리라 입력칸이 없고, 파일만 시스템이 아니라 **그 부서 관리자**
 * 가 올린다(신뢰성 시험과 같은 규칙 — 시스템 관리자를 거치게 하면 문서가 안 올라온다).
 *
 * 개정본은 파일을 더해서 쌓는다. 어느 것이 현행인지는 **「판」 칸**이 말하고, 파일 이름과
 * 설명이 나머지를 말한다 — 파일에 순서를 매기는 칸을 따로 두지 않는다.
 */

import { AlertTriangle, Pencil } from 'lucide-react'

import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { Button } from '@/shared/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
import { useResource } from '@/shared/hooks/useResource'
import { AttachmentStrip } from '@/modules/attachments/AttachmentStrip'
import { attachmentApi } from '@/modules/attachments/api'
import type { Attachment } from '@/modules/attachments/api'
import type { SpecDocument } from '@/modules/documents/api'

export function SpecDocumentViewDialog({
  document,
  onClose,
  onEdit,
  onChanged,
}: {
  document: SpecDocument | null
  onClose: () => void
  onEdit?: (row: SpecDocument) => void
  /** 파일이 붙거나 빠졌다 — 목록의 파일 수가 바뀐다. */
  onChanged?: () => void
}) {
  const id = document?.id ?? null
  const files = useResource(
    () => (id ? attachmentApi.list('spec_document', id) : Promise.resolve([] as Attachment[])),
    [id],
  )

  if (!document) return null
  const rows = files.data ?? []

  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-h-[85vh] w-[80vw] overflow-y-auto sm:max-w-[80vw] lg:max-w-4xl">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            {document.code}
            {document.revision && (
              <span className="text-muted-foreground text-sm font-normal">
                {document.revision}
              </span>
            )}
          </DialogTitle>
          <DialogDescription>
            {document.workspace_name} · {document.title}
          </DialogDescription>
        </DialogHeader>

        {document.note && <p className="text-sm whitespace-pre-line">{document.note}</p>}

        <ErrorNotice error={files.error} />

        <section className="space-y-2">
          <h3 className="border-b pb-1 text-sm font-medium">
            원본 파일{rows.length > 0 && ` · ${rows.length}`}
          </h3>
          {rows.length === 0 && !document.can_edit && (
            // **파일 없는 규격서는 번호일 뿐이다.** 그 사실을 읽는 사람이 알아야 한다.
            <p className="text-amber-600 flex items-center gap-1.5 text-sm">
              <AlertTriangle className="size-3.5" />
              올라온 파일이 없습니다. {document.workspace_name} 관리자가 올립니다.
            </p>
          )}
          <AttachmentStrip
            target="spec_document"
            objectId={document.id}
            rows={rows}
            canEdit={document.can_edit}
            size="lg"
            label="원본 파일 올리기"
            onChanged={() => {
              files.reload()
              onChanged?.()
            }}
          />
        </section>

        {document.linked_test_count > 0 && (
          <p className="text-muted-foreground text-sm">
            이 규격서를 가리키는 신뢰성 시험 <strong>{document.linked_test_count}건</strong>.
            지우려면 먼저 끊어야 합니다.
          </p>
        )}

        <DialogFooter>
          {document.can_edit && onEdit && (
            <Button variant="outline" onClick={() => onEdit(document)}>
              <Pencil className="size-4" />
              수정
            </Button>
          )}
          <Button onClick={onClose}>닫기</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

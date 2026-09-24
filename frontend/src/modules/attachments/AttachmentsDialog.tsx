/**
 * 붙은 그림 보기 — **조회하는 사람을 위한 자리.**
 *
 * 등록·수정 창에만 그림이 있으면 고칠 수 있는 사람만 본다. 그런데 그림의 값은 **플랫폼에
 * 들어와 카드를 읽는 사람**에게 있다 — 절차 그림을 보려고 수정 창을 여는 것은 위험하고
 * (실수로 저장한다), 애초에 권한이 없으면 열지도 못한다.
 *
 * 붙은 자리(어느 칸)로 묶어 보인다. 그림이 어느 칸의 것인지가 문서마다 다르므로, 그것을
 * 안 보이면 절차 그림과 판정 기준 그림이 한 더미로 섞인다.
 */

import { useMemo } from 'react'

import { ErrorNotice } from '@/shared/components/ErrorNotice'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
import { useResource } from '@/shared/hooks/useResource'
import { AttachmentStrip } from '@/modules/attachments/AttachmentStrip'
import { attachmentApi } from '@/modules/attachments/api'
import type { Attachment } from '@/modules/attachments/api'

export function AttachmentsDialog({
  open,
  testId,
  title,
  onClose,
}: {
  open: boolean
  testId: string | null
  title: string
  onClose: () => void
}) {
  const shots = useResource(
    () =>
      testId && open
        ? attachmentApi.list('reliability_test', testId)
        : Promise.resolve([] as Attachment[]),
    [testId, open],
  )

  /** 붙은 칸으로 묶는다. 칸 없는 것이 맨 뒤 — 「그 밖의 그림」. */
  const groups = useMemo(() => {
    const byField = new Map<string, { title: string; rows: Attachment[] }>()
    for (const row of shots.data ?? []) {
      const key = row.definition_id ?? ''
      const bucket = byField.get(key) ?? {
        title: row.definition_label ?? '항목에 연결되지 않은 이미지',
        rows: [],
      }
      bucket.rows.push(row)
      byField.set(key, bucket)
    }
    return [...byField.entries()]
      .sort(([a], [b]) => (a === '' ? 1 : b === '' ? -1 : 0))
      .map(([, value]) => value)
  }, [shots.data])

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{title} — 이미지</DialogTitle>
          <DialogDescription>
            연결된 항목별로 묶었습니다. 첨부와 삭제는 등록·수정 창에서 합니다.
          </DialogDescription>
        </DialogHeader>

        <ErrorNotice error={shots.error} />
        {groups.length === 0 && !shots.loading && (
          <p className="text-muted-foreground text-sm">첨부된 이미지가 없습니다.</p>
        )}
        <div className="space-y-4">
          {groups.map((group) => (
            <section key={group.title} className="space-y-2">
              <h3 className="text-sm font-medium">{group.title}</h3>
              <AttachmentStrip
                target="reliability_test"
                objectId={testId}
                rows={group.rows}
                canEdit={false}
                onChanged={() => shots.reload()}
              />
            </section>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}

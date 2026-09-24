/**
 * ReportArchive 부서 정보 가져오기 — **계획을 보고 누른다.**
 *
 * 조직도는 한 번 잘못 들어가면 지우기 어렵다(부서마다 장비가 매달리기 시작한다). 그래서
 * 붙여넣는 즉시 만들지 않고 무엇이 만들어질지 먼저 보여 준다 — 만들 것·덮을 것·건너뛸 것·
 * 오류를 줄마다. 미리보기와 적용은 서버의 같은 코드가 판정한다.
 *
 * ## 파일이 아니라 붙여넣기
 *
 * 장비 반입과 같은 이유다 — 문서 보안(DRM)이 걸린 환경에서는 파일을 올릴 수 없다. 내보내기
 * 파일을 메모장·엑셀에서 열어 전체를 복사해 붙여넣는다(머리글 줄까지). 파일 선택이 되는
 * 환경을 위해 「파일에서 읽기」 도 두는데, 그것도 **브라우저 안에서 글자로 읽어** 같은 칸에
 * 넣을 뿐 올리지 않는다.
 *
 * 오류가 있어도 **막지 않는다.** TF 아래 행 하나 때문에 부서 마흔 개를 못 들이면 사람은 파일을
 * 손으로 고치기 시작하고, 고친 파일은 원본과 갈린다. 오류 줄은 남겨 두고 되는 것만 들인다.
 */

import { useRef, useState } from 'react'
import { FileUp, Loader2 } from 'lucide-react'

import { ApiError } from '@/shared/api/client'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { Badge } from '@/shared/components/ui/badge'
import { Button } from '@/shared/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
import { Textarea } from '@/shared/components/ui/textarea'
import { workspaceApi } from '@/modules/workspaces/api'
import type { WorkspaceImportResult, WorkspaceImportRow } from '@/modules/workspaces/api'

const ACTION_LABEL: Record<string, string> = {
  create: '생성',
  update: '갱신',
  skip_exists: '이미 있음',
  skip_kind: '대상 아님',
  error: '오류',
}

function RowBadge({ row }: { row: WorkspaceImportRow }) {
  const variant =
    row.action === 'create' || row.action === 'update'
      ? 'default'
      : row.action === 'error'
        ? 'destructive'
        : 'secondary'
  return (
    <Badge variant={variant} className="shrink-0 text-[10px]">
      {ACTION_LABEL[row.action] ?? row.action}
    </Badge>
  )
}

export function ImportWorkspacesDialog({
  open,
  onClose,
  onDone,
}: {
  open: boolean
  onClose: () => void
  /** 들인 뒤 목록을 다시 읽는다. */
  onDone: () => void
}) {
  const picker = useRef<HTMLInputElement>(null)
  const [text, setText] = useState('')
  const [updateExisting, setUpdateExisting] = useState(false)
  const [preview, setPreview] = useState<WorkspaceImportResult | null>(null)
  const [done, setDone] = useState<WorkspaceImportResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | Error | null>(null)

  function reset() {
    setText('')
    setUpdateExisting(false)
    setPreview(null)
    setDone(null)
    setError(null)
  }

  async function run(dryRun: boolean) {
    setBusy(true)
    setError(null)
    try {
      const result = await workspaceApi.importText(text, updateExisting, dryRun)
      if (dryRun) {
        setPreview(result)
      } else {
        setDone(result)
        onDone()
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  // 파일 선택이 되는 환경이면 글자로 읽어 칸에 넣는다 — 올리지 않는다.
  async function readFile(file: File) {
    setText(await file.text())
    setPreview(null)
    setDone(null)
  }

  const shown = done ?? preview
  const willChange = preview ? preview.created + preview.updated : 0

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next && !busy) {
          reset()
          onClose()
        }
      }}
    >
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>ReportArchive 부서 정보 가져오기</DialogTitle>
          <DialogDescription>
            ReportArchive 의 「부서 정보 내보내기」 파일(부서정보.csv)을 메모장이나 엑셀에서
            열어 전체를 복사해 붙여넣습니다 — 머리글 줄까지. 이미 있는 부서는 건드리지
            않습니다. 공개 정책(external_view_default)은 다른 물음이라 옮기지 않습니다.
          </DialogDescription>
        </DialogHeader>

        <input
          ref={picker}
          type="file"
          accept=".csv,text/csv,text/plain"
          className="hidden"
          aria-label="부서 정보 파일"
          onChange={(event) => {
            const next = event.target.files?.[0]
            if (next) void readFile(next)
            // 같은 파일을 다시 골라도 change 가 뜨게 비운다.
            event.target.value = ''
          }}
        />

        {!done && (
          <div className="space-y-3">
            <Textarea
              value={text}
              onChange={(event) => {
                setText(event.target.value)
                setPreview(null)
              }}
              placeholder={'slug,name,parent_slug,…\nrnd,개발본부,,…'}
              rows={8}
              className="font-mono text-xs"
              aria-label="부서 정보 CSV"
              disabled={busy}
            />
            <div className="flex flex-wrap items-center gap-3">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => picker.current?.click()}
                disabled={busy}
              >
                <FileUp className="size-4" />
                파일 불러오기
              </Button>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={updateExisting}
                  onChange={(event) => {
                    setUpdateExisting(event.target.checked)
                    setPreview(null)
                  }}
                  disabled={busy}
                />
                이미 있는 부서도 이름·설명·순서·보관 상태를 저쪽 값으로 갱신
              </label>
            </div>
          </div>
        )}

        <ErrorNotice error={error} />

        {shown && (
          <div className="space-y-2">
            <p className="text-sm">
              {done ? (
                <>
                  <b>
                    생성 {done.created} · 갱신 {done.updated}
                  </b>{' '}
                  · 건너뜀 {done.skipped} · 오류 {done.errors}
                </>
              ) : (
                <>
                  <b>
                    생성 {shown.created} · 갱신 {shown.updated}
                  </b>{' '}
                  예정 · 건너뜀 {shown.skipped} · 오류 {shown.errors}
                </>
              )}
            </p>
            <div className="max-h-72 space-y-1 overflow-y-auto rounded-md border p-2">
              {shown.rows.map((row) => (
                <div key={row.line} className="flex items-start gap-2 text-xs">
                  <RowBadge row={row} />
                  <span className="min-w-0">
                    <span className="font-medium">{row.name}</span>{' '}
                    <span className="text-muted-foreground font-mono">({row.slug})</span>
                    {row.parent_slug && (
                      <span className="text-muted-foreground"> · 상위 {row.parent_slug}</span>
                    )}
                    {row.reason && (
                      <span className="text-muted-foreground block">
                        {row.line}행: {row.reason}
                      </span>
                    )}
                  </span>
                </div>
              ))}
            </div>
            {!done && shown.errors > 0 && (
              <p className="text-xs text-amber-700">
                오류 줄은 건너뛰고 나머지만 들어옵니다. 파일을 손으로 고치기보다 ReportArchive
                쪽을 고쳐 다시 내보내는 편이 안전합니다 — 두 시스템의 주소가 갈리지 않게.
              </p>
            )}
          </div>
        )}

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              reset()
              onClose()
            }}
            disabled={busy}
          >
            {done ? '닫기' : '취소'}
          </Button>
          {!done && !preview && (
            <Button
              type="button"
              onClick={() => void run(true)}
              disabled={busy || !text.trim()}
            >
              {busy && <Loader2 className="size-4 animate-spin" />}
              미리보기
            </Button>
          )}
          {!done && preview && (
            <Button
              type="button"
              onClick={() => void run(false)}
              disabled={busy || willChange === 0}
            >
              {busy && <Loader2 className="size-4 animate-spin" />}
              {willChange > 0 ? `${willChange}개 가져오기` : '가져올 것이 없습니다'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

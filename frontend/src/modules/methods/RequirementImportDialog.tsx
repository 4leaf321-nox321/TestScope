/**
 * 요구 조건 표 반입 — **규격서를 보고 적은 표를 붙여넣는다.**
 *
 * 규격 464 중 3 에만 요구 조건이 있다. 상세 화면에서 한 줄씩 넣게 되어 있는데, 규격서를
 * 펴 놓고 한 화면씩 오가며 넣는 일은 아무도 안 한다. 규격서를 보는 사람은 엑셀에 적고,
 * 그 표를 여기 붙여넣는다.
 *
 * 장비 대장 반입과 같은 두 걸음이다: 먼저 미리보기(아무것도 저장 안 함), 줄마다 판정을
 * 보고, 사람이 확인하면 같은 글자를 다시 보내 넣는다. 덮어쓰는 줄은 미리 그렇다고 말한다 —
 * 조용히 덮으면 누가 언제 적은 값이 사라졌는지 아무도 모른다.
 */

import { useState } from 'react'
import { Download, Loader2 } from 'lucide-react'

import { ApiError } from '@/shared/api/client'
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
import { Textarea } from '@/shared/components/ui/textarea'
import { methodApi } from '@/modules/methods/api'
import type { RequirementImportResult } from '@/modules/methods/api'

export function RequirementImportDialog({
  open,
  onClose,
  onImported,
}: {
  open: boolean
  onClose: () => void
  onImported: () => void
}) {
  const [text, setText] = useState('')
  const [result, setResult] = useState<RequirementImportResult | null>(null)
  const [busy, setBusy] = useState<'preview' | 'put' | null>(null)
  const [error, setError] = useState<ApiError | Error | null>(null)

  async function run(dryRun: boolean) {
    setBusy(dryRun ? 'preview' : 'put')
    setError(null)
    try {
      const got = await methodApi.importRequirements(text, dryRun)
      setResult(got)
      if (!dryRun) onImported()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(null)
    }
  }

  function close() {
    if (busy) return
    setText('')
    setResult(null)
    setError(null)
    onClose()
  }

  const put = result !== null && !result.dry_run

  return (
    <Dialog open={open} onOpenChange={(next) => !next && close()}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>요구 조건 일괄 등록</DialogTitle>
          <DialogDescription>
            규격서를 보고 엑셀에 적은 표를 <strong>머리글 줄까지 함께</strong> 복사해
            붙여넣으십시오. 열: 규격 · 판 · 조건 · 최소 · 최대 · 값 · 필수 · 비고. 값은 조건의
            단위(kN · °C)로 적습니다 — 단위를 같이 적어도 됩니다.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void methodApi.requirementTemplate()}
            >
              <Download className="size-4" />
              양식 다운로드
            </Button>
            <span className="text-muted-foreground text-xs">
              보기 줄은 실제 규격(ISO 6892-1)의 값입니다.
            </span>
          </div>
          <Textarea
            value={text}
            onChange={(event) => {
              setText(event.target.value)
              setResult(null)
            }}
            rows={8}
            placeholder={
              '규격\t조건\t최소\t최대\t필수\t비고\nISO 6892-1\t하중 용량\t20\t\t예\t'
            }
            className="font-mono text-xs"
            aria-label="요구 조건 표"
            disabled={busy !== null || put}
          />

          <ErrorNotice error={error} />

          {result && (
            <div className="space-y-2">
              <p className="text-sm">
                {put ? (
                  <>
                    <strong>넣었습니다.</strong> 새로 {result.summary.created} · 덮어씀{' '}
                    {result.summary.replaced}
                    {result.summary.problems > 0 &&
                      ` · 못 넣은 줄 ${result.summary.problems} (아래에 남아 있습니다)`}
                  </>
                ) : (
                  <>
                    {result.summary.total}줄 중 넣을 수 있는 줄{' '}
                    <strong>{result.summary.ready}</strong>
                    {result.summary.problems > 0 && (
                      <>
                        , 문제 있는 줄{' '}
                        <strong className="text-destructive">{result.summary.problems}</strong>
                      </>
                    )}
                    . 아직 아무것도 저장하지 않았습니다.
                  </>
                )}
              </p>
              <div className="max-h-80 overflow-auto rounded-md border">
                <table className="w-full text-xs">
                  <thead className="bg-muted/50 sticky top-0">
                    <tr className="text-left">
                      <th className="px-2 py-1">줄</th>
                      <th className="px-2 py-1">규격</th>
                      <th className="px-2 py-1">조건</th>
                      <th className="px-2 py-1">최소</th>
                      <th className="px-2 py-1">최대</th>
                      <th className="px-2 py-1">값</th>
                      <th className="px-2 py-1">필수</th>
                      <th className="px-2 py-1">판정</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((row) => (
                      <tr
                        key={row.line}
                        className={
                          row.problems.length > 0
                            ? 'bg-destructive/5'
                            : row.imported
                              ? 'text-muted-foreground'
                              : undefined
                        }
                      >
                        <td className="px-2 py-1 tabular-nums">{row.line}</td>
                        <td className="px-2 py-1">{row.code ?? row.cells.code}</td>
                        <td className="px-2 py-1">
                          {row.condition_label ?? row.cells.condition}
                        </td>
                        <td className="px-2 py-1">{row.cells.min}</td>
                        <td className="px-2 py-1">{row.cells.max}</td>
                        <td className="px-2 py-1">{row.cells.text}</td>
                        <td className="px-2 py-1">{row.cells.mandatory}</td>
                        <td className="px-2 py-1">
                          {row.problems.length > 0 ? (
                            <ul className="text-destructive list-disc pl-4">
                              {row.problems.map((one) => (
                                <li key={one}>{one}</li>
                              ))}
                            </ul>
                          ) : row.imported ? (
                            '넣음'
                          ) : row.replaces ? (
                            <span className="text-amber-700">이미 있는 조건을 덮어씁니다</span>
                          ) : (
                            '넣을 수 있음'
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={close} disabled={busy !== null}>
            {put ? '닫기' : '취소'}
          </Button>
          {!put && (
            <>
              <Button
                type="button"
                variant={result ? 'outline' : 'default'}
                onClick={() => run(true)}
                disabled={busy !== null || !text.trim()}
              >
                {busy === 'preview' && <Loader2 className="size-4 animate-spin" />}
                미리보기
              </Button>
              {/* 미리보기를 본 뒤에만 넣는다 — 판정을 안 보고 넣으면 덮어쓰기를 모른 채
                  지나간다. */}
              <Button
                type="button"
                onClick={() => run(false)}
                disabled={busy !== null || !result || result.summary.ready === 0}
              >
                {busy === 'put' && <Loader2 className="size-4 animate-spin" />}
                {result ? `${result.summary.ready}줄 넣기` : '넣기'}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

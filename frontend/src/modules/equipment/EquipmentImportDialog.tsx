/**
 * 보유 장비 **일괄 반입** — 부서 대장을 그대로 올린다.
 *
 * 카탈로그는 198계열·714기종까지 찼는데 대장은 4대였다. 장비를 넣는 길이 한 대씩
 * 뿐이라 수백 대를 가진 부서는 시작조차 못 했고, 대장이 비어 있으면 이 시스템은
 * **어떤 질문에도 못 답한다.**
 *
 * ## 넣기 전에 보여 준다
 *
 * 파일을 고르면 먼저 미리보기를 부른다(`dry_run`). 300줄 중 틀린 12줄을 **넣기 전에**
 * 알아야 하고, 몇 번째 줄인지 말해 줘야 사람이 엑셀에서 그 줄을 찾는다.
 *
 * ## 전부 되거나 전부 안 되거나
 *
 * 문제가 하나라도 있으면 넣는 단추를 안 준다. 되는 것만 넣으면 사람은 파일을 고쳐
 * 다시 올리다가 이미 들어간 줄에서 「이미 등록된 자산번호」 를 만나고, 그때 무엇을
 * 지워야 할지 모른다.
 *
 * ## 기종에 안 이어진 줄을 세어 말한다
 *
 * 넣을 수는 있지만 **시험 항목이 0 건**이 되고, 0 건이면 그 장비는 검색에 절대 안
 * 걸린다 — 대장에만 있고 아무도 못 찾는다. 막지는 않는다(자작 장비가 실제로 있다).
 * 다만 몇 대가 그런지는 넣기 전에 보여 준다.
 */

import { useRef, useState } from 'react'
import { Download, Upload } from 'lucide-react'

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
import { equipmentApi } from '@/modules/equipment/api'
import type { EquipmentImportResult } from '@/modules/equipment/api'

/** 문제 줄을 몇 개까지 펼쳐 보이나. 나머지는 수로 접는다 — 200줄이 틀렸을 때
 *  전부 그리면 사람이 첫 줄도 못 읽는다. */
const SHOWN = 30

export function EquipmentImportDialog({
  open,
  onClose,
  onDone,
}: {
  open: boolean
  onClose: () => void
  onDone: () => void
}) {
  const input = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<EquipmentImportResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [done, setDone] = useState<number | null>(null)

  function reset() {
    setFile(null)
    setPreview(null)
    setError(null)
    setDone(null)
    if (input.current) input.current.value = ''
  }

  async function look(picked: File) {
    setFile(picked)
    setPreview(null)
    setError(null)
    setDone(null)
    setBusy(true)
    try {
      setPreview(await equipmentApi.importFile(picked, true))
    } catch (thrown) {
      setError(thrown as ApiError)
    } finally {
      setBusy(false)
    }
  }

  async function commit() {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      // **같은 파일을 다시 보낸다.** 서버가 미리보기 결과를 들고 있지 않아서,
      // 그 사이 남이 같은 자산번호를 넣었어도 여기서 다시 걸린다.
      const result = await equipmentApi.importFile(file, false)
      if (result.created > 0) {
        setDone(result.created)
        setPreview(null)
        onDone()
      } else {
        setPreview(result)
      }
    } catch (thrown) {
      setError(thrown as ApiError)
    } finally {
      setBusy(false)
    }
  }

  const bad = (preview?.rows ?? []).filter((one) => one.problems.length > 0)
  const unlinked = (preview?.rows ?? []).filter(
    (one) => one.problems.length === 0 && !one.model_linked,
  ).length

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          reset()
          onClose()
        }
      }}
    >
      <DialogContent className="max-h-[85vh] max-w-3xl">
        <DialogHeader>
          <DialogTitle>장비 일괄 반입</DialogTitle>
          <DialogDescription>
            부서 대장(CSV)을 통째로 올립니다. 넣기 전에 줄마다 확인합니다.
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => void equipmentApi.importTemplate()}
            >
              <Download className="size-4" />
              서식 내려받기
            </Button>
            <input
              ref={input}
              type="file"
              accept=".csv,text/csv"
              className="text-sm"
              onChange={(event) => {
                const picked = event.target.files?.[0]
                if (picked) void look(picked)
              }}
            />
          </div>

          <p className="text-muted-foreground text-xs">
            엑셀에서 「CSV UTF-8」 로 저장하세요. 부서·거점·장비유형·기종은{' '}
            <strong>이름으로</strong> 적습니다. 기준정보에 없는 거점·분류는 여기서 만들어지지
            않습니다 — 먼저 기준정보에 등록하세요.
          </p>

          <ErrorNotice error={error} />

          {done !== null && (
            <div className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm">
              <strong>{done}대</strong>를 등록했습니다.
            </div>
          )}

          {busy && <p className="text-muted-foreground text-sm">읽는 중…</p>}

          {preview && (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-4 text-sm">
                <span>
                  모두 <strong>{preview.total}</strong>줄
                </span>
                <span className="text-emerald-700">
                  넣을 수 있음 <strong>{preview.ready}</strong>
                </span>
                {preview.problems > 0 && (
                  <span className="text-amber-700">
                    문제 <strong>{preview.problems}</strong>
                  </span>
                )}
              </div>

              {preview.problems > 0 ? (
                <>
                  {/* **전부 되거나 전부 안 되거나.** 그 사실을 단추가 없는 이유로
                      먼저 말해 준다 — 안 말하면 사람은 단추를 찾는다. */}
                  <p className="text-sm">
                    문제가 있는 줄이 있어 <strong>아무것도 넣지 않았습니다.</strong> 파일에서
                    아래 줄을 고쳐 다시 올리세요. 줄 번호는 엑셀에서 보이는 번호와 같습니다.
                  </p>
                  <ul className="space-y-2">
                    {bad.slice(0, SHOWN).map((row) => (
                      <li key={row.line} className="rounded-md border p-2 text-sm">
                        <span className="font-mono text-xs">{row.line}번째 줄</span>
                        {row.asset_no && (
                          <span className="ml-2 font-medium">{row.asset_no}</span>
                        )}
                        <ul className="text-amber-700 mt-1 list-disc pl-5 text-xs">
                          {row.problems.map((one) => (
                            <li key={one}>{one}</li>
                          ))}
                        </ul>
                      </li>
                    ))}
                  </ul>
                  {bad.length > SHOWN && (
                    <p className="text-muted-foreground text-xs">
                      외 {bad.length - SHOWN}줄이 더 있습니다.
                    </p>
                  )}
                </>
              ) : (
                <div className="bg-muted/50 space-y-1 rounded-md border p-3 text-sm">
                  <p>
                    <strong>{preview.ready}대</strong>를 넣을 수 있습니다.
                  </p>
                  {unlinked > 0 && (
                    // 막지 않는다 — 자작 장비나 카탈로그에 없는 것이 실제로 있다.
                    // 다만 그 장비들이 **검색에 안 걸린다**는 사실은 넣기 전에 안다.
                    <p className="text-amber-700">
                      그중 <strong>{unlinked}대</strong>는 기종이 안 이어졌습니다. 시험 항목이
                      0 건이 되고, <strong>0 건이면 검색에 걸리지 않습니다</strong> — 나중에
                      장비마다 시험 항목을 채워야 합니다.
                    </p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            닫기
          </Button>
          <Button
            onClick={() => void commit()}
            disabled={busy || !preview || preview.problems > 0 || preview.ready === 0}
          >
            <Upload className="size-4" />
            {preview && preview.problems === 0 ? `${preview.ready}대 넣기` : '넣기'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

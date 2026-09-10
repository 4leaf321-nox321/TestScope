/**
 * 보유 장비 **일괄 반입** — 엑셀에서 복사해 붙여넣고, 표에서 고쳐 넣는다.
 *
 * 카탈로그는 198계열·714기종까지 찼는데 대장은 4대였다. 장비를 넣는 길이 한 대씩
 * 뿐이라 수백 대를 가진 부서는 시작조차 못 했고, 대장이 비어 있으면 이 시스템은
 * **어떤 질문에도 못 답한다.**
 *
 * ## 왜 파일이 아니라 붙여넣기인가
 *
 * 문서 보안(DRM)이 걸린 환경에서는 **파일을 올릴 수 없다.** 서식을 내려받는 것은
 * 되는데 그 파일을 다시 고르는 것이 막힌다 — 실제로 그랬다. 붙여넣기는 DRM 이 막지
 * 못한다. 서식 내려받기는 남긴다: 어느 열에 무엇을 적는지는 그것으로 안다.
 *
 * ## 글상자가 아니라 표인 이유
 *
 * 글상자 하나로 받으면 두 가지를 못 한다. 어느 **칸**이 틀렸는지 못 보여 주고(줄
 * 번호만 말한다), 그 자리에서 고칠 수 없다 — 12줄을 고치려고 엑셀로 돌아가 범위를
 * 다시 복사해야 한다. 그리고 「거점이 기준정보에 없다」 같은 것은 애초에 엑셀에서
 * 고칠 수 있는 문제가 아니다.
 *
 * 고친 표는 **다시 서버로 보내 확인한다.** 화면이 스스로 판정하면 판정이 두 벌이
 * 되고, 그때 화면은 「이제 됩니다」 라고 해 놓고 저장에서 막힌다.
 *
 * ## 전부 되거나 전부 안 되거나
 *
 * 문제가 하나라도 있으면 넣는 단추를 안 준다. 되는 것만 넣으면 사람은 고쳐 다시
 * 붙여넣다가 이미 들어간 줄에서 「이미 등록된 자산번호」 를 만나고, 그때 무엇을
 * 지워야 할지 모른다.
 *
 * ## 진행률(N/M) 대신 「무엇을 하는 중인지」 를 보인다
 *
 * 「지금 1500대째」 를 보여 주려면 서버가 넣는 중에 중간 보고를 해야 하는데, 그러려면
 * 쪽을 나눠 커밋해야 한다 — 그리고 그것이 바로 **반쯤 들어간 대장**이다. 한 트랜잭션을
 * 지키는 한 그 숫자는 확정된 것이 아니고, 전부 되돌아가는 순간 **거짓말이 된다.**
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { Download, Loader2, Upload } from 'lucide-react'

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
import { useResource } from '@/shared/hooks/useResource'
import { equipmentApi } from '@/modules/equipment/api'
import type {
  EquipmentImportResult,
  EquipmentImportRow,
  ImportColumn,
} from '@/modules/equipment/api'
import { GRID_MAX, ImportGrid } from '@/modules/equipment/ImportGrid'

/** 한 대를 넣는 데 드는 시간(ms). **실측이다** — 500대에 2.5초였다.
 *
 *  기종을 이은 줄은 계열의 시험 항목과 조건까지 복사하므로 더 든다. 넉넉히 잡는다:
 *  덜 걸리는 것은 반갑지만, 더 걸리면 사람은 멈춘 줄 안다. */
const MS_PER_UNIT = 6

/** 몇 초쯤 걸리는지. **짧으면 아예 말하지 않는다** — 「1초쯤 걸립니다」 는 아무
 *  도움이 안 되면서 읽을 것만 늘린다. */
function spent(count: number): string {
  const seconds = Math.round((count * MS_PER_UNIT) / 1000)
  return seconds >= 3 ? ` (${seconds}초쯤 걸립니다)` : ''
}

/** 표를 서버가 읽을 수 있는 글자로. **직렬화만 화면이 하고 파싱은 서버가 한다** —
 *  판정이 두 벌이 되면 화면은 「이제 됩니다」 라고 해 놓고 저장에서 막힌다. */
function serialize(columns: ImportColumn[], rows: EquipmentImportRow[]): string {
  const head = columns.map((one) => one.label).join('\t')
  const body = rows.map((row) => columns.map((one) => row.cells[one.key] ?? '').join('\t'))
  return [head, ...body].join('\n')
}

export function EquipmentImportDialog({
  open,
  onClose,
  onDone,
}: {
  open: boolean
  onClose: () => void
  onDone: () => void
}) {
  // **열은 서버가 준다.** 화면이 자기 목록을 따로 들면 열을 하나 더한 날 한쪽만
  // 고쳐지고, 그때 사람이 채운 칸이 조용히 버려진다.
  //
  // **창을 열 때만 부른다.** 이 창은 보유 장비 화면에 늘 붙어 있어서, 조건을 안 달면
  // 목록을 여는 사람마다 안 쓰는 조회를 하나씩 더 하게 된다.
  const columns = useResource(
    () => (open ? equipmentApi.importColumns() : Promise.resolve(null)),
    [open],
  )

  const [rows, setRows] = useState<EquipmentImportRow[]>([])
  const [summary, setSummary] = useState<EquipmentImportResult | null>(null)
  const [phase, setPhase] = useState<'idle' | 'looking' | 'putting'>('idle')
  const [error, setError] = useState<ApiError | null>(null)
  const [done, setDone] = useState<number | null>(null)
  const [onlyBad, setOnlyBad] = useState(false)

  /** 표를 서버가 읽을 수 있는 글자로. **직렬화만 화면이 하고 파싱은 서버가 한다** —
   *  판정이 두 벌이 되면 화면은 「이제 됩니다」 라고 해 놓고 저장에서 막힌다. */
  const asText = useMemo(() => serialize(columns.data ?? [], rows), [columns.data, rows])

  /** 방금 서버에 보낸 글자. 같은 것을 두 번 보내지 않는다 — 응답으로 rows 가
   *  갱신되면 `asText` 가 다시 계산되고, 그것이 또 조회를 부르면 끝이 없다. */
  const sent = useRef('')

  // 표가 바뀌면 다시 확인한다. 글자마다 부르지 않는다 — 한 칸을 치는 동안 조회가
  // 줄줄이 나간다.
  useEffect(() => {
    if (rows.length === 0 || !columns.data) return
    if (asText === sent.current) return
    setPhase('looking')
    const timer = setTimeout(() => {
      sent.current = asText
      equipmentApi
        .importPaste(asText, true)
        .then((result) => {
          setRows(result.rows)
          setSummary(result)
          setError(null)
        })
        .catch((thrown: ApiError) => setError(thrown))
        .finally(() => setPhase('idle'))
    }, 500)
    return () => clearTimeout(timer)
  }, [asText, rows.length, columns.data])

  /** 엑셀에서 복사한 것을 통째로 받는다. */
  async function pasted(text: string) {
    if (!text.trim()) return
    setError(null)
    setDone(null)
    setPhase('looking')
    try {
      const result = await equipmentApi.importPaste(text, true)
      // **방금 읽은 것을 다시 보내지 않는다.** 붙여넣은 원본과 우리가 표에서 만드는
      // 글자는 모양이 다르므로(구분자·열 순서), 비교할 것은 **표에서 만든 쪽**이다.
      sent.current = serialize(columns.data ?? [], result.rows)
      setRows(result.rows)
      setSummary(result)
    } catch (thrown) {
      setError(thrown as ApiError)
    } finally {
      setPhase('idle')
    }
  }

  function edit(line: number, field: string, value: string) {
    setRows((before) =>
      before.map((row) =>
        row.line === line ? { ...row, cells: { ...row.cells, [field]: value } } : row,
      ),
    )
  }

  async function commit() {
    setPhase('putting')
    setError(null)
    try {
      // **같은 글자를 다시 보낸다.** 서버가 미리보기 결과를 들고 있지 않아서,
      // 그 사이 남이 같은 자산번호를 넣었어도 여기서 다시 걸린다.
      const result = await equipmentApi.importPaste(asText, false)
      if (result.created > 0) {
        setDone(result.created)
        setRows([])
        setSummary(null)
        onDone()
      } else {
        setRows(result.rows)
        setSummary(result)
      }
    } catch (thrown) {
      setError(thrown as ApiError)
    } finally {
      setPhase('idle')
    }
  }

  function reset() {
    setRows([])
    setSummary(null)
    setError(null)
    setDone(null)
    setOnlyBad(false)
    sent.current = ''
  }

  const bad = rows.filter((one) => one.problems.length > 0)
  const unlinked = rows.filter((one) => one.problems.length === 0 && !one.model_linked).length
  // 다 그리면 DOM 이 먼저 죽는다(2000줄에 열 18이면 칸 36,000개). 넘으면 문제 줄만.
  const tooMany = rows.length > GRID_MAX
  const shown = onlyBad || tooMany ? bad : rows

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
      <DialogContent className="max-h-[88vh] max-w-6xl">
        <DialogHeader>
          <DialogTitle>장비 일괄 반입</DialogTitle>
          <DialogDescription>
            엑셀에서 <strong>머리글 줄까지 함께</strong> 복사해 붙여넣으세요. 틀린 칸은 표에서
            바로 고칠 수 있습니다.
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
            {rows.length > 0 && (
              <Button variant="outline" size="sm" onClick={reset} disabled={phase !== 'idle'}>
                다시 붙여넣기
              </Button>
            )}
            {bad.length > 0 && !tooMany && (
              <Button variant="outline" size="sm" onClick={() => setOnlyBad(!onlyBad)}>
                {onlyBad ? '전체 보기' : `문제 ${bad.length}줄만 보기`}
              </Button>
            )}
          </div>

          <ErrorNotice error={error} />

          {done !== null && (
            <div className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm">
              <strong>{done}대</strong>를 등록했습니다.
            </div>
          )}

          {rows.length === 0 ? (
            // **붙여넣는 자리는 글상자여야 한다.** 브라우저가 붙여넣기를 확실히
            // 주는 곳이 여기다 — 빈 div 에 걸면 포커스가 없어 이벤트가 안 온다.
            <textarea
              autoFocus
              rows={6}
              spellCheck={false}
              value=""
              onChange={() => {}}
              onPaste={(event) => {
                event.preventDefault()
                void pasted(event.clipboardData.getData('text'))
              }}
              placeholder={
                '여기에 붙여넣으세요 (Ctrl+V)\n\n' +
                '엑셀에서 머리글 줄까지 함께 범위를 복사하면 됩니다.\n' +
                '자산번호\t장비명\t보유부서\t거점\t설치위치\t…'
              }
              className="border-input bg-background w-full rounded-md border border-dashed p-3 font-mono text-xs"
            />
          ) : (
            <>
              {columns.data && (
                <ImportGrid
                  columns={columns.data}
                  rows={shown}
                  onChange={edit}
                  disabled={phase === 'putting'}
                />
              )}
              {tooMany && (
                <p className="text-muted-foreground text-xs">
                  {rows.length}줄이라 <strong>문제 있는 줄만</strong> 그렸습니다 — 표가 너무
                  크면 타이핑 한 번에 멈춥니다. 나머지 {rows.length - bad.length}줄은 그대로
                  들어갑니다.
                </p>
              )}
              {shown.length === 0 && (
                <p className="text-muted-foreground text-sm">고칠 줄이 없습니다.</p>
              )}
            </>
          )}

          <p className="text-muted-foreground text-xs">
            부서·거점·장비유형·기종은 <strong>이름으로</strong> 적습니다. 기준정보에 없는
            거점·분류는 여기서 만들어지지 않습니다 — 먼저 기준정보에 등록하세요.
          </p>

          {phase === 'looking' && <p className="text-muted-foreground text-sm">읽는 중…</p>}

          {phase === 'putting' && (
            // **몇 대를 넣는 중인지 말한다.** 「지금 1500대째」 는 못 말한다 —
            // 한 트랜잭션이라 그 수는 아직 확정된 것이 아니고, 전부 되돌아가는
            // 순간 거짓말이 된다.
            <div className="flex items-center gap-2 rounded-md border p-3 text-sm">
              <Loader2 className="size-4 animate-spin" />
              <span>
                <strong>{summary?.ready ?? 0}대</strong>를 넣는 중입니다
                {spent(summary?.ready ?? 0)}. <strong>창을 닫지 마세요</strong> — 도중에 끊기면
                아무것도 안 들어갑니다.
              </span>
            </div>
          )}

          {summary && rows.length > 0 && (
            <div className="flex flex-wrap gap-4 text-sm">
              <span>
                모두 <strong>{summary.total}</strong>줄
              </span>
              <span className="text-emerald-700">
                넣을 수 있음 <strong>{summary.ready}</strong>
              </span>
              {summary.problems > 0 && (
                <span className="text-amber-700">
                  문제 <strong>{summary.problems}</strong>
                </span>
              )}
            </div>
          )}

          {summary && rows.length > 0 && summary.problems === 0 && (
            <div className="bg-muted/50 space-y-1 rounded-md border p-3 text-sm">
              <p>
                <strong>{summary.ready}대</strong>를 넣을 수 있습니다
                {spent(summary.ready)}.
              </p>
              {unlinked > 0 && (
                // 막지 않는다 — 자작 장비나 카탈로그에 없는 것이 실제로 있다.
                // 다만 그 장비들이 **검색에 안 걸린다**는 사실은 넣기 전에 안다.
                <p className="text-amber-700">
                  그중 <strong>{unlinked}대</strong>는 기종이 안 이어졌습니다. 시험 항목이 0
                  건이 되고, <strong>0 건이면 검색에 걸리지 않습니다</strong> — 나중에 장비마다
                  시험 항목을 채워야 합니다.
                </p>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          {/* **넣는 중에는 못 닫는다.** 닫아도 요청은 계속 가는데 화면은 결과를
              못 보고, 그러면 사람은 들어갔는지 아닌지를 모르는 채 남는다. */}
          <Button variant="outline" onClick={onClose} disabled={phase === 'putting'}>
            닫기
          </Button>
          <Button
            onClick={() => void commit()}
            disabled={
              phase !== 'idle' || !summary || summary.problems > 0 || summary.ready === 0
            }
          >
            {phase === 'putting' ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Upload className="size-4" />
            )}
            {phase === 'putting'
              ? '넣는 중…'
              : summary && summary.problems === 0 && summary.ready > 0
                ? `${summary.ready}대 넣기`
                : '넣기'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/**
 * 보유 장비 **일괄 반입** — 표에 붙여넣고, 표에서 고쳐 넣는다.
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
 * ## 처음부터 표다
 *
 * 빈 글상자에 붙이고 그 다음에 표가 나타나면 두 화면을 거치는 셈이라 「어디에 붙이나」
 * 를 한 번 더 묻게 된다. 엑셀에서 오는 사람에게 표는 설명이 필요 없는 모양이고,
 * 몇 대만 손으로 치고 싶은 사람도 그냥 칠 수 있다.
 *
 * ## 줄의 주인은 화면이다
 *
 * 서버는 **빈 줄을 건너뛴다.** 그래서 서버가 매긴 줄 번호를 그대로 쓰면, 가운데
 * 한 줄을 비우는 순간 아래 줄들이 밀리고 사람이 치던 칸이 다른 줄로 옮겨간다.
 * 화면이 줄에 id 를 매기고, 서버에는 **내용이 있는 줄만** 순서대로 보내 그 순서로
 * 판정을 받아 붙인다.
 *
 * 다만 붙여넣기 직후만은 서버가 읽은 값을 그대로 받는다 — 그게 파싱 결과이고,
 * 화면이 다시 파싱하면 규칙이 두 벌이 되어 반드시 어긋난다.
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
import { Download, Loader2, Plus, Upload } from 'lucide-react'

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
import type { EquipmentImportResult, ImportColumn } from '@/modules/equipment/api'
import { GRID_MAX, ImportGrid, filled } from '@/modules/equipment/ImportGrid'
import type { GridRow } from '@/modules/equipment/ImportGrid'

/** 빈 표를 몇 줄로 시작하나. 붙여넣기가 주된 길이라 많을 필요는 없고, 몇 대를
 *  손으로 치려는 사람에게는 이만큼이면 시작이 된다. */
const BLANK_ROWS = 5

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

let nextId = 1

function blank(count: number): GridRow[] {
  return Array.from({ length: count }, () => ({
    id: nextId++,
    cells: {},
    problems: [],
    modelLinked: false,
  }))
}

/** 표를 서버가 읽을 수 있는 글자로. **직렬화만 화면이 하고 파싱은 서버가 한다** —
 *  판정이 두 벌이 되면 화면은 「이제 됩니다」 라고 해 놓고 저장에서 막힌다. */
function serialize(columns: ImportColumn[], rows: GridRow[]): string {
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

  const [rows, setRows] = useState<GridRow[]>(() => blank(BLANK_ROWS))
  const [summary, setSummary] = useState<EquipmentImportResult | null>(null)
  const [phase, setPhase] = useState<'idle' | 'looking' | 'putting'>('idle')
  const [error, setError] = useState<ApiError | null>(null)
  const [done, setDone] = useState<number | null>(null)
  const [onlyBad, setOnlyBad] = useState(false)

  /** 서버에 보낼 줄 — **내용이 있는 것만.** 서버가 빈 줄을 건너뛰므로, 이렇게 하면
   *  응답의 순서와 여기 순서가 1:1 로 맞는다. */
  const sending = useMemo(() => rows.filter(filled), [rows])
  const asText = useMemo(() => serialize(columns.data ?? [], sending), [columns.data, sending])

  /** 방금 서버에 보낸 글자. 같은 것을 두 번 보내지 않는다. */
  const sent = useRef('')

  /** 응답의 판정을 표에 붙인다. **칸 값은 건드리지 않는다** — 사람이 치고 있는
   *  중일 수 있고, 그때 서버가 읽은 값으로 덮으면 커서가 튄다. */
  function apply(result: EquipmentImportResult) {
    setSummary(result)
    setRows((before) => {
      let index = 0
      return before.map((row) => {
        if (!filled(row)) return { ...row, problems: [], modelLinked: false }
        const said = result.rows[index++]
        return {
          ...row,
          problems: said?.problems ?? [],
          modelLinked: said?.model_linked ?? false,
        }
      })
    })
  }

  // 표가 바뀌면 다시 확인한다. 글자마다 부르지 않는다 — 한 칸을 치는 동안 조회가
  // 줄줄이 나간다.
  useEffect(() => {
    if (!columns.data || sending.length === 0) {
      setSummary(null)
      return
    }
    if (asText === sent.current) return
    setPhase('looking')
    const timer = setTimeout(() => {
      sent.current = asText
      equipmentApi
        .importPaste(asText, true)
        .then((result) => {
          apply(result)
          setError(null)
        })
        .catch((thrown: ApiError) => setError(thrown))
        .finally(() => setPhase('idle'))
    }, 500)
    return () => clearTimeout(timer)
  }, [asText, sending.length, columns.data])

  /** 엑셀에서 복사한 **범위**를 받는다. 표를 통째로 갈아 끼운다. */
  async function pasteRange(text: string) {
    if (!text.trim()) return
    setError(null)
    setDone(null)
    setPhase('looking')
    try {
      const result = await equipmentApi.importPaste(text, true)
      // **여기서만 서버가 읽은 값을 그대로 받는다** — 그게 파싱 결과다. 화면이
      // 다시 파싱하면 구분자·빈 줄·머리글 별칭이 두 벌이 되어 반드시 어긋난다.
      const made: GridRow[] = result.rows.map((one) => ({
        id: nextId++,
        cells: { ...one.cells },
        problems: one.problems,
        modelLinked: one.model_linked,
      }))
      sent.current = serialize(columns.data ?? [], made)
      setRows(made.length > 0 ? made : blank(BLANK_ROWS))
      setSummary(result)
    } catch (thrown) {
      setError(thrown as ApiError)
    } finally {
      setPhase('idle')
    }
  }

  function edit(id: number, field: string, value: string) {
    setRows((before) =>
      before.map((row) =>
        row.id === id ? { ...row, cells: { ...row.cells, [field]: value } } : row,
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
        setRows(blank(BLANK_ROWS))
        setSummary(null)
        sent.current = ''
        onDone()
      } else {
        apply(result)
      }
    } catch (thrown) {
      setError(thrown as ApiError)
    } finally {
      setPhase('idle')
    }
  }

  function reset() {
    setRows(blank(BLANK_ROWS))
    setSummary(null)
    setError(null)
    setDone(null)
    setOnlyBad(false)
    sent.current = ''
  }

  const bad = rows.filter((one) => one.problems.length > 0)
  const unlinked = sending.filter(
    (one) => one.problems.length === 0 && !one.modelLinked,
  ).length
  // 다 그리면 DOM 이 먼저 죽는다(2000줄에 열 18이면 칸 36,000개). 넘으면 문제 줄만.
  const tooMany = rows.length > GRID_MAX
  const shown = onlyBad || tooMany ? bad : rows
  const ready = summary && summary.problems === 0 ? summary.ready : 0

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
      {/* **표가 들어가는 창이라 넓어야 한다.** 기본이 `sm:max-w-lg` 라, 브레이크포인트
          없는 `max-w-*` 를 주면 화면이 넓어지는 순간 기본값이 이긴다 — 실제로 그랬다. */}
      <DialogContent className="max-h-[90vh] sm:max-w-[94vw]">
        <DialogHeader>
          <DialogTitle>장비 일괄 반입</DialogTitle>
          <DialogDescription>
            엑셀에서 <strong>머리글 줄까지 함께</strong> 복사해 아래 표에 붙여넣으세요
            (Ctrl+V). 틀린 칸은 표에서 바로 고칠 수 있습니다.
          </DialogDescription>
        </DialogHeader>

        <div className="flex min-h-0 flex-1 flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => void equipmentApi.importTemplate()}
            >
              <Download className="size-4" />
              서식 내려받기
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setRows((before) => [...before, ...blank(BLANK_ROWS)])}
              disabled={phase === 'putting'}
            >
              <Plus className="size-4" />줄 추가
            </Button>
            <Button variant="outline" size="sm" onClick={reset} disabled={phase !== 'idle'}>
              비우기
            </Button>
            {bad.length > 0 && !tooMany && (
              <Button variant="outline" size="sm" onClick={() => setOnlyBad(!onlyBad)}>
                {onlyBad ? '전체 보기' : `문제 ${bad.length}줄만 보기`}
              </Button>
            )}
            <span className="text-muted-foreground text-xs">
              부서·거점·장비유형·기종은 <strong>이름으로</strong> 적습니다. 기준정보에 없는
              거점·분류는 여기서 만들어지지 않습니다.
            </span>
          </div>

          <ErrorNotice error={error} />

          {done !== null && (
            <div className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm">
              <strong>{done}대</strong>를 등록했습니다.
            </div>
          )}

          {columns.data && (
            <ImportGrid
              columns={columns.data}
              rows={shown}
              onEdit={edit}
              onPasteRange={(text) => void pasteRange(text)}
              disabled={phase === 'putting'}
            />
          )}

          {tooMany && (
            <p className="text-muted-foreground text-xs">
              {rows.length}줄이라 <strong>문제 있는 줄만</strong> 그렸습니다 — 표가 너무 크면
              타이핑 한 번에 멈춥니다. 나머지 {rows.length - bad.length}줄은 그대로 들어갑니다.
            </p>
          )}

          <div className="flex flex-wrap items-center gap-4 text-sm">
            {phase === 'looking' && <span className="text-muted-foreground">읽는 중…</span>}
            {phase === 'putting' && (
              // **몇 대를 넣는 중인지 말한다.** 「지금 1500대째」 는 못 말한다 —
              // 한 트랜잭션이라 그 수는 아직 확정된 것이 아니고, 전부 되돌아가는
              // 순간 거짓말이 된다.
              <span className="flex items-center gap-2">
                <Loader2 className="size-4 animate-spin" />
                <span>
                  <strong>{summary?.ready ?? 0}대</strong>를 넣는 중입니다
                  {spent(summary?.ready ?? 0)}. <strong>창을 닫지 마세요</strong> — 도중에
                  끊기면 아무것도 안 들어갑니다.
                </span>
              </span>
            )}
            {summary && phase === 'idle' && (
              <>
                <span>
                  적은 줄 <strong>{summary.total}</strong>
                </span>
                <span className="text-emerald-700">
                  넣을 수 있음 <strong>{summary.ready}</strong>
                </span>
                {summary.problems > 0 && (
                  <span className="text-amber-700">
                    문제 <strong>{summary.problems}</strong>
                  </span>
                )}
                {unlinked > 0 && summary.problems === 0 && (
                  // 막지 않는다 — 자작 장비나 카탈로그에 없는 것이 실제로 있다.
                  // 다만 그 장비들이 **검색에 안 걸린다**는 사실은 넣기 전에 안다.
                  <span className="text-amber-700">
                    기종 미연결 <strong>{unlinked}</strong> — 시험 항목이 0 건이 되고,{' '}
                    <strong>0 건이면 검색에 걸리지 않습니다</strong>
                  </span>
                )}
              </>
            )}
          </div>
        </div>

        <DialogFooter>
          {/* **넣는 중에는 못 닫는다.** 닫아도 요청은 계속 가는데 화면은 결과를
              못 보고, 그러면 사람은 들어갔는지 아닌지를 모르는 채 남는다. */}
          <Button variant="outline" onClick={onClose} disabled={phase === 'putting'}>
            닫기
          </Button>
          <Button onClick={() => void commit()} disabled={phase !== 'idle' || ready === 0}>
            {phase === 'putting' ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Upload className="size-4" />
            )}
            {phase === 'putting' ? '넣는 중…' : ready > 0 ? `${ready}대 넣기` : '넣기'}
            {ready > 0 && phase === 'idle' && spent(ready)}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

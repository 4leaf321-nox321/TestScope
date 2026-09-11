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
 * ## 머리글을 안 붙여 오는 사람이 있다
 *
 * 엑셀에서 **값만** 긁어 오는 것이 실은 더 흔하다. 그때 표 전체를 갈아 끼우면 첫 줄이
 * 머리글로 읽혀 한 대가 통째로 사라진다. 그래서 붙여넣은 첫 줄이 머리글인지 보고,
 * 아니면 **커서가 있는 칸부터** 채운다 — 엑셀에서 붙여넣는 것과 같은 동작이다.
 *
 * 머리글인지는 **서버가 준 별칭 목록**으로 판정한다(`ImportColumn.aliases`). 화면이
 * 자기 목록으로 하면 서버가 받아 주는 이름과 어긋나서, 「보유 부서」 라고 적은 머리글이
 * 값으로 읽힌다.
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
 * ## 없는 거점·분류는 여기서 만든다
 *
 * 대장에 새 거점이 섞여 있는 것은 흔하다. 「기준정보에서 먼저 만드세요」 하고 멈추면
 * 사람은 창을 닫고 나갔다 와야 하고, **그 사이 표에서 고치던 것을 잃는다.** 거점과
 * 장비 분류는 원래 누구나 더하는 열린 축이라(`entry_policy=open`) 막을 이유가 없다.
 *
 * 다만 **반입이 스스로 만들지는 않는다.** 오타가 그대로 축이 되면 「본사」 와 「본사 」
 * 가 서로 다른 거점이 되고, 그 둘은 나중에 합칠 방법이 없다. 사람이 눌러서 만든다.
 *
 * 같은 값이 300줄에 50번 나와도 **단추는 하나**다.
 *
 * ## 기종은 여기서 못 만든다
 *
 * 거점·분류와 다르다. 기종은 **전사 공용이라 시스템 관리자만** 만들고(계열도 그렇다),
 * 계열이 먼저 있어야 하며, 사양 0칸 기종을 만들면 그 기종으로 등록한 장비는 조건 없이
 * 복사되어 **검색이 「모름」 으로 답한다.** 실제로 그 사고가 한 번 났다 — 데모 시드가
 * 이름만 딴 껍데기 계열을 만들어서, 같은 이름의 기종이 두 계열에 생기고 반입까지 막혔다.
 *
 * 그래서 기종은 **비워 두고 모델명에 적어 둔다.** 그 장비는 시험 항목이 0 건이라
 * 검색에 안 걸리지만, 홈의 「카탈로그에 안 이어진 장비」 가 세고 목록이 거른다
 * (`?catalog=unlinked`) — 시스템 관리자가 그것을 보고 카탈로그를 채운다.
 *
 * ## 표를 엑셀로 되가져갈 수 있다
 *
 * 300줄 중 12줄이 걸렸을 때, 그 판정을 **엑셀에서 다시 보고 싶은 일**이 있다 — 다른
 * 사람에게 보내거나, 원본 대장과 나란히 놓고 맞춰 보거나. 그래서 표를 탭으로 이어
 * 클립보드에 넣는다. 붙이면 바로 표가 된다.
 *
 * **문제도 함께 나간다.** 값만 돌려주면 무엇이 틀렸는지가 다시 화면 안에만 남고,
 * 그러면 되가져가는 뜻이 없다. 되돌아올 때 그 열은 서버가 모르는 이름이라 그냥
 * 무시되므로, 고쳐서 다시 붙여넣는 왕복이 된다.
 *
 * ## 넣을 수 있는 줄은 넣고, 그 줄은 표에서 사라진다
 *
 * 문제가 있는 줄 때문에 멀쩡한 줄까지 막으면, 300줄 중 12줄이 틀렸을 때 288줄을 다시
 * 붙여넣어야 한다. 넣고 나면 **들어간 줄을 표에서 지운다** — 남는 것은 고쳐야 할
 * 12줄뿐이고, 고쳐서 다시 누르면 된다.
 *
 * 지우는 것이 핵심이다. 안 지우면 다시 누를 때 이미 들어간 288줄이 「이미 등록된
 * 자산번호」 로 되돌아오고, 그때 사람은 무엇을 지워야 할지 모른다.
 *
 * ## 이미 등록된 자산번호는 갱신할 수 있다
 *
 * 부서는 엑셀 대장을 계속 굴린다. 300대 중 30대의 위치·상태가 바뀌었을 때 상세 화면에서
 * 30번 고치라는 것은 무리라, 같은 대장을 다시 붙여넣어 맞출 수 있어야 한다. 기본은
 * 거절이고 **켜야 갱신한다** — 기본이 갱신이면 다른 부서의 옛 대장을 실수로 붙인 사람이
 * 남의 장비 위치를 바꾼다.
 *
 * 빈 칸은 「비운다」 가 아니라 「안 건드린다」 다. 부서와 기종은 안 바꾼다. 바뀔 칸은
 * 파랗게 칠하고 전후를 보인다 — 누르기 전에 잘못 붙은 열이 눈에 띄어야 한다.
 *
 * ## 줄마다 넣을지 고른다 — 기본은 다 켜짐
 *
 * 「하나하나 확인」 과 「전부 한 번에」 사이다. 30줄에 30번 확인을 누르게 하면 사람은
 * 읽지 않고 누른다. 기본은 다 켜져 있고, 이상해 보이는 줄만 끄고 넣는다. 꺼진 줄은
 * 서버에 안 보내고 표에 남는다.
 *
 * ## 진행률(N/M) 대신 「무엇을 하는 중인지」 를 보인다
 *
 * 「지금 1500대째」 를 보여 주려면 서버가 넣는 중에 중간 보고를 해야 하는데, 그러려면
 * 쪽을 나눠 커밋해야 한다 — 그리고 그것이 바로 **반쯤 들어간 대장**이다. 한 트랜잭션을
 * 지키는 한 그 숫자는 확정된 것이 아니고, 전부 되돌아가는 순간 **거짓말이 된다.**
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { Copy, Download, Loader2, Plus, Upload } from 'lucide-react'

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
import { copyText } from '@/shared/lib/clipboard'
import { equipmentApi } from '@/modules/equipment/api'
import { vocabularyApi } from '@/modules/vocabulary/api'
import type { EquipmentImportResult, ImportColumn } from '@/modules/equipment/api'
import { GRID_MAX, ImportGrid, filled } from '@/modules/equipment/ImportGrid'
import type { GridRow } from '@/modules/equipment/ImportGrid'

/** 빈 표를 몇 줄로 시작하나. 붙여넣기가 주된 길이라 많을 필요는 없고, 몇 대를
 *  손으로 치려는 사람에게는 이만큼이면 시작이 된다. */
const BLANK_ROWS = 5

/** 되가져가는 표에 붙는 판정 열의 이름. **서버가 모르는 이름이라야** 다시 붙여넣을
 *  때 값으로 안 읽힌다 — 열 이름 하나가 겹치면 그 줄의 칸이 하나씩 밀린다. */
const PROBLEM_COLUMN = '확인 필요'

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

/** 붙여넣은 글자를 격자로 나눈다.
 *
 *  **구분자 고르는 규칙은 서버와 같다** — 첫 줄에 탭이 있으면 탭, 없으면 쉼표. 값
 *  안의 쉼표(「3동, 201호」)는 탭 쪽에서만 안 밀린다.
 *
 *  이것은 반입 파싱이 아니라 **표에 어느 칸을 채울지**를 정하는 일이다. 채운 표는
 *  다시 서버로 보내 판정을 받으므로, 판정이 두 벌이 되지는 않는다. */
function split(text: string): string[][] {
  const body = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').replace(/\n+$/, '')
  const cut = body.split('\n')[0].includes('\t') ? '\t' : ','
  return body.split('\n').map((line) => line.split(cut))
}

/** 붙여넣은 첫 줄이 머리글인가.
 *
 *  **절반 넘게 아는 이름이면** 머리글로 본다. 하나만 맞아도 머리글이라 하면 「비고」
 *  라는 값 하나에 표가 통째로 갈리고, 전부 맞아야 한다고 하면 열 하나를 빼고 복사한
 *  사람이 값으로 읽힌다. */
function looksLikeHeader(cells: string[], columns: ImportColumn[]): boolean {
  const known = new Set(
    columns.flatMap((one) => one.aliases).map((one) => one.replace(/\s/g, '').toLowerCase()),
  )
  const hit = cells.filter((one) => known.has(one.replace(/\s/g, '').toLowerCase())).length
  return cells.length > 0 && hit * 2 > cells.length
}

let nextId = 1

function blank(count: number): GridRow[] {
  return Array.from({ length: count }, () => ({
    id: nextId++,
    cells: {},
    problems: [],
    modelLinked: false,
    exists: false,
    changes: [],
    included: true,
  }))
}

/** 표를 서버가 읽을 수 있는 글자로. **직렬화만 화면이 하고 파싱은 서버가 한다** —
 *  판정이 두 벌이 되면 화면은 「이제 됩니다」 라고 해 놓고 저장에서 막힌다. */
function serialize(columns: ImportColumn[], rows: GridRow[]): string {
  const head = columns.map((one) => one.label).join('\t')
  const body = rows.map((row) => columns.map((one) => row.cells[one.key] ?? '').join('\t'))
  return [head, ...body].join('\n')
}

/** 엑셀로 되가져갈 글자. **판정을 한 열 더 붙인다** — 값만 돌려주면 무엇이
 *  틀렸는지가 화면 안에만 남고, 그러면 되가져가는 뜻이 없다.
 *
 *  이 열은 되돌아올 때 서버가 모르는 이름이라 그냥 무시된다. */
function withProblems(columns: ImportColumn[], rows: GridRow[]): string {
  const head = [...columns.map((one) => one.label), PROBLEM_COLUMN].join('\t')
  const body = rows.map((row) =>
    [
      ...columns.map((one) => row.cells[one.key] ?? ''),
      row.problems.map((one) => one.message).join(' · '),
    ].join('\t'),
  )
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
  /** 방금 몇 줄을 복사했나. **말해 주지 않으면 눌렀는지도 모른다.** */
  const [copied, setCopied] = useState<number | null>(null)
  /** 이미 등록된 자산번호를 만나면 갱신할 것인가. **기본은 거절이다.** */
  const [updateExisting, setUpdateExisting] = useState(false)

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
          exists: said?.exists ?? false,
          changes: said?.changes ?? [],
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
    const key = `${updateExisting ? 'u' : 'c'}:${asText}`
    if (key === sent.current) return
    setPhase('looking')
    const timer = setTimeout(() => {
      sent.current = key
      equipmentApi
        .importPaste(asText, true, updateExisting)
        .then((result) => {
          apply(result)
          setError(null)
        })
        .catch((thrown: ApiError) => setError(thrown))
        .finally(() => setPhase('idle'))
    }, 500)
    return () => clearTimeout(timer)
    // 갱신을 켜고 끄면 같은 표라도 판정이 달라진다 — 다시 묻는다.
  }, [asText, sending.length, columns.data, updateExisting])

  /** 엑셀에서 복사한 **범위**를 받는다.
   *
   *  머리글이 붙어 왔으면 표를 통째로 갈아 끼우고, 값만 왔으면 **커서 자리부터**
   *  채운다 — 값만 긁어 오는 것이 실은 더 흔하고, 그때 전체를 갈아 끼우면 첫 줄이
   *  머리글로 읽혀 한 대가 통째로 사라진다. */
  function pasteRange(text: string, atRow: number, atColumn: string) {
    if (!text.trim()) return
    const grid = split(text)
    if (looksLikeHeader(grid[0] ?? [], columns.data ?? [])) {
      void replaceAll(text)
      return
    }
    setDone(null)
    setRows((before) => {
      const keys = (columns.data ?? []).map((one) => one.key)
      const startRow = Math.max(
        0,
        before.findIndex((one) => one.id === atRow),
      )
      const startCol = Math.max(0, keys.indexOf(atColumn))
      // 붙여넣을 것이 남은 줄보다 많으면 줄을 늘린다 — 모자라서 잘리면 사람은
      // 그 사실을 모른 채 넣는다.
      const next = [...before, ...blank(Math.max(0, startRow + grid.length - before.length))]
      grid.forEach((cells, down) => {
        const row = next[startRow + down]
        const patch = { ...row.cells }
        cells.forEach((value, right) => {
          const key = keys[startCol + right]
          if (key) patch[key] = value.trim()
        })
        next[startRow + down] = { ...row, cells: patch }
      })
      return next
    })
  }

  /** 머리글이 붙어 온 것. 표를 통째로 갈아 끼운다. */
  async function replaceAll(text: string) {
    setError(null)
    setDone(null)
    setPhase('looking')
    try {
      const result = await equipmentApi.importPaste(text, true, updateExisting)
      // **여기서만 서버가 읽은 값을 그대로 받는다** — 그게 파싱 결과다. 화면이
      // 다시 파싱하면 구분자·빈 줄·머리글 별칭이 두 벌이 되어 반드시 어긋난다.
      const made: GridRow[] = result.rows.map((one) => ({
        id: nextId++,
        cells: { ...one.cells },
        problems: one.problems ?? [],
        modelLinked: one.model_linked,
        exists: one.exists ?? false,
        changes: one.changes ?? [],
        included: true,
      }))
      sent.current = `${updateExisting ? 'u' : 'c'}:${serialize(columns.data ?? [], made)}`
      setRows(made.length > 0 ? made : blank(BLANK_ROWS))
      setSummary(result)
    } catch (thrown) {
      setError(thrown as ApiError)
    } finally {
      setPhase('idle')
    }
  }

  /** 못 들어간 줄만 남긴다. 빈 줄과 **꺼 둔 줄**은 그대로 둔다 — 빈 줄은 더 칠 자리고,
   *  꺼 둔 줄은 서버에 안 보냈으니 응답에 없다. */
  function keepFailed(result: EquipmentImportResult): GridRow[] {
    let index = 0
    const left: GridRow[] = []
    for (const row of rows) {
      if (!filled(row) || !row.included) {
        left.push(row)
        continue
      }
      const said = result.rows[index++]
      if (said?.imported) continue
      left.push({
        ...row,
        problems: said?.problems ?? [],
        modelLinked: said?.model_linked ?? false,
        exists: said?.exists ?? false,
        changes: said?.changes ?? [],
      })
    }
    return left
  }

  function include(id: number | null, included: boolean) {
    setRows((before) =>
      before.map((row) =>
        (id === null ? filled(row) : row.id === id) ? { ...row, included } : row,
      ),
    )
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
      // **켜진 줄만 보낸다.** 미리보기는 전부 보내 판정을 보이지만, 넣는 것은 고른 것만이다.
      const result = await equipmentApi.importPaste(
        serialize(
          columns.data ?? [],
          sending.filter((one) => one.included),
        ),
        false,
        updateExisting,
      )
      const handled = result.created + (result.updated ?? 0) + (result.unchanged ?? 0)
      if (handled > 0) {
        setDone(handled)
        onDone()
      }
      // **들어간 줄을 지운다.** 안 지우면 다시 누를 때 그 줄들이 「이미 등록된
      // 자산번호」 로 되돌아오고, 그때 사람은 무엇을 지워야 할지 모른다.
      const left = keepFailed(result)
      if (left.length === 0) {
        setRows(blank(BLANK_ROWS))
        setSummary(null)
        sent.current = ''
      } else {
        setRows(left)
        setSummary(result)
        // 남은 줄만으로 다시 물어야 판정이 맞는다 — 줄이 줄었으니 글자도 달라진다.
        sent.current = ''
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

  /** 만들 수 있는 것들. **고유한 (축, 값) 으로 묶는다** — 같은 거점이 50줄에 나와도
   *  단추는 하나여야 한다. */
  const makeable = useMemo(() => {
    const found = new Map<string, { axis: string; value: string; label: string }>()
    for (const row of rows) {
      for (const one of row.problems) {
        if (!one.make_axis || !one.make_value) continue
        const key = `${one.make_axis}:${one.make_value}`
        if (found.has(key)) continue
        const column = (columns.data ?? []).find((col) => col.key === one.field)
        found.set(key, {
          axis: one.make_axis,
          value: one.make_value,
          label: column?.label ?? one.make_axis,
        })
      }
    }
    return [...found.values()]
  }, [rows, columns.data])

  /** 축에 값 하나를 더하고 다시 판정받는다. */
  async function make(axis: string, value: string) {
    setPhase('looking')
    setError(null)
    try {
      await vocabularyApi.createTerm(axis, { value })
      // 방금 만든 것이 반영되게 **강제로 다시 묻는다** — 표 글자는 안 바뀌었으므로
      // 그냥 두면 「같은 것은 두 번 안 보낸다」 에 걸려 판정이 그대로 남는다.
      sent.current = ''
      const result = await equipmentApi.importPaste(asText, true, updateExisting)
      apply(result)
    } catch (thrown) {
      setError(thrown as ApiError)
    } finally {
      setPhase('idle')
    }
  }

  /** 표를 엑셀로. **보이는 것을 복사한다** — 「문제만 보기」 중이면 그것만이다.
   *  화면과 다른 것이 나가면 사람은 무엇을 받았는지 모른다. */
  async function copyGrid() {
    const rowsToCopy = shown.filter(filled)
    if (rowsToCopy.length === 0) return
    try {
      await copyText(withProblems(columns.data ?? [], rowsToCopy))
      setCopied(rowsToCopy.length)
      window.setTimeout(() => setCopied(null), 2500)
    } catch (thrown) {
      // 브라우저가 거절하는 일이 있다(권한·문맥). 조용히 실패하면 사람은 복사된
      // 줄 알고 엑셀에서 옛 것을 붙인다.
      setError(
        new ApiError(0, {
          error: {
            code: 'TSC-CLIENT-0002',
            message: `복사하지 못했습니다: ${(thrown as Error).message}`,
          },
        }),
      )
    }
  }

  const bad = rows.filter((one) => one.problems.length > 0)
  const unlinked = sending.filter(
    (one) => one.problems.length === 0 && !one.modelLinked,
  ).length
  // 다 그리면 DOM 이 먼저 죽는다(2000줄에 열 18이면 칸 36,000개). 넘으면 문제 줄만.
  const tooMany = rows.length > GRID_MAX
  const shown = onlyBad || tooMany ? bad : rows
  // **문제가 있어도 넣을 수 있는 줄이 있으면 누를 수 있다.** 전에는 하나라도 틀리면
  // 통째로 막았는데, 그러면 300줄 중 12줄 때문에 288줄을 다시 붙여넣어야 한다.
  //
  // 세는 것은 화면이다 — 꺼 둔 줄은 서버가 모른다.
  const ready = summary
    ? sending.filter((one) => one.included && one.problems.length === 0).length
    : 0

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
      {/* **표가 들어가는 창이라 크게 잡는다** — 가로세로 화면의 80%.
          `max-w`·`max-h` 는 상한일 뿐이라 내용이 적으면 창이 쪼그라든다. 표는 남는
          높이를 채우는 것이므로 **높이를 정해 줘야** 처음부터 넓게 열린다.

          기본이 `sm:max-w-lg` 라, 브레이크포인트 없는 `max-w-*` 로는 화면이 넓어지는
          순간 기본값이 이긴다 — 실제로 그랬다. */}
      <DialogContent className="h-[80vh] max-h-[80vh] sm:w-[80vw] sm:max-w-[80vw]">
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
            <Button
              variant="outline"
              size="sm"
              onClick={() => void copyGrid()}
              disabled={phase === 'putting' || sending.length === 0}
            >
              <Copy className="size-4" />
              {copied === null ? '표 복사' : `${copied}줄 복사했습니다`}
            </Button>
            <Button variant="outline" size="sm" onClick={reset} disabled={phase !== 'idle'}>
              비우기
            </Button>
            {/* **기본은 거절이다.** 기본이 갱신이면 다른 부서의 옛 대장을 실수로 붙인
                사람이 남의 장비 위치를 바꾼다. */}
            <label className="flex cursor-pointer items-center gap-1.5 text-sm">
              <input
                type="checkbox"
                checked={updateExisting}
                onChange={(event) => setUpdateExisting(event.target.checked)}
                disabled={phase === 'putting'}
              />
              이미 등록된 장비는 갱신
            </label>
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

          {makeable.length > 0 && (
            // **창을 안 떠나고 만든다.** 나갔다 오면 표에서 고치던 것을 잃는다.
            <div className="flex flex-wrap items-center gap-2 rounded-md border border-amber-300 bg-amber-50 p-2 text-sm">
              <span>기준정보에 없는 값 {makeable.length}개 —</span>
              {makeable.map((one) => (
                <Button
                  key={`${one.axis}:${one.value}`}
                  size="sm"
                  variant="outline"
                  disabled={phase !== 'idle'}
                  onClick={() => void make(one.axis, one.value)}
                >
                  <Plus className="size-4" />
                  {one.label} 「{one.value}」 만들기
                </Button>
              ))}
            </div>
          )}

          {done !== null && (
            <div className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm">
              <strong>{done}</strong>건을 처리했습니다.
              {sending.length > 0 && (
                // **남은 줄이 표에 그대로 있다.** 안 말하면 사람은 다 들어간 줄 안다.
                <>
                  {' '}
                  못 넣은 <strong>{sending.length}줄</strong>이 표에 남아 있습니다 — 고쳐서
                  다시 누르세요.
                </>
              )}
            </div>
          )}

          {columns.data && (
            <ImportGrid
              columns={columns.data}
              rows={shown}
              onEdit={edit}
              onPasteRange={pasteRange}
              onInclude={include}
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
                  새로{' '}
                  <strong>
                    {
                      sending.filter(
                        (one) => one.included && !one.exists && one.problems.length === 0,
                      ).length
                    }
                  </strong>
                </span>
                {updateExisting && (
                  <>
                    <span className="text-sky-800">
                      갱신{' '}
                      <strong>
                        {
                          sending.filter(
                            (one) =>
                              one.included &&
                              one.exists &&
                              one.changes.length > 0 &&
                              one.problems.length === 0,
                          ).length
                        }
                      </strong>
                    </span>
                    <span className="text-muted-foreground">
                      변경 없음 <strong>{summary.unchanged}</strong>
                    </span>
                  </>
                )}
                {summary.problems > 0 && (
                  <span className="text-amber-700">
                    문제 <strong>{summary.problems}</strong>
                  </span>
                )}
                {sending.some((one) => !one.included) && (
                  <span className="text-muted-foreground">
                    뺌 <strong>{sending.filter((one) => !one.included).length}</strong>
                  </span>
                )}
                {unlinked > 0 && summary.problems === 0 && (
                  // 막지 않는다 — 자작 장비나 카탈로그에 없는 것이 실제로 있다.
                  // 다만 그 장비들이 **검색에 안 걸린다**는 사실은 넣기 전에 안다.
                  <span className="text-amber-700">
                    기종 미연결 <strong>{unlinked}</strong> — 시험 항목이 0 건이 되고,{' '}
                    <strong>0 건이면 검색에 걸리지 않습니다.</strong> 카탈로그에 없는 기종이면{' '}
                    <strong>모델명</strong> 칸에 적어 두세요. 넣은 뒤 홈의 「카탈로그에 안
                    이어진 장비」 에서 다시 찾을 수 있습니다.
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
            {phase === 'putting' ? '넣는 중…' : ready > 0 ? `${ready}건 넣기` : '넣기'}
            {ready > 0 && phase === 'idle' && spent(ready)}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

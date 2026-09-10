/**
 * 반입 표 — **붙여넣는 자리이자 고치는 자리.**
 *
 * 전에는 빈 글상자에 붙이고 그 다음에 표가 나타났다. 두 화면을 거치는 셈이라
 * 「어디에 붙이나」 를 한 번 더 묻게 된다. 처음부터 표를 두고 거기 붙인다 —
 * 엑셀에서 오는 사람에게 표는 설명이 필요 없는 모양이다.
 *
 * ## 붙여넣기는 칸 안에서 가로챈다
 *
 * 엑셀에서 복사한 것은 한 칸이 아니라 **범위**다. 그대로 두면 한 칸 안에 탭이 든
 * 글자가 통째로 박힌다. 그래서 탭이나 줄바꿈이 든 것은 가로채 표 전체를 갈아 끼우고,
 * 한 칸짜리 값은 그냥 그 칸에 붙게 둔다.
 *
 * ## 틀린 칸은 붉게
 *
 * 줄 단위로만 말하면 열여덟 칸 중 어디를 고쳐야 할지 사람이 되짚어야 한다. 서버가
 * 문제마다 열 키를 함께 주므로(`ImportProblem.field`) 그 칸을 칠한다. 한 칸에 못
 * 붙이는 문제(자산번호가 다른 줄과 겹침)는 줄 끝에 적는다.
 */

import { cn } from '@/shared/lib/utils'
import type { ImportColumn, ImportProblem } from '@/modules/equipment/api'

/** 표 한 줄. **줄의 주인은 화면이다** — 서버는 빈 줄을 건너뛰므로, 서버의 줄 번호를
 *  그대로 쓰면 가운데를 지우는 순간 아래 줄들이 밀린다. */
export interface GridRow {
  id: number
  cells: Record<string, string>
  problems: ImportProblem[]
  modelLinked: boolean
}

/** 한 번에 그리는 줄 수. **DOM 이 먼저 죽는다** — 2000줄에 열 열여덟이면 칸이
 *  36,000개고, 그 표는 타이핑 한 번에 멈춘다. 넘는 것은 「문제만 보기」 로 좁힌다. */
export const GRID_MAX = 300

/** 그 줄에 적힌 것이 있나. 빈 줄은 서버에 안 보낸다. */
export function filled(row: GridRow): boolean {
  return Object.values(row.cells).some((one) => one.trim() !== '')
}

export function ImportGrid({
  columns,
  rows,
  onEdit,
  onPasteRange,
  disabled,
}: {
  columns: ImportColumn[]
  rows: GridRow[]
  onEdit: (id: number, field: string, value: string) => void
  /** 엑셀에서 복사한 **범위**를 붙여넣었다. 표 전체를 갈아 끼운다. */
  onPasteRange: (text: string) => void
  disabled: boolean
}) {
  return (
    <div className="min-h-0 flex-1 overflow-auto rounded-md border">
      <table className="w-max border-collapse text-xs">
        <thead className="bg-muted/60 sticky top-0 z-10">
          <tr>
            <th className="text-muted-foreground border-b border-r px-2 py-1 font-normal">
              #
            </th>
            {columns.map((one) => (
              <th
                key={one.key}
                className="border-b border-r px-2 py-1 text-left font-medium whitespace-nowrap"
              >
                {one.label}
                {/* 비우면 그 줄을 못 넣는 칸. 표시가 없으면 사람은 다 채워야 하는
                    줄 알고, 다 채워야 하면 등록을 미룬다. */}
                {one.required && <span className="text-amber-600"> *</span>}
              </th>
            ))}
            <th className="border-b px-2 py-1 text-left font-medium">비고</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const bad = new Map(
              row.problems.filter((one) => one.field).map((one) => [one.field, one.message]),
            )
            const notes = row.problems.filter((one) => !one.field).map((one) => one.message)
            return (
              <tr key={row.id} className={notes.length > 0 ? 'bg-amber-50' : undefined}>
                <td className="text-muted-foreground border-b border-r px-2 py-1 text-right font-mono">
                  {index + 1}
                </td>
                {columns.map((one) => {
                  const said = bad.get(one.key)
                  return (
                    <td key={one.key} className="border-b border-r p-0">
                      <input
                        value={row.cells[one.key] ?? ''}
                        onChange={(event) => onEdit(row.id, one.key, event.target.value)}
                        onPaste={(event) => {
                          const text = event.clipboardData.getData('text')
                          // 탭이나 줄바꿈이 있으면 **범위**다 — 한 칸에 넣으면
                          // 그 칸 안에 표 전체가 글자로 박힌다.
                          if (/[\t\n\r]/.test(text)) {
                            event.preventDefault()
                            onPasteRange(text)
                          }
                        }}
                        disabled={disabled}
                        // **틀린 칸을 칠한다.** 무엇이 틀렸는지는 마우스를 얹으면
                        // 나오고, 아래 목록에도 그대로 있다.
                        title={said ?? ''}
                        className={cn(
                          'w-32 bg-transparent px-2 py-1 outline-none',
                          'focus:bg-background focus:ring-ring focus:ring-1',
                          said && 'bg-red-50 text-red-700 ring-1 ring-red-300',
                        )}
                      />
                    </td>
                  )
                })}
                <td className="text-amber-700 border-b px-2 py-1 whitespace-nowrap">
                  {notes.join(' · ')}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

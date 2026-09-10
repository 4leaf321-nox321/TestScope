/**
 * 반입 표 — **붙여넣는 자리이자 고치는 자리.**
 *
 * 전에는 큰 글상자 하나였다. 붙여넣기는 됐지만 두 가지를 못 했다: 어느 **칸**이
 * 틀렸는지 못 보여 줬고(줄 번호만 말했다), 그 자리에서 고칠 수 없었다 — 12줄을
 * 고치려고 엑셀로 돌아가 다시 복사해야 했다.
 *
 * ## 붙여넣기는 표 전체가 받는다
 *
 * 어느 칸에 커서가 있든 붙여넣으면 표 전체를 갈아 끼운다. 엑셀에서 복사한 것은
 * 한 칸이 아니라 **범위**라, 한 칸에 넣으려 하면 그 칸 안에 탭이 든 글자가 박힌다.
 *
 * ## 틀린 칸은 붉게
 *
 * 줄 단위로만 말하면 열여덟 칸 중 어디를 고쳐야 할지 사람이 되짚어야 한다. 서버가
 * 문제마다 열 키를 함께 주므로(`ImportProblem.field`) 그 칸을 칠한다. 한 칸에 못
 * 붙이는 문제(자산번호가 다른 줄과 겹침)는 줄 끝에 적는다.
 *
 * ## 서버가 읽은 값을 그린다
 *
 * 화면이 붙여넣은 글자를 다시 파싱하지 않는다. 구분자 고르기·빈 줄 건너뛰기·머리글
 * 별칭이 두 벌이 되면 반드시 어긋나고, 그때 사람은 자기가 붙여넣은 것과 다른 표를
 * 본다. 표에 그리는 것은 언제나 **서버가 읽은 그대로**(`cells`)다.
 */

import { useMemo } from 'react'

import { cn } from '@/shared/lib/utils'
import type { EquipmentImportRow, ImportColumn } from '@/modules/equipment/api'

/** 한 번에 그리는 줄 수. **DOM 이 먼저 죽는다** — 2000줄에 열 열여덟이면 칸이
 *  36,000개고, 그 표는 타이핑 한 번에 멈춘다. 넘는 것은 「문제만 보기」 로 좁힌다. */
export const GRID_MAX = 300

export function ImportGrid({
  columns,
  rows,
  onChange,
  disabled,
}: {
  columns: ImportColumn[]
  rows: EquipmentImportRow[]
  /** 한 칸을 고쳤다. 줄 번호와 열 키로 가리킨다. */
  onChange: (line: number, field: string, value: string) => void
  disabled: boolean
}) {
  /** 줄마다 「어느 칸이 걸렸나」. 칸을 그릴 때마다 목록을 훑지 않게 미리 모은다. */
  const badCells = useMemo(() => {
    const map = new Map<number, Map<string, string>>()
    for (const row of rows) {
      const cells = new Map<string, string>()
      for (const one of row.problems) {
        if (one.field) cells.set(one.field, one.message)
      }
      map.set(row.line, cells)
    }
    return map
  }, [rows])

  /** 한 칸에 못 붙이는 문제. 줄 끝에 적는다. */
  const rowNotes = useMemo(() => {
    const map = new Map<number, string[]>()
    for (const row of rows) {
      const said = row.problems.filter((one) => !one.field).map((one) => one.message)
      if (said.length > 0) map.set(row.line, said)
    }
    return map
  }, [rows])

  return (
    <div className="overflow-auto rounded-md border" style={{ maxHeight: '22rem' }}>
      <table className="w-max border-collapse text-xs">
        <thead className="bg-muted/60 sticky top-0 z-10">
          <tr>
            <th className="text-muted-foreground border-b border-r px-2 py-1 font-normal">
              줄
            </th>
            {columns.map((one) => (
              <th key={one.key} className="border-b border-r px-2 py-1 text-left font-medium">
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
          {rows.map((row) => {
            const bad = badCells.get(row.line)
            const notes = rowNotes.get(row.line)
            return (
              <tr key={row.line} className={notes ? 'bg-amber-50' : undefined}>
                <td className="text-muted-foreground border-b border-r px-2 py-1 text-right font-mono">
                  {row.line}
                </td>
                {columns.map((one) => {
                  const said = bad?.get(one.key)
                  return (
                    <td key={one.key} className="border-b border-r p-0">
                      <input
                        value={row.cells[one.key] ?? ''}
                        onChange={(event) => onChange(row.line, one.key, event.target.value)}
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
                <td className="text-amber-700 border-b px-2 py-1">{notes?.join(' · ')}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

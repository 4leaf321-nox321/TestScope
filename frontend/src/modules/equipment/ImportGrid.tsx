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
 * 글자가 통째로 박힌다. 그래서 탭이나 줄바꿈이 든 것은 가로채고, 한 칸짜리 값은
 * 그냥 그 칸에 붙게 둔다.
 *
 * 가로챈 것을 **어디에 넣을지는 창이 정한다** — 머리글이 붙어 왔으면 표 전체를
 * 갈아 끼우고, 값만 왔으면 **지금 커서가 있는 칸부터** 채운다. 그래서 어느 줄
 * 어느 열에서 붙였는지를 함께 넘긴다.
 *
 * ## 줄마다 넣을지 고른다
 *
 * 「하나하나 확인」 과 「전부 한 번에」 사이다. 30줄을 갱신하는데 30번 확인을 누르게 하면
 * 사람은 읽지 않고 누른다 — 확인이 의례가 되면 없는 것보다 나쁘다. 그래서 **기본은 다
 * 켜져 있고**, 이상해 보이는 줄만 끄고 넣는다. 30줄이면 클릭 0번, 한 줄이 이상하면 1번.
 *
 * 꺼진 줄은 서버에 보내지 않고 표에 그대로 남는다 — 나중에 다시 켜서 넣을 수 있다.
 *
 * ## 바뀔 칸은 파랗게
 *
 * 갱신을 켜면 이미 있는 장비의 줄은 새로 넣는 대신 고쳐진다. **어느 칸이 어떻게 바뀌는지**를
 * 칠해 보인다 — 「30대를 갱신합니다」 만 말하면 사람은 누르고, 그 안에 잘못 붙은 열이
 * 있었다는 것을 나중에 안다. 마우스를 얹으면 전후가 나온다.
 *
 * ## 틀린 칸은 붉게, 그리고 **이유는 맨 앞에**
 *
 * 줄 단위로만 말하면 열여덟 칸 중 어디를 고쳐야 할지 사람이 되짚어야 한다. 서버가
 * 문제마다 열 키를 함께 주므로(`ImportProblem.field`) 그 칸을 칠한다.
 *
 * 그런데 붉은 칸만으로는 모자랐다. 파일럿에서 300줄을 붙이고 「문제만 보기」 를 눌렀더니
 * **여덟 줄 중 셋은 붉은 칸이 화면에 없었다** — 문제가 열여덟 열 중 오른쪽 끝(상태·
 * 교정주기)에 있었고, 줄 끝의 비고 열도 화면 밖이었다. 문제 줄만 보는 화면에서 왜
 * 문제인지가 안 보이는 것이다. 그래서 이유 열을 **줄 번호 바로 옆**에 둔다.
 */

import { cn } from '@/shared/lib/utils'
import type { ImportChange, ImportColumn, ImportProblem } from '@/modules/equipment/api'

/** 표 한 줄. **줄의 주인은 화면이다** — 서버는 빈 줄을 건너뛰므로, 서버의 줄 번호를
 *  그대로 쓰면 가운데를 지우는 순간 아래 줄들이 밀린다. */
export interface GridRow {
  id: number
  cells: Record<string, string>
  problems: ImportProblem[]
  modelLinked: boolean
  /** 이 자산번호가 이미 등록돼 있나. 갱신을 켜면 이 줄은 새로 넣는 대신 고쳐진다. */
  exists: boolean
  /** 갱신이면 **바뀔 칸들**. 넣기 전에 무엇이 어떻게 바뀌는지 보이는 근거다. */
  changes: ImportChange[]
  /** 이 줄을 넣을 것인가. **기본은 켜짐** — 이상해 보이는 줄만 끈다. */
  included: boolean
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
  onInclude,
  disabled,
}: {
  columns: ImportColumn[]
  rows: GridRow[]
  onEdit: (id: number, field: string, value: string) => void
  /** 엑셀에서 복사한 **범위**를 붙여넣었다. 어디에 넣을지는 창이 정한다 — 머리글이
   *  있으면 표 전체를, 없으면 이 칸부터. */
  onPasteRange: (text: string, atRow: number, atColumn: string) => void
  /** 한 줄을 넣을지 끄고 켠다. `id` 가 `null` 이면 **보이는 줄 전부**다. */
  onInclude: (id: number | null, included: boolean) => void
  disabled: boolean
}) {
  const filledRows = rows.filter(filled)
  const allOn = filledRows.length > 0 && filledRows.every((one) => one.included)
  return (
    <div className="min-h-0 flex-1 overflow-auto rounded-md border">
      <table className="w-max border-collapse text-xs">
        <thead className="bg-muted/60 sticky top-0 z-10">
          <tr>
            <th className="border-b border-r px-2 py-1">
              {/* 전부 켜고 끄기. 20줄을 빼려고 20번 누르게 하지 않는다. */}
              <input
                type="checkbox"
                aria-label="전부 넣기"
                checked={allOn}
                onChange={(event) => onInclude(null, event.target.checked)}
                disabled={disabled || filledRows.length === 0}
              />
            </th>
            <th className="text-muted-foreground border-b border-r px-2 py-1 font-normal">
              #
            </th>
            {/* **이유가 맨 앞이다.** 오른쪽 열에서 걸린 문제는 붉은 칸이 화면 밖이다. */}
            <th className="border-b border-r px-2 py-1 text-left font-medium">확인</th>
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
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const bad = new Map(
              row.problems.filter((one) => one.field).map((one) => [one.field, one.message]),
            )
            const notes = row.problems.filter((one) => !one.field).map((one) => one.message)
            const willChange = new Map(
              row.changes.map((one) => [
                one.field,
                `${one.before ?? '(없음)'} → ${one.after ?? '(없음)'}`,
              ]),
            )
            // 이미 있는데 바뀔 것도 문제도 없는 줄 — 손댈 것이 없다는 사실을 말해 준다.
            const same = row.exists && row.problems.length === 0 && row.changes.length === 0
            return (
              <tr
                key={row.id}
                className={cn(
                  notes.length > 0 && 'bg-amber-50',
                  // 꺼진 줄은 흐리게 — 안 들어간다는 것이 한눈에 보여야 한다.
                  !row.included && 'opacity-50',
                )}
              >
                <td className="border-b border-r px-2 py-1 text-center">
                  {filled(row) && (
                    <input
                      type="checkbox"
                      aria-label={`${index + 1}번째 줄 넣기`}
                      checked={row.included}
                      onChange={(event) => onInclude(row.id, event.target.checked)}
                      disabled={disabled}
                    />
                  )}
                </td>
                <td className="text-muted-foreground border-b border-r px-2 py-1 text-right font-mono">
                  {index + 1}
                </td>
                <td
                  className="max-w-64 border-b border-r px-2 py-1 whitespace-normal"
                  title={row.problems.map((one) => one.message).join('\n')}
                >
                  {row.problems.length > 0 ? (
                    // 첫 둘만 펼치고 나머지는 수로 접는다 — 한 줄에 다섯 문제가 붙으면
                    // 표가 그 줄 하나로 세로로 늘어난다. 마우스를 얹으면 전부 나온다.
                    <span className="text-amber-700">
                      {row.problems
                        .slice(0, 2)
                        .map((one) => one.message)
                        .join(' · ')}
                      {row.problems.length > 2 && ` 외 ${row.problems.length - 2}`}
                    </span>
                  ) : row.exists && row.changes.length > 0 ? (
                    <span className="text-sky-800">갱신 {row.changes.length}칸</span>
                  ) : same ? (
                    <span className="text-muted-foreground">변경 없음</span>
                  ) : null}
                </td>
                {columns.map((one) => {
                  const said = bad.get(one.key)
                  const diff = willChange.get(one.key)
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
                            onPasteRange(text, row.id, one.key)
                          }
                        }}
                        disabled={disabled}
                        // **틀린 칸을 칠한다.** 무엇이 틀렸는지는 마우스를 얹으면
                        // 나오고, 아래 목록에도 그대로 있다.
                        title={said ?? diff ?? ''}
                        className={cn(
                          'w-32 bg-transparent px-2 py-1 outline-none',
                          'focus:bg-background focus:ring-ring focus:ring-1',
                          diff && 'bg-sky-50 text-sky-800 ring-1 ring-sky-300',
                          said && 'bg-red-50 text-red-700 ring-1 ring-red-300',
                        )}
                      />
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

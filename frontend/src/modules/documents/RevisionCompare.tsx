/**
 * 두 판을 견준다 — **개정이 오면 무엇을 다시 봐야 하는가.**
 *
 * 「전부 다시」 는 그날 일을 멈추고, 「아무것도 안 봄」 은 바뀐 조건을 놓친다. 그 사이를
 * 이 표가 메운다 — 더해진 시험 · 없어진 시험 · **조건이 바뀐 시험** 셋으로 가른다.
 *
 * 바뀐 것은 **어디가 어떻게** 까지 보여 준다(85 degC 이상 → 95 degC 이상). 「N건 바뀜」
 * 으로 접으면 사람이 다시 열어 봐야 하고, 그 수고를 없애려고 만든 자리다.
 */

import { useState } from 'react'

import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { Button } from '@/shared/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import { useResource } from '@/shared/hooks/useResource'
import type { SpecDocumentRevision } from '@/modules/documents/api'
import { reliabilityApi } from '@/modules/reliability/api'

export function RevisionCompare({ revisions }: { revisions: SpecDocumentRevision[] }) {
  // 목록은 나중 판이 먼저다 — 대개 궁금한 것은 「최신판이 이전과 뭐가 다른가」 다.
  const [after, setAfter] = useState(revisions[0]?.id ?? '')
  const [before, setBefore] = useState(revisions[1]?.id ?? '')
  const found = useResource(
    () =>
      before && after && before !== after
        ? reliabilityApi.compareRevisions(before, after)
        : Promise.resolve(null),
    [before, after],
  )

  // 판이 하나뿐이면 견줄 것이 없다 — 빈 칸을 세워 두지 않는다.
  if (revisions.length < 2) return null
  const body = found.data

  return (
    <section className="space-y-2">
      <h3 className="text-sm font-medium">판 견주기</h3>
      <div className="flex flex-wrap items-center gap-2">
        <Picker value={before} onChange={setBefore} rows={revisions} label="앞 판" />
        <span className="text-muted-foreground text-sm">→</span>
        <Picker value={after} onChange={setAfter} rows={revisions} label="뒤 판" />
        <Button size="sm" variant="outline" onClick={() => found.reload()}>
          다시 보기
        </Button>
      </div>

      <ErrorNotice error={found.error} />

      {body && (
        <div className="space-y-2 rounded-md border p-2 text-sm">
          <p className="text-muted-foreground text-xs">
            {body.before.label}({body.before.test_count}건) → {body.after.label}(
            {body.after.test_count}건) · 그대로 {body.unchanged_count}건
          </p>
          <Group title="더해진 시험" rows={body.added.map((one) => one.name)} />
          <Group
            title="없어진 시험"
            rows={body.removed.map((one) => one.name)}
            hint="앞 판의 줄은 그대로 남습니다 — 뒤 판에 없다는 뜻입니다."
          />
          {body.changed.length > 0 && (
            <div className="space-y-1">
              <p className="font-medium">조건이 바뀐 시험 {body.changed.length}건</p>
              <ul className="space-y-1">
                {body.changed.map((one) => (
                  <li key={one.after_id} className="rounded-md border p-2">
                    <p className="font-medium">{one.name}</p>
                    <ul className="text-muted-foreground space-y-0.5 text-xs">
                      {one.differences.map((row) => (
                        <li key={row.at}>
                          {row.at} — {row.before ?? '(없음)'} → {row.after ?? '(없음)'}
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {body.added.length === 0 &&
            body.removed.length === 0 &&
            body.changed.length === 0 && (
              // **0 은 「안 봤다」 가 아니라 「볼 것이 없다」 다.** 그 둘을 구별해 말한다.
              <p className="text-muted-foreground">
                두 판의 시험이 같습니다 — 다시 볼 것이 없습니다.
              </p>
            )}
        </div>
      )}
    </section>
  )
}

function Group({ title, rows, hint }: { title: string; rows: string[]; hint?: string }) {
  if (rows.length === 0) return null
  return (
    <div className="space-y-0.5">
      <p className="font-medium">
        {title} {rows.length}건
      </p>
      {hint && <p className="text-muted-foreground text-xs">{hint}</p>}
      <ul className="text-muted-foreground text-xs">
        {rows.map((one) => (
          <li key={one}>{one}</li>
        ))}
      </ul>
    </div>
  )
}

function Picker({
  value,
  onChange,
  rows,
  label,
}: {
  value: string
  onChange: (next: string) => void
  rows: SpecDocumentRevision[]
  label: string
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="w-32" aria-label={label}>
        <SelectValue placeholder={label} />
      </SelectTrigger>
      <SelectContent>
        {rows.map((one) => (
          <SelectItem key={one.id} value={one.id}>
            {one.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

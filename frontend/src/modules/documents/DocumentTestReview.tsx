/**
 * 한 규격서에서 올라온 시험을 **문서 단위로 검토한다.**
 *
 * AI 가 규격서 한 권에서 시험 스무 건을 뽑아 올린다. 그 스무 줄은 **같은 실수를 함께
 * 한다** — 한 번에 읽고 한 번에 옮겨 적은 것이라, 단위를 잘못 읽었으면 스무 줄이 전부
 * 틀렸고 조건 하나를 빠뜨렸으면 스무 줄에 전부 없다. 한 건씩 흩어 놓고 보면 그 결이 안
 * 보이고, 사람은 같은 오답을 스무 번 통과시킨다.
 *
 * 그래서 **검토하는 자리를 문서 옆에 둔다.** 사업부 화면에도 같은 줄이 서지만 거기서는
 * 다른 문서에서 온 줄과 섞인다 — 섞이면 「이 문서가 통째로 잘못됐다」 를 못 읽는다.
 *
 * 고치는 것은 여기서 안 한다. 한 줄이 미심쩍으면 이름을 눌러 그 사업부 화면으로 간다 —
 * 검토용 편집 화면을 따로 두면 두 벌이 되고, 그 둘은 반드시 갈라진다.
 */

import { Link } from 'react-router-dom'

import { BulkBar } from '@/shared/components/BulkBar'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { Button } from '@/shared/components/ui/button'
import { useResource } from '@/shared/hooks/useResource'
import { useSelection } from '@/shared/hooks/useSelection'
import { CandidateBadge, isCandidate } from '@/modules/reliability/CandidateReview'
import { reliabilityApi } from '@/modules/reliability/api'
import { useBulkRunner } from '@/modules/reliability/useBulkRunner'
import type { BulkAction } from '@/modules/reliability/api'

export function DocumentTestReview({ documentId }: { documentId: string }) {
  const tests = useResource(() => reliabilityApi.byDocument(documentId), [documentId])
  const rows = tests.data?.items ?? []
  // 한 문서에서 나온 줄이 한 쪽을 넘으면 그 사실을 말한다 — 안 말하면 「이게 전부」 로 읽힌다.
  const more = (tests.data?.total ?? 0) - rows.length
  // **고를 수 있는 것은 고칠 수 있는 것뿐이다.** 남의 사업부 줄까지 골라지면, 누른 사람은
  // 「12건 실패」 를 받고 무엇이 왜 막혔는지 세어 보게 된다.
  const editable = rows.filter((one) => one.can_edit)
  const picked = useSelection(editable.map((one) => one.id))
  /**
   * 끊어 보내고, **막히면 말한다** — 사업부 목록과 같은 것 하나를 쓴다.
   *
   * 여기도 `catch` 가 없어서 실패가 조용히 사라지고 있었다. 이 자리는 한 쪽(쉰 건)만
   * 고를 수 있어 500 상한에 안 닿지만, 403·409 는 얼마든지 난다.
   */
  const bulk = useBulkRunner(() => {
    picked.clear()
    tests.reload()
  })

  function runBulk(action: BulkAction, reason?: string) {
    void bulk.run(picked.ids, action, reason)
  }

  if (rows.length === 0) {
    return tests.data ? null : <ErrorNotice error={tests.error} />
  }

  const pending = rows.filter(isCandidate).length
  // **표시일 뿐 권한이 아니다** — 서버가 줄마다 `can_edit` 을 판정한다.
  const canEdit = editable.length > 0

  return (
    <section className="space-y-2">
      <h3 className="text-sm font-medium">
        이 규격서에서 올라온 시험 {tests.data?.total ?? rows.length}건
        {more > 0 && (
          <span className="text-muted-foreground ml-1 text-xs font-normal">
            (앞 {rows.length}건만 보입니다)
          </span>
        )}
        {pending > 0 && (
          // **문서 단위로 세어 준다.** 「확인 전 12건」 이 안 보이면 아무도 안 연다.
          <span className="text-destructive ml-2">확인 전 {pending}건</span>
        )}
      </h3>

      <ErrorNotice error={bulk.error ?? tests.error} />

      {canEdit && (
        <>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              aria-label="이 문서의 시험 전부 고르기"
              checked={picked.allPicked}
              ref={(box) => {
                // 하나라도 골랐지만 전부는 아니면 **반쯤 찬 모양** — 「전부 골랐다」 로
                // 읽히면 그대로 지우기를 누른다.
                if (box) box.indeterminate = picked.somePicked
              }}
              onChange={picked.toggleAll}
            />
            <span className="text-muted-foreground text-xs">
              고칠 수 있는 {editable.length}건 전부 고르기
            </span>
          </div>
          <BulkBar
            count={picked.ids.length}
            onClear={picked.clear}
            busy={bulk.busy}
            outcome={bulk.outcome}
          >
            <Button size="sm" disabled={bulk.busy} onClick={() => runBulk('confirm')}>
              확인
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={bulk.busy}
              onClick={() => {
                // **사유를 받는다** — 없으면 AI 가 무엇을 자주 틀리는지 셀 수 없다.
                const said = window.prompt(
                  `${picked.ids.length}건을 반려합니다. 사유를 적어 주십시오`,
                )
                if (said?.trim()) runBulk('reject', said.trim())
              }}
            >
              반려
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={bulk.busy}
              onClick={() => {
                // **확정을 푸는 것이라 사유를 받는다** — 문서 단위로 다시 볼 때 한 번에
                // 푸는 일이 실제로 있다(개정본이 왔거나, 원문을 다시 파싱하려 할 때).
                const said = window.prompt(
                  `${picked.ids.length}건의 확정을 풀어 다시 후보로 돌립니다. 사유를 적어 주십시오`,
                )
                if (said?.trim()) runBulk('reopen', said.trim())
              }}
            >
              다시 후보로
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={bulk.busy}
              onClick={() => {
                if (window.confirm(`${picked.ids.length}건을 지웁니다. 되돌릴 수 없습니다.`)) {
                  runBulk('delete')
                }
              }}
            >
              지우기
            </Button>
          </BulkBar>
        </>
      )}

      <ul className="divide-y rounded-md border">
        {rows.map((row) => (
          <li key={row.id} className="flex items-center gap-2 p-2">
            {canEdit && (
              <input
                type="checkbox"
                aria-label={`${row.name} 고르기`}
                checked={picked.has(row.id)}
                disabled={!row.can_edit}
                onChange={() => picked.toggle(row.id)}
              />
            )}
            {/* 한 줄이 미심쩍으면 그 사업부 화면에서 읽고 고친다 — 여기서는 안 고친다. */}
            <Link
              to={`/reliability-tests/${row.division_code}`}
              className="flex-1 text-sm hover:underline"
            >
              {row.name}
            </Link>
            <span className="text-muted-foreground text-xs">{row.division_name}</span>
            <CandidateBadge row={row} />
          </li>
        ))}
      </ul>
    </section>
  )
}

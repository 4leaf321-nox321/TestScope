/**
 * 시험 항목 제안 검토 — **같은 말은 한 번만 판단한다.**
 *
 * 시험 항목 축은 닫혀 있다. 검색의 첫 축이라 오타 하나가 값이 되면 그 뒤로 아무도 못
 * 찾기 때문이고, 그래서 AI 가 값을 못 더하는 것은 옳다. 그런데 못 더하는 쪽에 **말할
 * 자리도** 없어서, 스무 건 중 아홉 건이 시험 항목 없이 들어오고 왜 비었는지가 아무 데도
 * 안 남았다.
 *
 * 여기서는 같은 말이 한 줄로 서고(띄어쓰기·대소문자를 지운 비교키), 관리자가 한 번 정하면
 * **그 말을 낸 시험 전부에** 걸린다 — 스무 건을 스무 번 여는 것이 이 화면이 없앤 일이다.
 *
 * 건수가 큰 것이 먼저다: 스무 시험에서 나온 말은 축에 없는 것이 거의 확실하고, 한 번 나온
 * 말은 오타일 수 있다.
 */

import { useState } from 'react'

import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { SearchablePicker } from '@/shared/components/SearchablePicker'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { useResource } from '@/shared/hooks/useResource'
import { reliabilityApi } from '@/modules/reliability/api'
import { vocabularyApi } from '@/modules/vocabulary/api'

export default function ItemProposalsPage() {
  const groups = useResource(() => reliabilityApi.proposalGroups(), [])
  const terms = useResource(() => vocabularyApi.terms('test_item'), [])
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [drafts, setDrafts] = useState<Record<string, string>>({})

  async function decide(
    normalized: string,
    body: { term_id?: string | null; new_value?: string | null },
  ) {
    setBusy(normalized)
    setError(null)
    try {
      await reliabilityApi.decideProposal({ normalized, ...body })
      groups.reload()
      terms.reload()
    } catch (failed) {
      setError(failed as Error)
    } finally {
      setBusy(null)
    }
  }

  const rows = groups.data ?? []
  const options = (terms.data ?? []).map((one) => ({ id: one.id, label: one.value }))

  return (
    <div className="space-y-6">
      <PageHeader
        title="시험 항목 제안"
        description="AI 가 문서에서 읽었지만 시험 항목 축에 없던 말입니다. 축에 세우거나 기존 값에 이으면, 그 말을 낸 시험 전부에 한 번에 걸립니다."
      />

      <ErrorNotice error={error ?? groups.error} />

      {groups.data && rows.length === 0 ? (
        <EmptyState
          title="검토할 제안이 없습니다"
          hint="AI 가 시험을 올리면서 축에 없는 말을 만나면 여기에 쌓입니다."
        />
      ) : (
        <ul className="space-y-3">
          {rows.map((group) => (
            <li key={group.normalized} className="space-y-2 rounded-md border p-3">
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="text-base font-medium">{group.text}</span>
                <span className="text-muted-foreground text-sm">
                  시험 {group.count}건에서 나왔습니다
                </span>
              </div>

              <ul className="text-muted-foreground space-y-0.5 text-sm">
                {group.proposals.map((one) => (
                  <li key={one.id}>
                    {one.reliability_test_name}
                    {one.text !== group.text && ` — 「${one.text}」 로 적힘`}
                    {one.note && ` · ${one.note}`}
                  </li>
                ))}
              </ul>

              <div className="flex flex-wrap items-center gap-2">
                <SearchablePicker
                  options={options}
                  value=""
                  onChange={(id) => id && void decide(group.normalized, { term_id: id })}
                  placeholder="기존 값에 잇기"
                  detailTitle="시험 항목"
                  className="w-56"
                />
                <Input
                  value={drafts[group.normalized] ?? group.text}
                  onChange={(event) =>
                    setDrafts((before) => ({
                      ...before,
                      [group.normalized]: event.target.value,
                    }))
                  }
                  aria-label={`${group.text} 새 값 이름`}
                  className="w-56"
                  maxLength={200}
                />
                <Button
                  size="sm"
                  disabled={busy === group.normalized}
                  onClick={() =>
                    void decide(group.normalized, {
                      new_value: drafts[group.normalized] ?? group.text,
                    })
                  }
                >
                  축에 세우기
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy === group.normalized}
                  onClick={() => void decide(group.normalized, {})}
                >
                  아니오
                </Button>
              </div>
              {/* **원문을 고쳐 세울 수 있게 둔다** — 「염수분무(5%)」 는 문서의 말이지
                  축의 값이 아니다. 다만 무엇을 고쳤는지는 위의 원문 줄에 남는다. */}
              <p className="text-muted-foreground text-xs">
                축에 세울 이름은 고칠 수 있습니다 — 문서의 말이 곧 축의 값은 아닙니다.
                「아니오」 는 제안을 닫고 시험 항목을 안 겁니다.
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

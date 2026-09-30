/**
 * 카탈로그 기종 등록 요청 검토 — **같은 기종은 한 번만 판단한다.**
 *
 * 장비를 등록할 때 카탈로그에 그 기종이 없으면 비워 두게 되어 있다. 그 안내는 맞다:
 * 비슷한 기종을 고르면 그 장비의 하중·온도가 **남의 것**이 되고, 조건으로 장비를 찾는
 * 화면이 그 수치로 답한다. 그런데 비워 둔 다음에 왜 비었는지가 아무 데도 안 남았다 —
 * 제조사·모델명 글자는 표시용이라 아무도 그것을 일감으로 세지 않았다.
 *
 * 여기서는 같은 기종 요청이 한 줄로 서고(제조사+모델명의 비교키), 관리자가 한 번 정하면
 * **그 기종을 요청한 장비 전부가 이어진다** — 세워 놓고 장비를 하나씩 열어 다시 고르는
 * 것이 이 화면이 없앤 일이다.
 *
 * 건수가 큰 것이 먼저다: 다섯 부서가 요청한 기종은 카탈로그에 있어야 할 것이 거의
 * 확실하고, 한 번 나온 것은 자작 장비일 수 있다.
 */

import { useState } from 'react'

import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { SearchablePicker } from '@/shared/components/SearchablePicker'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { useResource } from '@/shared/hooks/useResource'
import { modelProposalApi, seriesApi } from '@/modules/equipment/api'

/** 계열 고르기에 쓸 만큼만 받는다 — 서버 상한이 200이다. */
const SERIES_LIMIT = 200

export default function ModelProposalsPage() {
  const groups = useResource(() => modelProposalApi.groups(), [])
  const series = useResource(() => seriesApi.list({ limit: SERIES_LIMIT }), [])
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [names, setNames] = useState<Record<string, string>>({})
  const [picked, setPicked] = useState<Record<string, string>>({})

  async function decide(
    normalized: string,
    body: { series_id?: string | null; name?: string | null },
  ) {
    setBusy(normalized)
    setError(null)
    try {
      await modelProposalApi.decide({ normalized, ...body })
      groups.reload()
    } catch (failed) {
      setError(failed as Error)
    } finally {
      setBusy(null)
    }
  }

  const rows = groups.data ?? []
  const options = (series.data?.items ?? []).map((one) => ({
    id: one.id,
    label: one.name,
    detail: one.maker ?? undefined,
  }))

  return (
    <div className="space-y-6">
      <PageHeader
        title="기종 등록 요청"
        description="장비를 등록하면서 카탈로그에서 못 찾은 기종입니다. 계열을 고르고 세우면, 그 기종을 요청한 장비 전부가 한 번에 이어집니다."
      />

      <ErrorNotice error={error ?? groups.error ?? series.error} />

      {groups.data && rows.length === 0 ? (
        <EmptyState
          title="검토할 요청이 없습니다"
          hint="장비를 등록하면서 카탈로그에 없는 기종을 만나면 여기에 쌓입니다."
        />
      ) : (
        <ul className="space-y-3">
          {rows.map((group) => (
            <li key={group.normalized} className="space-y-2 rounded-md border p-3">
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="text-base font-medium">{group.text}</span>
                <span className="text-muted-foreground text-sm">
                  장비 {group.count}대가 요청했습니다
                </span>
              </div>

              <ul className="text-muted-foreground space-y-0.5 text-sm">
                {group.proposals.map((one) => (
                  <li key={one.id}>
                    {one.equipment_asset_no} {one.equipment_name}
                    {one.text !== group.text && ` — 「${one.text}」 로 적힘`}
                    {one.note && ` · ${one.note}`}
                  </li>
                ))}
              </ul>

              <div className="flex flex-wrap items-center gap-2">
                {/* **계열을 먼저 고른다.** 제조사·분류·시험 항목은 계열이 갖고, 기종에는
                    그 기종만의 수치 사양이 온다(ADR 0006). */}
                <SearchablePicker
                  options={options}
                  value={picked[group.normalized] ?? ''}
                  onChange={(id) =>
                    setPicked((before) => ({ ...before, [group.normalized]: id }))
                  }
                  placeholder="어느 계열에"
                  detailTitle="장비 계열"
                  className="w-64"
                />
                <Input
                  value={names[group.normalized] ?? group.text}
                  onChange={(event) =>
                    setNames((before) => ({
                      ...before,
                      [group.normalized]: event.target.value,
                    }))
                  }
                  aria-label={`${group.text} 기종 이름`}
                  className="w-56"
                  maxLength={150}
                />
                <Button
                  size="sm"
                  disabled={busy === group.normalized || !picked[group.normalized]}
                  onClick={() =>
                    void decide(group.normalized, {
                      series_id: picked[group.normalized],
                      name: names[group.normalized] ?? group.text,
                    })
                  }
                >
                  카탈로그에 세우기
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
              {/* **이름은 고칠 수 있게 둔다** — 라벨의 글자가 곧 기종명은 아니다. 다만
                  계열 이름을 섞지 않는다: 섞으면 `6800 68FM-300` 과 `68FM-300` 이 별개
                  기종으로 갈리고, 그 둘을 나중에 묶을 방법이 없다. */}
              <p className="text-muted-foreground text-xs">
                기종 이름은 고칠 수 있습니다 — <strong>계열 이름을 섞지 마십시오.</strong>{' '}
                「아니오」 는 요청을 닫고 장비는 미연결로 둡니다(자작 장비 등).
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

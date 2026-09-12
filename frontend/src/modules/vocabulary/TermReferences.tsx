/**
 * 값의 쓰임 — **무엇이 이 값을 가리키나, 그리고 그 자리에서 떼거나 옮긴다.**
 *
 * 쓰임 수 「12」 는 「지워도 되나」 에는 답하지만 「그 12 가 무엇인가」 에는 답하지 않는다.
 * 합치거나 폐기하기 전에 사람이 보는 것은 목록이다. 그리고 잘못 붙은 줄 하나를 고치러
 * 계열 화면까지 가게 하면 안 고친다 — 여기서 뗀다.
 *
 * ## 세 가지 떼기
 *
 *     연결 줄을 지운다   계열의 시험 항목 · 장비의 시험 항목 · 물성 연결
 *     칸을 비운다        계열의 제조사 · 시험법의 시험 항목
 *     못 뗀다            장비의 거점 — 비울 수 없는 칸이라 **옮기기만** 된다
 *
 * 어느 쪽인지는 서버가 종류마다 말한다(`detach`). 화면이 짐작하면 「왜 이건 안 떼지」 를
 * 사람이 되짚어야 한다.
 */

import { useState } from 'react'
import { ArrowRightLeft, ExternalLink, Unlink } from 'lucide-react'
import { Link } from 'react-router-dom'

import { ApiError } from '@/shared/api/client'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { SearchablePicker } from '@/shared/components/SearchablePicker'
import { Button } from '@/shared/components/ui/button'
import { useResource } from '@/shared/hooks/useResource'
import { vocabularyApi } from '@/modules/vocabulary/api'
import type { Term } from '@/modules/vocabulary/api'

const DETACH_LABEL: Record<string, string> = {
  delete: '연결 줄을 지웁니다',
  null: '칸을 비웁니다',
  none: '비울 수 없는 칸 — 옮기기만 됩니다',
}

export function TermReferences({
  term,
  siblings,
  onChanged,
}: {
  term: Term
  /** 같은 축의 다른 값 — 옮길 대상. */
  siblings: Term[]
  onChanged: () => void
}) {
  const groups = useResource(() => vocabularyApi.references(term.id), [term.id])
  /** 옮기는 중인 줄 — `${kind}/${rowId}`. 한 번에 하나. */
  const [moving, setMoving] = useState<string | null>(null)
  const [target, setTarget] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | Error | null>(null)

  async function run(work: () => Promise<unknown>) {
    setBusy(true)
    setError(null)
    try {
      await work()
      groups.reload()
      onChanged()
      setMoving(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  const total = (groups.data ?? []).reduce((sum, one) => sum + one.rows.length, 0)
  const options = siblings
    .filter((one) => one.id !== term.id && one.status === 'active')
    .map((one) => ({ id: one.id, label: one.value, detail: one.code }))

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <p className="text-sm font-medium">쓰임</p>
        {groups.data && (
          <span className="text-muted-foreground text-xs">
            {total === 0 ? '아무것도 이 값을 가리키지 않습니다' : `${total}군데`}
          </span>
        )}
      </div>
      <ErrorNotice error={groups.error ?? error} />
      {(groups.data ?? []).map((group) => (
        <div key={group.key} className="rounded-md border">
          <div className="bg-muted/50 flex items-baseline justify-between px-3 py-1.5">
            <span className="text-sm">
              {group.label} <span className="text-muted-foreground">{group.rows.length}</span>
            </span>
            <span className="text-muted-foreground text-xs">{DETACH_LABEL[group.detach]}</span>
          </div>
          <ul className="divide-y">
            {group.rows.map((row) => {
              const key = `${group.key}/${row.id}`
              return (
                <li key={row.id} className="space-y-1 px-3 py-1.5 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="min-w-0 flex-1 truncate">
                      {row.href ? (
                        <Link
                          to={row.href}
                          className="inline-flex items-center gap-1 hover:underline"
                        >
                          {row.label}
                          <ExternalLink className="size-3 opacity-60" />
                        </Link>
                      ) : (
                        row.label
                      )}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 text-xs"
                      aria-label={`${row.label} 옮기기`}
                      disabled={busy || options.length === 0}
                      onClick={() => {
                        setMoving(moving === key ? null : key)
                        setTarget('')
                      }}
                    >
                      <ArrowRightLeft className="mr-1 size-3" />
                      옮기기
                    </Button>
                    {group.detach !== 'none' && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="hover:text-destructive h-7 px-2 text-xs"
                        aria-label={`${row.label} 떼기`}
                        disabled={busy}
                        onClick={() =>
                          window.confirm(
                            `「${row.label}」 에서 이 값을 뗍니다 — ${DETACH_LABEL[group.detach]}. 계속할까요?`,
                          ) &&
                          void run(() =>
                            vocabularyApi.detachReference(term.id, group.key, row.id),
                          )
                        }
                      >
                        <Unlink className="mr-1 size-3" />
                        떼기
                      </Button>
                    )}
                  </div>
                  {moving === key && (
                    <div className="flex flex-wrap items-center gap-2 pb-1">
                      <SearchablePicker
                        options={options}
                        value={target}
                        onChange={setTarget}
                        placeholder="옮길 값"
                        className="w-64"
                      />
                      <Button
                        size="sm"
                        className="h-7"
                        disabled={!target || busy}
                        onClick={() =>
                          void run(() =>
                            vocabularyApi.reassignReference(
                              term.id,
                              group.key,
                              row.id,
                              target,
                            ),
                          )
                        }
                      >
                        옮기기
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7"
                        onClick={() => setMoving(null)}
                      >
                        취소
                      </Button>
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      ))}
    </div>
  )
}

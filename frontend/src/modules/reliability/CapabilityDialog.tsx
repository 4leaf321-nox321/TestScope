/**
 * 「이 시험, 어느 장비로 돌리나」 — **조건 속성이 그대로 장비 판정이 된다.**
 *
 * 지금까지 이 표가 준 답은 「인장 되는 장비 12대」 였다. 그런데 그 시험은 -40 ~ 125 °C 에서
 * 도는데, 12대 중 그 온도를 내는 것이 몇인지는 사람이 장비를 하나씩 열어 봐야 했다 — 그
 * 순간 이 시스템은 전화 돌리기를 한 단계 줄였을 뿐 없애지는 못한다.
 *
 * 판정은 **서버가, 장비 찾기와 같은 규칙으로** 한다. 화면은 그 답을 옮겨 적고, 세 가지를 꼭
 * 보여 준다: 물은 조건 수 · 못 옮겨 뺀 조건 · 안 되는 것으로 빠진 장비 수. 마지막이 있어야
 * 「0대」 가 「장비가 없다」 인지 「조건이 안 맞는다」 인지 갈린다.
 */

import { Link } from 'react-router-dom'
import { AlertTriangle, Loader2 } from 'lucide-react'

import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table'
import { useResource } from '@/shared/hooks/useResource'
import { reliabilityApi } from '@/modules/reliability/api'
import type { ReliabilityTest } from '@/modules/reliability/api'

/** 판정의 우리말. **안 되는 것은 아예 안 온다** — 여기 있는 것은 전부 후보다. */
const VERDICTS: Record<string, { label: string; tone: string; hint: string }> = {
  match: { label: '가능', tone: 'text-emerald-600', hint: '조회 조건 모두 충족' },
  accessory: {
    label: '부속 필요',
    tone: 'text-sky-600',
    hint: '챔버·노 장착 시 충족되는 조건 있음. 해당 기종과 보유 대수는 줄마다 표시',
  },
  partial: {
    label: '일부 모름',
    tone: 'text-amber-600',
    hint: '일부 조건이 이 장비에 미기재. 불가를 뜻하지 않음',
  },
  unknown: {
    label: '모름',
    tone: 'text-muted-foreground',
    hint: '조회 조건 전부 이 장비에 미기재',
  },
}

export function CapabilityDialog({
  test,
  onClose,
}: {
  test: ReliabilityTest
  onClose: () => void
}) {
  const answer = useResource(() => reliabilityApi.capability(test.id), [test.id])
  const data = answer.data

  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>{test.name}: 수행 가능 장비</DialogTitle>
          <DialogDescription>
            이 시험의 조건 속성을 검색 조건으로 사용한 시험 항목별 장비 조회. 부서 제한
            없음(다른 부서 장비 포함).
          </DialogDescription>
        </DialogHeader>

        {answer.error && <ErrorNotice error={answer.error} />}
        {answer.loading && (
          <div className="text-muted-foreground flex items-center gap-2 py-8 text-sm">
            <Loader2 className="size-4 animate-spin" />
            장비를 불러오는 중…
          </div>
        )}

        {data && (
          <div className="space-y-6">
            <p className="text-muted-foreground text-sm">
              {data.conditions_asked === 0
                ? '조건 속성 없음. 시험 항목만으로 조회. 조건 입력 시 결과가 더 좁혀짐.'
                : `조건 ${data.conditions_asked}개로 조회 (범위 하나는 위·아래 두 조건으로 계산).`}
            </p>

            {/**
             * **묶음이 둘 이상이면 묶음마다 따로 답한다.**
             *
             * 주 조건 80 °C 와 「불량 시」 70 °C 를 한꺼번에 물으면 아무도 요구하지 않는
             * 조건이 만들어지고, 그 조건으로 장비가 걸러지는데 왜 걸러졌는지 화면 어디에도
             * 안 나왔다. 아래 표는 **모든 묶음을 한꺼번에** 만족하는 장비다 — 그것도 답이지만
             * (예외까지 통째로 돌릴 장비), 유일한 답이 아니었던 것이 문제였다.
             */}
            {(data.sets ?? []).length > 0 && (
              <div className="space-y-2 rounded-md border p-3">
                <p className="text-sm font-medium">조건 묶음별 결과</p>
                <ul className="space-y-1 text-sm">
                  {(data.sets ?? []).map((one) => (
                    <li key={one.set_label ?? '(기본)'} className="flex flex-wrap gap-x-2">
                      <span className="font-medium">{one.set_label || '이름 없는 한 벌'}</span>
                      <span className="text-muted-foreground">
                        조건 {one.conditions_asked}개 ·{' '}
                        {one.items
                          .map((item) => `${item.value} ${item.total}대`)
                          .join(' · ') || '적용 시험 항목 없음'}
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="text-muted-foreground text-xs">
                  아래 표: <strong>모든 묶음을 동시에</strong> 만족하는 장비. 예외 경로까지
                  포함해 이 시험 전체 수행 가능.
                </p>
              </div>
            )}

            {data.skipped.length > 0 && (
              // **조용히 빼지 않는다.** 뺀 줄 모르면 조건을 다 본 것처럼 읽힌다.
              <div className="flex gap-2 rounded-md border border-amber-300 p-3 text-sm">
                <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600" />
                <div className="space-y-1">
                  <p className="font-medium">조회에서 제외된 조건 있음</p>
                  <ul className="text-muted-foreground space-y-0.5">
                    {data.skipped.map((one) => (
                      <li key={one.label}>
                        {one.label}: {one.reason}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {data.items.length === 0 ? (
              <EmptyState
                title="적용 시험 항목 없음"
                hint="시험 항목 지정 후 장비 조회 가능. ‘수정’에서 선택."
              />
            ) : (
              data.items.map((item) => (
                <section key={item.term_id} className="space-y-2">
                  <div className="flex flex-wrap items-baseline gap-2">
                    <Link
                      to={`/catalog/test-items/${item.term_id}`}
                      className="font-medium hover:underline"
                    >
                      {item.value}
                    </Link>
                    <span className="text-muted-foreground text-sm">
                      {item.total}대
                      {item.total > item.hits.length ? ` (앞 ${item.hits.length}대)` : ''}
                      {item.unmet_count > 0
                        ? ` · 조건 불충족으로 제외된 장비 ${item.unmet_count}대`
                        : ''}
                    </span>
                  </div>

                  {item.hits.length === 0 ? (
                    <p className="text-muted-foreground rounded-md border border-dashed p-3 text-sm">
                      {item.unmet_count > 0
                        ? '이 항목 수행 장비는 있으나 조건 불충족. 조건 완화 또는 외부 의뢰 필요.'
                        : '이 시험 항목이 등록된 장비 없음. 장비에 시험 항목 입력 시 검색 가능.'}
                    </p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>장비</TableHead>
                          <TableHead>보유 부서 · 위치</TableHead>
                          <TableHead>담당자</TableHead>
                          <TableHead>판정</TableHead>
                          <TableHead>조건</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {item.hits.map((hit) => {
                          const verdict = VERDICTS[hit.verdict] ?? VERDICTS.unknown
                          return (
                            <TableRow key={hit.equipment_test_item_id}>
                              <TableCell>
                                <Link
                                  to={`/equipment/${hit.equipment_id}`}
                                  className="font-medium hover:underline"
                                >
                                  {hit.equipment_name}
                                </Link>
                                <div className="text-muted-foreground text-xs">
                                  {hit.asset_no}
                                </div>
                              </TableCell>
                              <TableCell className="text-sm">
                                {hit.workspace_name ?? '—'}
                                <div className="text-muted-foreground text-xs">
                                  {[hit.site, hit.location].filter(Boolean).join(' · ') || '—'}
                                </div>
                              </TableCell>
                              {/* **찾은 다음에 연락할 사람.** 없으면 검색은 절반만 한 것이다. */}
                              <TableCell className="text-sm">
                                {hit.contact_name ?? '—'}
                              </TableCell>
                              <TableCell
                                className={`text-sm ${verdict.tone}`}
                                title={verdict.hint}
                              >
                                {verdict.label}
                              </TableCell>
                              <TableCell className="text-xs">
                                {hit.conditions.length === 0 ? (
                                  '—'
                                ) : (
                                  <ul className="space-y-0.5">
                                    {hit.conditions.map((one, index) => (
                                      <li key={`${one.condition_key_id}-${index}`}>
                                        <span className="text-muted-foreground">
                                          {one.condition_label} {one.asked}
                                        </span>{' '}
                                        {one.verdict === 'met'
                                          ? '됨'
                                          : one.verdict === 'accessory'
                                            ? '부속 필요'
                                            : '모름'}
                                        {one.condition_range
                                          ? ` (${one.condition_range})`
                                          : ''}
                                        {/* **무엇을 달면 되는지까지.** 「부속 필요」 만
                                            적으면 사람은 카탈로그를 뒤지러 간다. */}
                                        {one.accessory && (
                                          <span className="text-sky-700">
                                            {`: ${one.accessory.model_name} ${one.accessory.condition_range}`}
                                            {one.accessory.owned_units > 0
                                              ? ` · 보유 ${one.accessory.owned_units}대`
                                              : ' · 미보유'}
                                          </span>
                                        )}
                                      </li>
                                    ))}
                                  </ul>
                                )}
                              </TableCell>
                            </TableRow>
                          )
                        })}
                      </TableBody>
                    </Table>
                  )}
                </section>
              ))
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

/**
 * 신뢰성 시험 **보기** — 줄을 누르면 이것이 열린다. 고치려면 연필이다.
 *
 * 왜 따로 있나: 카드를 **읽으려고** 수정 창을 여는 것은 위험하다. 스물두 칸이 전부 입력칸인
 * 화면에서는 읽다가 글자를 건드리고, 「그림 넣기」 가 읽는 사람 눈앞에 서 있다. 그리고
 * 애초에 고칠 권한이 없는 사람은 연필이 안 보여서 카드를 **열 길이 없었다** — 옆 부서가
 * 무슨 조건으로 시험하는지 보는 것이 이 플랫폼의 쓸모인데도.
 *
 * 그래서 여기에는 **입력칸이 하나도 없다.** 값은 서버가 만든 글자(`display`)를 그대로 쓰고,
 * 긴 글은 줄바꿈을 살리고, 짝·매트릭스는 표로 편다. 그림은 붙은 칸 아래에 읽기 전용으로.
 *
 * **확인 단추는 여기 있다.** 「내용을 읽고 맞으면 ok」 가 후보 검토의 전부이고, 그 읽는
 * 자리가 여기다 — 틀린 칸이 보이면 「수정」 으로 건너간다.
 */

import { useMemo } from 'react'
import type { ReactNode } from 'react'
import { Pencil } from 'lucide-react'

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
import { AttachmentStrip } from '@/modules/attachments/AttachmentStrip'
import { attachmentApi } from '@/modules/attachments/api'
import type { Attachment } from '@/modules/attachments/api'
import { attributeApi } from '@/modules/attributes/api'
import type { AttributeValue } from '@/modules/attributes/api'
import { SECTIONS, anchorOf } from '@/modules/attributes/StandardAttributeFields'
import { CandidateBadge, ReviewBanner } from '@/modules/reliability/CandidateReview'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs'
import { ValueHistory } from '@/modules/reliability/ValueHistory'
import { reliabilityApi } from '@/modules/reliability/api'
import { CardOutline } from '@/modules/reliability/CardOutline'
import type { OutlineItem } from '@/modules/reliability/CardOutline'
import type { ReliabilityTest } from '@/modules/reliability/api'

/** 한 줄에 안 들어가는 것 — 긴 글과 표는 칸을 통째로 쓴다. */
function isWide(row: AttributeValue): boolean {
  if (row.kind === 'pairs' || row.kind === 'matrix') return true
  return (row.text_value ?? '').length > 40 || (row.text_value ?? '').includes('\n')
}

type Pair = { label?: string; value?: number | string }

function pairs(raw: unknown): Pair[] {
  return Array.isArray(raw) ? (raw as Pair[]) : []
}

/** 「A등급 4 · B등급 4」 를 표로 편다 — 줄이 여섯만 돼도 한 줄 글은 안 읽힌다. */
function PairTable({ rows, unit }: { rows: Pair[]; unit: string }) {
  return (
    <ul className="divide-border w-fit min-w-40 divide-y rounded-md border text-sm">
      {rows.map((one, at) => (
        <li key={`${one.label}-${at}`} className="flex justify-between gap-6 px-2.5 py-1">
          <span className="text-muted-foreground">{one.label}</span>
          <span className="font-medium">
            {one.value}
            {unit && ` ${unit}`}
          </span>
        </li>
      ))}
    </ul>
  )
}

/**
 * 이 줄이 어느 묶음의 몇 번째인가.
 *
 * **안 보이면 두 줄이 한 벌로 읽힌다** — 동작 -15 ~ 45 와 저장 -40 ~ 25 가 나란히 서 있는데
 * 이름이 없으면, 읽는 사람은 그 시험이 -40 ~ 45 를 요구한다고 읽는다.
 */
function SetTag({ row }: { row: AttributeValue }) {
  if (!row.set_label && row.step_order === null) return null
  return (
    <span className="bg-muted rounded px-1 py-px text-[10px] font-normal">
      {row.set_label}
      {row.step_order !== null && `${row.set_label ? ' ' : ''}${row.step_order}번째`}
      {row.step_label && ` ${row.step_label}`}
    </span>
  )
}

/**
 * 축에 맞는 값이 없어 남긴 제안 — **「시험 항목 미지정」 옆에 왜가 서야 한다.**
 *
 * 시험 항목 축은 닫혀 있어 AI 가 값을 못 더한다. 그래서 지금까지는 그냥 비웠고, 검토하는
 * 사람은 그 줄을 「안 적은 것」 과 구별할 수 없었다 — 스무 건 중 아홉 건이 그랬다.
 */
function ItemProposals({ testId }: { testId: string }) {
  const rows = useResource(() => reliabilityApi.itemProposals(testId), [testId])
  const listed = rows.data ?? []
  if (listed.length === 0) return null
  return (
    <div className="mt-1 space-y-1 rounded-md border border-amber-300 p-2">
      <p className="text-xs font-medium">축에서 못 찾아 제안으로 남긴 것</p>
      <ul className="space-y-0.5 text-sm">
        {listed.map((one) => (
          <li key={one.id} className="flex flex-wrap items-baseline gap-2">
            <span className="font-medium">{one.text}</span>
            {one.note && <span className="text-muted-foreground text-xs">{one.note}</span>}
            <span className="text-muted-foreground text-xs">
              {one.status === 'open'
                ? '관리자 판단 대기'
                : one.term_value
                  ? `→ ${one.term_value}`
                  : '아니라고 정해짐'}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Value({ row }: { row: AttributeValue }) {
  if (row.kind === 'pairs') return <PairTable rows={pairs(row.json_value)} unit={row.unit} />
  if (row.kind === 'matrix') {
    // 사양 → 등급 → 값. 사양마다 제 표를 준다 — 한 표에 섞으면 어느 사양의 등급인지 흐려진다.
    return (
      <div className="flex flex-wrap gap-4">
        {pairs(row.json_value).map((spec, at) => (
          <div key={`${spec.label}-${at}`} className="space-y-1">
            <p className="text-xs font-medium">{spec.label}</p>
            <PairTable rows={pairs((spec as { entries?: unknown }).entries)} unit={row.unit} />
          </div>
        ))}
      </div>
    )
  }
  if (row.text_value) {
    // **줄바꿈을 살린다.** 절차 네 단계가 한 줄로 붙으면 그것은 절차가 아니다.
    return <p className="text-sm whitespace-pre-line">{row.text_value}</p>
  }
  return <p className="text-sm">{row.display || '—'}</p>
}

export function ReliabilityTestViewDialog({
  test,
  onClose,
  onEdit,
  onChanged,
}: {
  /** 볼 시험. `null` 이면 닫힌 것이다. */
  test: ReliabilityTest | null
  onClose: () => void
  /** 「수정」 — 이 창을 닫고 등록·수정 창을 연다. 없으면 단추를 안 보인다. */
  onEdit?: (row: ReliabilityTest) => void
  /** 확인·되돌리기로 상태가 바뀌었다. */
  onChanged?: (next: ReliabilityTest) => void
}) {
  const open = test !== null
  const testId = test?.id ?? null

  // 칸의 순서는 **정의**가 안다(등록 창과 같은 표). 값은 이름만 갖고 있어서 그것만으로는
  // 「무엇을 왜 → 근거 → 조건 → …」 순서를 못 만든다.
  const defs = useResource(
    () => (open ? attributeApi.definitions('reliability_test') : Promise.resolve([])),
    [open],
  )
  const shots = useResource(
    () =>
      testId
        ? attachmentApi.list('reliability_test', testId)
        : Promise.resolve([] as Attachment[]),
    [testId],
  )

  /** 정의 id → key. 목차와 본문이 같은 자리표를 써야 해서 밖으로 뺀다. */
  const keyOf = useMemo(
    () => new Map((defs.data ?? []).map((one) => [one.id, one.key])),
    [defs.data],
  )

  const grouped = useMemo(() => {
    const values = test?.attributes ?? []
    if (values.length === 0) return []
    // **줄마다 자리를 준다**(칸 id 가 아니라 순번). 묶음이 생기면서 한 칸이 여러 줄이 된다
    // — 칸 id 로 묶으면 동작 -15~45 와 저장 -40~25 중 하나가 화면에서 조용히 사라진다.
    const left = new Map(values.map((one, at) => [at, one]))
    const out: { title: string; rows: AttributeValue[] }[] = []
    for (const section of SECTIONS) {
      const rows: AttributeValue[] = []
      for (const key of section.keys) {
        for (const [at, one] of left) {
          if (keyOf.get(one.definition_id) === key && left.delete(at)) rows.push(one)
        }
      }
      if (section.conditions) {
        // 서버가 준 순서 그대로 — 이름 없는 묶음이 먼저, 묶음 · 차례 · 칸 순이다.
        for (const [at, one] of left) {
          if (one.kind === 'condition' && left.delete(at)) rows.push(one)
        }
      }
      if (rows.length > 0) out.push({ title: section.title, rows })
    }
    // 표에 없는 칸(초안 · 나중에 는 칸)은 자리를 잃지 않고 맨 뒤로.
    if (left.size > 0) out.push({ title: '기타 항목', rows: [...left.values()] })
    return out
  }, [test?.attributes, defs.data])

  /**
   * 왼쪽 목차 — **적힌 칸만 선다.** 보기 창은 읽는 자리라, 없는 칸을 목차에 세워 두면
   * 「왜 빈 자리로 가지」 가 된다(수정 창은 반대로 빈 칸도 세운다 — 채울 자리니까).
   */
  const outline = useMemo(() => {
    const items: OutlineItem[] = []
    if (test?.purpose) {
      items.push({ anchor: anchorOf('section', '목적'), label: '목적' })
    }
    items.push({
      anchor: anchorOf('section', '적용 시험 항목'),
      label: '적용 시험 항목',
    })
    for (const section of grouped) {
      items.push({
        anchor: anchorOf('section', section.title),
        label: section.title,
        children: section.rows
          .filter(
            (row, at) =>
              section.rows.findIndex((one) => one.definition_id === row.definition_id) === at,
          )
          .map((row) => ({
            anchor: anchorOf('field', keyOf.get(row.definition_id) ?? row.definition_id),
            label: row.label,
            filled: true,
          })),
      })
    }
    return items
  }, [grouped, keyOf, test?.purpose])

  const byField = useMemo(() => {
    const out = new Map<string, Attachment[]>()
    for (const one of shots.data ?? []) {
      const key = one.definition_id ?? ''
      out.set(key, [...(out.get(key) ?? []), one])
    }
    return out
  }, [shots.data])

  /**
   * 어느 항목 아래에도 안 그려진 이미지 — **떨어뜨리지 않으려는 그물.**
   *
   * 값이 빈 항목은 갈래에 안 서는데, 그 항목에 이미지가 붙어 있을 수 있다(조건은 아직 못
   * 적었지만 프로파일 그림은 먼저 받아 둔 경우). 그때 이미지가 화면에서 **조용히 사라졌다** —
   * 붙인 사람은 붙인 줄 알고, 읽는 사람은 없는 줄 안다.
   */
  const orphans = useMemo(() => {
    const drawn = new Set(grouped.flatMap((one) => one.rows.map((row) => row.definition_id)))
    const out = new Map<string, { title: string; rows: Attachment[] }>()
    for (const [key, rows] of byField) {
      if (key !== '' && drawn.has(key)) continue
      const title = rows[0]?.definition_label || '항목에 연결되지 않은 이미지'
      const bucket = out.get(title) ?? { title, rows: [] }
      bucket.rows.push(...rows)
      out.set(title, bucket)
    }
    return [...out.values()]
  }, [byField, grouped])

  if (!test) return null

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-h-[88vh] w-[92vw] overflow-y-auto sm:max-w-[92vw] lg:max-w-[1300px]">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            {test.name}
            <CandidateBadge row={test} />
          </DialogTitle>
          <DialogDescription>
            {test.division_name} 가 수행하는 시험입니다. 고치려면 아래 「수정」 을 누르십시오.
          </DialogDescription>
        </DialogHeader>

        <ReviewBanner row={test} onChanged={(next) => onChanged?.(next)} />
        <ErrorNotice error={defs.error ?? shots.error} />

        {/**
         * **이력을 탭으로 가른다.**
         *
         * 판별 이력은 자리(칸·묶음·차례)마다 판을 늘어세우므로, 칸이 스물이면 그만큼
         * 길어진다. 그것을 카드 아래에 이어 두니 창의 대부분이 이력이 되고, 정작 읽으려고
         * 연 목적·시험 구분은 위쪽 한 줌에 밀렸다(2026-10-03).
         *
         * 접어 두는 것(`<details>`)으로는 부족하다 — 접힌 것은 안 읽히고, 이력은 「이 개정에서
         * 무엇이 바뀌었나」 라는 **제 물음**을 가진 자리다. 물음이 다르면 탭이 맞다.
         */}
        <Tabs defaultValue="card">
          <TabsList>
            <TabsTrigger value="card">내용</TabsTrigger>
            <TabsTrigger value="history">
              이력
              {test.document_revision_label && (
                <span className="text-muted-foreground ml-1.5 text-xs font-normal">
                  지금 판 {test.document_revision_label}
                </span>
              )}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="card">
            {/* 왼쪽 목차 + 오른쪽 본문 — 수정 창과 같은 모양이다. */}
            <div className="flex gap-6">
              <CardOutline items={outline} />
              <dl className="min-w-0 flex-1 space-y-5">
                {test.purpose && (
                  <div id={anchorOf('section', '목적')} className="scroll-mt-4 space-y-1">
                    <dt className="text-muted-foreground text-xs font-medium">목적</dt>
                    <dd className="text-sm whitespace-pre-line">{test.purpose}</dd>
                  </div>
                )}

                <div
                  id={anchorOf('section', '적용 시험 항목')}
                  className="scroll-mt-4 space-y-1"
                >
                  <dt className="text-muted-foreground text-xs font-medium">적용 시험 항목</dt>
                  <dd className="flex flex-wrap gap-1.5 text-sm">
                    {test.test_items.length === 0 ? (
                      // 「장비 없음」 이 아니라 「안 정함」 — 둘은 해야 할 일이 다르다.
                      <span className="text-muted-foreground">시험 항목 미지정</span>
                    ) : (
                      test.test_items.map((item) => (
                        <span key={item.term_id} className="bg-muted rounded-md px-2 py-0.5">
                          {item.value}
                          <span
                            className={
                              item.equipment_count === 0
                                ? 'text-amber-600 ml-1 text-xs'
                                : 'text-muted-foreground ml-1 text-xs'
                            }
                            title={
                              item.equipment_count === 0
                                ? '이 항목이 되는 장비가 이 부서에 없습니다'
                                : undefined
                            }
                          >
                            {item.equipment_count}대
                          </span>
                        </span>
                      ))
                    )}
                  </dd>
                  <ItemProposals testId={test.id} />
                </div>

                {grouped.map((section) => (
                  <section
                    key={section.title}
                    id={anchorOf('section', section.title)}
                    className="scroll-mt-4 space-y-2"
                  >
                    <h3 className="border-b pb-1 text-sm font-medium">{section.title}</h3>
                    <div className="grid gap-x-8 gap-y-3 md:grid-cols-2">
                      {section.rows.map((row, at) => (
                        <div
                          key={`${row.definition_id}-${row.set_label ?? ''}-${row.step_order ?? ''}`}
                          // 같은 칸이 묶음마다 서므로 **자리는 첫 줄만 갖는다** — 같은 id 가 둘이면
                          // 목차가 어디로 가는지 브라우저가 정한다.
                          id={
                            section.rows.findIndex(
                              (one) => one.definition_id === row.definition_id,
                            ) === at
                              ? anchorOf(
                                  'field',
                                  keyOf.get(row.definition_id) ?? row.definition_id,
                                )
                              : undefined
                          }
                          className={`scroll-mt-4 space-y-1 ${isWide(row) ? 'md:col-span-2' : ''}`}
                        >
                          <dt className="text-muted-foreground flex items-center gap-1 text-xs font-medium">
                            {row.label}
                            <SetTag row={row} />
                            {row.status === 'draft' && (
                              <span title="초안 속성 — 검색·판정에는 안 쓰입니다">초안</span>
                            )}
                          </dt>
                          <dd className="space-y-1">
                            <Value row={row} />
                            {row.note && (
                              <p className="text-muted-foreground text-xs whitespace-pre-line">
                                {row.note}
                              </p>
                            )}
                            {/* 이 칸에 붙은 그림 — **읽는 사람의 것이다.** 넣고 지우는 것은 수정 창. */}
                            {(byField.get(row.definition_id) ?? []).length > 0 && (
                              <AttachmentStrip
                                target="reliability_test"
                                objectId={test.id}
                                rows={byField.get(row.definition_id) ?? []}
                                canEdit={false}
                                size="lg"
                                onChanged={() => shots.reload()}
                              />
                            )}
                          </dd>
                        </div>
                      ))}
                    </div>
                  </section>
                ))}

                {orphans.map((group) => (
                  <section key={group.title} className="space-y-2">
                    <h3 className="border-b pb-1 text-sm font-medium">{group.title}</h3>
                    <AttachmentStrip
                      target="reliability_test"
                      objectId={test.id}
                      rows={group.rows}
                      canEdit={false}
                      size="lg"
                      onChanged={() => shots.reload()}
                    />
                  </section>
                ))}

                {grouped.length === 0 && !defs.loading && (
                  <p className="text-muted-foreground text-sm">
                    적힌 항목이 없습니다. 시험 조건을 적어 두면 「수행 가능 장비」 가 답할 수
                    있습니다.
                  </p>
                )}
              </dl>
            </div>
          </TabsContent>

          {/**
           * **화면은 최신판을 보여 주고, 과거 판은 여기서 본다.**
           *
           * 카드가 지금 값만 보여 주는 것은 옳지만(85 와 95 가 나란히 서면 어느 것이
           * 조건인지 안 보인다), 그러면 「개정 14에서는 얼마였나」 를 볼 길이 없어진다 —
           * 그 물음이 곧 「이 개정에서 무엇이 바뀌었나」 다.
           */}
          <TabsContent value="history">
            <ValueHistory testId={test.id} />
          </TabsContent>
        </Tabs>

        <DialogFooter>
          {test.can_edit && onEdit && (
            <Button variant="outline" onClick={() => onEdit(test)}>
              <Pencil className="size-4" />
              수정
            </Button>
          )}
          <Button onClick={onClose}>닫기</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** 목록 줄에서 보기 창을 여는 이름 단추 — **키보드로도 닿아야 한다.** */
export function RowOpener({
  name,
  onOpen,
  children,
}: {
  name: string
  onOpen: () => void
  children?: ReactNode
}) {
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <button
        type="button"
        className="text-left font-medium hover:underline"
        aria-label={`${name} 보기`}
        onClick={onOpen}
      >
        {name}
      </button>
      {children}
    </span>
  )
}

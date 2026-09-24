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
import { SECTIONS } from '@/modules/attributes/StandardAttributeFields'
import { CandidateBadge, ReviewBanner } from '@/modules/reliability/CandidateReview'
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

  const grouped = useMemo(() => {
    const values = test?.attributes ?? []
    if (values.length === 0) return []
    const keyOf = new Map((defs.data ?? []).map((one) => [one.id, one.key]))
    const left = new Map(values.map((one) => [one.definition_id, one]))
    const out: { title: string; rows: AttributeValue[] }[] = []
    for (const section of SECTIONS) {
      const rows: AttributeValue[] = []
      for (const key of section.keys) {
        const hit = values.find((one) => keyOf.get(one.definition_id) === key)
        if (hit && left.delete(hit.definition_id)) rows.push(hit)
      }
      if (section.conditions) {
        for (const one of values) {
          if (one.kind === 'condition' && left.delete(one.definition_id)) rows.push(one)
        }
      }
      if (rows.length > 0) out.push({ title: section.title, rows })
    }
    // 표에 없는 칸(초안 · 나중에 는 칸)은 자리를 잃지 않고 맨 뒤로.
    if (left.size > 0) out.push({ title: '기타 항목', rows: [...left.values()] })
    return out
  }, [test?.attributes, defs.data])

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
      <DialogContent className="max-h-[85vh] w-[80vw] overflow-y-auto sm:max-w-[80vw] lg:max-w-5xl">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            {test.name}
            <CandidateBadge row={test} />
          </DialogTitle>
          <DialogDescription>
            {test.workspace_name} 가 수행하는 시험입니다. 고치려면 아래 「수정」 을 누르십시오.
          </DialogDescription>
        </DialogHeader>

        <ReviewBanner row={test} onChanged={(next) => onChanged?.(next)} />
        <ErrorNotice error={defs.error ?? shots.error} />

        <dl className="space-y-5">
          {test.purpose && (
            <div className="space-y-1">
              <dt className="text-muted-foreground text-xs font-medium">목적</dt>
              <dd className="text-sm whitespace-pre-line">{test.purpose}</dd>
            </div>
          )}

          <div className="space-y-1">
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
          </div>

          {grouped.map((section) => (
            <section key={section.title} className="space-y-2">
              <h3 className="border-b pb-1 text-sm font-medium">{section.title}</h3>
              <div className="grid gap-x-8 gap-y-3 md:grid-cols-2">
                {section.rows.map((row) => (
                  <div
                    key={row.definition_id}
                    className={`space-y-1 ${isWide(row) ? 'md:col-span-2' : ''}`}
                  >
                    <dt className="text-muted-foreground flex items-center gap-1 text-xs font-medium">
                      {row.label}
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

/**
 * 조직도 — **표가 아니라 트리다.**
 *
 * 전에는 표의 한 칸에 들여쓰기만 넣었는데, 옆에 열이 여섯이나 서 있으니 그 들여쓰기가
 * 묻혀서 **상하 관계가 없는 것처럼** 보였다. 줄 목록으로 세우고 세로 줄기를 그린다.
 * 줄마다 「↳ 상위slug」 를 적어 눈이 아니라 글자로도 알 수 있게 한다(ReportArchive 와
 * 같은 모양).
 *
 * ## 끌어다 놓기 — 놓는 자리가 둘이다
 *
 *     줄 위의 얇은 띠   before:slug  →  그 부서의 **바로 앞 형제**가 된다
 *     줄 자체           inside:slug  →  그 부서의 **마지막 자식**이 된다
 *
 * 「뒤 형제로」 가 없는 것은 일부러다 — 둘이면 어느 자리든 한두 번에 닿고, 셋이면 어디에
 * 놓았는지 사람이 헷갈린다. 맨 뒤로 보내려면 그 부모 위에 놓으면 된다.
 *
 * **자기 자신과 제 하위에는 못 놓는다.** 놓이면 그 가지가 트리에서 통째로 사라지고,
 * 화면에 안 나오니 되돌릴 수도 없다. 서버도 같은 판정을 한다 — 화면만 막으면 안 된다.
 */

import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  pointerWithin,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import { GripVertical } from 'lucide-react'

import { cn } from '@/shared/lib/utils'
import type { Workspace } from '@/modules/workspaces/api'

/** 옮긴 뒤의 자리. 한 줄이 아니라 **형제 전부**가 온다 — 순서가 함께 바뀌기 때문이다. */
export interface TreePlan {
  slug: string
  parent_slug: string | null
  sort_order: number
}

/** 부모-자식으로 묶어 문서 순서(깊이 우선)로 편다. 서버가 준 `depth` 를 안 믿는 이유는
 *  끌어 놓는 동안 화면이 먼저 움직여야 하기 때문이다. */
export function ordered(rows: Workspace[]): (Workspace & { level: number })[] {
  const byParent = new Map<string | null, Workspace[]>()
  for (const one of rows) {
    const key = one.parent_slug ?? null
    byParent.set(key, [...(byParent.get(key) ?? []), one])
  }
  const out: (Workspace & { level: number })[] = []
  const walk = (parent: string | null, level: number) => {
    const children = [...(byParent.get(parent) ?? [])].sort(
      (a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name),
    )
    for (const one of children) {
      out.push({ ...one, level })
      walk(one.slug, level + 1)
    }
  }
  walk(null, 0)
  return out
}

/** 자기 자신 + 모든 하위. **놓으면 안 되는 자리**다. */
export function forbiddenFor(rows: Workspace[], slug: string | null): Set<string> {
  const found = new Set<string>()
  if (!slug) return found
  found.add(slug)
  let edge = [slug]
  while (edge.length) {
    const next: string[] = []
    for (const one of rows) {
      if (one.parent_slug && edge.includes(one.parent_slug) && !found.has(one.slug)) {
        found.add(one.slug)
        next.push(one.slug)
      }
    }
    edge = next
  }
  return found
}

/**
 * 어디에 놓았는지로 **형제 전부의 새 자리**를 만든다.
 *
 * 옮긴 줄 하나만 보내면 나머지 형제의 `sort_order` 가 옛 값 그대로라, 새 자리가 그 사이
 * 어디인지 서버가 알 수 없다. 그래서 그 무리를 0부터 다시 매겨 통째로 보낸다.
 */
export function movePlan(
  rows: Workspace[],
  moving: string,
  where: { kind: 'before' | 'inside'; slug: string },
): TreePlan[] {
  const active = rows.find((one) => one.slug === moving)
  const target = rows.find((one) => one.slug === where.slug)
  if (!active || !target) return []
  if (forbiddenFor(rows, moving).has(where.slug)) return []

  const parent = where.kind === 'before' ? (target.parent_slug ?? null) : target.slug
  const siblings = rows
    .filter((one) => (one.parent_slug ?? null) === parent && one.slug !== moving)
    .sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name))

  const at =
    where.kind === 'inside'
      ? siblings.length
      : Math.max(
          0,
          siblings.findIndex((one) => one.slug === target.slug),
        )
  const final = [...siblings.slice(0, at), active, ...siblings.slice(at)]
  return final.map((one, index) => ({
    slug: one.slug,
    parent_slug: parent,
    sort_order: index,
  }))
}

function Band({ id, lit, off }: { id: string; lit: boolean; off: boolean }) {
  const { setNodeRef } = useDroppable({ id, disabled: off })
  return (
    <div
      ref={setNodeRef}
      className={cn('-my-0.5 h-1 rounded-full transition-colors', lit && 'bg-primary')}
    />
  )
}

function Row({
  row,
  lit,
  dragging,
  off,
  disabled,
  children,
}: {
  row: Workspace & { level: number }
  lit: boolean
  dragging: boolean
  off: boolean
  disabled: boolean
  children?: ReactNode
}) {
  const { setNodeRef: dropRef } = useDroppable({ id: `inside:${row.slug}`, disabled: off })
  const {
    attributes,
    listeners,
    setNodeRef: dragRef,
  } = useDraggable({
    id: row.slug,
    disabled,
  })
  return (
    <div
      ref={(node) => {
        dropRef(node)
        dragRef(node)
      }}
      className={cn(
        'flex items-center gap-2 rounded-md px-2 py-2 transition-colors',
        lit && 'bg-primary/10 ring-primary/40 ring-1',
        dragging && 'opacity-40',
        off && 'opacity-30',
      )}
      // 줄기(세로줄)는 들여쓴 만큼 왼쪽에 선다 — 깊이가 눈에 보여야 트리로 읽힌다.
      style={{ paddingLeft: row.level * 20 + 8 }}
    >
      <button
        type="button"
        {...listeners}
        {...attributes}
        disabled={disabled}
        aria-label={`${row.name} 끌어서 옮기기`}
        className="hover:bg-muted cursor-grab touch-none rounded p-1 active:cursor-grabbing"
      >
        <GripVertical className="text-muted-foreground size-3.5" />
      </button>
      {row.level > 0 && <span className="text-muted-foreground/60 -ml-1 text-xs">└</span>}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span
            className={cn('truncate font-medium', !row.is_active && 'text-muted-foreground')}
          >
            {row.name}
          </span>
          <span className="text-muted-foreground font-mono text-[10px]">{row.slug}</span>
          {row.parent_slug && (
            <span className="text-muted-foreground text-[10px]">↳ {row.parent_slug}</span>
          )}
          {!row.is_active && <span className="text-muted-foreground text-[10px]">보관됨</span>}
        </div>
        <div className="text-muted-foreground text-xs">
          멤버 {row.member_count} · 장비 {row.equipment_count}
        </div>
      </div>
      {children}
    </div>
  )
}

export function WorkspaceTree({
  rows,
  onMove,
  disabled = false,
  renderActions,
}: {
  rows: Workspace[]
  /** 형제 전부의 새 자리. 부르는 쪽이 한 번에 보낸다. */
  onMove: (plan: TreePlan[]) => void
  disabled?: boolean
  renderActions?: (row: Workspace) => ReactNode
}) {
  const [moving, setMoving] = useState<string | null>(null)
  const [over, setOver] = useState<string | null>(null)
  const list = useMemo(() => ordered(rows), [rows])
  const off = useMemo(() => forbiddenFor(rows, moving), [rows, moving])

  // 손이 조금 움직여야 끌기로 본다 — 안 그러면 줄 안의 단추를 누를 때마다 끌린다.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
  )
  const held = moving ? rows.find((one) => one.slug === moving) : null

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={pointerWithin}
      onDragStart={(event) => setMoving(String(event.active.id))}
      onDragOver={(event) => setOver(event.over ? String(event.over.id) : null)}
      onDragCancel={() => {
        setMoving(null)
        setOver(null)
      }}
      onDragEnd={(event) => {
        const held = moving
        setMoving(null)
        setOver(null)
        if (!held || !event.over) return
        const [kind, ...rest] = String(event.over.id).split(':')
        const slug = rest.join(':')
        if (kind !== 'before' && kind !== 'inside') return
        const plan = movePlan(rows, held, { kind, slug })
        if (plan.length > 0) onMove(plan)
      }}
    >
      <ul className="divide-y">
        {list.map((row) => (
          <li key={row.slug} className="relative">
            <Band
              id={`before:${row.slug}`}
              lit={over === `before:${row.slug}` && !off.has(row.slug)}
              off={off.has(row.slug)}
            />
            <Row
              row={row}
              lit={over === `inside:${row.slug}` && !off.has(row.slug)}
              dragging={moving === row.slug}
              off={off.has(row.slug) && moving !== null && moving !== row.slug}
              disabled={disabled}
            >
              {renderActions?.(row)}
            </Row>
          </li>
        ))}
      </ul>

      <DragOverlay>
        {held ? (
          <div className="bg-card flex items-center gap-2 rounded-md border px-3 py-2 text-sm shadow-lg">
            <span className="font-medium">{held.name}</span>
            <span className="text-muted-foreground font-mono text-[10px]">{held.slug}</span>
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  )
}

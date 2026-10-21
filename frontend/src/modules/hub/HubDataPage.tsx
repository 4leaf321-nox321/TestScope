/**
 * 허브 기준정보 — **받은 데이터 조회.** 누구나 본다(요청서 1.2 §9 「수신 데이터 조회」).
 *
 * 기준정보 허브(StandardPlatform)에서 받은 개발모델 · 과제 · 프로젝트 같은 공통 기준정보다.
 * TestScope 에서는 고칠 수 없고(허브에서 고친다), 신뢰성 시험 · 장비의 칸에서 **고를** 수 있다.
 * 식별자(허브 key)가 플랫폼 사이의 공통 열쇠다.
 */

import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { Button } from '@/shared/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
import { Input } from '@/shared/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table'
import { useResource } from '@/shared/hooks/useResource'
import { shownDateTime } from '@/shared/lib/datetime'
import { ITEM_STATE, hubApi } from '@/modules/hub/api'
import type { HubItem } from '@/modules/hub/api'

/** 속성 값 한 칸을 글로 — 참조는 이름을 붙인다(옛 식별자도 풀려 있다). */
function shown(value: unknown, refs: Record<string, string>): string {
  const one = (raw: unknown) => {
    const text = typeof raw === 'string' ? raw : JSON.stringify(raw)
    return refs[text] ? `${refs[text]} (${text})` : text
  }
  return Array.isArray(value) ? value.map(one).join(', ') : one(value)
}

function ItemDialog({
  type,
  item,
  onClose,
}: {
  type: string
  item: HubItem
  onClose: () => void
}) {
  const detail = useResource(() => hubApi.item(type, item.key), [type, item.key])
  const one = detail.data
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{item.label}</DialogTitle>
          <DialogDescription>
            허브 식별자 <span className="font-mono">{item.key}</span> ·{' '}
            {ITEM_STATE[item.state] ?? item.state}
            {item.merged_into && ` → ${item.merged_into}`}
          </DialogDescription>
        </DialogHeader>
        <ErrorNotice error={detail.error} />
        <dl className="grid grid-cols-[10rem_1fr] gap-x-3 gap-y-1 text-sm">
          {Object.entries(item.properties).map(([key, value]) => (
            <div key={key} className="contents">
              <dt className="text-muted-foreground font-mono text-xs">{key}</dt>
              <dd className="break-words">{shown(value, item.references)}</dd>
            </div>
          ))}
          {item.previous_keys.length > 0 && (
            <div className="contents">
              <dt className="text-muted-foreground text-xs">옛 식별자</dt>
              <dd className="font-mono text-xs">{item.previous_keys.join(', ')}</dd>
            </div>
          )}
          <div className="contents">
            <dt className="text-muted-foreground text-xs">허브 갱신</dt>
            <dd className="font-mono text-xs">{item.hub_updated_at ?? '—'}</dd>
          </div>
        </dl>
        {one && (one.outgoing.length > 0 || one.incoming.length > 0) && (
          <div className="space-y-1 text-sm">
            <p className="font-medium">관계</p>
            <ul className="space-y-0.5">
              {one.outgoing.map((rel) => (
                <li
                  key={`o-${rel.relation}-${rel.dst_type}-${rel.dst}`}
                  className={rel.deleted ? 'line-through opacity-60' : ''}
                >
                  {rel.relation} → {rel.dst_label ?? rel.dst}
                  <span className="text-muted-foreground font-mono text-xs">
                    {' '}
                    {rel.dst_type}:{rel.dst}
                  </span>
                </li>
              ))}
              {one.incoming.map((rel) => (
                <li
                  key={`i-${rel.relation}-${rel.src}`}
                  className={rel.deleted ? 'line-through opacity-60' : ''}
                >
                  ← {rel.relation} · {rel.dst_label ?? rel.src}
                  <span className="text-muted-foreground font-mono text-xs"> {rel.src}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

export default function HubDataPage() {
  const [params, setParams] = useSearchParams()
  const types = useResource(() => hubApi.types(), [])
  const type = params.get('type') ?? types.data?.[0]?.slug ?? ''
  const [query, setQuery] = useState('')
  const [asked, setAsked] = useState('')
  const [state, setState] = useState('active')
  const [offset, setOffset] = useState(0)
  const [opening, setOpening] = useState<HubItem | null>(null)
  useEffect(() => {
    const timer = setTimeout(() => setAsked(query), 300)
    return () => clearTimeout(timer)
  }, [query])
  useEffect(() => setOffset(0), [type, asked, state])
  const items = useResource(
    () =>
      type
        ? hubApi.items(type, { q: asked || undefined, state: state || undefined, offset })
        : Promise.resolve({ items: [], total: 0 }),
    [type, asked, state, offset],
  )
  const current = types.data?.find((one) => one.slug === type)

  return (
    <div className="space-y-6">
      <PageHeader
        title="허브 기준정보"
        description="기준정보 허브(StandardPlatform)에서 받은 공통 기준정보. TestScope에서는 수정 불가(허브에서 수정). 신뢰성 시험·장비의 칸에서 선택 가능."
      />
      <ErrorNotice error={types.error ?? items.error} />
      {types.data && types.data.length === 0 ? (
        <EmptyState
          title="받은 기준정보 없음"
          hint="시스템 관리자가 ‘관리 → 허브 연계’에서 허브를 연결하고 수신하면 표시됨."
        />
      ) : (
        <>
          <div className="flex flex-wrap gap-1">
            {(types.data ?? []).map((one) => (
              <Button
                key={one.slug}
                size="sm"
                variant={one.slug === type ? 'secondary' : 'ghost'}
                onClick={() => setParams({ type: one.slug }, { replace: true })}
              >
                {one.label} {one.active}
              </Button>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="검색: 식별자 · 이름"
              className="w-72"
            />
            <select
              aria-label="상태"
              className="border-input bg-background h-9 rounded-md border px-2 text-sm"
              value={state}
              onChange={(event) => setState(event.target.value)}
            >
              <option value="active">사용 중</option>
              <option value="inactive">사용 중지·삭제·병합</option>
              <option value="">전체</option>
            </select>
            {items.data && (
              <span className="text-muted-foreground text-sm">
                {items.data.total}건
                {current?.last_received_at &&
                  ` · 마지막 수신 ${shownDateTime(current.last_received_at)}`}
                {current?.axis_slug && (
                  <span className="font-mono text-xs"> · 축 {current.axis_slug}</span>
                )}
              </span>
            )}
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>식별자</TableHead>
                <TableHead>이름</TableHead>
                <TableHead>상태</TableHead>
                <TableHead>속성</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(items.data?.items ?? []).map((one) => (
                <TableRow
                  key={one.key}
                  className="cursor-pointer"
                  onClick={() => setOpening(one)}
                >
                  <TableCell className="font-mono text-xs">{one.key}</TableCell>
                  <TableCell>{one.label}</TableCell>
                  <TableCell className="text-xs whitespace-nowrap">
                    {ITEM_STATE[one.state] ?? one.state}
                    {one.merged_into && ` → ${one.merged_into}`}
                  </TableCell>
                  <TableCell className="text-muted-foreground max-w-md truncate text-xs">
                    {Object.entries(one.properties)
                      .slice(0, 4)
                      .map(([key, value]) => `${key}: ${shown(value, one.references)}`)
                      .join(' · ')}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {items.data && items.data.total > 50 && (
            <div className="flex items-center gap-2 text-sm">
              <Button
                size="sm"
                variant="outline"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - 50))}
              >
                이전
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={offset + 50 >= items.data.total}
                onClick={() => setOffset(offset + 50)}
              >
                다음
              </Button>
            </div>
          )}
        </>
      )}
      {opening && <ItemDialog type={type} item={opening} onClose={() => setOpening(null)} />}
    </div>
  )
}

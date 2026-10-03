/**
 * VOC — **문제를 여기서 내고, 여기서 따라간다.**
 *
 * 앱 안에 접수 경로가 없으면 문제는 구두로만 오가고 기록이 안 남는다. 그런데 「낸 사람만
 * 보는 카드」 로 두면 그것대로 같은 문제가 여러 벌 쌓이고, 무엇이 고쳐졌는지 남들이 모른다 —
 * 그래서 **게시판**이다.
 *
 * 기본 목록은 **아직 끝나지 않은 것**만 보여 준다. 종료·반려는 쌓이기만 하므로 기본에
 * 두면 금세 그것들이 목록을 채우고, 그러면 아무도 목록을 안 본다.
 *
 * 접수 창은 **어느 화면에서 냈는지를 몰래 싣는다**(`page_path`). 사람에게 물으면 대개 안
 * 적고, 안 적힌 것을 나중에 물으면 그때는 기억이 없다.
 */

import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Textarea } from '@/shared/components/ui/textarea'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table'
import { useResource } from '@/shared/hooks/useResource'
import { shownDate } from '@/shared/lib/datetime'
import { VOC_STATUS_LABELS, vocApi } from '@/modules/voc/api'

/** 머리의 거르기. 「전부」 는 끝난 것까지. */
const FILTERS = [
  { key: '', label: '진행 중' },
  { key: 'all', label: '전부' },
  { key: 'mine', label: '내가 낸 것' },
]

export default function VocPage() {
  const [search, setSearch] = useSearchParams()
  const picked = search.get('f') ?? ''
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [writing, setWriting] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [busy, setBusy] = useState(false)

  const page = useResource(
    () =>
      vocApi.list({
        status: picked === 'all' ? 'all' : undefined,
        mine: picked === 'mine',
      }),
    [picked],
  )

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      // **어느 화면에서 냈는지를 함께 보낸다** — 재현의 실마리다. 지금은 VOC 화면이지만
      // 사람은 대개 막힌 화면에서 사이드바를 눌러 여기로 온다. 그래서 완벽하지는 않고,
      // 그래도 없는 것보다 낫다.
      await vocApi.create({ title, body, page_path: document.referrer || null })
      setTitle('')
      setBody('')
      setWriting(false)
      page.reload()
    } catch (problem) {
      setError(problem as Error)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="VOC"
        description="안 되는 것·불편한 것을 여기에 냅니다. 로그인한 사람은 모두 볼 수 있고, 처리 과정이 그대로 남습니다."
      />

      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map((one) => (
          <Button
            key={one.key}
            size="sm"
            variant={picked === one.key ? 'default' : 'outline'}
            onClick={() => setSearch(one.key ? { f: one.key } : {})}
          >
            {one.label}
          </Button>
        ))}
        <div className="flex-1" />
        <Button size="sm" onClick={() => setWriting((before) => !before)}>
          {writing ? '접기' : '새로 내기'}
        </Button>
      </div>

      {writing && (
        <div className="space-y-3 rounded-md border p-4">
          <Input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="한 줄로 — 「장비 수정에서 저장이 안 됩니다」"
          />
          <Textarea
            value={body}
            onChange={(event) => setBody(event.target.value)}
            rows={6}
            placeholder={
              '무엇을 하려다 무엇이 됐는지를 적어 주십시오.\n' +
              '어느 화면 · 무엇을 눌렀나 · 기대한 것 · 실제로 본 것'
            }
          />
          {/* **왜 자세히 적어야 하는지를 말해 준다.** 안 적어 두면 「안 돼요」 한 줄이
              오고, 그 한 줄로는 아무도 재현하지 못한다. */}
          <p className="text-muted-foreground text-xs">
            자산번호·기종명처럼 <strong>그 줄을 찾을 수 있는 것</strong>을 함께 적으면 훨씬
            빨리 고쳐집니다.
          </p>
          <Button onClick={submit} disabled={busy || !title.trim() || !body.trim()}>
            {busy ? '보내는 중…' : '내기'}
          </Button>
        </div>
      )}

      <ErrorNotice error={error ?? page.error} />

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-16">번호</TableHead>
            <TableHead>제목</TableHead>
            <TableHead className="w-24">상태</TableHead>
            <TableHead className="w-28">낸 사람</TableHead>
            <TableHead className="w-28">낸 날</TableHead>
            <TableHead className="w-28">최근 처리</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(page.data?.items ?? []).length === 0 && (
            <TableRow>
              <TableCell colSpan={99} className="text-muted-foreground py-10 text-center">
                {picked === 'mine'
                  ? '내가 낸 것이 없습니다.'
                  : picked === 'all'
                    ? '아직 낸 것이 없습니다.'
                    : '진행 중인 것이 없습니다. 끝난 것까지 보려면 「전부」 를 누르십시오.'}
              </TableCell>
            </TableRow>
          )}
          {(page.data?.items ?? []).map((one) => (
            <TableRow key={one.id} className="hover:bg-muted/50">
              <TableCell className="text-muted-foreground font-mono text-xs">
                {one.seq}
              </TableCell>
              <TableCell>
                <Link to={`/voc/${one.id}`} className="hover:underline">
                  {one.title}
                </Link>
                {one.comment_count > 0 && (
                  // 말이 오간 건을 눈으로 고른다 — 조용한 건은 아직 아무도 안 봤다는 뜻이다.
                  <span className="text-muted-foreground ml-2 text-xs">
                    말 {one.comment_count}
                  </span>
                )}
              </TableCell>
              <TableCell className="text-sm">
                {VOC_STATUS_LABELS[one.status] ?? one.status_label}
              </TableCell>
              <TableCell className="text-sm">{one.created_by_name ?? '—'}</TableCell>
              <TableCell className="text-sm">{shownDate(one.created_at)}</TableCell>
              <TableCell className="text-sm">{shownDate(one.status_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

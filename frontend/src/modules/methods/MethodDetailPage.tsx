/**
 * 시험법 상세 — 요구 조건이 본문이다.
 *
 * **요구 조건이 곧 검색 물음이 된다.** 여기 적힌 숫자를 검색 화면이 그대로 물어
 * 주므로, 사람이 규격서를 펴 놓고 숫자를 옮겨 적을 필요가 없다 — 그 옮겨 적기에서
 * 자릿수가 틀린다.
 *
 * **시험 항목은 여기서 정한다.** 카탈로그가 인용했는데 어느 시험의 것인지 안 정해진 규격이
 * 172 건 있다 — 정하는 순간 인용한 계열의 그 시험 항목에 붙는다. 그래서 인용한 계열 목록이
 * 이 화면에 함께 있다: 무엇이 붙을지 보고 정한다.
 */

import { useState } from 'react'
import { Trash2 } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ApiError } from '@/shared/api/client'
import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { Button } from '@/shared/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import { Textarea } from '@/shared/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table'
import { useAuth } from '@/shared/auth/AuthContext'
import { useResource } from '@/shared/hooks/useResource'
import { AttachmentStrip } from '@/modules/attachments/AttachmentStrip'
import { attachmentApi } from '@/modules/attachments/api'
import { AXIS, vocabularyApi } from '@/modules/vocabulary/api'
import { AttributeValuesPanel } from '@/modules/attributes/AttributeValuesPanel'
import { GraphPanel } from '@/modules/graph/GraphPanel'
import { methodApi } from '@/modules/methods/api'
import type { DetachImpact, TestMethod } from '@/modules/methods/api'

/** "제한 없음" 을 0 으로 적지 않는다 — 하한이 0 인 요구와 구별되지 않는다. */
function shownBound(value: number | null, unit: string): string {
  return value === null ? '—' : `${value} ${unit}`.trim()
}

/**
 * 규격 수정 — 번호 · 판 · 제목 · 요약.
 *
 * **번호는 시스템 관리자만** 고친다. 번호는 반입 · 검토함 · 검색이 규격을 찾는 열쇠라, 고치면 옛
 * 번호가 별칭으로 남아 그 자리들이 계속 찾는다(서버가 판정 — 여기는 칸을 잠글 뿐).
 */
function MethodEditDialog({
  method,
  isAdmin,
  onClose,
  onSaved,
}: {
  method: TestMethod
  isAdmin: boolean
  onClose: () => void
  onSaved: () => void
}) {
  const [code, setCode] = useState(method.code)
  const [edition, setEdition] = useState(method.edition ?? '')
  const [title, setTitle] = useState(method.title)
  const [summary, setSummary] = useState(method.summary ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  async function save() {
    setBusy(true)
    setError(null)
    try {
      const body: Record<string, unknown> = {
        edition: edition.trim() || null,
        title: title.trim(),
        summary: summary.trim() || null,
      }
      if (isAdmin && code.trim() !== method.code) body.code = code.trim()
      await methodApi.update(method.id, body)
      onSaved()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && !busy && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>규격 수정</DialogTitle>
          <DialogDescription>
            번호 수정은 시스템 관리자 전용. 바꾼 뒤에도 옛 번호로 반입·검색·검토함이 이 규격을
            찾음.
          </DialogDescription>
        </DialogHeader>
        <ErrorNotice error={error} />
        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="method-code">규격 번호</Label>
            <Input
              id="method-code"
              value={code}
              onChange={(event) => setCode(event.target.value)}
              disabled={!isAdmin}
              maxLength={100}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="method-edition">판</Label>
            <Input
              id="method-edition"
              value={edition}
              onChange={(event) => setEdition(event.target.value)}
              placeholder="예: 2024"
              maxLength={30}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="method-title">제목</Label>
            <Input
              id="method-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={300}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="method-summary">요약</Label>
            <Textarea
              id="method-summary"
              value={summary}
              onChange={(event) => setSummary(event.target.value)}
              rows={3}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" disabled={busy} onClick={onClose}>
            취소
          </Button>
          <Button disabled={busy || !title.trim() || !code.trim()} onClick={() => void save()}>
            저장
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/**
 * 이 규격을 **다른 규격으로 병합** — 인용 · 요구 조건 · 장비 시험 항목이 남는 쪽으로 옮겨 가고
 * 이 규격은 지워진다. 이 규격의 번호는 남는 쪽의 옛 번호가 되어 반입 · 검색 · 검토함이 계속 찾는다.
 */
function MergeDialog({
  method,
  onClose,
  onMerged,
}: {
  method: TestMethod
  onClose: () => void
  onMerged: (target: TestMethod) => void
}) {
  // 판 표시를 뗀 번호로 먼저 찾아 둔다 — 「ASTM D638-14」 면 「ASTM D638」 이 첫 후보.
  const [query, setQuery] = useState(
    method.code.replace(/[-:(]\s*(19|20)?\d{2}[a-z]?\)?$/, ''),
  )
  const found = useResource(
    () =>
      query.trim().length >= 2
        ? methodApi.list({ q: query.trim() })
        : Promise.resolve({ items: [], total: 0, limit: 0, offset: 0 }),
    [query],
  )
  const [target, setTarget] = useState<TestMethod | null>(null)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const options = (found.data?.items ?? []).filter((row) => row.id !== method.id)

  async function merge() {
    if (!target) return
    setBusy(true)
    setError(null)
    try {
      onMerged(await methodApi.merge(method.id, target.id, reason.trim()))
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && !busy && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>다른 규격으로 병합: {method.code}</DialogTitle>
          <DialogDescription>
            인용 계열·요구 조건·장비 시험 항목이 고른 규격으로 옮겨지고 이 규격은 삭제됨. 이
            번호는 고른 규격의 옛 번호로 남음.
          </DialogDescription>
        </DialogHeader>
        <ErrorNotice error={found.error ?? error} />
        <div className="space-y-2">
          <Label htmlFor="merge-query">남길 규격 찾기</Label>
          <Input
            id="merge-query"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value)
              setTarget(null)
            }}
            placeholder="규격 번호"
          />
          <ul className="max-h-48 space-y-1 overflow-y-auto text-sm">
            {options.map((row) => (
              <li key={row.id}>
                <label className="flex cursor-pointer items-start gap-2">
                  <input
                    type="radio"
                    name="merge-target"
                    className="mt-1"
                    checked={target?.id === row.id}
                    onChange={() => setTarget(row)}
                  />
                  <span>
                    {row.code}
                    {row.edition ? ` ${row.edition}` : ''}
                    <span className="text-muted-foreground block text-xs">{row.title}</span>
                  </span>
                </label>
              </li>
            ))}
            {found.data && options.length === 0 && (
              <li className="text-muted-foreground">일치하는 규격 없음</li>
            )}
          </ul>
        </div>
        <div className="space-y-1">
          <Label htmlFor="merge-reason">사유 (감사 기록에 남음)</Label>
          <Input
            id="merge-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="예: 판 표시만 다른 같은 규격"
            maxLength={500}
          />
        </div>
        <DialogFooter>
          <Button variant="outline" disabled={busy} onClick={onClose}>
            취소
          </Button>
          <Button
            variant="destructive"
            disabled={busy || !target}
            onClick={() => void merge()}
          >
            {target ? `${target.code}(으)로 병합` : '병합'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/**
 * 규격에 걸린 시험 항목 해제 — **떼기 전에 끊기는 계열을 보여 준다.**
 *
 * 그 항목으로만 이 규격에 이어진 계열은 끊겨 미연결 인용으로 돌아간다 — 그 계열의 장비는 이
 * 규격으로 검색되지 않는다. 사유는 필수이고 감사 기록에 남는다.
 */
function DetachDialog({
  methodId,
  termId,
  value,
  onClose,
  onDone,
}: {
  methodId: string
  termId: string
  value: string
  onClose: () => void
  onDone: (impact: DetachImpact) => void
}) {
  const impact = useResource(
    () => methodApi.detachPreview(methodId, termId),
    [methodId, termId],
  )
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  async function detach() {
    setBusy(true)
    setError(null)
    try {
      onDone(await methodApi.detachTestItem(methodId, termId, reason.trim()))
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  const cut = impact.data?.cut ?? []
  const kept = impact.data?.kept ?? []
  return (
    <Dialog open onOpenChange={(open) => !open && !busy && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>시험 항목 해제: {value}</DialogTitle>
          <DialogDescription>
            이 규격에서 ‘{value}’를 뗌. 그 항목으로 걸린 계열 연결도 함께 걷힘.
          </DialogDescription>
        </DialogHeader>
        <ErrorNotice error={impact.error ?? error} />
        {impact.data && (
          <div className="space-y-2 text-sm">
            {cut.length > 0 ? (
              <div className="rounded-md border border-amber-300 bg-amber-50 p-3 dark:bg-amber-950/30">
                <p>
                  <strong>{cut.length}개 계열이 이 규격과 끊김.</strong> 이 항목으로만 이어져
                  있어 미연결 인용으로 돌아감. 그 계열의 장비는 이 규격으로 검색되지 않음.
                </p>
                <p className="text-muted-foreground mt-1 text-xs">{cut.join(', ')}</p>
              </div>
            ) : (
              <p className="text-muted-foreground">끊기는 계열 없음.</p>
            )}
            {kept.length > 0 && (
              <p className="text-muted-foreground text-xs">
                다른 시험 항목으로 연결이 남는 계열 {kept.length}개: {kept.join(', ')}
              </p>
            )}
          </div>
        )}
        <div className="space-y-1">
          <Label htmlFor="detach-reason">해제 사유 (필수, 감사 기록에 남음)</Label>
          <Textarea
            id="detach-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="예: 이 규격은 방수만 다룸. 방진은 잘못 걸림."
            rows={2}
            maxLength={500}
          />
        </div>
        <DialogFooter>
          <Button variant="outline" disabled={busy} onClick={onClose}>
            취소
          </Button>
          <Button
            variant="destructive"
            disabled={busy || !impact.data || !reason.trim()}
            onClick={() => void detach()}
          >
            {cut.length > 0 ? `해제 (${cut.length}개 계열 끊김)` : '해제'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function MethodDetailPage() {
  const { id = '' } = useParams<{ id: string }>()
  const { user } = useAuth()
  const method = useResource(() => methodApi.read(id), [id])
  /** 규격서 원문 — 목록과 따로 받는다. 상세를 열 때마다 파일 목록이 필요하다. */
  const documents = useResource(() => attachmentApi.list('method', id), [id])
  const conditions = useResource(() => vocabularyApi.conditions(), [])
  const items = useResource(() => vocabularyApi.terms(AXIS.testItem), [])
  const [pickingItem, setPickingItem] = useState('')

  const [conditionKey, setConditionKey] = useState('')
  const [min, setMin] = useState('')
  const [max, setMax] = useState('')
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [editing, setEditing] = useState(false)
  const [linking, setLinking] = useState(false)
  const [linked, setLinked] = useState<string | null>(null)
  const [linkError, setLinkError] = useState<Error | null>(null)
  /** 떼려는 시험 항목 — 창을 연다. */
  const [detaching, setDetaching] = useState<{ termId: string; value: string } | null>(null)
  const [detached, setDetached] = useState<string | null>(null)
  const [merging, setMerging] = useState(false)
  const navigate = useNavigate()

  if (method.error) return <ErrorNotice error={method.error} />
  if (!method.data) return null

  const one = method.data

  async function decideTestItem() {
    if (!pickingItem) return
    setError(null)
    try {
      // **더한다.** 통째로 바뀌는 칸이라, 이미 정해진 것을 안 실으면 조용히 끊긴다 —
      // 규격 하나가 시험 항목 여럿을 덮으므로 실제로 일어나는 일이다.
      await methodApi.update(id, {
        test_item_term_ids: [
          ...(one?.test_items ?? []).map((item) => item.term_id),
          pickingItem,
        ],
      })
      setPickingItem('')
      method.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

  /** 안 이어진 인용 계열에 이 규격의 시험 항목을 더해 잇는다 — 시스템 관리자. */
  async function linkCitations() {
    setLinking(true)
    setLinkError(null)
    try {
      const done = await methodApi.linkCitations(id)
      setLinked(
        done.added_to.length > 0
          ? `인용 계열 ${done.added_to.length}개에 시험 항목 추가 후 연결: ${done.added_to.join(', ')}`
          : '연결할 인용 계열 없음',
      )
      method.reload()
    } catch (caught) {
      setLinkError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setLinking(false)
    }
  }

  /** 시험 항목은 정했는데 그 시험 항목이 없어 미정으로 남은 인용 계열. */
  const unlinked =
    one.test_items.length > 0 ? one.cited_series.filter((row) => row.pending) : []

  async function addRequirement() {
    if (!conditionKey) return
    setError(null)
    try {
      await methodApi.putRequirement(id, {
        condition_key_id: conditionKey,
        // **빈 칸은 null 이다.** 20 kN 이상은 min 만 있고 max 가 없다.
        min_value: min.trim() === '' ? null : Number(min),
        max_value: max.trim() === '' ? null : Number(max),
      })
      setConditionKey('')
      setMin('')
      setMax('')
      method.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        back={{ to: '/methods', label: '시험법·규격' }}
        title={`${one.code}${one.edition ? ` ${one.edition}` : ''}`}
        description={one.title}
        actions={
          one.can_edit || user?.is_system_admin ? (
            <div className="flex gap-2">
              {one.can_edit && (
                <Button variant="outline" onClick={() => setEditing(true)}>
                  수정
                </Button>
              )}
              {/* 표기만 다른 같은 규격을 하나로 — 시스템 관리자. */}
              {user?.is_system_admin && (
                <Button variant="outline" onClick={() => setMerging(true)}>
                  다른 규격으로 병합
                </Button>
              )}
            </div>
          ) : undefined
        }
      />
      {/* 옛 번호 — 번호를 고쳐도 이 번호로 찾아온다(반입 · 검색 · 검토함). */}
      {(one.former_codes ?? []).length > 0 && (
        <p className="text-muted-foreground -mt-4 text-xs">
          옛 번호: {(one.former_codes ?? []).join(', ')}
        </p>
      )}

      <dl className="grid grid-cols-2 gap-4 rounded-md border p-4 sm:grid-cols-4">
        <div>
          <dt className="text-muted-foreground text-xs">시험 항목</dt>
          {/* **여럿일 수 있다** — IEC 60529 는 방진과 방수를 한 문서가 정의한다. */}
          <dd className="text-sm">
            {one.test_items.length === 0 ? (
              <span className="text-amber-600">미지정</span>
            ) : user?.is_system_admin ? (
              // **잘못 걸린 항목을 뗀다** — 시스템 관리자. 전에는 뗄 길이 없었다(2026-10-13).
              <span className="flex flex-wrap gap-1">
                {one.test_items.map((item) => (
                  <span
                    key={item.term_id}
                    className="bg-muted inline-flex items-center gap-1 rounded px-1.5 py-0.5"
                  >
                    {item.value}
                    <button
                      type="button"
                      className="text-muted-foreground hover:text-destructive"
                      aria-label={`${item.value} 해제`}
                      title="이 규격에서 시험 항목 해제"
                      onClick={() => {
                        setDetached(null)
                        setDetaching({ termId: item.term_id, value: item.value })
                      }}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </span>
            ) : (
              one.test_items.map((item) => item.value).join(' · ')
            )}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">제정 기관</dt>
          <dd className="text-sm">{one.body ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">상태</dt>
          <dd className="text-sm">
            {one.status === 'superseded'
              ? `대체됨${one.superseded_by_code ? ` (${one.superseded_by_code})` : ''}`
              : one.status === 'draft'
                ? '초안'
                : '현행'}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">수행 가능 장비</dt>
          <dd className="text-sm">
            {one.equipment_count === 0 ? (
              <span className="text-amber-600">없음(현재 수행 불가)</span>
            ) : (
              `${one.equipment_count}대`
            )}
          </dd>
        </div>
      </dl>

      {one.summary && <p className="text-sm">{one.summary}</p>}

      {one.test_items.length === 0 && one.can_edit && (
        <div className="space-y-2 rounded-md border border-amber-300 bg-amber-50 p-4 dark:bg-amber-950/30">
          <p className="text-sm">
            <strong>이 규격의 시험 항목 지정 필요.</strong>
            {one.pending_series_count > 0
              ? ` 지정 즉시 인용 계열 ${one.pending_series_count}개가 이 규격에 연결됨.`
              : ' 지정 시 계열의 시험 항목에 이 규격 연결 가능.'}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Select value={pickingItem} onValueChange={setPickingItem}>
              <SelectTrigger className="w-56" aria-label="시험 항목 선택">
                <SelectValue placeholder="시험 항목" />
              </SelectTrigger>
              <SelectContent>
                {(items.data ?? []).map((term) => (
                  <SelectItem key={term.id} value={term.id}>
                    {term.value}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button onClick={decideTestItem} disabled={!pickingItem}>
              적용 규격으로 지정
            </Button>
          </div>
        </div>
      )}

      <GraphPanel objectId={`method:${one.id}`} />

      {/* **규격서 원문.** 번호만 있고 문서가 없으면 읽을 수가 없고, 요구 조건을 채울
          재료도 없다(601건 중 원문을 가진 것이 19건이었다). 사내 규격서도 여기 붙는다 —
          여러 신뢰성 시험이 한 문서를 인용하므로 시험마다 복사하지 않는다.

          **올리고 지우는 것은 시스템 관리자만**이다. 규격은 전사 공용이라 한 부서가 올린
          판이 전사의 근거가 되면 안 된다 — 판정은 서버가 하고 여기는 표시일 뿐이다. */}
      <section className="space-y-3">
        <h2 className="text-base font-semibold">
          규격서
          {(documents.data ?? []).length > 0 && ` · ${(documents.data ?? []).length}`}
        </h2>
        <ErrorNotice error={documents.error} />
        <AttachmentStrip
          target="method"
          objectId={one.id}
          rows={documents.data ?? []}
          canEdit={Boolean(user?.is_system_admin)}
          size="lg"
          label="규격서 올리기"
          onChanged={() => documents.reload()}
        />
        {(documents.data ?? []).length === 0 && !user?.is_system_admin && (
          <p className="text-muted-foreground text-sm">
            업로드된 규격서 없음. 업로드 권한: 시스템 관리자.
          </p>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-base font-semibold">속성</h2>
        <AttributeValuesPanel
          target="method"
          values={one.attributes ?? []}
          canEdit={one.can_edit}
          onSave={async (attributes) => {
            await methodApi.update(one.id, { attributes })
            method.reload()
          }}
        />
      </section>

      {unlinked.length > 0 && (
        // **끊긴 연결.** 시험 항목은 정했는데 그 시험 항목이 없어 미정으로 남은 인용 계열 —
        // 그 계열의 장비는 이 규격으로 검색되지 않는다(2026-10-13).
        <div className="space-y-2 rounded-md border border-amber-300 bg-amber-50 p-4 dark:bg-amber-950/30">
          <p className="text-sm">
            <strong>연결되지 않은 인용 계열 {unlinked.length}개.</strong> 이 규격의 시험 항목(
            {one.test_items.map((item) => item.value).join(' · ')})이 그 계열에 없어 미연결
            상태. 그 계열의 장비는 이 규격으로 검색되지 않음.
          </p>
          <p className="text-muted-foreground text-xs">
            {unlinked.map((row) => row.series_name).join(', ')}
          </p>
          {user?.is_system_admin && (
            <Button size="sm" disabled={linking} onClick={() => void linkCitations()}>
              인용 계열에 시험 항목 추가
            </Button>
          )}
        </div>
      )}
      <ErrorNotice error={linkError} />
      {linked && <p className="text-sm">{linked}</p>}
      {detached && <p className="text-sm">{detached}</p>}

      <section className="space-y-3">
        <h2 className="text-base font-semibold">인용한 계열</h2>
        {one.cited_series.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            이 규격을 인용한 카탈로그 계열 없음. 카탈로그에 이 시험을 수행하는 계열이 없거나
            아직 반입 전.
          </p>
        ) : (
          <ul className="flex flex-wrap gap-2 text-sm">
            {one.cited_series.map((row) => (
              <li key={row.series_id}>
                <Link
                  to={`/catalog/equipment-series/${row.series_id}`}
                  className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 hover:underline ${row.pending ? 'border-dashed text-muted-foreground' : ''}`}
                >
                  {row.series_name}
                  {/* 미정은 점선 — 인용은 했는데 어느 시험 항목 밑에 둘지 못 정한 것. */}
                  <span className="text-muted-foreground text-xs">
                    {row.pending ? '시험 항목 미지정' : row.test_item}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-base font-semibold">요구 조건</h2>

        {one.requirements.length === 0 ? (
          <EmptyState
            title="요구 조건 없음"
            hint="조건 입력 시 검색에 이 수치가 그대로 적용됨."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>조건</TableHead>
                <TableHead>최소</TableHead>
                <TableHead>최대</TableHead>
                <TableHead>필수</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {one.requirements.map((requirement) => (
                <TableRow key={requirement.id}>
                  <TableCell>{requirement.condition_label}</TableCell>
                  <TableCell>
                    {shownBound(
                      requirement.min_value,
                      requirement.display_unit || requirement.si_unit,
                    )}
                  </TableCell>
                  <TableCell>
                    {shownBound(
                      requirement.max_value,
                      requirement.display_unit || requirement.si_unit,
                    )}
                  </TableCell>
                  <TableCell>{requirement.is_mandatory ? '필수' : '권고'}</TableCell>
                  <TableCell className="text-right">
                    {one.can_edit && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={async () => {
                          await methodApi.removeRequirement(id, requirement.id)
                          method.reload()
                        }}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {one.can_edit && (
          <div className="flex flex-wrap items-center gap-2 border-t pt-3">
            <Select value={conditionKey} onValueChange={setConditionKey}>
              <SelectTrigger className="w-44">
                <SelectValue placeholder="조건 추가" />
              </SelectTrigger>
              <SelectContent>
                {(conditions.data ?? []).map((condition) => (
                  <SelectItem key={condition.id} value={condition.id}>
                    {condition.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              type="number"
              value={min}
              onChange={(event) => setMin(event.target.value)}
              placeholder="최소 (비우면 없음)"
              className="w-48"
            />
            <Input
              type="number"
              value={max}
              onChange={(event) => setMax(event.target.value)}
              placeholder="최대 (비우면 없음)"
              className="w-48"
            />
            <Button variant="outline" onClick={addRequirement} disabled={!conditionKey}>
              저장
            </Button>
          </div>
        )}

        <ErrorNotice error={error} />
      </section>
      {merging && (
        <MergeDialog
          method={one}
          onClose={() => setMerging(false)}
          onMerged={(target) => {
            setMerging(false)
            void navigate(`/methods/${target.id}`)
          }}
        />
      )}
      {detaching && (
        <DetachDialog
          methodId={id}
          termId={detaching.termId}
          value={detaching.value}
          onClose={() => setDetaching(null)}
          onDone={(impact) => {
            setDetaching(null)
            setDetached(
              `‘${detaching.value}’ 해제됨.` +
                (impact.cut.length > 0
                  ? ` 끊긴 계열 ${impact.cut.length}개는 미연결 인용으로 남음: ${impact.cut.join(', ')}.`
                  : '') +
                (impact.reopened ? ' 남은 시험 항목이 없어 검토함 질문을 다시 엶.' : ''),
            )
            method.reload()
          }}
        />
      )}
      {editing && (
        <MethodEditDialog
          method={one}
          isAdmin={Boolean(user?.is_system_admin)}
          onClose={() => setEditing(false)}
          onSaved={() => {
            setEditing(false)
            method.reload()
          }}
        />
      )}
    </div>
  )
}

/**
 * 기준정보 편집 — **화면에서 고친 것이 사실이 되는 자리.**
 *
 * 전에는 이름 바꾸기·표기 추가·폐기 셋뿐이었다. 코드·상위 값·속성은 API 가 받는데
 * 화면이 안 내밀었고, 병합은 화면에 없었다. 그래서 반입한 값을 고치려면 파일을 고쳐 다시
 * 들이는 수밖에 없었고, 그것은 「화면은 정본이 아니다」 라는 뜻이었다.
 *
 * ## 둘로 나뉜다
 *
 *     축   이름 · 설명 · 정책(열림/닫힘) · **속성 칸** — 이 축의 값이 무엇을 갖는가
 *     값   이름 · 코드 · 상위 값 · 속성 · 표기 · 병합 · 폐기 — 값마다 창 하나
 *
 * 축을 **만드는** 것은 여기 없다. 축은 코드가 걸어야 뜻이 있어서(검색·반입·화면), 화면에서
 * 만든 축은 아무 화면도 안 쓴다. 축이 늘어나는 것은 스키마가 바뀌는 일이다.
 *
 * 합치기는 원본을 **별칭으로 남긴다** — 지우면 같은 오타가 또 들어오고, 그때는 아무도
 * 그것이 예전에 합쳐졌던 값이라는 것을 모른다.
 */

import { useEffect, useMemo, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { Pencil, Plus, Trash2 } from 'lucide-react'

import { ApiError } from '@/shared/api/client'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
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
import { Textarea } from '@/shared/components/ui/textarea'
import { useResource } from '@/shared/hooks/useResource'
import { vocabularyApi } from '@/modules/vocabulary/api'
import type { Term, Vocabulary } from '@/modules/vocabulary/api'
import { TermEditorDialog } from '@/modules/vocabulary/TermEditorDialog'

type Field = Vocabulary['attribute_schema'][number]

/** 축의 정의를 고치는 절. 값 표 위에 접혀 있고, 「축 고치기」 로 편다. */
function AxisEditor({
  axis,
  onSaved,
}: {
  axis: Vocabulary
  onSaved: (next: Vocabulary) => void
}) {
  const [open, setOpen] = useState(false)
  const [label, setLabel] = useState(axis.label)
  const [description, setDescription] = useState(axis.description ?? '')
  const [policy, setPolicy] = useState(axis.entry_policy)
  const [fields, setFields] = useState<Field[]>(axis.attribute_schema ?? [])
  const [error, setError] = useState<ApiError | Error | null>(null)

  useEffect(() => {
    setLabel(axis.label)
    setDescription(axis.description ?? '')
    setPolicy(axis.entry_policy)
    setFields(axis.attribute_schema ?? [])
    setOpen(false)
  }, [axis])

  function setField(index: number, patch: Partial<Field>) {
    setFields((current) => current.map((one, i) => (i === index ? { ...one, ...patch } : one)))
  }

  if (!open) {
    return (
      <div className="flex flex-wrap items-start justify-between gap-2 rounded-md border p-3">
        <div className="min-w-0 space-y-1 text-sm">
          <p>
            <span className="font-medium">{axis.label}</span>{' '}
            <span className="text-muted-foreground font-mono text-xs">{axis.slug}</span>{' '}
            <span className="text-muted-foreground text-xs">
              ·{' '}
              {axis.entry_policy === 'closed'
                ? '닫힘 — 관리자만 값을 더함'
                : '열림 — 누구나 값을 더함'}
              {axis.parent_slug && ` · 상위 축 ${axis.parent_slug}`}
            </span>
          </p>
          {axis.description && <p className="text-muted-foreground">{axis.description}</p>}
          {(axis.attribute_schema ?? []).length > 0 && (
            <p className="text-muted-foreground text-xs">
              값의 칸: {(axis.attribute_schema ?? []).map((one) => one.label).join(' · ')}
            </p>
          )}
        </div>
        <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
          <Pencil className="mr-1 size-3" />축 편집
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-3 rounded-md border p-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor="axis-label">축 이름</Label>
          <Input
            id="axis-label"
            value={label}
            onChange={(event) => setLabel(event.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="axis-policy">값 추가 정책</Label>
          <Select value={policy} onValueChange={setPolicy}>
            <SelectTrigger id="axis-policy">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="open">열림 — 누구나 더한다</SelectItem>
              <SelectItem value="closed">닫힘 — 시스템 관리자만</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="space-y-1">
        <Label htmlFor="axis-description">설명</Label>
        <Textarea
          id="axis-description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={2}
          placeholder="고르는 사람이 축의 뜻을 모르면 비슷한 축 둘 중 아무 데나 값을 넣습니다."
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>값 속성 항목</Label>
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              setFields((current) => [...current, { key: '', label: '', kind: 'text' }])
            }
          >
            <Plus className="mr-1 size-3" />칸 추가
          </Button>
        </div>
        {fields.length === 0 && (
          <p className="text-muted-foreground text-xs">
            없음. 물성처럼 값마다 기호·단위 같은 것이 붙으면 여기 칸을 정합니다 — 그러면 값
            편집 창이 그 칸을 그립니다.
          </p>
        )}
        {fields.map((field, index) => (
          <div key={index} className="flex flex-wrap items-center gap-2">
            <Input
              value={field.key}
              onChange={(event) => setField(index, { key: event.target.value })}
              placeholder="키 (영문)"
              className="w-40 font-mono text-xs"
              aria-label={`속성 ${index + 1} 키`}
            />
            <Input
              value={field.label}
              onChange={(event) => setField(index, { label: event.target.value })}
              placeholder="이름"
              className="w-40"
              aria-label={`속성 ${index + 1} 이름`}
            />
            <Select
              value={field.kind ?? 'text'}
              onValueChange={(kind) => setField(index, { kind })}
            >
              <SelectTrigger className="w-28" aria-label={`속성 ${index + 1} 형`}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="text">글자</SelectItem>
                <SelectItem value="number">숫자</SelectItem>
                <SelectItem value="list">목록</SelectItem>
              </SelectContent>
            </Select>
            <Input
              value={field.help ?? ''}
              onChange={(event) => setField(index, { help: event.target.value || null })}
              placeholder="도움말 (선택)"
              className="w-56"
            />
            <Button
              variant="ghost"
              size="sm"
              aria-label={`속성 ${index + 1} 제거`}
              onClick={() => setFields((current) => current.filter((_, i) => i !== index))}
            >
              <Trash2 className="size-4" />
            </Button>
          </div>
        ))}
      </div>

      <ErrorNotice error={error} />
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={() => setOpen(false)}>
          취소
        </Button>
        <Button
          size="sm"
          onClick={async () => {
            setError(null)
            try {
              const next = await vocabularyApi.updateAxis(axis.slug, {
                label,
                description: description || null,
                entry_policy: policy,
                attribute_schema: fields
                  .filter((one) => one.key.trim() && one.label.trim())
                  .map((one) => ({
                    key: one.key.trim(),
                    label: one.label.trim(),
                    kind: one.kind ?? 'text',
                    ...(one.help ? { help: one.help } : {}),
                  })),
              })
              onSaved(next)
              setOpen(false)
            } catch (caught) {
              setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
            }
          }}
        >
          축 저장
        </Button>
      </div>
    </div>
  )
}

/**
 * 축 하나의 편집 판 — 기준정보 허브의 오른쪽. `canEdit` 이 아니면 읽기만(축 편집·등록·값
 * 편집 단추를 감춘다). 권한은 서버가 판정한다.
 */
export function AxisPanel({ slug, canEdit }: { slug: string; canEdit: boolean }) {
  const axes = useResource(() => vocabularyApi.list(), [])
  const current = slug
  const axis = useMemo(
    () => (axes.data ?? []).find((one) => one.slug === current) ?? null,
    [axes.data, current],
  )
  const terms = useResource(
    () => (current ? vocabularyApi.terms(current) : Promise.resolve([])),
    [current],
  )
  // 상위 축이 따로 있으면 그 축의 값이 상위 값 후보다. 없으면 같은 축(트리).
  const parentTerms = useResource(
    () =>
      axis?.parent_slug ? vocabularyApi.terms(axis.parent_slug) : Promise.resolve<Term[]>([]),
    [axis?.parent_slug],
  )
  const [query, setQuery] = useState('')
  const [value, setValue] = useState('')
  const [code, setCode] = useState('')
  const [editing, setEditing] = useState<Term | null>(null)
  const [error, setError] = useState<ApiError | Error | null>(null)

  async function act(run: () => Promise<unknown>) {
    setError(null)
    try {
      await run()
      terms.reload()
      axes.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

  const needle = query.trim().toLowerCase()
  const shownTerms = (terms.data ?? []).filter(
    (one) =>
      !needle ||
      [one.value, one.code ?? '', ...one.aliases].some((text) =>
        text.toLowerCase().includes(needle),
      ),
  )
  const parentOptions = axis?.parent_slug ? (parentTerms.data ?? []) : (terms.data ?? [])
  const byId = new Map((terms.data ?? []).map((one) => [one.id, one]))

  return (
    <div className="space-y-6">
      <div className="min-w-0 flex-1 space-y-4">
        {axis && canEdit && <AxisEditor axis={axis} onSaved={() => axes.reload()} />}
        {axis && !canEdit && (
          <div className="space-y-1">
            <h2 className="text-base font-semibold">{axis.label}</h2>
            {axis.description && (
              <p className="text-muted-foreground text-sm">{axis.description}</p>
            )}
          </div>
        )}

        <div className="flex flex-wrap items-end gap-2">
          {canEdit && (
            <>
              <Input
                value={value}
                onChange={(event) => setValue(event.target.value)}
                placeholder={axis ? `새 ${axis.label}` : '새 값'}
                className="w-56"
              />
              <Input
                value={code}
                onChange={(event) => setCode(event.target.value)}
                placeholder="코드 (선택)"
                className="w-40 font-mono"
              />
              <Button
                onClick={() =>
                  act(async () => {
                    await vocabularyApi.createTerm(current, { value, code: code || null })
                    setValue('')
                    setCode('')
                  })
                }
                disabled={!value || !current}
              >
                {/* **새 기록을 만드는 단추는 「<대상> 등록」.** 계열 등록·기종 등록·장비
                      등록과 같은 말 — 어느 화면에서 눌러도 같은 일이라는 것이 이름에 보여야
                      한다. 있는 것에 잇는 단추(시험 항목 추가·표기 추가)는 「추가」 로 남긴다. */}
                {axis ? `${axis.label} 등록` : '등록'}
              </Button>
            </>
          )}
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="찾기 — 이름 · 코드 · 표기"
            className="ml-auto w-56"
          />
        </div>

        {/* 서버가 중복을 잡으면 **어느 값과 겹치는지**까지 말해 준다. 그 메시지를
              그대로 보여 준다 — 다시 쓰면 표현이 갈린다. */}
        <ErrorNotice error={error ?? terms.error} />

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>값</TableHead>
              <TableHead>코드</TableHead>
              <TableHead>상위 값</TableHead>
              <TableHead>별칭</TableHead>
              <TableHead>상태</TableHead>
              <TableHead className="text-right">참조</TableHead>
              <TableHead className="text-right"> </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {shownTerms.map((term) => (
              <TableRow key={term.id} className={term.status !== 'active' ? 'opacity-60' : ''}>
                <TableCell>
                  <div>{term.value}</div>
                  {Object.keys(term.attributes).length > 0 && (
                    <div className="text-muted-foreground text-xs">
                      {(axis?.attribute_schema ?? [])
                        .filter((field) => term.attributes[field.key] !== undefined)
                        .map((field) => `${field.label} ${String(term.attributes[field.key])}`)
                        .join(' · ')}
                    </div>
                  )}
                </TableCell>
                <TableCell className="font-mono text-xs">{term.code ?? '—'}</TableCell>
                <TableCell className="text-sm">
                  {term.parent_value ??
                    (term.parent_term_id
                      ? (byId.get(term.parent_term_id)?.value ?? '…')
                      : '—')}
                </TableCell>
                <TableCell className="text-muted-foreground text-sm">
                  {term.aliases.join(', ') || '—'}
                </TableCell>
                <TableCell>{term.status === 'active' ? '사용' : '폐기'}</TableCell>
                <TableCell className="text-right">
                  {/* 수를 누르면 내역이 열린다 — 「12」 만으로는 무엇이 쓰는지 모른다. */}
                  {term.usage_count > 0 ? (
                    <button
                      type="button"
                      className="underline decoration-dotted underline-offset-2"
                      title="이 값의 사용처 보기"
                      onClick={() => setEditing(term)}
                    >
                      {term.usage_count}
                    </button>
                  ) : (
                    <span className="text-muted-foreground">0</span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  {canEdit && (
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={`${term.value} 편집`}
                      onClick={() => setEditing(term)}
                    >
                      <Pencil className="size-4" />
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {axis && (
        <TermEditorDialog
          term={editing}
          axis={axis}
          siblings={terms.data ?? []}
          parentOptions={parentOptions}
          onClose={() => setEditing(null)}
          onChanged={() => {
            terms.reload()
            axes.reload()
            // 편집 중인 값을 새 것으로 바꿔 창이 최신 표기를 보이게 한다.
            if (editing) {
              void vocabularyApi
                .terms(current)
                .then((rows) => setEditing(rows.find((one) => one.id === editing.id) ?? null))
            }
          }}
        />
      )}
    </div>
  )
}

/** 예전 주소(`/admin/vocabulary`)로 온 사람을 허브로 보낸다 — 기준정보는 한 화면이다. */
export default function VocabularyAdminPage() {
  return <Navigate to="/reference" replace />
}

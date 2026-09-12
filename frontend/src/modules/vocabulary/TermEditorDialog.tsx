/**
 * 값 하나를 고치는 창 — **이름·코드·상위 값·속성·표기·병합·폐기, 한 자리에서.**
 *
 * 전에는 줄마다 단추 셋(이름·표기 추가·폐기)이 `window.prompt` 로 물었다. 코드·상위 값·
 * 속성은 API 가 받는데 화면이 안 내밀었고, 물성의 기호·단위 같은 속성은 JSON 이라 아무도
 * 안 고쳤다. 화면이 정본이 되려면 고칠 수 있는 것이 전부 보여야 한다.
 *
 * ## 속성 칸은 축이 정한다
 *
 * 축의 `attribute_schema` 가 「이 값은 기호·단위·설명을 갖는다」 를 말하고, 이 창은 그것을
 * 보고 칸을 그린다. 스키마에 없는 키가 값에 있어도(반입이 넣은 것) 지우지 않는다 —
 * 「그 밖의 속성」 으로 보인다.
 *
 * ## 상위 값
 *
 * 축에 `parent_slug` 가 있으면 그 축의 값을, 없으면 **같은 축**의 값을 고른다(장비 분류
 * 트리). 자기 자신은 고를 수 없다.
 */

import { useEffect, useMemo, useState } from 'react'
import { X } from 'lucide-react'

import { ApiError } from '@/shared/api/client'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { SearchablePicker } from '@/shared/components/SearchablePicker'
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
import { vocabularyApi } from '@/modules/vocabulary/api'
import type { Term, Vocabulary } from '@/modules/vocabulary/api'

type Field = Vocabulary['attribute_schema'][number]

/** 속성 값을 칸에 보이는 글자로. list 는 쉼표로 잇는다. */
function shown(value: unknown, kind: string | undefined): string {
  if (value === null || value === undefined) return ''
  if (kind === 'list' && Array.isArray(value)) return value.map(String).join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

/** 칸의 글자를 저장할 값으로. 빈 칸은 키를 뺀다 — 빈 문자열을 저장하면 「없음」 과 갈린다. */
function parsed(text: string, kind: string | undefined): unknown {
  const trimmed = text.trim()
  if (trimmed === '') return undefined
  if (kind === 'number') {
    const number = Number(trimmed)
    return Number.isNaN(number) ? trimmed : number
  }
  if (kind === 'list') {
    return trimmed
      .split(',')
      .map((one) => one.trim())
      .filter(Boolean)
  }
  return trimmed
}

export function TermEditorDialog({
  term,
  axis,
  siblings,
  parentOptions,
  onClose,
  onChanged,
}: {
  term: Term | null
  axis: Vocabulary
  /** 같은 축의 값들 — 병합 대상. */
  siblings: Term[]
  /** 상위 값 후보. 축에 parent_slug 가 있으면 그 축의 값, 없으면 같은 축의 값. */
  parentOptions: Term[]
  onClose: () => void
  onChanged: () => void
}) {
  const [value, setValue] = useState('')
  const [code, setCode] = useState('')
  const [parent, setParent] = useState('')
  const [fields, setFields] = useState<Record<string, string>>({})
  const [alias, setAlias] = useState('')
  const [mergeInto, setMergeInto] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | Error | null>(null)

  const schema = useMemo<Field[]>(() => axis.attribute_schema ?? [], [axis.attribute_schema])
  /** 스키마에 없는 키 — 반입이 넣은 것. 보이되 편집은 글자로. */
  const extraKeys = useMemo(
    () =>
      Object.keys(term?.attributes ?? {}).filter(
        (key) => !schema.some((field) => field.key === key),
      ),
    [term, schema],
  )

  useEffect(() => {
    if (!term) return
    setValue(term.value)
    setCode(term.code ?? '')
    setParent(term.parent_term_id ?? '')
    const next: Record<string, string> = {}
    for (const field of schema) next[field.key] = shown(term.attributes[field.key], field.kind)
    for (const key of Object.keys(term.attributes))
      if (!(key in next)) next[key] = shown(term.attributes[key], undefined)
    setFields(next)
    setAlias('')
    setMergeInto('')
    setError(null)
  }, [term, schema])

  async function run(work: () => Promise<unknown>, { close = false } = {}) {
    setBusy(true)
    setError(null)
    try {
      await work()
      onChanged()
      if (close) onClose()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  function save() {
    if (!term) return
    const attributes: Record<string, unknown> = {}
    for (const field of schema) {
      const one = parsed(fields[field.key] ?? '', field.kind)
      if (one !== undefined) attributes[field.key] = one
    }
    for (const key of extraKeys) {
      const one = parsed(fields[key] ?? '', undefined)
      if (one !== undefined) attributes[key] = one
    }
    void run(
      () =>
        vocabularyApi.updateTerm(term.id, {
          value,
          code: code.trim() || null,
          // 「안 보낸 것」 과 「비운 것」 이 다르다 — 상위 값을 비우는 길은 아직 없어서
          // 빈 값이면 안 보낸다.
          ...(parent ? { parent_term_id: parent } : {}),
          attributes,
        }),
      { close: true },
    )
  }

  const open = term !== null
  const usage = term?.usage_count ?? 0

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{term?.value ?? ''}</DialogTitle>
          <DialogDescription>
            {axis.label}
            {usage > 0 && (
              <>
                {' '}
                · <strong>{usage}군데</strong>서 쓰입니다 — 이름을 바꾸면 그곳 전부의 표시가
                바뀝니다.
              </>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-1">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="term-value">이름</Label>
              <Input
                id="term-value"
                value={value}
                onChange={(event) => setValue(event.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="term-code">코드</Label>
              <Input
                id="term-code"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                placeholder="코드가 거는 이름 — 바꾸면 반입·검색이 못 찾습니다"
                className="font-mono"
              />
            </div>
          </div>

          {parentOptions.length > 0 && (
            <div className="space-y-1">
              <Label htmlFor="term-parent">상위 값</Label>
              <SearchablePicker
                id="term-parent"
                options={parentOptions
                  .filter((one) => one.id !== term?.id)
                  .map((one) => ({ id: one.id, label: one.value, detail: one.code }))}
                value={parent}
                onChange={setParent}
                placeholder="없음"
                detailTitle="상위 값"
              />
            </div>
          )}

          {(schema.length > 0 || extraKeys.length > 0) && (
            <div className="space-y-2">
              <p className="text-sm font-medium">속성</p>
              <div className="grid gap-3 sm:grid-cols-2">
                {schema.map((field) => (
                  <div key={field.key} className="space-y-1">
                    <Label htmlFor={`attr-${field.key}`}>
                      {field.label}
                      {field.help && (
                        <span className="text-muted-foreground ml-2 font-normal">
                          {field.help}
                        </span>
                      )}
                    </Label>
                    <Input
                      id={`attr-${field.key}`}
                      value={fields[field.key] ?? ''}
                      onChange={(event) =>
                        setFields((current) => ({
                          ...current,
                          [field.key]: event.target.value,
                        }))
                      }
                      placeholder={field.kind === 'list' ? '쉼표로 나눕니다' : undefined}
                    />
                  </div>
                ))}
                {extraKeys.map((key) => (
                  <div key={key} className="space-y-1">
                    <Label htmlFor={`attr-${key}`}>
                      <span className="font-mono">{key}</span>
                      <span className="text-muted-foreground ml-2 font-normal">
                        그 밖의 속성
                      </span>
                    </Label>
                    <Input
                      id={`attr-${key}`}
                      value={fields[key] ?? ''}
                      onChange={(event) =>
                        setFields((current) => ({ ...current, [key]: event.target.value }))
                      }
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-2">
            <p className="text-sm font-medium">다른 표기</p>
            <div className="flex flex-wrap items-center gap-1.5">
              {(term?.aliases ?? []).map((one) => (
                <span
                  key={one}
                  className="bg-muted inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs"
                >
                  {one}
                  <button
                    type="button"
                    aria-label={`표기 ${one} 떼기`}
                    className="hover:text-destructive"
                    disabled={busy || !term}
                    onClick={() =>
                      term && void run(() => vocabularyApi.removeAlias(term.id, one))
                    }
                  >
                    <X className="size-3" />
                  </button>
                </span>
              ))}
              {(term?.aliases ?? []).length === 0 && (
                <span className="text-muted-foreground text-xs">없음</span>
              )}
            </div>
            <div className="flex gap-2">
              <Input
                value={alias}
                onChange={(event) => setAlias(event.target.value)}
                placeholder="이 값을 부르는 다른 이름 — UTM · 만능시험기"
                className="max-w-xs"
              />
              <Button
                variant="outline"
                size="sm"
                disabled={!alias.trim() || busy || !term}
                onClick={() =>
                  term &&
                  void run(async () => {
                    await vocabularyApi.addAlias(term.id, alias.trim())
                    setAlias('')
                  })
                }
              >
                표기 추가
              </Button>
            </div>
          </div>

          <div className="space-y-2 rounded-md border p-3">
            <p className="text-sm font-medium">다른 값으로 합치기</p>
            <p className="text-muted-foreground text-xs">
              이 값을 가리키던 것 전부가 대상으로 옮겨 가고, 이 이름은 대상의 표기로 남습니다.
              되돌릴 수 없습니다.
            </p>
            <div className="flex flex-wrap gap-2">
              <SearchablePicker
                options={siblings
                  .filter((one) => one.id !== term?.id)
                  .map((one) => ({ id: one.id, label: one.value, detail: one.code }))}
                value={mergeInto}
                onChange={setMergeInto}
                placeholder="합칠 대상"
                detailTitle={axis.label}
                className="w-72"
              />
              <Button
                variant="destructive"
                size="sm"
                disabled={!mergeInto || busy || !term}
                onClick={() =>
                  term &&
                  window.confirm(`「${term.value}」 을(를) 합치고 지웁니다. 계속할까요?`) &&
                  void run(() => vocabularyApi.mergeTerm(term.id, mergeInto), { close: true })
                }
              >
                합치기
              </Button>
            </div>
          </div>

          <ErrorNotice error={error} />
        </div>

        <DialogFooter className="flex-wrap gap-2 sm:justify-between">
          <Button
            variant="ghost"
            disabled={busy || !term}
            onClick={() =>
              term &&
              void run(() =>
                vocabularyApi.updateTerm(term.id, {
                  // **지우지 않고 폐기한다.** 지우면 그 값을 가리키던 장비가 무엇이었는지
                  // 알 수 없게 된다.
                  status: term.status === 'active' ? 'deprecated' : 'active',
                }),
              )
            }
          >
            {term?.status === 'active' ? '폐기' : '되살리기'}
          </Button>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose} disabled={busy}>
              닫기
            </Button>
            <Button onClick={save} disabled={busy || !value.trim()}>
              저장
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

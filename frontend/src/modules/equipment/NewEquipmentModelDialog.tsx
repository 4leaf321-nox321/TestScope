/**
 * 장비 기종 등록.
 *
 * **계열을 먼저 고른다.** 제조사·분류·시험 항목은 계열이 갖고, 여기에는 그 기종만의
 * 것이 온다 — 수치 사양·생김새(ADR 0006).
 *
 * 기종명에 계열 이름을 섞지 않는다. 섞으면 `6800 68FM-300` 과 `68FM-300` 이 별개
 * 기종으로 갈리고, 그 둘을 나중에 묶을 방법이 없다.
 */

import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError } from '@/shared/api/client'
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
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import { SearchablePicker } from '@/shared/components/SearchablePicker'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import { Textarea } from '@/shared/components/ui/textarea'
import { useResource } from '@/shared/hooks/useResource'
import { AXIS, vocabularyApi } from '@/modules/vocabulary/api'
import { catalogApi, seriesApi } from '@/modules/equipment/api'

export function NewEquipmentModelDialog({
  open,
  seriesId,
  onClose,
  onCreated,
}: {
  open: boolean
  /** 계열 상세에서 열면 그 계열로 고정된다 — 거기서 고를 이유가 없다. */
  seriesId?: string
  onClose: () => void
  onCreated: () => void
}) {
  const list = useResource(() => seriesApi.list({ limit: 200 }), [])
  // 형태는 축의 값이다 — 열여섯 남짓이라 피커 하나로 다 보인다.
  const formFactors = useResource(() => vocabularyApi.terms(AXIS.formFactor), [])

  const [series, setSeries] = useState(seriesId ?? '')
  const [name, setName] = useState('')
  const [nameKo, setNameKo] = useState('')
  const [formFactor, setFormFactor] = useState('')
  const [summary, setSummary] = useState('')
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (seriesId) setSeries(seriesId)
  }, [seriesId])

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await catalogApi.create({
        series_id: series,
        name,
        name_ko: nameKo || null,
        form_factor_term_id: formFactor || null,
        summary: summary || null,
      })
      setName('')
      setNameKo('')
      setFormFactor('')
      setSummary('')
      onCreated()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && !busy && onClose()}>
      <DialogContent>
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>장비 기종 등록</DialogTitle>
            <DialogDescription>
              수치 사양은 등록한 뒤 상세 화면에서 적습니다. 검색축에 이어진 사양은 이 기종으로
              등록하는 보유 장비의 시험 조건이 됩니다.
            </DialogDescription>
          </DialogHeader>

          {!seriesId && (
            <div className="space-y-2">
              <Label htmlFor="model-series">계열</Label>
              <Select value={series} onValueChange={setSeries}>
                <SelectTrigger id="model-series">
                  <SelectValue placeholder="계열 고르기" />
                </SelectTrigger>
                <SelectContent>
                  {(list.data?.items ?? []).map((one) => (
                    <SelectItem key={one.id} value={one.id}>
                      {[one.maker, one.name_ko || one.name].filter(Boolean).join(' · ')}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-muted-foreground text-xs">
                없으면 계열을 먼저 만듭니다. 단품이라도 기종 하나짜리 계열로 둡니다.
              </p>
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="model-name">기종명</Label>
            <Input
              id="model-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="68FM-300"
              required
            />
            <p className="text-muted-foreground text-xs">
              계열 이름은 위 칸이 갖습니다. 이름에 같이 적지 마세요.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="model-name-ko">한글 이름</Label>
              <Input
                id="model-name-ko"
                value={nameKo}
                onChange={(event) => setNameKo(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="model-form">기종 형태</Label>
              {/* **자유 문자열이 아니라 축이다.** 전에는 `dual_column_tabletop` 을
                  손으로 적게 두어서, 화면에 영어가 그대로 뜨고 「탁상형만」 으로
                  거를 수도 없었다. */}
              <SearchablePicker
                id="model-form"
                value={formFactor}
                onChange={setFormFactor}
                options={(formFactors.data ?? []).map((one) => ({
                  id: one.id,
                  label: one.value,
                  detail: one.code,
                }))}
                placeholder="형태 고르기"
                detailTitle="기종 형태"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="model-summary">한 줄 설명</Label>
            <Textarea
              id="model-summary"
              value={summary}
              onChange={(event) => setSummary(event.target.value)}
              rows={2}
            />
          </div>

          <ErrorNotice error={error} />

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
              취소
            </Button>
            <Button type="submit" disabled={busy || !series}>
              {busy ? '등록 중…' : '등록'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

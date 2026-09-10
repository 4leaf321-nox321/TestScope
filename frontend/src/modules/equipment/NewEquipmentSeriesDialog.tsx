/**
 * 장비 계열 등록.
 *
 * **계열명만 적는다. 제조사는 옆 칸이 갖는다** — 이름에 섞으면 `Instron 6800` 과
 * `6800` 이 별개 계열로 갈리고, 그 둘을 나중에 묶을 방법이 없다.
 *
 * 부속(챔버·퍼니스·신율계)도 여기서 만든다. 부속도 계열이다 — 챔버에도 모델이
 * 여럿이고 온도 범위가 갈린다(ADR 0006).
 */

import { useState } from 'react'
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
import { seriesApi } from '@/modules/equipment/api'

export function NewEquipmentSeriesDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean
  onClose: () => void
  onCreated: () => void
}) {
  const makers = useResource(() => vocabularyApi.terms(AXIS.manufacturer), [])
  const categories = useResource(() => vocabularyApi.terms(AXIS.equipmentCategory), [])

  const [name, setName] = useState('')
  const [nameKo, setNameKo] = useState('')
  const [kind, setKind] = useState('main')
  const [maker, setMaker] = useState('')
  const [category, setCategory] = useState('')
  const [summary, setSummary] = useState('')
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await seriesApi.create({
        name,
        name_ko: nameKo || null,
        kind,
        maker_term_id: maker || null,
        category_term_id: category || null,
        summary: summary || null,
      })
      setName('')
      setNameKo('')
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
            <DialogTitle>장비 계열 등록</DialogTitle>
            <DialogDescription>
              무슨 시험이 되는지는 등록한 뒤 상세 화면에서 적습니다. 수치 사양은 그 안의 기종이
              갖습니다 — 한 계열 안에서 하중이 수백 배 갈리기 때문입니다.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label htmlFor="series-name">계열명</Label>
            <Input
              id="series-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="6800 Series Universal Testing Systems"
              required
            />
            <p className="text-muted-foreground text-xs">
              제조사는 아래에서 고릅니다. 이름에 같이 적지 마세요.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="series-name-ko">한글 이름</Label>
              {/* **검색이 이것으로도 걸려야 한다** — 사람은 「인스트론 6800」 으로
                  찾지 영문 정식 명칭으로 찾지 않는다. */}
              <Input
                id="series-name-ko"
                value={nameKo}
                onChange={(event) => setNameKo(event.target.value)}
                placeholder="인스트론 6800 시리즈 만능재료시험기"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="series-kind">종류</Label>
              <Select value={kind} onValueChange={setKind}>
                <SelectTrigger id="series-kind">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="main">본체</SelectItem>
                  <SelectItem value="accessory">부속</SelectItem>
                  <SelectItem value="sensor">센서</SelectItem>
                  <SelectItem value="software">소프트웨어</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="series-maker">제조사</Label>
              <Select value={maker} onValueChange={setMaker}>
                <SelectTrigger id="series-maker">
                  <SelectValue placeholder="선택 (자작이면 비움)" />
                </SelectTrigger>
                <SelectContent>
                  {(makers.data ?? []).map((one) => (
                    <SelectItem key={one.id} value={one.id}>
                      {one.value}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="series-category">장비 분류</Label>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger id="series-category">
                  <SelectValue placeholder="선택" />
                </SelectTrigger>
                <SelectContent>
                  {(categories.data ?? []).map((one) => (
                    <SelectItem key={one.id} value={one.id}>
                      {one.value}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="series-summary">한 줄 설명</Label>
            <Textarea
              id="series-summary"
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
            <Button type="submit" disabled={busy}>
              {busy ? '등록 중…' : '등록'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

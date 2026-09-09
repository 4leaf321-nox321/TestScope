/**
 * 교정 이력.
 *
 * **역량과 별개의 칸이다.** 장비가 20 kN 을 낼 수 있다는 것과 그 값이 지금 믿을
 * 만하다는 것은 다른 이야기다. 기한이 지난 장비도 목록에는 남되, 화면이 그 사실을
 * 말해 줘야 한다 — 말 안 하면 사람은 만료된 장비로 시험을 잡는다.
 */

import { useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError } from '@/shared/api/client'
import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
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
import { equipmentApi } from '@/modules/equipment/api'

function isOverdue(due: string | null): boolean {
  if (!due) return false
  return new Date(due).getTime() < Date.now()
}

export function CalibrationPanel({
  equipmentId,
  canEdit,
}: {
  equipmentId: string
  canEdit: boolean
}) {
  const list = useResource(() => equipmentApi.calibrations(equipmentId), [equipmentId])
  const [calibratedOn, setCalibratedOn] = useState('')
  const [nextDueOn, setNextDueOn] = useState('')
  const [certificate, setCertificate] = useState('')
  const [error, setError] = useState<ApiError | Error | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      await equipmentApi.addCalibration(equipmentId, {
        calibrated_on: calibratedOn,
        next_due_on: nextDueOn || null,
        certificate_no: certificate || null,
      })
      setCalibratedOn('')
      setNextDueOn('')
      setCertificate('')
      list.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

  return (
    <div className="space-y-4">
      {canEdit && (
        <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
          <div className="space-y-2">
            <Label htmlFor="calibrated-on">교정일</Label>
            <Input
              id="calibrated-on"
              type="date"
              value={calibratedOn}
              onChange={(event) => setCalibratedOn(event.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="next-due">다음 예정일</Label>
            <Input
              id="next-due"
              type="date"
              value={nextDueOn}
              onChange={(event) => setNextDueOn(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="certificate">성적서 번호</Label>
            <Input
              id="certificate"
              value={certificate}
              onChange={(event) => setCertificate(event.target.value)}
            />
          </div>
          <Button type="submit">기록 추가</Button>
        </form>
      )}

      <ErrorNotice error={error ?? list.error} />

      {list.data && list.data.length === 0 ? (
        <EmptyState
          title="교정 기록이 없습니다"
          hint="교정 기록이 없으면 이 장비의 값이 지금 믿을 만한지 아무도 답할 수 없습니다."
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>교정일</TableHead>
              <TableHead>다음 예정일</TableHead>
              <TableHead>성적서</TableHead>
              <TableHead>기관</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(list.data ?? []).map((one) => (
              <TableRow key={one.id}>
                <TableCell>{shownDate(one.calibrated_on)}</TableCell>
                <TableCell>
                  {shownDate(one.next_due_on)}
                  {/* **지났으면 말한다.** 날짜만 적어 두면 사람이 오늘 날짜와
                      비교해야 하고, 대개 안 한다. */}
                  {isOverdue(one.next_due_on) && (
                    <span className="text-destructive ml-2 text-xs">기한 지남</span>
                  )}
                </TableCell>
                <TableCell>{one.certificate_no ?? '—'}</TableCell>
                <TableCell>{one.provider ?? '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}

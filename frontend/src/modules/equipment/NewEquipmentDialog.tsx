/**
 * 장비 등록.
 *
 * **자산번호와 이름만 필수다.** 나머지를 다 채워야 저장되면 사람은 임시값을 넣고,
 * 그 임시값은 영원히 남는다 — 빈 칸은 나중에 채울 수 있지만 틀린 값은 안 고쳐진다.
 */

import { useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError } from '@/shared/api/client'
import { useAuth } from '@/shared/auth/AuthContext'
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
import { useResource } from '@/shared/hooks/useResource'
import { ModelPicker } from '@/modules/equipment/ModelPicker'
import { AXIS, vocabularyApi } from '@/modules/vocabulary/api'
import { equipmentApi } from '@/modules/equipment/api'

export function NewEquipmentDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean
  onClose: () => void
  onCreated: () => void
}) {
  const { user } = useAuth()
  // **제조사·분류·모델명은 카탈로그가 갖는다.** 여기서는 고르기만 한다(ADR 0004).
  const sites = useResource(() => vocabularyApi.terms(AXIS.site), [])

  const [assetNo, setAssetNo] = useState('')
  const [name, setName] = useState('')
  const [model, setModel] = useState('')
  const [site, setSite] = useState('')
  const [location, setLocation] = useState('')
  // 소속이 여럿이면 어느 부서 것인지 사람이 정해야 한다. 하나면 그것으로 채운다.
  const managed = (user?.memberships ?? []).filter(
    (one) => one.role === 'manager' || user?.is_system_admin,
  )
  const [workspace, setWorkspace] = useState(managed[0]?.slug ?? '')
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await equipmentApi.create({
        asset_no: assetNo,
        name,
        workspace_slug: workspace || null,
        // 모델을 고르면 **그 모델의 사양서 역량이 이 장비로 복사된다.**
        model_id: model || null,
        site_term_id: site || null,
        location: location || null,
      })
      setAssetNo('')
      setName('')
      onCreated()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && !busy && onClose()}>
      {/* **넓힌다.** 기종 칸에는 「Instron · 6800 Series Universal Testing Systems ·
          68FM-300」 이 들어간다 — 512px 두 칸으로 쪼개면 그 줄이 잘려서, 고른 것이
          맞는지 확인할 수가 없다. 고르는 것이 이 창의 요점인데. */}
      <DialogContent className="sm:max-w-3xl">
        <form onSubmit={submit} className="space-y-6">
          <DialogHeader>
            <DialogTitle>장비 등록</DialogTitle>
            <DialogDescription>
              기종을 고르면 그 계열의 역량이 복사됩니다. 안 고르면 상세 화면에서 직접
              적어야 검색에 걸립니다.
            </DialogDescription>
          </DialogHeader>

          {/* 묶는 순서가 사람이 아는 순서다 — **무엇인지 먼저, 어디 있는지 다음.**
              라벨을 보며 앞의 둘을 적고, 그다음 고개를 들어 자리를 적는다. */}
          <section className="space-y-4">
            <h3 className="text-muted-foreground text-xs font-medium">무엇인가</h3>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="asset-no">자산번호</Label>
                <Input
                  id="asset-no"
                  value={assetNo}
                  onChange={(event) => setAssetNo(event.target.value)}
                  placeholder="UTM-001"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="equipment-name">장비 이름</Label>
                <Input
                  id="equipment-name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="만능재료시험기 300kN"
                  required
                />
              </div>
            </div>

            {/* **한 줄을 통째로 준다.** 이 창에서 제일 중요한 칸이고, 고른 결과가
                길다 — 반 칸에 넣으면 확인이 안 된다. */}
            <div className="space-y-2">
              <Label htmlFor="model">장비 기종</Label>
              {/* **목록을 받아 두지 않는다.** 563기종을 200개씩 받으면 나머지는
                  조용히 안 보이고, 못 찾은 사람은 빈 칸으로 저장한다. */}
              <ModelPicker id="model" value={model} onChange={(id) => setModel(id)} />
              <p className="text-muted-foreground text-xs">
                고르면 그 기종이 속한 계열의 역량이 이 장비로 복사되고, 조건은 이 기종의
                사양에서 옵니다. <strong>카탈로그에 없으면 비워 두세요</strong> — 비슷한
                기종을 고르면 그 장비의 하중·온도가 남의 것이 됩니다.
              </p>
            </div>
          </section>

          <section className="space-y-4 border-t pt-4">
            <h3 className="text-muted-foreground text-xs font-medium">어디에 있나</h3>
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="workspace">보유 부서</Label>
                <Select value={workspace} onValueChange={setWorkspace}>
                  <SelectTrigger id="workspace" className="w-full">
                    <SelectValue placeholder="부서" />
                  </SelectTrigger>
                  <SelectContent>
                    {managed.map((one) => (
                      <SelectItem key={one.slug} value={one.slug}>
                        {one.path}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="site">거점</Label>
                {/* **실무에서 가장 먼저 묻는 것이다** — 가려면 이동해야 하는 단위라서. */}
                <Select value={site} onValueChange={setSite}>
                  <SelectTrigger id="site" className="w-full">
                    <SelectValue placeholder="선택" />
                  </SelectTrigger>
                  <SelectContent>
                    {(sites.data ?? []).map((one) => (
                      <SelectItem key={one.id} value={one.id}>
                        {one.value}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="location">설치 위치</Label>
                <Input
                  id="location"
                  value={location}
                  onChange={(event) => setLocation(event.target.value)}
                  placeholder="3동 201호"
                />
              </div>
            </div>
          </section>

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

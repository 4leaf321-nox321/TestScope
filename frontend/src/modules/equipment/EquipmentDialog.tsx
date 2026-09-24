/**
 * 보유 장비 등록·수정.
 *
 * **한 벌이다.** 등록 창과 수정 창을 따로 두면 칸이 갈라지고, 그때 「등록은 되는데 수정은
 * 안 되는 칸」 이 생긴다 — 그 칸은 반입(엑셀)으로만 고칠 수 있게 되고, 한 대의 위치를
 * 바꾸려고 대장을 통째로 다시 붙여넣게 된다.
 *
 * **자산번호는 수정에서 못 고친다.** 서버가 안 받는다(`EquipmentUpdateRequest`) — 그것이
 * 이 장비를 가리키는 이름이라, 바꾸면 밖에 나간 문서·라벨과 어긋난다.
 *
 * ## 무엇을 필수로 두나
 *
 *     자산번호 · 장비명 · 보유 부서 · 거점 · 설치위치 · 무슨 종류인가
 *
 * **전부 「없으면 그 장비를 못 찾는」 칸이다.** 어디 있는지 모르는 장비는 찾아도
 * 소용이 없고, 종류를 모르는 장비는 분류로 좁히는 화면에서 통째로 빠진다.
 *
 * 나머지는 권장이나 선택이다 — 다 채워야 저장되게 하면 사람은 임시값을 넣고, 그
 * 임시값은 영원히 남는다. 빈 칸은 나중에 채울 수 있지만 틀린 값은 안 고쳐진다.
 *
 * ## 종류는 기종을 고르면 따라온다
 *
 * 분류는 그 기종이 속한 계열이 갖는다(ADR 0006). 기종을 못 찾아 비웠을 때만 장비유형을
 * 직접 고르고, 제조사·모델명도 그때만 글자로 적는다 — **그 글자는 검색이 안 본다.**
 */

import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError } from '@/shared/api/client'
import { useAuth } from '@/shared/auth/AuthContext'
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
import { Textarea } from '@/shared/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import { useResource } from '@/shared/hooks/useResource'
import {
  AttributeValuesEditor,
  fromValues,
  toPayload,
} from '@/modules/attributes/AttributeValuesEditor'
import type { AttributeRow } from '@/modules/attributes/AttributeValuesEditor'
import { ModelPicker } from '@/modules/equipment/ModelPicker'
import { EQUIPMENT_STATUS_OPTIONS } from '@/modules/equipment/status'
import { AXIS, vocabularyApi } from '@/modules/vocabulary/api'
import { equipmentApi } from '@/modules/equipment/api'
import type { Equipment } from '@/modules/equipment/api'

export function EquipmentDialog({
  open,
  editing = null,
  onClose,
  onSaved,
}: {
  open: boolean
  /** 있으면 수정, 없으면 등록. */
  editing?: Equipment | null
  onClose: () => void
  onSaved: () => void
}) {
  const { user } = useAuth()
  const sites = useResource(() => vocabularyApi.terms(AXIS.site), [])
  // 분류는 108종이다. **스물을 넘으면 `<Select>` 를 쓰지 않는다**(AGENTS.md) —
  // 못 찾은 사람은 없다고 결론 내리고 새로 만든다.
  const categories = useResource(() => vocabularyApi.terms(AXIS.equipmentCategory), [])

  const [assetNo, setAssetNo] = useState('')
  const [name, setName] = useState('')
  const [deptAssetNo, setDeptAssetNo] = useState('')
  const [serialNo, setSerialNo] = useState('')

  const [model, setModel] = useState('')
  const [category, setCategory] = useState('')
  const [makerText, setMakerText] = useState('')
  const [modelText, setModelText] = useState('')

  // 소속이 여럿이면 어느 부서 것인지 사람이 정해야 한다. 하나면 그것으로 채운다.
  const managed = (user?.memberships ?? []).filter(
    (one) => one.role === 'manager' || user?.is_system_admin,
  )
  const [workspace, setWorkspace] = useState(managed[0]?.slug ?? '')
  const [site, setSite] = useState('')
  const [location, setLocation] = useState('')
  const [shared, setShared] = useState(false)

  const [status, setStatus] = useState('operational')
  const [acquiredOn, setAcquiredOn] = useState('')
  const [madeYear, setMadeYear] = useState('')

  const [calibrated, setCalibrated] = useState(false)
  const [interval, setInterval] = useState('12')

  const [note, setNote] = useState('')
  const [retiredOn, setRetiredOn] = useState('')

  const [attributes, setAttributes] = useState<AttributeRow[]>([])
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [busy, setBusy] = useState(false)

  const linked = model !== ''
  const siteId = (value: string | null) =>
    (sites.data ?? []).find((one) => one.value === value)?.id ?? ''
  const categoryId = (value: string | null) =>
    (categories.data ?? []).find((one) => one.value === value)?.id ?? ''

  /**
   * 열 때마다 대상에 맞춰 채운다 — **지난번에 적던 값이 남아 있으면 안 된다.**
   *
   * 거점·분류는 응답이 **이름**으로 온다(`site` · `category`). 고르는 칸은 id 를 쓰므로
   * 목록에서 되짚는다 — 그래서 목록이 도착한 뒤에도 한 번 더 돈다.
   */
  useEffect(() => {
    if (!open) return
    setError(null)
    setAssetNo(editing?.asset_no ?? '')
    setName(editing?.name ?? '')
    setDeptAssetNo(editing?.dept_asset_no ?? '')
    setSerialNo(editing?.serial_no ?? '')
    setModel(editing?.model_id ?? '')
    setCategory(editing ? categoryId(editing.category) : '')
    setMakerText(editing?.catalog_linked ? '' : (editing?.manufacturer ?? ''))
    setModelText(editing?.catalog_linked ? '' : (editing?.model_name ?? ''))
    setWorkspace(editing?.workspace_slug ?? managed[0]?.slug ?? '')
    setSite(editing ? siteId(editing.site) : '')
    setLocation(editing?.location ?? '')
    setShared(editing?.shared_use ?? false)
    setStatus(editing?.status ?? 'operational')
    setAcquiredOn(editing?.acquired_on ?? '')
    setMadeYear(editing?.manufactured_year ? String(editing.manufactured_year) : '')
    setCalibrated(editing?.calibration_required ?? false)
    setInterval(
      editing?.calibration_interval_months
        ? String(editing.calibration_interval_months)
        : '12',
    )
    setNote(editing?.note ?? '')
    setRetiredOn(editing?.retired_on ?? '')
    setAttributes(fromValues(editing?.attributes ?? []))
    // 기준정보 목록이 늦게 와도 거점·분류가 채워지게 같이 본다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, editing, sites.data, categories.data])

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      // **빈 칸은 `null` 로 보낸다.** 수정에서 안 보낸 칸은 「안 바꿈」 이라, 비우려고
      // 지운 값이 그냥 남는다(`EquipmentUpdateRequest` 의 주석과 짝).
      const body = {
        name,
        dept_asset_no: deptAssetNo || null,
        serial_no: serialNo || null,
        workspace_slug: workspace,
        site_term_id: site,
        location,
        shared_use: shared,
        // 기종을 고르면 **그 계열의 시험 항목이 이 장비로 복사된다.**
        model_id: model || null,
        // 기종이 있으면 아래 셋은 안 보낸다 — 서버가 어차피 비운다.
        category_term_id: linked ? null : category || null,
        maker_text: linked ? null : makerText || null,
        model_text: linked ? null : modelText || null,
        status,
        acquired_on: acquiredOn || null,
        manufactured_year: madeYear ? Number(madeYear) : null,
        calibration_required: calibrated,
        calibration_interval_months: calibrated && interval ? Number(interval) : null,
        retired_on: status === 'retired' ? retiredOn || null : null,
        note: note || null,
        attributes: toPayload(attributes),
      }
      if (editing) {
        // **자산번호는 안 보낸다** — 서버가 안 받는다. 이 장비를 가리키는 이름이라,
        // 바꾸면 밖에 나간 문서·라벨과 어긋난다.
        await equipmentApi.update(editing.id, body)
      } else {
        await equipmentApi.create({ ...body, asset_no: assetNo })
      }
      onSaved()
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
            <DialogTitle>{editing ? '보유 장비 수정' : '장비 등록'}</DialogTitle>
            <DialogDescription>
              {editing
                ? '자산번호는 바꿀 수 없습니다 — 이 장비를 가리키는 이름이라 밖에 나간 문서·라벨과 어긋납니다. 시험 항목·사양·교정 이력은 상세 화면의 탭에서 고칩니다.'
                : '기종을 고르면 그 계열의 시험 항목이 복사되고 분류·제조사가 따라옵니다. 안 고르면 장비유형을 직접 골라야 합니다.'}
            </DialogDescription>
          </DialogHeader>

          {/* 묶는 순서가 사람이 아는 순서다 — **무엇인지 먼저, 어디 있는지 다음.**
              라벨을 보며 앞의 둘을 적고, 그다음 고개를 들어 자리를 적는다. */}
          <section className="space-y-4">
            <h3 className="text-muted-foreground text-xs font-medium">장비 구분</h3>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="asset-no">자산번호</Label>
                <Input
                  id="asset-no"
                  value={assetNo}
                  onChange={(event) => setAssetNo(event.target.value)}
                  placeholder="UTM-001"
                  required
                  // 수정에서는 못 고친다 — 서버가 안 받는다. 칸을 숨기지는 않는다:
                  // 어느 장비를 고치고 있는지가 보여야 한다.
                  disabled={editing !== null}
                  readOnly={editing !== null}
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
                <p className="text-muted-foreground text-xs">
                  현장에서 부르는 이름입니다. 사람이 찾을 때 치는 말이 이쪽입니다.
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="dept-asset-no">부서관리번호</Label>
                <Input
                  id="dept-asset-no"
                  value={deptAssetNo}
                  onChange={(event) => setDeptAssetNo(event.target.value)}
                  placeholder="선택 · 부서 안에서만 유일하면 됩니다"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="serial-no">제조번호</Label>
                <Input
                  id="serial-no"
                  value={serialNo}
                  onChange={(event) => setSerialNo(event.target.value)}
                  placeholder="SN-5982"
                />
              </div>
            </div>

            {/* **한 줄을 통째로 준다.** 이 창에서 제일 중요한 칸이고, 고른 결과가
                길다 — 반 칸에 넣으면 확인이 안 된다. */}
            <div className="space-y-2">
              <Label htmlFor="model">장비 기종</Label>
              {/* **목록을 받아 두지 않는다.** 714기종을 200개씩 받으면 나머지는
                  조용히 안 보이고, 못 찾은 사람은 빈 칸으로 저장한다. */}
              <ModelPicker id="model" value={model} onChange={(id) => setModel(id)} />
              <p className="text-muted-foreground text-xs">
                고르면 그 기종이 속한 계열의 시험 항목이 이 장비로 복사되고, 조건은 이 기종의
                사양에서 옵니다. <strong>카탈로그에 없으면 비워 두십시오</strong> — 비슷한
                기종을 고르면 그 장비의 하중·온도가 남의 것이 됩니다.
              </p>
            </div>

            {/* 기종을 안 골랐을 때만. 골랐으면 이 셋은 카탈로그가 갖는다. */}
            {!linked && (
              <div className="bg-muted/40 space-y-4 rounded-md border p-3">
                <p className="text-xs">
                  카탈로그에 없는 장비입니다. <strong>장비유형은 반드시 고르십시오</strong> —
                  종류를 모르는 장비는 분류로 좁히는 화면에서 통째로 빠집니다.
                </p>
                <div className="space-y-2">
                  <Label htmlFor="category">장비유형</Label>
                  <SearchablePicker
                    id="category"
                    value={category}
                    onChange={setCategory}
                    options={(categories.data ?? []).map((one) => ({
                      id: one.id,
                      label: one.value,
                    }))}
                    placeholder="유형 선택"
                    detailTitle="장비유형"
                    detailHint="장비군 아래의 유형입니다. 고르면 장비군은 따라옵니다."
                  />
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="maker-text">제조사</Label>
                    <Input
                      id="maker-text"
                      value={makerText}
                      onChange={(event) => setMakerText(event.target.value)}
                      placeholder="사내 제작"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="model-text">모델명</Label>
                    <Input
                      id="model-text"
                      value={modelText}
                      onChange={(event) => setModelText(event.target.value)}
                      placeholder="자작-1호"
                    />
                  </div>
                </div>
                <p className="text-muted-foreground text-xs">
                  이 둘은 <strong>표시용입니다</strong> — 기준정보와 이어져 있지 않아 검색이
                  보지 않습니다. 나중에 기종에 연결하면 지워집니다.
                </p>
              </div>
            )}
          </section>

          <section className="space-y-4 border-t pt-4">
            <h3 className="text-muted-foreground text-xs font-medium">설치 위치</h3>
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
                  required
                />
              </div>
            </div>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={shared}
                onChange={(event) => setShared(event.target.checked)}
              />
              <span>
                다른 부서도 쓸 수 있는 <strong>공용 장비</strong>입니다
                <span className="text-muted-foreground block text-xs">
                  관리하는 부서는 그대로입니다 — 공용이라고 주인이 없어지지 않습니다.
                </span>
              </span>
            </label>
          </section>

          <section className="space-y-4 border-t pt-4">
            <h3 className="text-muted-foreground text-xs font-medium">생애와 교정</h3>
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="status">현재 상태</Label>
                <Select value={status} onValueChange={setStatus}>
                  <SelectTrigger id="status" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {EQUIPMENT_STATUS_OPTIONS.map((one) => (
                      <SelectItem key={one.value} value={one.value}>
                        {one.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="acquired-on">도입일</Label>
                <Input
                  id="acquired-on"
                  type="date"
                  value={acquiredOn}
                  onChange={(event) => setAcquiredOn(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="made-year">제조연도</Label>
                <Input
                  id="made-year"
                  type="number"
                  min={1900}
                  max={2200}
                  value={madeYear}
                  onChange={(event) => setMadeYear(event.target.value)}
                  placeholder="2019"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={calibrated}
                  onChange={(event) => setCalibrated(event.target.checked)}
                />
                <strong>교정 대상</strong> 장비입니다
              </label>
              {calibrated && (
                <div className="flex items-end gap-3">
                  <div className="w-40 space-y-2">
                    <Label htmlFor="interval">교정 주기(개월)</Label>
                    <Input
                      id="interval"
                      type="number"
                      min={1}
                      max={600}
                      value={interval}
                      onChange={(event) => setInterval(event.target.value)}
                      required
                    />
                  </div>
                  <p className="text-muted-foreground pb-2 text-xs">
                    주기가 없으면 차기일을 계산할 수 없고, 그러면 「곧 만료」 목록이 이 장비를
                    부르지 않습니다.
                  </p>
                </div>
              )}
            </div>
          </section>

          <section className="space-y-4 border-t pt-4">
            <h3 className="text-muted-foreground text-xs font-medium">그 밖</h3>
            <div className="grid gap-4 sm:grid-cols-2">
              {/* 폐기일은 폐기일 때만 묻는다 — 아닌 장비에 세워 두면 빈 칸으로만 남는다. */}
              {status === 'retired' && (
                <div className="space-y-2">
                  <Label htmlFor="retired-on">폐기일</Label>
                  <Input
                    id="retired-on"
                    type="date"
                    value={retiredOn}
                    onChange={(event) => setRetiredOn(event.target.value)}
                  />
                </div>
              )}
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="equipment-note">비고</Label>
                <Textarea
                  id="equipment-note"
                  className="max-w-2xl"
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  rows={3}
                  maxLength={4000}
                  placeholder="상세 화면에 그대로 보입니다. 검색은 이 글자를 안 봅니다."
                />
              </div>
            </div>
          </section>

          {/* **고정 칸이 아닌 정보는 여기.** 담당 구역·구매 연도처럼 부서마다 다른 것 — 열을
              미리 뚫지 않고 「보유 장비 속성」 정의로 받는다(attributes 모듈). */}
          <section className="space-y-2 border-t pt-4">
            <Label>속성</Label>
            <AttributeValuesEditor
              target="equipment"
              rows={attributes}
              onChange={setAttributes}
            />
          </section>

          <ErrorNotice error={error} />

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
              취소
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? '저장 중…' : editing ? '저장' : '등록'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

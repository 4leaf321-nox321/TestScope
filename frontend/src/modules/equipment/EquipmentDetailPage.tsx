/**
 * 장비 상세 — 제원 · 시험 역량 · 교정 이력.
 *
 * **역량이 이 화면의 본문이다.** 제원은 대장이고, 이 시스템이 답하려는 물음에
 * 답하는 것은 역량 쪽이다.
 */

import { Link, useParams } from 'react-router-dom'

import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { StatusBadge } from '@/shared/components/StatusBadge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs'
import { useResource } from '@/shared/hooks/useResource'
import { shownDate } from '@/shared/lib/datetime'
import { equipmentApi } from '@/modules/equipment/api'
import { CapabilityPanel } from '@/modules/equipment/CapabilityPanel'
import { CalibrationPanel } from '@/modules/equipment/CalibrationPanel'

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <dt className="text-muted-foreground text-xs">{label}</dt>
      {/* **빈 칸을 빈 칸으로 두지 않는다.** 값이 없는 것과 화면이 못 그린 것을
          구별할 수 있어야 한다. */}
      <dd className="text-sm">{value || '—'}</dd>
    </div>
  )
}

export default function EquipmentDetailPage() {
  const { id = '' } = useParams<{ id: string }>()
  const equipment = useResource(() => equipmentApi.read(id), [id])

  if (equipment.error) return <ErrorNotice error={equipment.error} />
  if (!equipment.data) return null

  const one = equipment.data

  return (
    <div className="space-y-6">
      <PageHeader
        back={{ to: '/equipment', label: '보유 장비' }}
        title={
          <span className="flex flex-wrap items-center gap-2">
            {one.name}
            <StatusBadge kind="equipment" value={one.status} />
          </span>
        }
        description={
          <>
            {one.asset_no}
            {/* **모델은 카탈로그로 간다.** 개체 화면에서 사양을 보려면 그쪽이다. */}
            {one.model_id ? (
              <>
                {' · '}
                <Link
                  to={`/catalog/equipment-models/${one.model_id}`}
                  className="hover:underline"
                >
                  {one.manufacturer ? `${one.manufacturer} ` : ''}
                  {one.model_name}
                </Link>
              </>
            ) : (
              // 빈 칸을 빈 칸으로 두면 아무도 안 채운다(ADR 0004).
              <span className="ml-2 text-amber-600">카탈로그 미연결</span>
            )}
          </>
        }
      />

      <dl className="grid grid-cols-2 gap-4 rounded-md border p-4 sm:grid-cols-4">
        <Field label="분류" value={one.category} />
        <Field label="보유 부서" value={one.workspace_name ?? '전사'} />
        <Field
          label="위치"
          value={[one.site, one.location].filter(Boolean).join(' · ')}
        />
        <Field label="담당자" value={one.contact_name} />
        <Field label="제조사" value={one.manufacturer} />
        <Field label="시리얼" value={one.serial_no} />
        <Field label="도입일" value={shownDate(one.acquired_on)} />
        <Field label="교정 예정" value={shownDate(one.calibration_due_on)} />
      </dl>

      {one.note && <p className="text-sm">{one.note}</p>}

      <Tabs defaultValue="capabilities">
        <TabsList>
          <TabsTrigger value="capabilities">시험 역량</TabsTrigger>
          <TabsTrigger value="calibration">교정 이력</TabsTrigger>
        </TabsList>
        <TabsContent value="capabilities" className="pt-4">
          <CapabilityPanel equipmentId={one.id} canEdit={one.can_edit} />
        </TabsContent>
        <TabsContent value="calibration" className="pt-4">
          <CalibrationPanel equipmentId={one.id} canEdit={one.can_edit} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

/**
 * 장비 상세 — 제원 · 시험 항목 · 교정 이력.
 *
 * **시험 항목이 이 화면의 본문이다.** 제원은 대장이고, 이 시스템이 답하려는 물음에
 * 답하는 것은 시험 항목 쪽이다.
 */

import { useState } from 'react'
import { Pencil } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { RecordListPanel } from '@/modules/equipment/RecordListPanel'
import { StatusBadge } from '@/shared/components/StatusBadge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs'
import { useResource } from '@/shared/hooks/useResource'
import { shownDate } from '@/shared/lib/datetime'
import { AttributeValuesPanel } from '@/modules/attributes/AttributeValuesPanel'
import { GraphPanel } from '@/modules/graph/GraphPanel'
import { Button } from '@/shared/components/ui/button'
import { EquipmentDialog } from '@/modules/equipment/EquipmentDialog'
import { equipmentApi } from '@/modules/equipment/api'
import { TestItemPanel } from '@/modules/equipment/TestItemPanel'
import { CalibrationPanel } from '@/modules/equipment/CalibrationPanel'
import { EquipmentSpecPanel } from '@/modules/equipment/EquipmentSpecPanel'

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
  const [editing, setEditing] = useState(false)

  if (equipment.error) return <ErrorNotice error={equipment.error} />
  if (!equipment.data) return null

  const one = equipment.data

  return (
    <div className="space-y-6">
      {/* 옆 장비로 뒤로 가지 않고 건너뛴다 — 한 부서의 장비를 훑는 일이 흔하다. */}
      <RecordListPanel kind="equipment" currentId={one.id} />

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
        /* **여기가 고치는 문이다.** 탭 안(시험 항목·사양·교정)은 각자 고칠 수 있었는데
           이름·부서·거점·위치·상태 같은 기본 칸은 화면에 고치는 자리가 없어서, 한 대의
           위치를 바꾸려고 대장을 엑셀로 다시 붙여넣어야 했다. */
        actions={
          one.can_edit && (
            <Button variant="outline" onClick={() => setEditing(true)}>
              <Pencil className="size-4" />
              수정
            </Button>
          )
        }
      />

      <EquipmentDialog
        open={editing}
        editing={one}
        onClose={() => setEditing(false)}
        onSaved={() => {
          setEditing(false)
          equipment.reload()
        }}
      />

      <dl className="grid grid-cols-2 gap-4 rounded-md border p-4 sm:grid-cols-4">
        {/* **장비군은 저장된 값이 아니다** — 유형에서 따라 나온다. */}
        <Field
          label="분류"
          value={[one.category_group, one.category]
            .filter(Boolean)
            .filter((value, index, all) => all.indexOf(value) === index)
            .join(' · ')}
        />
        <Field
          label="보유 부서"
          value={one.shared_use ? `${one.workspace_name ?? '—'} · 공용` : one.workspace_name}
        />
        <Field
          label="건물 · 설치 위치"
          value={[one.site, one.location].filter(Boolean).join(' · ')}
        />
        <Field label="담당자" value={one.contact_name} />
        <Field label="제조사" value={one.manufacturer} />
        <Field label="제조번호" value={one.serial_no} />
        <Field label="부서관리번호" value={one.dept_asset_no} />
        <Field
          label="도입일"
          value={[
            shownDate(one.acquired_on),
            one.manufactured_year ? `${one.manufactured_year}년 제조` : null,
          ]
            .filter(Boolean)
            .join(' · ')}
        />
        {/* **교정은 세 가지를 구별해 말한다** — 대상이 아님 · 대상인데 이력 없음 ·
            다음 예정일(성적서인지 계산인지). 하나로 뭉치면 빠뜨린 장비가 안 보인다. */}
        <Field
          label="교정"
          value={
            one.calibration_required
              ? one.calibration_missing
                ? '대상 · 이력 없음'
                : `${shownDate(one.calibration_due_on)}${one.calibration_due_estimated ? ' (주기로 계산)' : ''}`
              : '대상 아님'
          }
        />
        {one.status === 'retired' && (
          <Field label="폐기일" value={shownDate(one.retired_on)} />
        )}
      </dl>

      {one.note && <p className="text-sm">{one.note}</p>}

      <GraphPanel objectId={`equipment:${one.id}`} />

      <Tabs defaultValue="test_items">
        <TabsList>
          <TabsTrigger value="test_items">시험 항목</TabsTrigger>
          <TabsTrigger value="specs">
            사양
            {one.spec_override_count > 0 && ` · 실측 ${one.spec_override_count}`}
          </TabsTrigger>
          <TabsTrigger value="calibration">교정 이력</TabsTrigger>
          <TabsTrigger value="attributes">
            속성{one.attributes.length > 0 && ` · ${one.attributes.length}`}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="test_items" className="pt-4">
          <TestItemPanel equipmentId={one.id} canEdit={one.can_edit} />
        </TabsContent>
        <TabsContent value="specs" className="pt-4">
          <EquipmentSpecPanel equipmentId={one.id} canEdit={one.can_edit} />
        </TabsContent>
        <TabsContent value="calibration" className="pt-4">
          <CalibrationPanel equipmentId={one.id} canEdit={one.can_edit} />
        </TabsContent>
        <TabsContent value="attributes" className="pt-4">
          {/* 부서가 적는 정보(담당 구역·구매 연도 …). 「사양」 탭은 카탈로그 기종의 사양서
              칸이고, 여기는 우리 장비에 붙는 속성이다 — 다른 층. */}
          <AttributeValuesPanel
            target="equipment"
            values={one.attributes}
            canEdit={one.can_edit}
            onSave={async (attributes) => {
              await equipmentApi.update(one.id, { attributes })
              equipment.reload()
            }}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}

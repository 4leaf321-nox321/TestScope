/**
 * 시험 항목 상세 — 얻는 물성 · 규격 · 되는 계열 · 보유 장비 · 검색축을 **한 자리에.**
 *
 * 각 조각은 다른 화면에도 있다(물성 항목·시험법·계열·장비). 여기 모으는 이유는 하나다:
 * 「인장」 을 두고 **무엇이 비었나**를 한 번에 보고, 그 자리에서 채우게 하는 것. 물성은 줄
 * 단위로 확인하고, 검색축은 여기서 정한다. 규격의 시험 항목·계열의 시험 항목은 각자의
 * 화면이 정본이라 링크로 보낸다.
 */

import { useEffect, useState } from 'react'
import { Check, Pencil } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { ApiError } from '@/shared/api/client'
import { useAuth } from '@/shared/auth/AuthContext'
import { isSystemAdmin } from '@/shared/auth/roles'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { StatusBadge } from '@/shared/components/StatusBadge'
import { Button } from '@/shared/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table'
import { useResource } from '@/shared/hooks/useResource'
import { propertyApi } from '@/modules/properties/api'
import { testItemCatalogApi } from '@/modules/test_items/api'
import { vocabularyApi } from '@/modules/vocabulary/api'

/** 검색 조건 고르기 — 축은 일곱 개라 체크상자로 충분하다. */
function AxesEditor({
  itemId,
  current,
  onSaved,
}: {
  itemId: string
  current: string[]
  onSaved: () => void
}) {
  const keys = useResource(() => vocabularyApi.conditions(), [])
  const [picked, setPicked] = useState<Set<string>>(() => new Set(current))
  const [error, setError] = useState<string | null>(null)
  useEffect(() => setPicked(new Set(current)), [current])

  return (
    <div className="space-y-2 rounded-md border p-3">
      <div className="flex flex-wrap gap-3">
        {(keys.data ?? []).map((key) => (
          <label key={key.id} className="flex items-center gap-1.5 text-sm">
            <input
              type="checkbox"
              checked={picked.has(key.id)}
              onChange={(event) => {
                const next = new Set(picked)
                if (event.target.checked) next.add(key.id)
                else next.delete(key.id)
                setPicked(next)
              }}
            />
            {key.label}
            {(key.display_unit || key.si_unit) && (
              <span className="text-muted-foreground text-xs">
                [{key.display_unit || key.si_unit}]
              </span>
            )}
          </label>
        ))}
      </div>
      {error && <p className="text-destructive text-sm">{error}</p>}
      <Button
        size="sm"
        onClick={async () => {
          setError(null)
          try {
            await testItemCatalogApi.setConditionKeys(itemId, [...picked])
            onSaved()
          } catch (caught) {
            setError(caught instanceof ApiError ? caught.message : '알 수 없는 오류')
          }
        }}
      >
        검색 조건 저장
      </Button>
    </div>
  )
}

export default function TestItemCatalogDetailPage() {
  const { id = '' } = useParams<{ id: string }>()
  const { user } = useAuth()
  const admin = isSystemAdmin(user)
  const item = useResource(() => testItemCatalogApi.read(id), [id])
  const [editingAxes, setEditingAxes] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<ApiError | Error | null>(null)

  if (item.error) return <ErrorNotice error={item.error} />
  if (!item.data) return null
  const one = item.data
  const suggested = one.properties.filter((link) => link.status === 'suggested')

  return (
    <div className="space-y-6">
      <PageHeader
        back={{ to: '/catalog/test-items', label: '시험 항목' }}
        title={one.value}
        description={
          [one.code, one.aliases.length > 0 ? `별칭: ${one.aliases.join(' · ')}` : null]
            .filter(Boolean)
            .join(' · ') || undefined
        }
      />

      {message && <p className="text-sm text-emerald-700">{message}</p>}
      <ErrorNotice error={error} />

      {/* 검색 조건 — 이 시험에 뜻이 있는 조건. 없으면 검색이 축 일곱 개를 다 묻는다. */}
      <section className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-base font-semibold">검색 조건</h2>
          {one.condition_keys.length === 0 ? (
            <span className="text-sm text-amber-600">
              아직 안 정해짐 — 검색이 이 시험에 어떤 조건을 물어야 하는지 모릅니다
            </span>
          ) : (
            <span className="text-sm">
              {one.condition_keys
                .map((key) => `${key.label}${key.unit ? ` [${key.unit}]` : ''}`)
                .join(' · ')}
            </span>
          )}
          {admin && !editingAxes && (
            <Button size="sm" variant="ghost" onClick={() => setEditingAxes(true)}>
              <Pencil className="size-3.5" />
              정하기
            </Button>
          )}
        </div>
        {editingAxes && (
          <AxesEditor
            itemId={one.id}
            current={one.condition_keys.map((key) => key.id)}
            onSaved={() => {
              setEditingAxes(false)
              item.reload()
            }}
          />
        )}
      </section>

      {/* 얻는 물성 — 제안은 점선. 줄 단위로 확인한다. */}
      <section className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-base font-semibold">측정 물성</h2>
          <span className="text-muted-foreground text-sm">
            {one.properties.length}
            {suggested.length > 0 && ` · 확인 안 한 제안 ${suggested.length}`}
          </span>
          {admin && suggested.length > 0 && (
            <Button
              size="sm"
              variant="outline"
              onClick={async () => {
                setError(null)
                try {
                  const got = await propertyApi.bulk(
                    suggested.map((link) => link.link_id),
                    'confirmed',
                  )
                  setMessage(`${got.changed}건을 확인으로 올렸습니다.`)
                  item.reload()
                } catch (caught) {
                  setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
                }
              }}
            >
              <Check className="size-3.5" />
              {suggested.length}개 다 확인
            </Button>
          )}
        </div>
        {one.properties.length === 0 ? (
          <p className="text-sm text-amber-600">
            이어진 물성이 없습니다 — 판정·곡선으로 끝나는 시험이면 정상이고, 물성을 내는
            시험이면{' '}
            <Link to="/properties" className="underline">
              물성 항목
            </Link>
            에서 잇습니다.
          </p>
        ) : (
          <ul className="flex flex-wrap gap-1">
            {one.properties.map((link) => (
              <li
                key={link.link_id}
                className={`rounded-full border px-2 py-0.5 text-xs ${
                  link.status === 'suggested'
                    ? 'border-dashed text-muted-foreground'
                    : 'bg-muted'
                }`}
                title={link.property_code ?? undefined}
              >
                {link.property}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* 규격 — 정본은 시험법 화면. */}
      <section className="space-y-2">
        <h2 className="text-base font-semibold">
          규격{' '}
          <span className="text-muted-foreground text-sm font-normal">
            {one.methods.length}
          </span>
        </h2>
        {one.methods.length === 0 ? (
          <p className="text-sm text-amber-600">
            이 시험의 규격으로 정해진 것이 없습니다.{' '}
            <Link to="/methods?test_item=none" className="underline">
              시험 항목 미지정 규격
            </Link>
            에 이 시험의 것이 있을 수 있습니다.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>규격</TableHead>
                <TableHead>제목</TableHead>
                <TableHead className="text-right">인용 계열</TableHead>
                <TableHead>요구 조건</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {one.methods.map((method) => (
                <TableRow key={method.id}>
                  <TableCell className="font-medium">
                    <Link to={`/methods/${method.id}`} className="hover:underline">
                      {method.code}
                      {method.edition ? ` ${method.edition}` : ''}
                    </Link>
                  </TableCell>
                  <TableCell className="max-w-md truncate">{method.title}</TableCell>
                  <TableCell className="text-right">{method.series_count}</TableCell>
                  <TableCell className="text-sm">
                    {method.has_requirements ? (
                      '있음'
                    ) : (
                      <span className="text-muted-foreground">없음</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      {/* 되는 계열 — 카탈로그. */}
      <section className="space-y-2">
        <h2 className="text-base font-semibold">
          가능 계열{' '}
          <span className="text-muted-foreground text-sm font-normal">
            {one.series.length}
          </span>
        </h2>
        {one.series.length === 0 ? (
          <p className="text-sm text-amber-600">
            이 시험을 한다고 적힌 계열이 카탈로그에 없습니다 — 그 장비가 카탈로그에 없거나,
            계열의 시험 항목에 아직 안 적힌 것입니다.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>계열</TableHead>
                <TableHead>제조사 · 분류</TableHead>
                <TableHead className="text-right">기종</TableHead>
                <TableHead>이 시험의 규격</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {one.series.map((series) => (
                <TableRow key={series.id}>
                  <TableCell className="font-medium">
                    <Link
                      to={`/catalog/equipment-series/${series.id}`}
                      className="hover:underline"
                    >
                      {series.name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {[series.maker, series.category].filter(Boolean).join(' · ')}
                  </TableCell>
                  <TableCell className="text-right">{series.model_count}</TableCell>
                  <TableCell className="text-sm">
                    {series.method_codes.length > 0 ? (
                      series.method_codes.join(' · ')
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      {/* 보유 장비 — 우리가 가진 것. 내가 볼 수 있는 것만. */}
      <section className="space-y-2">
        <h2 className="text-base font-semibold">
          보유 장비{' '}
          <span className="text-muted-foreground text-sm font-normal">
            {one.equipment.length}대
          </span>
        </h2>
        {one.equipment.length === 0 ? (
          <p className="text-sm text-amber-600">
            이 시험이 적힌 보유 장비가 없습니다 — 현재 수행 불가한 시험입니다.
            {one.series.length > 0 && ' 위 계열의 기종을 사면 됩니다.'}
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>자산번호</TableHead>
                <TableHead>장비</TableHead>
                <TableHead>부서</TableHead>
                <TableHead>상태</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {one.equipment.map((equipment) => (
                <TableRow key={equipment.id}>
                  <TableCell className="font-mono text-sm">
                    <Link to={`/equipment/${equipment.id}`} className="hover:underline">
                      {equipment.asset_no}
                    </Link>
                  </TableCell>
                  <TableCell>{equipment.name}</TableCell>
                  <TableCell className="text-sm">{equipment.workspace ?? '—'}</TableCell>
                  <TableCell>
                    <StatusBadge kind="equipment" value={equipment.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>
    </div>
  )
}

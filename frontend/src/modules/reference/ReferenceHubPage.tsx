/**
 * 기준정보 — **이 시스템이 다루는 객체 종류 전부를 한 화면에서.**
 *
 * 왼쪽에 객체 종류가 세 층(카탈로그 · 사내 운영 · 이름 사전)으로 펼쳐져 있고, 하나를 고르면
 * 오른쪽에 그 종류의 판이 선다 — 「기준정보 편집」 이 축을 고르던 것과 같은 모양이다. 전에는
 * 「기준정보」(이름 사전 보기)와 「기준정보 편집」 이 다른 메뉴였고, 계열·기종·규격 같은 객체는
 * 어느 쪽에도 없어서 기준정보가 아닌 것처럼 읽혔다. 이제 한 화면이다:
 *
 *     이름 사전의 축   →  값 목록 + (관리자면) 축 편집·값 등록·값 편집   (AxisPanel)
 *     자기 표의 객체   →  건수 · 고정 칸 · 관리자가 정의한 칸 · 목록/정의 화면    (KindPanel)
 *
 * 저장 구조는 안 바꿨다 — 사슬의 뼈대는 자기 표, 이름은 축의 값(reference/services.py).
 */

import { useEffect, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { useAuth } from '@/shared/auth/AuthContext'
import { isSystemAdmin } from '@/shared/auth/roles'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { Badge } from '@/shared/components/ui/badge'
import { Button } from '@/shared/components/ui/button'
import { fromReference } from '@/shared/hooks/useBackFromReference'
import { useResource } from '@/shared/hooks/useResource'
import { referenceApi } from '@/modules/reference/api'
import type { ObjectKind } from '@/modules/reference/api'
import { AxisPanel } from '@/modules/vocabulary/VocabularyAdminPage'

const LAYERS: { key: string; label: string }[] = [
  { key: 'catalog', label: '카탈로그 — 전사 공용 객체' },
  { key: 'operations', label: '사내 운영 — 부서가 적는 것' },
  { key: 'vocabulary', label: '이름 사전 — 분류 이름의 목록' },
]

/** 왼쪽 목록 — AxisList 와 같은 모양. 층으로 묶고, 건수를 함께 그린다. */
function KindList({
  kinds,
  current,
  onSelect,
}: {
  kinds: ObjectKind[]
  current: string | null
  onSelect: (key: string) => void
}) {
  return (
    <nav className="w-56 shrink-0 space-y-4" aria-label="객체 종류">
      {LAYERS.map((layer) => {
        const mine = kinds.filter((one) => one.layer === layer.key)
        if (mine.length === 0) return null
        return (
          <div key={layer.key}>
            <p className="text-muted-foreground mb-1 px-2 text-xs font-medium">
              {layer.label}
            </p>
            <ul className="space-y-0.5">
              {mine.map((kind) => (
                <li key={kind.key}>
                  <button
                    type="button"
                    onClick={() => onSelect(kind.key)}
                    className={`flex w-full items-center justify-between rounded-md px-2 py-1 text-left text-sm ${
                      kind.key === current ? 'bg-muted font-medium' : 'hover:bg-muted/60'
                    }`}
                  >
                    <span className="truncate">{kind.label}</span>
                    <span className="text-muted-foreground ml-2 text-xs tabular-nums">
                      {kind.count.toLocaleString()}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )
      })}
    </nav>
  )
}

/** 자기 표를 가진 객체 종류의 판 — 칸의 구성과 가는 문. */
function KindPanel({ kind }: { kind: ObjectKind }) {
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-base font-semibold">
          {kind.label}
          <span className="text-muted-foreground ml-2 text-sm font-normal">
            {kind.count.toLocaleString()}건
          </span>
        </h2>
        <p className="text-muted-foreground mt-1 text-sm">{kind.note}</p>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button asChild variant="outline" size="sm">
          <Link to={fromReference(kind.list_path, kind.key)}>목록 · 등록</Link>
        </Button>
        {kind.define_path && kind.defined_kind && (
          <Button asChild variant="outline" size="sm">
            <Link to={kind.define_path}>{kind.defined_kind} 정의</Link>
          </Button>
        )}
      </div>

      <section className="space-y-1">
        <h3 className="text-sm font-medium">고정 칸</h3>
        <p className="text-muted-foreground text-xs">
          코드가 참조하거나 모든 {kind.label}에 항상 있어야 하는 것 — 화면에서 더하거나 뺄 수
          없다.
        </p>
        <ul className="flex flex-wrap gap-1.5">
          {kind.fixed_fields.map((field) => (
            <li key={field} className="bg-muted rounded px-2 py-0.5 text-sm">
              {field}
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-1">
        <h3 className="text-sm font-medium">관리자 정의 항목</h3>
        {kind.defined_kind ? (
          <p className="text-sm">
            {kind.define_path ? (
              <Link to={kind.define_path} className="underline">
                {kind.defined_kind} {kind.defined_count}
              </Link>
            ) : (
              `${kind.defined_kind} ${kind.defined_count}`
            )}
            {kind.draft_count > 0 && (
              <Badge variant="secondary" className="ml-2 text-[10px]">
                초안 {kind.draft_count}
              </Badge>
            )}
            <span className="text-muted-foreground ml-2 text-xs">
              {kind.defined_kind === '속성' &&
                '값을 적는 사람이 새 이름으로 쓰면 초안이 생기고, 관리자가 정식으로 올립니다.'}
              {kind.defined_kind === '사양' &&
                '사양서의 칸. 검색 조건 축에 이은 사양은 검색에 반영됩니다.'}
            </span>
          </p>
        ) : (
          // **없음은 없음이라고 말한다.** 빈 칸이면 「아직 안 읽힌 것」 과 구별이 안 된다.
          <p className="text-muted-foreground text-sm">고정 칸만 있습니다.</p>
        )}
      </section>
    </div>
  )
}

export default function ReferenceHubPage() {
  const { user } = useAuth()
  const canEdit = isSystemAdmin(user)
  const kinds = useResource(() => referenceApi.overview(), [])
  const [params, setParams] = useSearchParams()
  const rows = useMemo(() => kinds.data ?? [], [kinds.data])
  const current = params.get('kind') ?? rows[0]?.key ?? null
  const kind = rows.find((one) => one.key === current) ?? null

  // 처음 열면 첫 종류가 골라진 채로 — 주소에도 적어 되돌아올 수 있게.
  useEffect(() => {
    if (!params.get('kind') && rows[0]) {
      setParams({ kind: rows[0].key }, { replace: true })
    }
  }, [params, rows, setParams])

  return (
    <div className="space-y-6">
      <PageHeader
        title="기준정보"
        description="이 시스템이 다루는 객체 종류 전부 — 왼쪽에서 고르면 그 종류의 칸과 값이 보입니다. 이름 사전의 축은 여기서 값을 등록·편집하고(시스템 관리자), 자기 표를 가진 객체는 목록·정의 화면으로 이어집니다."
      />
      <ErrorNotice error={kinds.error} />

      <div className="flex gap-6">
        <KindList
          kinds={rows}
          current={current}
          onSelect={(key) => setParams({ kind: key })}
        />
        <div className="min-w-0 flex-1">
          {kind && kind.storage === 'vocabulary' && (
            <AxisPanel slug={kind.key.replace(/^axis:/, '')} canEdit={canEdit} />
          )}
          {kind && kind.storage === 'table' && <KindPanel kind={kind} />}
        </div>
      </div>
    </div>
  )
}

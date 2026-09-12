/**
 * 상세 옆 목록 — **장비·기종·계열을 오갈 때 뒤로 가지 않는다.**
 *
 * 같은 계열의 기종을 견주고(사양이 어디서 갈리나), 한 부서의 장비를 훑는 일은 늘 있는
 * 일이다. 그때마다 목록 → 상세 → 뒤로 → 상세를 반복하면 보던 자리와 걸어 둔 거르기가
 * 매번 사라진다.
 *
 * ## 여기서 거르지 않는다
 *
 * 찾기는 **서버가** 한다. 앞 50건을 받아 놓고 화면에서 거르면, 그보다 많은 순간 뒤엣것이
 * 없는 것처럼 보인다 — 목록 화면이 같은 이유로 서버 거르기를 쓴다.
 *
 * ## 지금 보는 것을 표시한다
 *
 * 목록에서 자기 자리를 못 찾으면 옆 것으로 옮겨 갈 수가 없다. 현재 줄은 칠하고, 화면을
 * 열 때 보이는 자리로 끌어온다.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { Input } from '@/shared/components/ui/input'
import { LeftPanel } from '@/shared/layout/SidePanel'
import { catalogApi, equipmentApi, seriesApi } from '@/modules/equipment/api'

/** 한 번에 받아 오는 수. 옆 목록이라 스크롤로 훑는 것이 전부다. */
const LIMIT = 50

type Kind = 'equipment' | 'model' | 'series'

interface Row {
  id: string
  title: string
  detail: string | null
}

const SHAPE: Record<Kind, { label: string; placeholder: string; to: (id: string) => string }> =
  {
    equipment: {
      label: '보유 장비',
      placeholder: '자산번호 · 장비명',
      to: (id) => `/equipment/${id}`,
    },
    model: {
      label: '장비 기종',
      placeholder: '기종 · 계열 · 제조사',
      to: (id) => `/catalog/equipment-models/${id}`,
    },
    series: {
      label: '장비 계열',
      placeholder: '계열 · 제조사',
      to: (id) => `/catalog/equipment-series/${id}`,
    },
  }

async function fetchRows(kind: Kind, query: string): Promise<{ rows: Row[]; total: number }> {
  const q = query.trim() || undefined
  if (kind === 'equipment') {
    const page = await equipmentApi.list({ q, limit: LIMIT })
    return {
      rows: page.items.map((one) => ({
        id: one.id,
        title: one.name,
        // 자산번호가 그 장비를 가리키는 이름이다 — 이름만으로는 같은 것이 여럿이다.
        detail: [one.asset_no, one.location].filter(Boolean).join(' · ') || null,
      })),
      total: page.total,
    }
  }
  if (kind === 'model') {
    const page = await catalogApi.list({ q, limit: LIMIT })
    return {
      rows: page.items.map((one) => ({
        id: one.id,
        title: one.name,
        detail: [one.series_name, one.maker].filter(Boolean).join(' · ') || null,
      })),
      total: page.total,
    }
  }
  const page = await seriesApi.list({ q, limit: LIMIT })
  return {
    rows: page.items.map((one) => ({
      id: one.id,
      title: one.name,
      detail: [one.maker, one.category].filter(Boolean).join(' · ') || null,
    })),
    total: page.total,
  }
}

export function RecordListPanel({ kind, currentId }: { kind: Kind; currentId: string }) {
  const shape = SHAPE[kind]
  const [query, setQuery] = useState('')
  const [rows, setRows] = useState<Row[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const currentRef = useRef<HTMLAnchorElement | null>(null)

  useEffect(() => {
    let dropped = false
    setLoading(true)
    // 글자마다 요청하면 옆 목록 하나가 서버를 두드리는 꼴이 된다.
    const timer = setTimeout(() => {
      fetchRows(kind, query)
        .then((got) => {
          if (dropped) return
          setRows(got.rows)
          setTotal(got.total)
        })
        .catch(() => {
          if (!dropped) setRows([])
        })
        .finally(() => {
          if (!dropped) setLoading(false)
        })
    }, 250)
    return () => {
      dropped = true
      clearTimeout(timer)
    }
  }, [kind, query])

  // **지금 보는 줄로 끌어온다.** 목록 한가운데 있는 것을 열었는데 목록이 맨 위를
  // 보여 주면, 자기 자리를 스스로 찾아야 한다.
  useEffect(() => {
    currentRef.current?.scrollIntoView({ block: 'nearest' })
  }, [currentId, rows])

  const missing = useMemo(
    () => rows.length > 0 && !rows.some((one) => one.id === currentId),
    [rows, currentId],
  )

  return (
    <LeftPanel label={shape.label}>
      <aside className="bg-background flex h-full w-64 shrink-0 flex-col border-r">
        <div className="space-y-2 border-b p-2">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={shape.placeholder}
            className="h-8 text-xs"
            aria-label={`${shape.label} 찾기`}
          />
          <p className="text-muted-foreground px-1 text-xs">
            {loading
              ? '찾는 중…'
              : total > rows.length
                ? `${total}건 중 ${rows.length}건 — 좁혀서 찾으세요`
                : `${total}건`}
          </p>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <ul className="text-sm">
            {rows.map((one) => {
              const here = one.id === currentId
              return (
                <li key={one.id}>
                  <Link
                    ref={here ? currentRef : undefined}
                    to={shape.to(one.id)}
                    aria-current={here ? 'page' : undefined}
                    className={`block border-b px-3 py-2 leading-tight ${
                      here ? 'bg-muted font-medium' : 'hover:bg-muted/50'
                    }`}
                  >
                    <span className="block truncate">{one.title}</span>
                    {one.detail && (
                      <span className="text-muted-foreground block truncate text-xs">
                        {one.detail}
                      </span>
                    )}
                  </Link>
                </li>
              )
            })}
          </ul>
          {!loading && rows.length === 0 && (
            <p className="text-muted-foreground p-3 text-xs">찾는 것이 없습니다.</p>
          )}
          {missing && (
            // 거르기가 지금 보는 것을 밀어냈다. 말 안 하면 「목록에 없다」 로 읽힌다.
            <p className="text-muted-foreground border-t p-3 text-xs">
              지금 보고 있는 것은 이 거르기에 안 걸립니다.
            </p>
          )}
        </div>
      </aside>
    </LeftPanel>
  )
}

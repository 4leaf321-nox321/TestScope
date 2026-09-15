/**
 * 서버 상태 — **한 화면이 답해야 하는 물음이 셋이다.**
 *
 *   지금 뭐가 깔렸나 · DB 는 맞춰져 있나 · 무엇이 얼마나 쌓였나
 *
 * 셋을 따로 두면 아무도 다 보지 않는다. 그리고 문제가 났을 때 첫 물음은 언제나
 * "지금 서버 버전이 뭐냐" 와 "어느 DB 를 보고 있냐" 다.
 */

import { api } from '@/shared/api/client'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { useResource } from '@/shared/hooks/useResource'
import { shownDateTime } from '@/shared/lib/datetime'

interface ServerStatus {
  version: string
  app_env: string
  /** 비밀번호를 지운 접속 문자열. **어느 DB 를 보고 있는지가 첫 물음이다.** */
  database_url_safe: string
  schema_head: string | null
  schema_current: string | null
  /** DB 가 코드보다 뒤처져 있나. 뒤처지면 새 컬럼을 읽는 화면이 500 을 낸다. */
  schema_behind: boolean
  disk: { path: string; total_bytes: number; free_bytes: number; used_percent: number } | null
  counts: { label: string; count: number }[]
  started_at: string
  /** 카탈로그 정본(파일)과 DB 에 반입된 시점이 같은가. 배포는 파일을 새로 놓지만 반입은
   *  사람이 돌린다 — 안 돌린 사실을 여기서 말하지 않으면 어디서도 안 보인다. */
  catalog: {
    available: boolean
    digest: string | null
    objects: number | null
    imported_at: string | null
    imported_digest: string | null
    imported_objects: number | null
    never: boolean
    behind: boolean
  }
  /** 의미 검색 부품 셋 — 엔진(Ollama)·확장(pgvector)·표. 없는 것은 고장이 아니라 설정이고,
   *  그 사실을 여기서 말하지 않으면 「검색이 뜻을 못 알아듣네」 로만 드러난다. */
  semantic: {
    backend: string
    engine_ready: boolean
    engine_note: string | null
    extension: boolean
    table: boolean
    chunks: number
    kinds: Record<string, number>
    /** 가장 최근 색인 작업. running 이면 지금 색인 중 — 색인 수가 새로고침마다 는다. */
    reindex_status: 'queued' | 'running' | 'done' | 'failed' | null
    reindex_at: string | null
    reindex_error: string | null
  }
  /** 작업 큐. failed 가 있으면 사람이 봐야 한다 — 워커 로그(_data\logs)에 이유가 있다. */
  jobs: { queued: number; running: number; done: number; failed: number }
}

function semanticLine(one: ServerStatus['semantic']): string {
  if (one.backend === 'off') return '꺼짐 (.env 의 EMBEDDING_BACKEND) — 검색은 이름·별칭으로만'
  if (!one.extension)
    return `엔진 ${one.backend} · pgvector 없음 — install_pgvector.ps1 로 넣는다`
  if (!one.table)
    return `엔진 ${one.backend} · 표 없음 — 다음 배포(ensure_semantic_schema)가 만든다`
  if (!one.engine_ready) return `엔진 ${one.backend} 응답 없음 — ${one.engine_note ?? ''}`
  const kinds = Object.entries(one.kinds)
    .map(([kind, count]) => `${kind} ${count}`)
    .join(' · ')
  return `${one.backend} · 색인 ${one.chunks}개` + (kinds ? ` (${kinds})` : ' — 워커가 채운다')
}

/** 색인 작업의 상태 한 줄. **지금 도는 중인지**가 첫 물음이라 그것부터 말한다. */
function reindexLine(one: ServerStatus['semantic']): string {
  if (!one.reindex_status) return '색인 작업 없음 — 반입 뒤 또는 하루 한 번 워커가 넣는다'
  const when = one.reindex_at ? shownDateTime(one.reindex_at) : ''
  switch (one.reindex_status) {
    case 'running':
      return `색인 진행 중 (${when} 시작) — 새로고침하면 색인 수가 는다`
    case 'queued':
      return `색인 대기 중 (${when} 등록) — 워커(TestScope-Worker)가 떠 있으면 곧 시작`
    case 'failed':
      return `마지막 색인 실패 (${when}) — ${one.reindex_error ?? ''}`
    default:
      return `마지막 색인 완료 ${when}`
  }
}

function gib(bytes: number): string {
  return `${(bytes / 1024 ** 3).toFixed(1)} GiB`
}

export default function ServerPage() {
  const status = useResource(() => api.get<ServerStatus>('/server/status'), [])

  if (status.error) return <ErrorNotice error={status.error} />
  if (!status.data) return null

  const one = status.data

  return (
    <div className="space-y-6">
      <PageHeader title="서버" description="이 설치의 상태입니다." />

      {/* **뒤처져 있으면 여기서 말한다.** 안 그러면 사람은 그 사실을 엉뚱한
          화면의 500 으로 만나고, 거기엔 원인이 안 적힌다. */}
      {one.schema_behind && (
        <div className="border-destructive/40 bg-destructive/5 text-destructive rounded-md border p-3 text-sm">
          데이터베이스가 코드보다 뒤처져 있습니다 ({one.schema_current} → {one.schema_head}).
          서버에서 <span className="font-mono">alembic upgrade head</span> 를 돌리세요.
          그전까지는 새 칸을 읽는 화면이 오류를 냅니다.
        </div>
      )}

      {/* 카탈로그도 같은 자리에서 말한다 — 반입을 안 돌린 설치는 지난 카탈로그를
          새 것처럼 보여 주고, 그 차이는 「이 기종 카탈로그에 없던데」 로만 드러난다. */}
      {one.catalog.available && (one.catalog.never || one.catalog.behind) && (
        <div className="border-destructive/40 bg-destructive/5 text-destructive rounded-md border p-3 text-sm">
          {one.catalog.never
            ? '카탈로그가 아직 반입되지 않았습니다.'
            : `카탈로그 반입이 정본보다 뒤져 있습니다 (반입 ${shownDateTime(one.catalog.imported_at)} · 객체 ${one.catalog.imported_objects ?? '?'} → 정본 ${one.catalog.objects}).`}{' '}
          서버에서 <span className="font-mono">python scripts\import_catalog.py</span> 를
          돌리세요.
        </div>
      )}

      <dl className="grid gap-4 rounded-md border p-4 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="text-muted-foreground text-xs">버전</dt>
          <dd className="font-mono text-sm">{one.version}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">환경</dt>
          <dd className="text-sm">{one.app_env}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-muted-foreground text-xs">데이터베이스</dt>
          <dd className="font-mono text-xs break-all">{one.database_url_safe}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">스키마 리비전</dt>
          <dd className="font-mono text-xs">{one.schema_current ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs">기동 시각</dt>
          <dd className="text-sm">{shownDateTime(one.started_at)}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-muted-foreground text-xs">카탈로그</dt>
          <dd className="text-sm">
            {!one.catalog.available
              ? '정본 파일 없음 — 이 설치에서는 반입할 수 없습니다'
              : one.catalog.never
                ? `아직 반입 안 함 (정본 객체 ${one.catalog.objects})`
                : `${shownDateTime(one.catalog.imported_at)} 반입 · 객체 ${one.catalog.imported_objects ?? '?'}` +
                  (one.catalog.behind
                    ? ` · 정본은 ${one.catalog.objects} (미반영)`
                    : ' · 정본과 같음')}
          </dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-muted-foreground text-xs">의미 검색</dt>
          <dd className="text-sm">
            {semanticLine(one.semantic)}
            {one.semantic.backend !== 'off' && (
              <span
                className={
                  'block text-xs ' +
                  (one.semantic.reindex_status === 'failed'
                    ? 'text-amber-600'
                    : 'text-muted-foreground')
                }
              >
                {reindexLine(one.semantic)}
              </span>
            )}
          </dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-muted-foreground text-xs">작업 큐</dt>
          <dd className="text-sm">
            대기 {one.jobs.queued} · 실행 중 {one.jobs.running} · 끝남 {one.jobs.done} ·{' '}
            <span className={one.jobs.failed > 0 ? 'font-semibold text-amber-600' : ''}>
              실패 {one.jobs.failed}
            </span>
            {one.jobs.queued > 0 && one.jobs.running === 0 && (
              <span className="text-muted-foreground">
                {' '}
                — 워커(TestScope-Worker)가 떠 있나 확인
              </span>
            )}
          </dd>
        </div>
        {one.disk && (
          <div className="sm:col-span-2">
            <dt className="text-muted-foreground text-xs">디스크</dt>
            <dd className="text-sm">
              {gib(one.disk.free_bytes)} 남음 / {gib(one.disk.total_bytes)} (
              {one.disk.used_percent}% 사용)
            </dd>
          </div>
        )}
      </dl>

      <section className="space-y-3">
        <h2 className="text-base font-semibold">쌓인 것</h2>
        <ul className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {one.counts.map((count) => (
            <li key={count.label} className="rounded-md border p-4">
              <p className="text-2xl font-semibold">{count.count}</p>
              <p className="text-muted-foreground text-sm">{count.label}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

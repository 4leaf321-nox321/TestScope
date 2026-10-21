/**
 * 기준정보 허브 연계 — **시스템 관리자.** 연계 설정 · 수신 현황 · 수신 이력(요청서 1.2 §9).
 *
 * 허브(StandardPlatform)의 코어 API 에서 기준정보를 받아 온톨로지 축(`hub_<타입>`)으로 세운다.
 * 받은 축은 잠긴다 — 고치는 길은 허브뿐이다. 수신은 워커가 돈다(야간 · 수동 · 주간 전량 대조).
 *
 * **토큰은 다시 보여 주지 않는다.** 저장하면 「설정됨」 만 선다 — 화면을 본 사람 누구나 허브
 * 전체를 읽는 자격을 갖게 되면 안 된다.
 */

import { Fragment, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
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
import { shownDateTime } from '@/shared/lib/datetime'
import { RUN_STATUS, RUN_TRIGGER, hubApi } from '@/modules/hub/api'
import type { HubCheck, HubConnection, HubRun } from '@/modules/hub/api'

/** 실행 하나의 변경 건수 합 — 이력 표의 한 칸. */
function changed(run: HubRun): number {
  let total = 0
  for (const counts of Object.values(run.counts)) {
    const one = counts as Record<string, number>
    for (const key of [
      'created',
      'updated',
      'deactivated',
      'restored',
      'merged',
      'renamed',
      'absent',
      'relations_added',
      'relations_removed',
    ])
      total += one[key] ?? 0
  }
  return total
}

function ConnectionForm({
  current,
  onSaved,
}: {
  current: HubConnection
  onSaved: (next: HubConnection) => void
}) {
  const [baseUrl, setBaseUrl] = useState(current.base_url)
  const [token, setToken] = useState('')
  const [caBundle, setCaBundle] = useState(current.ca_bundle ?? '')
  const [nightlyAt, setNightlyAt] = useState(current.nightly_at)
  const [enabled, setEnabled] = useState(current.enabled)
  /** `null` 이면 공개 타입 전부. */
  const [selected, setSelected] = useState<string[] | null>(current.selected_types)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [checked, setChecked] = useState<HubCheck | null>(null)
  const types = checked?.types.length ? checked.types : current.types

  async function save() {
    setBusy(true)
    setError(null)
    try {
      const next = await hubApi.saveConnection({
        base_url: baseUrl.trim(),
        token: token.trim() || null,
        ca_bundle: caBundle.trim() || null,
        selected_types: selected,
        nightly_at: nightlyAt,
        enabled,
      })
      setToken('')
      onSaved(next)
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  async function check() {
    setBusy(true)
    setError(null)
    try {
      setChecked(await hubApi.check())
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    } finally {
      setBusy(false)
    }
  }

  function toggle(slug: string) {
    const base = selected ?? types.map((one) => one.slug)
    setSelected(base.includes(slug) ? base.filter((one) => one !== slug) : [...base, slug])
  }

  return (
    <section className="space-y-4 rounded-md border p-4">
      <h2 className="text-base font-semibold">연계 설정</h2>
      <ErrorNotice error={error} />
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor="hub-url">허브 주소</Label>
          <Input
            id="hub-url"
            value={baseUrl}
            onChange={(event) => setBaseUrl(event.target.value)}
            placeholder="https://허브주소/api"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="hub-token">토큰 (범위 core:read)</Label>
          <Input
            id="hub-token"
            type="password"
            autoComplete="off"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder={
              current.has_token ? '설정됨 — 바꾸려면 입력' : '허브 관리자가 발급한 토큰'
            }
          />
          {current.has_token && !current.token_readable && (
            <p className="text-destructive text-xs">
              저장된 토큰을 풀 수 없음(DB 이동 또는 JWT_SECRET 변경). 다시 입력 필요.
            </p>
          )}
          {current.token_set_at && (
            <p className="text-muted-foreground text-xs">
              마지막 설정 {shownDateTime(current.token_set_at)}
            </p>
          )}
        </div>
        <div className="space-y-1">
          <Label htmlFor="hub-ca">사내 인증서 경로 (선택)</Label>
          <Input
            id="hub-ca"
            value={caBundle}
            onChange={(event) => setCaBundle(event.target.value)}
            placeholder="비우면 기본 인증서"
          />
        </div>
        <div className="flex items-end gap-4">
          <div className="space-y-1">
            <Label htmlFor="hub-nightly">야간 수신 시각 (KST)</Label>
            <Input
              id="hub-nightly"
              type="time"
              value={nightlyAt}
              onChange={(event) => setNightlyAt(event.target.value)}
              className="w-32"
            />
          </div>
          <label className="flex items-center gap-1.5 pb-2 text-sm">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(event) => setEnabled(event.target.checked)}
            />
            야간 자동 수신
          </label>
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-sm font-medium">받을 타입</p>
        <div className="flex flex-wrap gap-4 text-sm">
          <label className="flex items-center gap-1.5">
            <input
              type="radio"
              checked={selected === null}
              onChange={() => setSelected(null)}
            />
            공개 타입 전부 (새 타입도 자동 포함)
          </label>
          <label className="flex items-center gap-1.5">
            <input
              type="radio"
              checked={selected !== null}
              onChange={() => setSelected(types.map((one) => one.slug))}
            />
            고른 타입만
          </label>
        </div>
        {types.length === 0 ? (
          <p className="text-muted-foreground text-xs">
            ‘연결 점검’으로 허브 카탈로그를 받으면 공개 타입 목록이 표시됨.
          </p>
        ) : (
          <ul className="grid gap-1 text-sm sm:grid-cols-2 lg:grid-cols-3">
            {types.map((one) => (
              <li key={one.slug}>
                <label className="flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    disabled={selected === null}
                    checked={selected === null || selected.includes(one.slug)}
                    onChange={() => toggle(one.slug)}
                  />
                  {one.label}
                  <span className="text-muted-foreground font-mono text-xs">
                    {one.slug} · {one.count}
                  </span>
                </label>
              </li>
            ))}
          </ul>
        )}
      </div>

      {checked && (
        <p className={`text-sm ${checked.ok ? '' : 'text-destructive'}`}>
          {checked.message}
          {checked.revision && ` · 판 ${checked.revision}`}
          {checked.request_id && (
            <span className="text-muted-foreground"> · request_id {checked.request_id}</span>
          )}
        </p>
      )}
      <div className="flex gap-2">
        <Button disabled={busy} onClick={() => void save()}>
          저장
        </Button>
        <Button variant="outline" disabled={busy} onClick={() => void check()}>
          연결 점검
        </Button>
      </div>
    </section>
  )
}

export default function HubAdminPage() {
  const connection = useResource(() => hubApi.connection(), [])
  const status = useResource(() => hubApi.status(), [])
  const runs = useResource(() => hubApi.runs(), [])
  const [error, setError] = useState<Error | null>(null)
  const [openRun, setOpenRun] = useState<string | null>(null)
  const pending = status.data?.pending_job

  // 대기 · 실행 중이면 잠깐마다 다시 읽는다 — 워커가 끝내면 현황이 바뀐다.
  useEffect(() => {
    if (!pending) return
    const timer = window.setInterval(() => {
      status.reload()
      runs.reload()
    }, 5000)
    return () => window.clearInterval(timer)
  }, [pending, status, runs])

  async function run(full: boolean) {
    setError(null)
    try {
      await hubApi.run(full)
      status.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

  async function seen() {
    await hubApi.catalogSeen()
    status.reload()
  }

  const data = status.data
  return (
    <div className="space-y-6">
      <PageHeader
        title="허브 연계"
        description="StandardPlatform 기준정보 허브의 코어 데이터를 받아 온톨로지 축으로 반영. 받은 축은 TestScope에서 수정 불가(허브에서 수정)."
        actions={
          <Button variant="outline" asChild>
            <Link to="/hub">받은 데이터 보기</Link>
          </Button>
        }
      />
      <ErrorNotice error={connection.error ?? status.error ?? runs.error ?? error} />

      {data?.catalog_changed_at && (
        <div className="flex items-center gap-3 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm dark:bg-amber-950/30">
          <span>
            허브 구조(타입·칸·관계 종류) 변경 감지 — {shownDateTime(data.catalog_changed_at)}.
            알림의 내용을 확인한 뒤 받을 타입을 점검.
          </span>
          <Button size="sm" variant="outline" onClick={() => void seen()}>
            확인함
          </Button>
        </div>
      )}

      {connection.data && (
        <ConnectionForm
          current={connection.data}
          onSaved={() => {
            connection.reload()
            status.reload()
          }}
        />
      )}

      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-base font-semibold">수신 현황</h2>
          {data && (
            <span className="text-muted-foreground text-sm">
              {data.enabled ? `야간 자동 ${data.nightly_at} KST` : '야간 자동 꺼짐'}
              {pending &&
                ` · ${pending === 'running' ? '수신 중' : '대기 중(워커가 꺼져 있으면 실행 안 됨)'}`}
            </span>
          )}
          <div className="flex-1" />
          <Button
            size="sm"
            disabled={!data?.configured || Boolean(pending)}
            onClick={() => void run(false)}
          >
            지금 받기
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={!data?.configured || Boolean(pending)}
            title="기준 시각을 무시하고 전부 받은 뒤, 이번에 안 온 것을 비활성(부재 대조)"
            onClick={() => void run(true)}
          >
            전량 다시 받기
          </Button>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>타입</TableHead>
              <TableHead>받기</TableHead>
              <TableHead className="text-right" title="허브 카탈로그의 객체 수">
                허브
              </TableHead>
              <TableHead className="text-right" title="받아 둔 것 중 사용 중">
                사용 중
              </TableHead>
              <TableHead className="text-right">관계</TableHead>
              <TableHead>기준 시각</TableHead>
              <TableHead>마지막 수신</TableHead>
              <TableHead>결과</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(data?.types ?? []).map((one) => (
              <TableRow key={one.slug}>
                <TableCell>
                  <Link
                    to={`/hub?type=${encodeURIComponent(one.slug)}`}
                    className="hover:underline"
                  >
                    {one.label}
                  </Link>
                  <span className="text-muted-foreground block font-mono text-xs">
                    {one.slug}
                  </span>
                </TableCell>
                <TableCell>{one.selected ? '받음' : '안 받음'}</TableCell>
                <TableCell className="text-right tabular-nums">{one.catalog_count}</TableCell>
                <TableCell
                  className={`text-right tabular-nums ${
                    one.selected && one.received > 0 && one.active !== one.catalog_count
                      ? 'text-amber-700 dark:text-amber-400'
                      : ''
                  }`}
                >
                  {one.active}
                </TableCell>
                <TableCell className="text-right tabular-nums">{one.relations}</TableCell>
                <TableCell className="font-mono text-xs">{one.rows?.as_of ?? '—'}</TableCell>
                <TableCell className="text-xs">
                  {one.rows?.last_run_at ? shownDateTime(one.rows.last_run_at) : '—'}
                </TableCell>
                <TableCell className="text-xs">
                  {one.rows?.stopped
                    ? '허브에서 비공개 전환'
                    : one.rows?.last_status === 'failed'
                      ? `실패: ${one.rows.last_error ?? ''}`
                      : one.rows?.last_status === 'ok'
                        ? '정상'
                        : '—'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </section>

      <section className="space-y-3">
        <h2 className="text-base font-semibold">수신 이력</h2>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>시작</TableHead>
              <TableHead>방식</TableHead>
              <TableHead>결과</TableHead>
              <TableHead className="text-right">변경</TableHead>
              <TableHead className="text-right">소요</TableHead>
              <TableHead>오류</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {(runs.data ?? []).map((one) => (
              <Fragment key={one.id}>
                <TableRow>
                  <TableCell className="text-xs">{shownDateTime(one.started_at)}</TableCell>
                  <TableCell className="text-xs">
                    {RUN_TRIGGER[one.trigger] ?? one.trigger}
                    {one.full && ' · 전량'}
                    {one.triggered_by && (
                      <span className="text-muted-foreground"> · {one.triggered_by}</span>
                    )}
                  </TableCell>
                  <TableCell
                    className={`text-xs ${one.status === 'ok' ? '' : 'text-amber-700 dark:text-amber-400'}`}
                  >
                    {RUN_STATUS[one.status] ?? one.status}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{changed(one)}</TableCell>
                  <TableCell className="text-right text-xs tabular-nums">
                    {one.duration_ms != null ? `${(one.duration_ms / 1000).toFixed(1)}s` : '—'}
                  </TableCell>
                  <TableCell className="max-w-72 truncate text-xs">
                    {one.errors.length > 0
                      ? `${one.errors.length}건: ${String(one.errors[0].message ?? '')}`
                      : '—'}
                  </TableCell>
                  <TableCell>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setOpenRun(openRun === one.id ? null : one.id)}
                    >
                      {openRun === one.id ? '접기' : '자세히'}
                    </Button>
                  </TableCell>
                </TableRow>
                {openRun === one.id && (
                  <TableRow>
                    <TableCell colSpan={7}>
                      <pre className="bg-muted overflow-x-auto rounded p-2 text-xs">
                        {JSON.stringify(
                          {
                            counts: one.counts,
                            errors: one.errors,
                            request_ids: one.request_ids,
                          },
                          null,
                          2,
                        )}
                      </pre>
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            ))}
          </TableBody>
        </Table>
      </section>
    </div>
  )
}

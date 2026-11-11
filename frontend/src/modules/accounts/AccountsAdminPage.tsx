/**
 * 계정 관리.
 *
 * **승인 대기가 맨 위에 온다.** 관리자가 할 일이 목록 맨 위에 있어야 한다 —
 * 이름순으로 두면 대기 하나를 찾으려고 세 쪽을 넘겨야 하고, 그러면 며칠씩 방치된다.
 */

import { useState } from 'react'

import { ApiError } from '@/shared/api/client'
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
import { useSearchParams } from 'react-router-dom'

import { Textarea } from '@/shared/components/ui/textarea'
import { useResource } from '@/shared/hooks/useResource'
import { copyText } from '@/shared/lib/clipboard'
import { shownDate } from '@/shared/lib/datetime'
import { accountApi } from '@/modules/accounts/api'
import type { Account } from '@/modules/accounts/api'
import { MembershipsDialog } from '@/modules/accounts/MembershipsDialog'

/** 서버가 한 번에 주는 계정 수의 상한(`list_accounts` 의 `le=100`). */
const PAGE = 100
/** 왕복 상한 — 1만 명. 넘으면 덜 받았다고 적는다. */
const ROUNDS = 100

/**
 * 계정을 **끝까지** 받는다.
 *
 * 서버는 한 번에 50명(기본)·100명(상한)까지만 준다. 그냥 부르면 51번째부터는 화면에
 * 안 나오고, 그러면 메일 주소를 「전체 선택」 해 복사해도 앞 50명뿐이다. 응답에 `total`
 * 이 없으니 **한 쪽이 덜 차면 끝**으로 본다.
 */
async function listEveryAccount(
  status?: string,
): Promise<{ items: Account[]; done: boolean }> {
  const items: Account[] = []
  for (let round = 0; round < ROUNDS; round += 1) {
    const got = await accountApi.list(status, PAGE, items.length)
    items.push(...got)
    if (got.length < PAGE) return { items, done: true }
  }
  return { items, done: false }
}

/** 메일 주소로 보이는가. 아이디는 메일 형식을 강제하지 않는다(`admin` 같은 짧은 아이디). */
const MAIL = /^[^\s@]+@[^\s@]+$/

/**
 * 받는 사람 칸에 붙여 넣을 글자. **`; ` 로 잇는다** — Outlook 의 기본 구분자다(쉼표는
 * 설정을 켜야 갈린다). 메일 형식이 아닌 아이디는 빼고, 뺀 것을 돌려준다 — 말없이 빼면
 * 「다 보냈다」 로 읽는다.
 */
function mailList(accounts: Account[]) {
  const addresses: string[] = []
  const skipped: string[] = []
  for (const one of accounts) {
    if (MAIL.test(one.email)) addresses.push(one.email)
    else skipped.push(one.email)
  }
  return { text: addresses.join('; '), count: addresses.length, skipped }
}

/** 복사한 결과. `text` 가 있으면 **브라우저가 막은 것**이라 손으로 복사할 칸을 띄운다. */
interface Copied {
  count: number
  skipped: string[]
  text?: string
}

export default function AccountsAdminPage() {
  // **홈의 「남은 일」 이 `?status=pending` 으로 온다.** 승인 대기가 며칠씩 방치되는
  // 것을 막으려고 만든 링크인데, 안 읽으면 그 줄은 아무 일도 안 한다.
  const [params] = useSearchParams()
  const status = params.get('status') ?? undefined
  const list = useResource(() => listEveryAccount(status), [status])
  const rows = list.data?.items ?? []
  /** 메일 주소를 복사할 계정. 목록이 바뀌어 없어진 id 는 `picked` 에서 저절로 빠진다. */
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const picked = rows.filter((one) => selected.has(one.id))
  const allPicked = rows.length > 0 && picked.length === rows.length
  const [copied, setCopied] = useState<Copied | null>(null)

  /** 걸러져 있으면 그 사실을 적는다. 안 적으면 「계정이 이것뿐인가」 로 읽힌다. */
  const filtered = status === 'pending'
  const summary = useResource(() => accountApi.summary(), [])
  const [error, setError] = useState<ApiError | Error | null>(null)
  /** 소속을 바꾸려고 연 사람. 창이 목록 전체를 들고 있다가 한 번에 보낸다. */
  const [moving, setMoving] = useState<Account | null>(null)
  // 임시 비밀번호는 **한 번만** 나온다. 화면이 붙들고 있어야 관리자가 옮겨 적는다.
  const [issued, setIssued] = useState<{ email: string; password: string } | null>(null)

  async function act(run: () => Promise<unknown>) {
    setError(null)
    try {
      await run()
      list.reload()
      summary.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

  function pick(ids: string[], on: boolean) {
    setCopied(null)
    setSelected((before) => {
      const next = new Set(before)
      for (const id of ids) {
        if (on) next.add(id)
        else next.delete(id)
      }
      return next
    })
  }

  // **누른 자리에서 곧장 복사한다** — 사이에 await 를 두지 않는다. 평문 http 의 복사
  // (`execCommand`)는 사용자가 누른 그 순간에만 허락되고, 무엇을 받아 오느라 한 박자
  // 늦으면 브라우저가 거절한다. 주소는 이미 화면에 있는 목록에서 만든다.
  async function copyMails() {
    const built = mailList(picked)
    if (built.count === 0) {
      setCopied({ count: 0, skipped: built.skipped })
      return
    }
    try {
      await copyText(built.text)
      setCopied({ count: built.count, skipped: built.skipped })
    } catch {
      setCopied({ count: built.count, skipped: built.skipped, text: built.text })
    }
  }

  const onlyOneAdmin = (summary.data?.active_system_admins ?? 0) <= 1

  return (
    <div className="space-y-6">
      <PageHeader
        title="계정"
        description={
          filtered
            ? '승인 대기 계정만 표시 중. 홈의 ‘처리 필요 항목’에서 이동함.'
            : '가입 승인 및 권한 관리. 부서 멤버 관리는 부서 화면에서 진행.'
        }
      />

      {/* **관리자가 하나뿐이면 말한다.** 그 사람이 잠기는 순간 복구 경로가 서버
          콘솔뿐이고, 그때는 화면에서 할 수 있는 것이 하나도 없다. */}
      {summary.data && onlyOneAdmin && (
        <div className="rounded-md border border-amber-500/40 bg-amber-500/5 p-3 text-sm">
          활성 시스템 관리자 1명. 해당 계정이 잠기면 서버 콘솔로만 복구 가능. 추가 지정 필요.
        </div>
      )}

      {issued && (
        <div className="rounded-md border border-amber-500/40 bg-amber-500/5 p-3 text-sm">
          <p className="font-medium">
            {issued.email}의 임시 비밀번호. 지금 전달 필요(다시 볼 수 없음).
          </p>
          <p className="mt-1 font-mono text-xs">{issued.password}</p>
        </div>
      )}

      <ErrorNotice error={error ?? list.error} />

      {list.data && !list.data.done && (
        <p className="text-sm text-amber-700 dark:text-amber-400">
          계정이 많아 앞 {rows.length.toLocaleString()}명만 표시.
        </p>
      )}

      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <Button
            size="sm"
            variant="outline"
            disabled={picked.length === 0}
            onClick={copyMails}
          >
            메일 주소 복사{picked.length > 0 ? ` (${picked.length})` : ''}
          </Button>
          <span className="text-muted-foreground text-sm">
            {picked.length === 0
              ? '계정 선택 시 받는 사람 칸에 붙여 넣을 주소를 한 번에 복사.'
              : `${picked.length}명 선택.`}
          </span>
        </div>
        {copied && (
          <div className="space-y-2 text-sm">
            <p>
              {copied.count === 0
                ? `복사할 메일 주소 없음. 선택한 아이디가 모두 메일 형식이 아님: ${copied.skipped.join(', ')}`
                : copied.text === undefined
                  ? `메일 주소 ${copied.count}개 복사함. 메일의 받는 사람 칸에 붙여넣기(; 로 구분).`
                  : `브라우저가 복사를 막음. 아래 칸의 주소 ${copied.count}개를 직접 복사(칸을 누르면 전체 선택).`}
              {copied.count > 0 && copied.skipped.length > 0 && (
                <span className="text-muted-foreground">
                  {' '}
                  메일 형식이 아닌 아이디 {copied.skipped.length}개 제외:{' '}
                  {copied.skipped.join(', ')}
                </span>
              )}
            </p>
            {copied.text !== undefined && (
              <Textarea
                readOnly
                aria-label="복사할 메일 주소"
                className="font-mono text-xs"
                value={copied.text}
                onFocus={(event) => event.currentTarget.select()}
                autoFocus
              />
            )}
          </div>
        )}
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-8">
              <input
                type="checkbox"
                aria-label="전체 선택"
                checked={allPicked}
                disabled={rows.length === 0}
                onChange={(event) =>
                  pick(
                    rows.map((one) => one.id),
                    event.target.checked,
                  )
                }
              />
            </TableHead>
            <TableHead>아이디</TableHead>
            <TableHead>이름</TableHead>
            <TableHead>상태</TableHead>
            <TableHead>소속</TableHead>
            <TableHead>신청/승인</TableHead>
            <TableHead className="text-right">처리</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((one) => (
            <TableRow key={one.id}>
              <TableCell>
                <input
                  type="checkbox"
                  aria-label={`${one.email} 선택`}
                  checked={selected.has(one.id)}
                  onChange={(event) => pick([one.id], event.target.checked)}
                />
              </TableCell>
              <TableCell className="font-mono text-xs">{one.email}</TableCell>
              <TableCell>
                {one.display_name}
                {one.is_system_admin && (
                  <span className="text-muted-foreground ml-2 text-xs">시스템 관리자</span>
                )}
              </TableCell>
              <TableCell>
                <StatusBadge kind="account" value={one.status} />
              </TableCell>
              {/* **길면 줄인다.** 부서 이름이 길거나 여럿이면 이 칸이 표를 통째로 밀어
                  버려서, 오른쪽의 처리 단추가 화면 밖으로 나간다. 전체는 `title` 에 남으므로
                  마우스를 올리면 보인다. */}
              <TableCell className="max-w-[16rem] text-sm">
                <span
                  className="block truncate"
                  title={one.memberships.join(', ') || one.requested_workspace_slug || ''}
                >
                  {one.memberships.join(', ') || one.requested_workspace_slug || '—'}
                </span>
              </TableCell>
              <TableCell className="text-sm">
                {shownDate(one.decided_at ?? one.created_at)}
              </TableCell>
              <TableCell className="space-x-1 text-right">
                {one.status === 'pending' ? (
                  <>
                    <Button
                      size="sm"
                      onClick={() => act(() => accountApi.approve(one.id, {}))}
                    >
                      승인
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        // **사유를 반드시 받는다.** 메일이 없어 통보가 앱 안에서만
                        // 되므로, 안 적으면 신청한 사람은 이유를 영영 모른다.
                        const note = window.prompt('거절 사유 입력')
                        if (note) act(() => accountApi.reject(one.id, note))
                      }}
                    >
                      거절
                    </Button>
                  </>
                ) : (
                  <>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        act(async () => {
                          const body = await accountApi.resetPassword(one.id)
                          setIssued({ email: one.email, password: body.temporary_password })
                        })
                      }
                    >
                      비밀번호 초기화
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setMoving(one)}>
                      소속
                    </Button>
                    {/* **위의 경고가 시키는 일을 여기서 한다.** 「한 명 더 지정해
                        두십시오」 라고 적어 두고 지정할 자리가 없으면, 읽은 사람은
                        서버 콘솔을 찾아보다 그만둔다.

                        마지막 한 명은 **해제를 못 누르게** 막는다 — 서버도 거절하지만,
                        눌러 보고 오류를 읽는 것과 못 누르는 것은 다르다. */}
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={one.is_system_admin && onlyOneAdmin}
                      title={
                        one.is_system_admin && onlyOneAdmin
                          ? '마지막 시스템 관리자. 다른 관리자 먼저 지정 필요.'
                          : undefined
                      }
                      onClick={() => {
                        const grant = !one.is_system_admin
                        // 권한을 넓히는 쪽이라 한 번 묻는다. 무엇이 열리는지 함께 적는다 —
                        // 「관리자」 라는 말만으로는 어디까지인지 사람마다 다르게 읽는다.
                        const asked = grant
                          ? `${one.display_name}(${one.email})을(를) 시스템 관리자로 지정하시겠습니까?\n\n카탈로그·온톨로지·계정·부서·서버 설정 전체 수정 권한이 부여됨.`
                          : `${one.display_name}(${one.email})의 시스템 관리자 권한을 해제하시겠습니까?`
                        if (window.confirm(asked)) {
                          act(() => accountApi.setSystemAdmin(one.id, grant))
                        }
                      }}
                    >
                      {one.is_system_admin ? '관리자 해제' : '관리자 지정'}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        act(() =>
                          one.status === 'active'
                            ? accountApi.suspend(one.id)
                            : accountApi.activate(one.id),
                        )
                      }
                    >
                      {one.status === 'active' ? '정지' : '활성화'}
                    </Button>
                  </>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <MembershipsDialog
        account={moving}
        onClose={() => setMoving(null)}
        onSaved={() => {
          setMoving(null)
          list.reload()
        }}
      />
    </div>
  )
}

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
import { useResource } from '@/shared/hooks/useResource'
import { shownDate } from '@/shared/lib/datetime'
import { accountApi } from '@/modules/accounts/api'

export default function AccountsAdminPage() {
  const list = useResource(() => accountApi.list(), [])
  const summary = useResource(() => accountApi.summary(), [])
  const [error, setError] = useState<ApiError | Error | null>(null)
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

  const onlyOneAdmin = (summary.data?.active_system_admins ?? 0) <= 1

  return (
    <div className="space-y-6">
      <PageHeader
        title="계정"
        description="가입 승인과 권한을 다룹니다. 부서 멤버 관리는 부서 화면에서 합니다."
      />

      {/* **관리자가 하나뿐이면 말한다.** 그 사람이 잠기는 순간 복구 경로가 서버
          콘솔뿐이고, 그때는 화면에서 할 수 있는 것이 하나도 없다. */}
      {summary.data && onlyOneAdmin && (
        <div className="rounded-md border border-amber-500/40 bg-amber-500/5 p-3 text-sm">
          활성 시스템 관리자가 1명입니다. 그 계정이 잠기면 서버 콘솔로만 복구할 수
          있습니다 — 한 명 더 지정해 두세요.
        </div>
      )}

      {issued && (
        <div className="rounded-md border border-amber-500/40 bg-amber-500/5 p-3 text-sm">
          <p className="font-medium">
            {issued.email} 의 임시 비밀번호입니다. 지금 전달하세요 — 다시 볼 수 없습니다.
          </p>
          <p className="mt-1 font-mono text-xs">{issued.password}</p>
        </div>
      )}

      <ErrorNotice error={error ?? list.error} />

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>아이디</TableHead>
            <TableHead>이름</TableHead>
            <TableHead>상태</TableHead>
            <TableHead>소속</TableHead>
            <TableHead>신청/승인</TableHead>
            <TableHead className="text-right">처리</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(list.data ?? []).map((one) => (
            <TableRow key={one.id}>
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
              <TableCell className="text-sm">
                {one.memberships.join(', ') || one.requested_workspace_slug || '—'}
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
                        const note = window.prompt('거절 사유를 적어 주세요')
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
    </div>
  )
}

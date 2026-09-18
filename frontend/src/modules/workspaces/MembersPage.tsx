/**
 * 부서 멤버.
 *
 * **마지막 관리자는 뺄 수 없다.** 서버가 막지만 화면도 그 이유를 말해 준다 —
 * 눌러 보고 알게 하면 사람은 그것을 고장으로 읽는다.
 */

import { useState } from 'react'
import { useParams } from 'react-router-dom'

import { ApiError } from '@/shared/api/client'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { StatusBadge } from '@/shared/components/StatusBadge'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
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
import { workspaceApi } from '@/modules/workspaces/api'

export default function MembersPage() {
  const { slug = '' } = useParams<{ slug: string }>()
  const list = useResource(() => workspaceApi.members(slug), [slug])
  const [email, setEmail] = useState('')
  const [error, setError] = useState<ApiError | Error | null>(null)

  async function act(run: () => Promise<unknown>) {
    setError(null)
    try {
      await run()
      list.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="부서 멤버"
        description="관리자는 이 부서의 장비와 멤버를 고칠 수 있습니다."
      />

      <form
        className="flex max-w-md gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          act(async () => {
            await workspaceApi.addMember(slug, email, 'member')
            setEmail('')
          })
        }}
      >
        <Input
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="추가할 계정의 아이디"
          required
        />
        <Button type="submit">멤버 추가</Button>
      </form>

      <ErrorNotice error={error ?? list.error} />

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>이름</TableHead>
            <TableHead>아이디</TableHead>
            <TableHead>계정 상태</TableHead>
            <TableHead>역할</TableHead>
            <TableHead>합류</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {(list.data ?? []).map((one) => (
            <TableRow key={one.user_id}>
              <TableCell>{one.display_name}</TableCell>
              <TableCell className="font-mono text-xs">{one.email}</TableCell>
              <TableCell>
                <StatusBadge kind="account" value={one.status} />
              </TableCell>
              <TableCell>
                <Select
                  value={one.role}
                  onValueChange={(role) =>
                    act(() => workspaceApi.setRole(slug, one.user_id, role))
                  }
                >
                  <SelectTrigger className="h-8 w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="member">멤버</SelectItem>
                    <SelectItem value="manager">부서 관리자</SelectItem>
                  </SelectContent>
                </Select>
              </TableCell>
              <TableCell>{shownDate(one.joined_at)}</TableCell>
              <TableCell className="text-right">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => act(() => workspaceApi.removeMember(slug, one.user_id))}
                >
                  빼기
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

/**
 * 알림 — **나에게 온 것.**
 *
 * 공지가 모두에게 가는 방송이라면 알림은 한 사람에게 가는 편지다. 메일이 없는
 * 환경이라 이것이 유일한 전달 경로이고, 그래서 읽음 상태를 서버가 든다.
 */

import { Link } from 'react-router-dom'

import { api } from '@/shared/api/client'
import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { Button } from '@/shared/components/ui/button'
import { useResource } from '@/shared/hooks/useResource'
import { shownDateTime } from '@/shared/lib/datetime'

interface Notification {
  id: string
  kind: string
  title: string
  body: string | null
  /** 눌렀을 때 갈 곳. **없으면 알림은 읽고 끝나는 글이 된다.** */
  link: string | null
  read_at: string | null
  created_at: string
}

export default function NotificationsPage() {
  const list = useResource(() => api.get<Notification[]>('/notifications'), [])

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="알림"
        description="가입 승인, 교정 만료처럼 나에게 온 일들입니다."
        actions={
          <Button
            variant="outline"
            onClick={async () => {
              await api.post('/notifications/read-all')
              list.reload()
            }}
          >
            모두 읽음
          </Button>
        }
      />

      <ErrorNotice error={list.error} />

      {list.data && list.data.length === 0 ? (
        <EmptyState title="알림이 없습니다" />
      ) : (
        <ul className="space-y-2">
          {(list.data ?? []).map((one) => (
            <li
              key={one.id}
              className={one.read_at ? 'rounded-md border p-3 opacity-60' : 'rounded-md border p-3'}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium">{one.title}</p>
                  {one.body && <p className="text-muted-foreground mt-1 text-sm">{one.body}</p>}
                  {one.link && (
                    <Link to={one.link} className="mt-1 inline-block text-xs underline">
                      보러 가기
                    </Link>
                  )}
                </div>
                <span className="text-muted-foreground shrink-0 text-xs">
                  {shownDateTime(one.created_at)}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/**
 * 안 읽은 알림 배지.
 *
 * **주기적으로 서버에 묻는다.** 알림은 메일이 없는 환경의 유일한 전달 경로라,
 * 화면을 새로 고쳐야만 보이면 전달이 안 된 것과 같다.
 *
 * 이 경로는 접근 로그에서 뺐다(shared/access_log.py) — 안 빼면 표가 이 한 줄로
 * 가득 차서 정작 찾을 것을 못 찾는다.
 */

import { useEffect, useState } from 'react'
import { Bell } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { api } from '@/shared/api/client'
import { Button } from '@/shared/components/ui/button'

const POLL_MS = 60_000

export function NotificationBell() {
  const [unread, setUnread] = useState(0)
  const navigate = useNavigate()

  useEffect(() => {
    let cancelled = false
    async function poll() {
      try {
        const body = await api.get<{ unread: number }>('/notifications/unread-count')
        if (!cancelled) setUnread(body.unread)
      } catch {
        // 세션이 끊겼거나 서버가 잠깐 없다. **배지 하나 때문에 화면에 오류를
        // 띄우지 않는다** — 사람이 하던 일과 아무 상관이 없다.
      }
    }
    void poll()
    const timer = window.setInterval(poll, POLL_MS)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [])

  return (
    <Button
      variant="ghost"
      size="icon"
      className="relative"
      aria-label={unread ? `안 읽은 알림 ${unread}건` : '알림'}
      onClick={() => navigate('/notifications')}
    >
      <Bell className="size-4" />
      {unread > 0 && (
        <span className="bg-destructive text-destructive-foreground absolute top-1 right-1 min-w-4 rounded-full px-1 text-[10px] leading-4">
          {unread > 99 ? '99+' : unread}
        </span>
      )}
    </Button>
  )
}

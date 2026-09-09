/**
 * 공지 — **배포 없이 안내를 전하는 자리.**
 *
 * 메일 서버가 없는 사내 설치에서는 이것이 유일한 전달 경로다. 코드에 박아
 * 배포하는 방식은 고치는 데 배포가 필요해지므로 결국 아무도 안 고친다.
 */

import { useState } from 'react'

import { ApiError } from '@/shared/api/client'
import { useAuth } from '@/shared/auth/AuthContext'
import { isSystemAdmin } from '@/shared/auth/roles'
import { EmptyState } from '@/shared/components/EmptyState'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { PageHeader } from '@/shared/components/PageHeader'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Textarea } from '@/shared/components/ui/textarea'
import { useResource } from '@/shared/hooks/useResource'
import { shownDateTime } from '@/shared/lib/datetime'
import { noticeApi } from '@/modules/notices/api'

export default function NoticesPage() {
  const { user } = useAuth()
  const list = useResource(() => noticeApi.list(), [])
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [isPopup, setIsPopup] = useState(false)
  const [error, setError] = useState<ApiError | Error | null>(null)

  async function submit() {
    setError(null)
    try {
      await noticeApi.create({ title, body, is_popup: isPopup, publish: true })
      setTitle('')
      setBody('')
      setIsPopup(false)
      list.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title="공지" description="시스템 안내와 점검 일정을 여기서 전합니다." />

      {isSystemAdmin(user) && (
        <div className="space-y-3 rounded-md border p-4">
          <Input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="제목"
          />
          <Textarea
            value={body}
            onChange={(event) => setBody(event.target.value)}
            placeholder="내용"
            rows={4}
          />
          <div className="flex items-center justify-between">
            <label className="text-muted-foreground flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={isPopup}
                onChange={(event) => setIsPopup(event.target.checked)}
              />
              {/* 팝업은 읽지 않은 사람에게 스스로 뜬다 — 급한 안내에만 쓴다. */}
              팝업으로 띄우기
            </label>
            <Button onClick={submit} disabled={!title || !body}>
              게시
            </Button>
          </div>
        </div>
      )}

      <ErrorNotice error={error ?? list.error} />

      {list.data && list.data.length === 0 ? (
        <EmptyState title="공지가 없습니다" />
      ) : (
        <ul className="space-y-4">
          {(list.data ?? []).map((one) => (
            <li key={one.id} className="rounded-md border p-4">
              <div className="flex items-start justify-between gap-3">
                <h2 className="font-medium">{one.title}</h2>
                <span className="text-muted-foreground shrink-0 text-xs">
                  {shownDateTime(one.published_at ?? one.created_at)}
                </span>
              </div>
              <p className="mt-2 text-sm whitespace-pre-wrap">{one.body}</p>
              <p className="text-muted-foreground mt-2 text-xs">
                {one.author_name ?? '시스템'}
                {one.published_at ? '' : ' · 초안'}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/**
 * 공지 — **배포 없이 안내를 전하는 자리.**
 *
 * 메일 서버가 없는 사내 설치에서는 이것이 유일한 전달 경로다. 코드에 박아
 * 배포하는 방식은 고치는 데 배포가 필요해지므로 결국 아무도 안 고친다.
 *
 * ## 초안 → 게시가 두 걸음이다
 *
 * 반쯤 쓴 공지를 저장해 둘 자리가 없으면 완성될 때까지 창을 열어 두다 날린다. 그래서
 * 「임시저장」 이 초안을 남기고(관리자만 본다), 게시는 **초안 줄의 「게시」 로 따로** 누른다 —
 * 고치다가 저장 단추 하나로 전사에 나가면 그 단추를 누를 때마다 망설이게 된다.
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
import type { Notice } from '@/modules/notices/api'

export default function NoticesPage() {
  const { user } = useAuth()
  const admin = isSystemAdmin(user)
  // 초안은 관리자에게만 온다 — 서버가 가르지만, 묻지도 않으면 관리자도 자기 초안을 못 찾는다.
  const list = useResource(() => noticeApi.list(admin), [admin])
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [isPopup, setIsPopup] = useState(false)
  /** 고치는 중인 공지. 비어 있으면 새로 쓰는 중이다. */
  const [editing, setEditing] = useState<Notice | null>(null)
  const [error, setError] = useState<ApiError | Error | null>(null)

  function reset() {
    setTitle('')
    setBody('')
    setIsPopup(false)
    setEditing(null)
  }

  async function run(work: () => Promise<unknown>) {
    setError(null)
    try {
      await work()
      list.reload()
    } catch (caught) {
      setError(caught instanceof Error ? caught : new Error('알 수 없는 오류'))
    }
  }

  /** 새로 쓰기 — `publish` 면 바로 게시, 아니면 초안. 고치는 중이면 고친 것만 저장한다. */
  function save(publish: boolean) {
    return run(async () => {
      if (editing) {
        await noticeApi.update(editing.id, { title, body, is_popup: isPopup })
      } else {
        await noticeApi.create({ title, body, is_popup: isPopup, publish })
      }
      reset()
    })
  }

  function startEdit(one: Notice) {
    setEditing(one)
    setTitle(one.title)
    setBody(one.body)
    setIsPopup(one.is_popup)
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title="공지" description="시스템 안내와 점검 일정을 여기서 전합니다." />

      {admin && (
        <div className="space-y-3 rounded-md border p-4">
          {editing && (
            <p className="text-muted-foreground text-xs">
              「{editing.title}」 을(를) 고치는 중입니다
              {editing.published_at ? ' — 게시된 공지라 저장하면 바로 바뀝니다' : ' — 초안'}
            </p>
          )}
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
          <div className="flex items-center justify-between gap-2">
            <label className="text-muted-foreground flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={isPopup}
                onChange={(event) => setIsPopup(event.target.checked)}
              />
              {/* 팝업은 읽지 않은 사람에게 스스로 뜬다 — 급한 안내에만 쓴다. */}
              팝업으로 띄우기
            </label>
            <div className="flex gap-2">
              {editing ? (
                <>
                  <Button variant="outline" onClick={reset}>
                    취소
                  </Button>
                  <Button onClick={() => void save(false)} disabled={!title || !body}>
                    저장
                  </Button>
                </>
              ) : (
                <>
                  {/* **초안은 관리자만 본다.** 반쯤 쓴 글이 전사에 보이면 그 자체가 사고다. */}
                  <Button
                    variant="outline"
                    onClick={() => void save(false)}
                    disabled={!title || !body}
                  >
                    임시저장
                  </Button>
                  <Button onClick={() => void save(true)} disabled={!title || !body}>
                    게시
                  </Button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      <ErrorNotice error={error ?? list.error} />

      {list.data && list.data.length === 0 ? (
        <EmptyState title="공지가 없습니다" />
      ) : (
        <ul className="space-y-4">
          {(list.data ?? []).map((one) => (
            <li
              key={one.id}
              className={`rounded-md border p-4 ${one.published_at ? '' : 'border-dashed'}`}
            >
              <div className="flex items-start justify-between gap-3">
                <h2 className="font-medium">
                  {one.title}
                  {!one.published_at && (
                    <span className="text-muted-foreground ml-2 rounded bg-amber-500/10 px-1.5 py-0.5 text-xs font-normal text-amber-700">
                      초안
                    </span>
                  )}
                </h2>
                <span className="text-muted-foreground shrink-0 text-xs">
                  {shownDateTime(one.published_at ?? one.created_at)}
                </span>
              </div>
              <p className="mt-2 text-sm whitespace-pre-wrap">{one.body}</p>
              <div className="mt-2 flex items-center justify-between gap-2">
                <p className="text-muted-foreground text-xs">
                  {one.author_name ?? '시스템'}
                  {one.published_at ? '' : ' · 아직 아무에게도 안 보입니다'}
                </p>
                {admin && (
                  <div className="flex gap-1">
                    {!one.published_at && (
                      <Button
                        size="sm"
                        onClick={() => void run(() => noticeApi.publish(one.id))}
                      >
                        게시
                      </Button>
                    )}
                    <Button size="sm" variant="ghost" onClick={() => startEdit(one)}>
                      고치기
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        if (window.confirm(`「${one.title}」 공지를 지웁니다. 계속할까요?`)) {
                          void run(() => noticeApi.remove(one.id))
                        }
                      }}
                    >
                      지우기
                    </Button>
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

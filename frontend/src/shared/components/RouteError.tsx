/**
 * 라우트 오류 화면 — **배포 직후의 「옛 조각을 못 찾음」 은 새로고침 한 번으로 끝난다.**
 *
 * 화면은 조각(chunk)으로 쪼개져 필요할 때 받는다. 배포(또는 개발의 `npm run build`)로 조각의
 * 이름이 바뀌면, 그 전에 열어 둔 탭은 옛 이름을 들고 있어 다음 화면을 여는 순간
 * `Failed to fetch dynamically imported module` 로 죽는다. 데이터 문제가 아니라 **탭이 낡은
 * 것**이므로 답은 새로고침이다 — 사람이 하게 두지 않고 한 번은 자동으로 한다. 두 번째도 같으면
 * (서버가 정말 그 파일을 못 주는 것) 사람에게 말한다: 무한 새로고침을 막는 표식이 sessionStorage.
 *
 * 그 밖의 오류는 무엇이 났는지와 「홈으로」 를 보인다 — React Router 의 기본 화면은 개발자
 * 말이다.
 */

import { useEffect } from 'react'
import { Link, useRouteError } from 'react-router-dom'

import { Button } from '@/shared/components/ui/button'

const RELOAD_FLAG = 'testscope.chunk-reloaded'

function isStaleChunkError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? '')
  return (
    /Failed to fetch dynamically imported module/i.test(message) ||
    /Importing a module script failed/i.test(message) ||
    /error loading dynamically imported module/i.test(message)
  )
}

export function RouteError() {
  const error = useRouteError()
  const stale = isStaleChunkError(error)

  useEffect(() => {
    if (!stale) return
    let reloaded = false
    try {
      reloaded = sessionStorage.getItem(RELOAD_FLAG) === '1'
      if (!reloaded) sessionStorage.setItem(RELOAD_FLAG, '1')
    } catch {
      // 저장소를 못 쓰면 한 번은 그냥 새로고침한다.
    }
    if (!reloaded) window.location.reload()
  }, [stale])

  // 정상으로 열리면 표식을 지운다 — 다음 배포 때 또 한 번은 자동으로 되게.
  useEffect(() => {
    if (stale) return
    try {
      sessionStorage.removeItem(RELOAD_FLAG)
    } catch {
      // 없어도 된다.
    }
  }, [stale])

  const message = error instanceof Error ? error.message : String(error ?? '알 수 없는 오류')

  return (
    <div className="mx-auto max-w-lg space-y-4 p-8">
      <h1 className="text-lg font-semibold">
        {stale ? '화면이 새 버전으로 바뀌었습니다' : '화면을 그리지 못했습니다'}
      </h1>
      <p className="text-muted-foreground text-sm">
        {stale
          ? '새로고침하면 됩니다. 자동으로 한 번 시도했는데도 이 화면이면, 서버가 새 파일을 아직 못 주는 것이라 잠시 뒤 다시 여세요.'
          : message}
      </p>
      <div className="flex gap-2">
        <Button onClick={() => window.location.reload()}>새로고침</Button>
        <Button asChild variant="outline">
          <Link to="/">홈으로</Link>
        </Button>
      </div>
    </div>
  )
}

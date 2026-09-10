/**
 * 앱 껍데기 — 사이드바 + 헤더 + 본문.
 *
 * **본문만 스크롤한다.** 헤더·사이드바가 함께 스크롤되면 긴 화면에서 지금 어디
 * 있는지를 잃는다.
 *
 * 스크롤 통은 이 `main` 하나다. **위쪽 여백을 여기 두지 않는다** — 화면 머리글이
 * 이 통의 꼭대기에 붙어 있어야 하고(`PageHeader`), 통에 padding-top 이 있으면 그
 * 머리글이 처음에 그만큼 내려와 붙는다. 좌우·아래 여백만 안쪽 상자가 갖는다.
 */

import { Suspense, useState } from 'react'
import { Outlet } from 'react-router-dom'
import { useParams } from 'react-router-dom'

import { useAuth } from '@/shared/auth/AuthContext'
import { Skeleton } from '@/shared/components/ui/skeleton'
import { Header } from '@/shared/layout/Header'
import { DEFAULT_WORKSPACE } from '@/shared/layout/navigation'
import { NoticePopup } from '@/modules/notices/NoticePopup'
import { Sidebar, SidebarDrawer } from '@/shared/layout/Sidebar'

/** 화면 조각을 받아 오는 동안. **빈 화면을 보이지 않는다.** */
function PageSkeleton() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-4 w-80" />
      <Skeleton className="h-64 w-full" />
    </div>
  )
}

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false)
  const [drawer, setDrawer] = useState(false)
  const { slug } = useParams<{ slug?: string }>()
  const { user } = useAuth()

  // 부서 스코프가 아닌 화면(장비·검색·관리)에서도 사이드바의 '홈'·'부서 멤버' 는
  // **어느 부서인지** 정해야 한다. 고정값으로 두면 자기 부서가 아닌 곳을 가리켜
  // 목록이 비어 보이고, 그것은 데이터가 없는 것과 구별이 안 된다.
  const workspaceSlug =
    slug ?? user?.home_workspace_slug ?? user?.memberships[0]?.slug ?? DEFAULT_WORKSPACE

  return (
    <div className="flex h-svh overflow-hidden">
      <Sidebar collapsed={collapsed} workspaceSlug={workspaceSlug} />
      <SidebarDrawer open={drawer} onOpenChange={setDrawer} workspaceSlug={workspaceSlug} />

      <div className="flex min-w-0 flex-1 flex-col">
        <Header
          // **같은 단추가 화면 폭에 따라 다른 일을 한다.** 넓으면 붙박이
          // 사이드바를 접고, 좁으면(md 미만, 사이드바가 아예 없다) 서랍을 연다.
          onToggleSidebar={() => {
            if (window.matchMedia('(min-width: 768px)').matches) {
              setCollapsed((value) => !value)
            } else {
              setDrawer(true)
            }
          }}
          workspaceSlug={workspaceSlug}
        />
        <main className="flex-1 overflow-auto">
          {/* **본문은 폭을 다 쓴다.** 상한을 두면 넓은 표가 접히고, 그때마다
              「이 화면도 예외로」 가 반복돼 목록이 곧 전부가 된다. 좁아야 하는
              화면은 자기 안에서 다시 좁힌다. */}
          <div className="w-full px-6 pb-6">
            <Suspense fallback={<PageSkeleton />}>
              <Outlet />
            </Suspense>
          </div>
        </main>
      </div>

      {/* 읽지 않은 팝업 공지는 스스로 뜬다 — 공지 화면에 들어가야만 보이면
          "배포 없이 안내를 전한다" 는 목적이 성립하지 않는다. */}
      <NoticePopup />
    </div>
  )
}

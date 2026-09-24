/**
 * 라우트 표.
 *
 * 사이드바(navigation.ts)에 있는 항목은 여기에 대응 경로가 있어야 한다. 아직
 * 구현되지 않은 화면은 Placeholder 로 두되 **어느 단계에서 들어오는지 명시**한다.
 *
 * /login · /signup · /force-password-change 만 가드 밖에 있고 나머지는 전부
 * ProtectedRoute 아래에 둔다 — **새 화면을 추가할 때 가드를 깜빡할 자리가 없도록.**
 */

import { lazy } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'

import ForcePasswordChangePage from '@/modules/auth/ForcePasswordChangePage'
import LoginPage from '@/modules/auth/LoginPage'
import SearchPage from '@/modules/search/SearchPage'
import { useAuth } from '@/shared/auth/AuthContext'
import { ProtectedRoute } from '@/shared/auth/ProtectedRoute'
import { Placeholder } from '@/shared/components/Placeholder'
import { RouteError } from '@/shared/components/RouteError'
import { AppShell } from '@/shared/layout/AppShell'
import { DEFAULT_WORKSPACE, pendingItems } from '@/shared/layout/navigation'

/**
 * **매일 밟는 길은 처음에 싣는다.** 로그인·검색이 그것이다.
 *
 * 나머지는 나눠 싣는다 — 관리 화면은 대부분의 사람이 한 번도 안 열고, 그것을 위해
 * 첫 로드가 느려질 이유가 없다.
 */
const AccountsAdminPage = lazy(() => import('@/modules/accounts/AccountsAdminPage'))
const AuditPage = lazy(() => import('@/modules/audit/AuditPage'))
const ConditionsPage = lazy(() => import('@/modules/vocabulary/ConditionsPage'))
const SpecDefinitionsPage = lazy(() => import('@/modules/vocabulary/SpecDefinitionsPage'))
const AttributeDefinitionsPage = lazy(
  () => import('@/modules/attributes/AttributeDefinitionsPage'),
)
const EquipmentDetailPage = lazy(() => import('@/modules/equipment/EquipmentDetailPage'))
const EquipmentModelDetailPage = lazy(
  () => import('@/modules/equipment/EquipmentModelDetailPage'),
)
const EquipmentSeriesPage = lazy(() => import('@/modules/equipment/EquipmentSeriesPage'))
const EquipmentSeriesDetailPage = lazy(
  () => import('@/modules/equipment/EquipmentSeriesDetailPage'),
)
const EquipmentModelsPage = lazy(() => import('@/modules/equipment/EquipmentModelsPage'))
const EquipmentPage = lazy(() => import('@/modules/equipment/EquipmentPage'))
const MembersPage = lazy(() => import('@/modules/workspaces/MembersPage'))
const MethodDetailPage = lazy(() => import('@/modules/methods/MethodDetailPage'))
const MethodsPage = lazy(() => import('@/modules/methods/MethodsPage'))
const NoticesPage = lazy(() => import('@/modules/notices/NoticesPage'))
const NotificationsPage = lazy(() => import('@/modules/notifications/NotificationsPage'))
const ProfilePage = lazy(() => import('@/modules/auth/ProfilePage'))
const PropertiesPage = lazy(() => import('@/modules/properties/PropertiesPage'))
const ServerPage = lazy(() => import('@/modules/server/ServerPage'))
const ReviewPage = lazy(() => import('@/modules/review/ReviewPage'))
const ReviewQueuePage = lazy(() => import('@/modules/review/ReviewQueuePage'))
const TestItemsCatalogPage = lazy(() => import('@/modules/test_items/TestItemsCatalogPage'))
const TestItemCatalogDetailPage = lazy(
  () => import('@/modules/test_items/TestItemCatalogDetailPage'),
)
const ReliabilityTestsPage = lazy(() => import('@/modules/reliability/ReliabilityTestsPage'))
const WorkspaceReliabilityPage = lazy(
  () => import('@/modules/reliability/WorkspaceReliabilityPage'),
)
const SignupPage = lazy(() => import('@/modules/auth/SignupPage'))
const VocabularyAdminPage = lazy(() => import('@/modules/vocabulary/VocabularyAdminPage'))
const VocabularyPage = lazy(() => import('@/modules/vocabulary/VocabularyPage'))
const ReferenceHubPage = lazy(() => import('@/modules/reference/ReferenceHubPage'))
const GraphPage = lazy(() => import('@/modules/graph/GraphPage'))
const WorkspaceHomePage = lazy(() => import('@/modules/workspaces/WorkspaceHomePage'))
const WorkspacesAdminPage = lazy(() => import('@/modules/workspaces/WorkspacesAdminPage'))

/**
 * 아직 화면이 없는 항목 — **사이드바가 정본이다.** 제목·단계·설명을 여기 다시
 * 적으면 메뉴와 화면이 다른 말을 하게 된다. 화면이 생기면 그 항목의 pending 을
 * 지우고 여기서 빠진다.
 */
const stubs = pendingItems().map((item) => ({
  path: item.to!.replace(/^\//, ''),
  element: (
    <Placeholder title={item.label} phase={item.phase ?? '—'} description={item.summary} />
  ),
}))

/**
 * 첫 화면 — **내 부서로 보낸다.**
 *
 * 고정된 slug 로 두면 다른 부서 사람이 로그인했을 때 자기 것이 아닌 부서를
 * 가리키고, 목록이 비어 보인다 — 그것은 데이터가 없는 것과 구별이 안 된다.
 */
function HomeRedirect() {
  const { user } = useAuth()
  const slug = user?.home_workspace_slug ?? user?.memberships[0]?.slug ?? DEFAULT_WORKSPACE
  return <Navigate to={`/w/${slug}`} replace />
}

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage />, errorElement: <RouteError /> },
  { path: '/signup', element: <SignupPage />, errorElement: <RouteError /> },
  {
    // **조각을 못 받으면 새로고침 한 번** — 배포 뒤 낡은 탭의 오류는 여기서 끝난다(RouteError).
    errorElement: <RouteError />,
    element: <ProtectedRoute />,
    children: [
      { path: '/force-password-change', element: <ForcePasswordChangePage /> },
      {
        path: '/',
        element: <AppShell />,
        children: [
          { index: true, element: <HomeRedirect /> },

          // 시험 항목 — 우리가 가진 것.
          { path: 'search', element: <SearchPage /> },
          { path: 'properties', element: <PropertiesPage /> },
          { path: 'equipment', element: <EquipmentPage /> },
          { path: 'equipment/:id', element: <EquipmentDetailPage /> },
          // 부서 하나의 신뢰성 시험 — 사이드바 「신뢰성 시험」 아래 자식. 「시험 항목」
          // (카탈로그)과 다른 층이라 주소도 다르다. 모양은 navigation.ts 의 reliabilityHref 와 같다.
          { path: 'reliability-tests', element: <ReliabilityTestsPage /> },
          { path: 'reliability-tests/:slug', element: <WorkspaceReliabilityPage /> },

          // 카탈로그 — 세상에 있는 것. 보유 장비가 이 둘을 엮은 인스턴스다(ADR 0004).
          { path: 'catalog/equipment-series', element: <EquipmentSeriesPage /> },
          {
            path: 'catalog/equipment-series/:id',
            element: <EquipmentSeriesDetailPage />,
          },
          { path: 'catalog/equipment-models', element: <EquipmentModelsPage /> },
          { path: 'catalog/equipment-models/:id', element: <EquipmentModelDetailPage /> },
          // 시험법 주소는 그대로 둔다 — 이미 나간 링크가 있고, 옮겨서 얻는 것이 없다.
          { path: 'catalog/test-items', element: <TestItemsCatalogPage /> },
          { path: 'catalog/test-items/:id', element: <TestItemCatalogDetailPage /> },
          { path: 'methods', element: <MethodsPage /> },
          { path: 'methods/:id', element: <MethodDetailPage /> },
          ...stubs,

          // 내 활동
          { path: 'notifications', element: <NotificationsPage /> },
          { path: 'me', element: <ProfilePage /> },

          // 공통
          { path: 'notices', element: <NoticesPage /> },
          { path: 'reference', element: <ReferenceHubPage /> },
          { path: 'graph', element: <GraphPage /> },
          { path: 'vocabulary', element: <VocabularyPage /> },
          { path: 'conditions', element: <ConditionsPage /> },
          { path: 'spec-definitions', element: <SpecDefinitionsPage /> },
          { path: 'attribute-definitions/:target', element: <AttributeDefinitionsPage /> },
          { path: 'audit', element: <AuditPage /> },

          // 관리 (전사)
          { path: 'admin/accounts', element: <AccountsAdminPage /> },
          { path: 'admin/workspaces', element: <WorkspacesAdminPage /> },
          { path: 'admin/vocabulary', element: <VocabularyAdminPage /> },
          { path: 'admin/server', element: <ServerPage /> },
          { path: 'admin/review', element: <ReviewPage /> },
          { path: 'admin/review/:queue', element: <ReviewQueuePage /> },

          // 부서 스코프
          {
            path: 'w/:slug',
            children: [
              { index: true, element: <WorkspaceHomePage /> },
              { path: 'members', element: <MembersPage /> },
            ],
          },

          {
            path: '*',
            element: (
              <Placeholder
                title="존재하지 않는 페이지"
                phase="—"
                description="주소를 확인해 주십시오."
              />
            ),
          },
        ],
      },
    ],
  },
])

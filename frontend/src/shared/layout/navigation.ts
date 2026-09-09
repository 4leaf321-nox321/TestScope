/**
 * 사이드바 메뉴 정의.
 *
 * 메뉴를 컴포넌트에서 분리해 두는 이유: **어떤 화면이 있어야 하는지가 한 곳에
 * 적혀 있어야** 라우터·사이드바·권한이 서로 어긋나지 않는다.
 */

import {
  Bell,
  Boxes,
  Building2,
  ClipboardList,
  Gauge,
  Home,
  ListTree,
  Megaphone,
  Package,
  Ruler,
  ScrollText,
  Search,
  Server,
  SlidersHorizontal,
  Tags,
  UserCog,
  Users,
  Wrench,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

/** 소속 부서를 아직 모를 때 쓰는 임시 slug. 설치 스크립트가 만드는 뿌리 부서다. */
export const DEFAULT_WORKSPACE = 'hq'

/**
 * 누구에게 보이는가.
 *
 * **없으면 누르고 나서 403 을 본다.** 눌러야 권한이 없다는 것을 아는 화면은
 * "할 수 있는 일" 을 알려 주지 못한다.
 *
 * 이것은 **표시**일 뿐 권한이 아니다. 권한은 서버가 판정한다 — 사이드바를 고쳐
 * 우회할 수 있으면 그건 애초에 보안이 아니다.
 */
export type NavAudience = 'everyone' | 'manager' | 'system_admin'

export interface NavItem {
  label: string
  icon: LucideIcon
  /** 고정 경로 */
  to?: string
  /** 부서 스코프 경로 */
  resolve?: (slug: string) => string
  /** NavLink 의 end 옵션 (부모 경로가 자식에도 활성화되지 않게) */
  end?: boolean
  /** 기본은 everyone. */
  audience?: NavAudience
  /** 아직 화면이 없다. 사이드바가 「미구현」 표를 단다 — **자리는 보이되 눌러
   *  보고 알게 하지 않는다.** 화면이 생기면 이 표시를 지운다. */
  pending?: boolean
  /** pending 인 것이 로드맵의 어느 단계에서 들어오는가. */
  phase?: string
  /** 한 줄 설명. 개요 화면과 stub 화면이 같은 말을 하도록 여기 한 번만 적는다. */
  summary?: string
}

export interface NavGroup {
  /** 없으면 제목 없이 항목만 선다. **한 항목짜리 그룹에는 제목을 안 단다** —
   *  제목은 「여기 여럿이 있다」 는 신호라서, 하나뿐인데 달면 거짓말이 된다. */
  title?: string
  items: NavItem[]
  /** 그룹 전체가 안 보이는 조건. 항목이 하나도 안 보이면 제목도 지운다. */
  audience?: NavAudience
}

export const NAV_GROUPS: NavGroup[] = [
  {
    // **제목이 없다.** 홈 하나뿐인데 제목을 달면 「여기 더 있다」 로 읽힌다.
    items: [{ label: '홈', icon: Home, resolve: (s) => `/w/${s}`, end: true }],
  },
  {
    // **동선이 곧 순서다.** 검색으로 답을 얻고(찾기), 그 답이 어디서 오는지
    // 확인하고(장비·시험법), 없으면 채운다. 화면의 차례가 사람이 밟는 차례여야
    // 「다음에 어디로」 를 안 묻는다.
    // **동선이 곧 순서다.** 검색으로 답을 얻고(찾기), 그 답이 어디서 오는지
    // 확인한다(보유 장비). 없으면 채운다.
    title: '시험 역량',
    items: [
      {
        // **이 시스템의 첫 화면이다.** 나머지는 이 한 물음에 답하기 위해 있다:
        // 「그 시험이 가능한 장비가 우리 조직에 있나」.
        label: '역량 검색',
        icon: Search,
        to: '/search',
      },
      {
        // **실물이다.** 카탈로그의 모델을 가리켜 만든 개체 — 자산번호·자리·상태·
        // 교정이 여기 붙는다(ADR 0004).
        label: '보유 장비',
        icon: Wrench,
        to: '/equipment',
      },
      {
        // 역량 자체를 훑는 자리. 장비 상세에서 하나씩 보면 「우리가 무엇을 못
        // 하나」 를 영영 알 수 없다 — 그것이 이 목록의 존재 이유다.
        label: '역량 현황',
        icon: Gauge,
        to: '/capabilities',
        pending: true,
        phase: '2단계',
        summary: '시험 항목 x 부서 표. 빈 칸이 곧 우리가 못 하는 시험이다.',
      },
    ],
  },
  {
    // **정의가 사는 자리.** 위의 '시험 역량' 은 우리가 가진 것이고, 여기는 세상에
    // 있는 것이다 — 제조사가 파는 모델과 기관이 낸 규격.
    //
    // 보유 장비 한 대는 이 둘을 엮은 인스턴스다: 어떤 모델이며 어떤 시험법을
    // 실제로 돌리는가(ADR 0004). 그래서 카탈로그를 채우는 일과 장비를 등록하는
    // 일은 순서가 있고, 메뉴도 그렇게 갈라 둔다.
    //
    // **전사 공용이라 고치는 것은 시스템 관리자다.** 보는 것은 누구나 한다 —
    // 장비를 등록하는 사람이 모델을 골라야 하고, 아직 없는 모델을 「사면 무엇이
    // 되나」 보는 것도 여기다.
    title: '카탈로그',
    items: [
      {
        // **계열이 먼저다.** 사람이 아는 이름은 대개 계열이고(「6800 시리즈」),
        // 기종은 라벨을 봐야 안다. 그리고 무슨 시험이 되는지를 정하는 자리가
        // 계열이라, 카탈로그를 채우는 순서도 이쪽이 먼저다(ADR 0006).
        label: '장비 계열',
        icon: Boxes,
        to: '/catalog/equipment-series',
      },
      {
        // 기종은 **보유 장비가 가리키는 것**이다. 수치가 여기서 갈린다.
        label: '장비 기종',
        icon: Package,
        to: '/catalog/equipment-models',
      },
      {
        // 시험법이 장비 모델 다음이다 — 규격은 그것을 돌릴 장비가 있어야 뜻이
        // 있고, 사람이 먼저 여는 것도 장비 쪽이다.
        label: '시험법·규격',
        icon: ClipboardList,
        to: '/methods',
      },
    ],
  },
  {
    title: '내 활동',
    items: [
      { label: '알림', icon: Bell, to: '/notifications' },
      { label: '내 정보', icon: UserCog, to: '/me' },
    ],
  },
  {
    title: '공통',
    items: [
      { label: '공지', icon: Megaphone, to: '/notices' },
      {
        // **고르는 사람이 목록을 볼 수 있어야 한다.** 이 값을 매일 드롭다운에서
        // 고르는 것은 멤버다 — 못 보면 찾는 값이 없을 때 「아직 없다」 인지
        // 「이름이 다르다」 인지 구별할 수 없다. 고치는 자리는 아래 '관리' 다.
        label: '기준정보',
        icon: Tags,
        to: '/vocabulary',
      },
      {
        // 조건 정의는 기준정보와 **같은 성격**이지만 표가 다르다(값의 목록 대
        // 칸의 계약). 화면 안에서 탭으로 갈리고 주소는 둘로 남는다 — 탭을 감추면
        // 조건 하나를 링크로 가리킬 수 없다.
        label: '시험 조건 정의',
        icon: Ruler,
        to: '/conditions',
      },
      {
        // 조건 바로 아래다. 둘 다 칸의 계약이고 다른 것은 쓰임뿐이라 — 조건은
        // 검색이 묻는 일곱 축, 사양은 사양서의 수백 칸(ADR 0005). 한 화면에
        // 합치면 검색 폼에 외형 치수가 뜬다.
        label: '장비 사양 정의',
        icon: SlidersHorizontal,
        to: '/spec-definitions',
      },
    ],
  },
  {
    // **사슬이 아닌 둘.** 부서 사람과 그 부서에서 무엇이 바뀌었나.
    title: '내 부서',
    audience: 'manager',
    items: [
      { label: '부서 멤버', icon: Users, resolve: (s) => `/w/${s}/members`, audience: 'manager' },
      {
        // **기록만 쌓이고 볼 자리가 없으면 자산이 아니다.** 여기에는 만들기·
        // 고치기·지우기가 없다 — 고칠 수 있으면 감사가 아니다.
        label: '변경 이력',
        icon: ScrollText,
        to: '/audit',
        audience: 'manager',
      },
    ],
  },
  {
    title: '관리',
    audience: 'system_admin',
    items: [
      { label: '계정', icon: UserCog, to: '/admin/accounts', audience: 'system_admin' },
      // **전사 부서 목록이다.** 위 '내 부서' 와 헷갈리지 않게 이름을 가른다 —
      // 이쪽은 부서를 만들고 고치는 자리고, 저쪽은 내 부서의 일이다.
      { label: '부서 정보', icon: Building2, to: '/admin/workspaces', audience: 'system_admin' },
      {
        // 보는 화면이 '공통' 에 따로 있는데 둘 다 「기준정보」 면 관리자는 어느
        // 쪽이 진짜인지 모른다. 이름에 「편집」 을 붙여 가른다.
        label: '기준정보 편집',
        icon: ListTree,
        to: '/admin/vocabulary',
        audience: 'system_admin',
      },
      { label: '서버', icon: Server, to: '/admin/server', audience: 'system_admin' },
    ],
  },
]

export function itemHref(item: NavItem, slug: string): string {
  return item.to ?? item.resolve?.(slug) ?? '/'
}

/** 이 사람에게 보이는가. 서버가 최종 판정을 한다 — 여기는 표시일 뿐이다. */
export function canSee(
  audience: NavAudience | undefined,
  viewer: { isSystemAdmin: boolean; isAnyManager: boolean },
): boolean {
  if (audience === 'system_admin') return viewer.isSystemAdmin
  if (audience === 'manager') return viewer.isSystemAdmin || viewer.isAnyManager
  return true
}

/** 볼 수 있는 것만 남긴 메뉴. **빈 그룹은 제목까지 지운다.** */
export function visibleGroups(viewer: {
  isSystemAdmin: boolean
  isAnyManager: boolean
}): NavGroup[] {
  return NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => canSee(item.audience, viewer)),
  })).filter((group) => canSee(group.audience, viewer) && group.items.length > 0)
}

/** 아직 화면이 없는 항목들. 라우터가 이것으로 stub 경로를 만든다 — **사이드바가
 *  정본이라** 제목·단계·설명을 두 곳에 적지 않는다. */
export function pendingItems(): NavItem[] {
  return NAV_GROUPS.flatMap((group) => group.items).filter((item) => item.pending && item.to)
}

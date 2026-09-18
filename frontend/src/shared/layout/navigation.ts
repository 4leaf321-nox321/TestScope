/**
 * 사이드바 메뉴 정의.
 *
 * 메뉴를 컴포넌트에서 분리해 두는 이유: **어떤 화면이 있어야 하는지가 한 곳에
 * 적혀 있어야** 라우터·사이드바·권한이 서로 어긋나지 않는다.
 */

import {
  Atom,
  Bell,
  Boxes,
  Building2,
  CheckSquare,
  ClipboardList,
  Gauge,
  ListChecks,
  Home,
  Megaphone,
  Package,
  ScrollText,
  Search,
  Server,
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
  /** 아래에 **서버가 정하는 항목들**이 붙는다. 사이드바가 그 목록을 받아 펼치고,
   *  이 항목 자체는 화면이 아니라 접고 펴는 손잡이가 된다. 어떤 목록인지는 이름
   *  하나로 가리키고, 목록을 받는 것과 자식의 경로는 사이드바가 안다. */
  expands?: 'reliability-workspaces'
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
    // **우리가 가진 것.** 보유 장비와 그것으로 되는 시험. 전에는 제목이 「시험 항목」
    // 이었는데, 기준정보 축 이름과 같아서 「여기가 시험 항목 정의인가」 로 읽혔다 —
    // 정의는 카탈로그와 기준정보에 있고, 여기는 **현황**이다.
    //
    // **동선이 곧 순서다.** 우리가 무엇을 할 수 있나(시험)가 맨 위, 그것을 하는
    // 실물(대장)이 다음, 물음이 생겼을 때 여는 찾기가 끝.
    title: '사내 장비·시험 현황',
    items: [
      {
        // 우리 조직이 **어떤 신뢰성 시험을 할 수 있나** — 시험 항목 × 부서 표. 장비
        // 상세에서 하나씩 보면 「우리가 무엇을 못 하나」 를 영영 알 수 없다. 시험 항목의
        // 정의는 카탈로그의 「시험 항목」 이고, 여기는 우리가 가진 것이다.
        //
        // 대장보다 **앞에 둔다**: 이 그룹의 제목이 「시험 현황」 이고, 장비는 시험을
        // 하기 위해 있다 — 목적이 위, 수단이 아래.
        //
        // **「시험 항목」 과 다른 층이다.** 시험 항목은 장비가 할 수 있는 측정(인장·경도·
        // 열충격)이고 전사 공용 정의라 카탈로그에 있다. 신뢰성 시험은 부서가 제품 개발·
        // 검증을 위해 **수행하는 시험**(고온고습 1000h · 열충격 500 cycle)이고, 부서가
        // 등록한다. 시험 항목 하나 이상을 써서 돌고, 그 항목이 장비로 이어진다.
        //
        // **아래에 부서가 선다.** 「부서 정보」 에서 고른 부서마다 그 부서의 신뢰성
        // 시험 화면이 하나씩(`/reliability-tests/<slug>`). 조직도를 통째로 펼치지 않는
        // 이유는 시험을 하는 부서 넷을 찾으려고 서른을 훑게 되기 때문이다. 이 항목 자체를
        // 누르면 **전사 전체 표**(부서를 가로질러 누가 무슨 시험을 하나) — 읽기만이고, 고치는
        // 문은 아래 부서 화면이다.
        label: '신뢰성 시험',
        icon: Gauge,
        to: '/reliability-tests',
        expands: 'reliability-workspaces',
        summary: '부서마다 수행하는 신뢰성 시험을 한 표로. 아래에서 부서를 골라 하나씩 본다.',
      },
      {
        // **실물이다.** 카탈로그의 모델을 가리켜 만든 개체 — 자산번호·자리·상태·
        // 교정이 여기 붙는다(ADR 0004).
        //
        // 찾기보다 **앞에 둔다**: 날마다 여는 것은 대장이고, 찾기는 물음이 생겼을 때
        // 연다. 자주 여는 것이 위에 있어야 손이 짧다.
        label: '보유 장비',
        icon: Wrench,
        to: '/equipment',
      },
      {
        // **이 시스템이 답하려는 물음이다**: 「그 시험이 가능한 장비가 우리 조직에
        // 있나」. 나머지 화면은 이 한 물음에 답하기 위해 있다.
        label: '장비 검색',
        icon: Search,
        to: '/search',
      },
    ],
  },
  {
    // **정의가 사는 자리.** 위는 우리가 가진 것이고, 여기는 세상에 있는 것이다 —
    // 제조사가 파는 모델, 기관이 낸 규격, 그리고 어떤 시험이 어떤 물성을 내는가.
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
        // **사슬의 가운데.** 계열·기종·규격·물성 네 화면이 전부 「→ 시험 항목」 으로 향하는데
        // 시험 항목에서 출발하는 자리가 없었다. 「인장」 하나를 두고 얻는 물성·규격·되는
        // 계열·보유 대수를 한 줄에 — 0 이 곧 공백이다. 사이드바 위쪽의 「신뢰성 시험」
        // (부서가 수행하는 개발·검증 시험)과 다르다: 여기는 장비가 할 수 있는 측정의 정의다.
        label: '시험 항목',
        icon: ListChecks,
        to: '/catalog/test-items',
      },
      {
        // 시험법이 장비 모델 다음이다 — 규격은 그것을 돌릴 장비가 있어야 뜻이
        // 있고, 사람이 먼저 여는 것도 장비 쪽이다.
        label: '시험법·규격',
        icon: ClipboardList,
        to: '/methods',
      },
      {
        // **사슬의 맨 앞.** 사람은 「인장」 이 아니라 「인장강도」 로 묻는다 — 어떤 시험으로
        // 어떤 물성을 얻는지가 여기 적혀야 그 물음이 시험 항목으로 바뀐다(N:M, ADR 0007).
        // 전사 공용 정의라 시험법 옆이 자리다. 부서가 가진 것이 아니다.
        label: '물성 항목',
        icon: Atom,
        to: '/properties',
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
        //
        // **허브다**(2026-09-18). 전에는 이름 사전(축의 값)으로 바로 갔는데, 그러면 계열·기종·
        // 규격 같은 객체는 기준정보가 아닌 것처럼 읽혔다. 이제 객체 종류 전부를 한 표로 보여
        // 주는 화면이 먼저고, 이름 사전은 그 안의 한 층이다.
        label: '기준정보',
        icon: Tags,
        to: '/reference',
      },
      // **정의 화면(시험 항목 검색 조건 · 장비 기종 사양 · 네 속성 정의)은 사이드바에 없다**
      // (2026-09-18). 전부 「기준정보」 안의 문이다 — 객체 종류를 고르면 그 종류의 정의 화면으로
      // 이어지고, 정의 화면은 「← 기준정보」 로 돌아온다. 여섯을 사이드바에 늘어놓으면 「공통」 이
      // 정의 목록이 되고, 기준정보가 무엇인지가 오히려 흐려진다.
      {
        // **후보와 근거를 보고 도메인 전문가가 고르는 자리.** 반입이 못 정한 것(어느 시험의
        // 규격인가 · 무슨 조건을 묻나 …)이 흩어진 화면마다 「미정」 으로 서 있었다.
        label: '검토함',
        icon: CheckSquare,
        to: '/admin/review',
        // **「관리」 가 아니라 「공통」 에 있다** — 의견은 로그인한 누구나 내고(데이터를 안
        // 건드린다), 확정만 시스템 관리자가 한다. 도메인 전문가가 관리자일 이유가 없다.
      },
    ],
  },
  {
    // **사슬이 아닌 둘.** 부서 사람과 그 부서에서 무엇이 바뀌었나.
    title: '내 부서',
    audience: 'manager',
    items: [
      {
        label: '부서 멤버',
        icon: Users,
        resolve: (s) => `/w/${s}/members`,
        audience: 'manager',
      },
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
      {
        label: '계정',
        icon: UserCog,
        to: '/admin/accounts',
        audience: 'system_admin',
      },
      // **전사 부서 목록이다.** 위 '내 부서' 와 헷갈리지 않게 이름을 가른다 —
      // 이쪽은 부서를 만들고 고치는 자리고, 저쪽은 내 부서의 일이다.
      {
        label: '부서 정보',
        icon: Building2,
        to: '/admin/workspaces',
        audience: 'system_admin',
      },
      {
        label: '서버',
        icon: Server,
        to: '/admin/server',
        audience: 'system_admin',
      },
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

/** 부서 하나의 신뢰성 시험 화면. 사이드바의 자식 항목과 라우터가 같은 모양을 쓴다. */
export function reliabilityHref(slug: string): string {
  return `/reliability-tests/${slug}`
}

/** 아직 화면이 없는 항목들. 라우터가 이것으로 stub 경로를 만든다 — **사이드바가
 *  정본이라** 제목·단계·설명을 두 곳에 적지 않는다. */
export function pendingItems(): NavItem[] {
  return NAV_GROUPS.flatMap((group) => group.items).filter((item) => item.pending && item.to)
}

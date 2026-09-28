/**
 * 상단 바 — 사이드바 토글 · 부서 선택 · 검색 · 테마 · 계정 메뉴.
 *
 * 부서 선택기는 **내가 속한 부서만** 보여 준다. 시스템 관리자라도 여기서는 자기
 * 소속만 오간다 — 전사 목록은 부서 관리 화면의 일이다. 두 목적을 한 위젯에
 * 섞으면 "내 부서" 라는 개념이 흐려진다.
 *
 * **이것이 바꾸는 것은 둘뿐이다** — 부서 홈(`/w/:slug`)과 부서 멤버. 장비·신뢰성 시험·
 * 카탈로그는 부서와 무관한 주소를 쓰고 API 에도 부서 맥락이 안 실린다. 그런데 상단에
 * 있으니 「지금 이 부서 안에 있다」 로 읽히기 쉽다(다른 시스템의 맥락 전환기가 그렇다) —
 * 그래서 **무엇이 바뀌는지 적어 둔다.** 목록이 걸러지는 줄 알고 보면 「우리 부서 장비가
 * 왜 이렇게 많지」 가 된다.
 *
 * 소속이 하나뿐이면 **선택기 대신 이름만** 둔다. 고를 것이 없는데 고르는 물건이 있으면
 * 사람은 「뭔가 더 있나」 를 계속 생각한다.
 */

import { useState } from 'react'
import type { FormEvent } from 'react'
import {
  KeyRound,
  List,
  LogOut,
  Moon,
  PanelLeft,
  Search,
  Sun,
  User,
  UserCog,
} from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'

import { useAuth } from '@/shared/auth/AuthContext'
import { Button } from '@/shared/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu'
import { Input } from '@/shared/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import { Separator } from '@/shared/components/ui/separator'
import { ChangePasswordDialog } from '@/shared/layout/ChangePasswordDialog'
import { NotificationBell } from '@/shared/layout/NotificationBell'
import { useLeftPanel } from '@/shared/layout/SidePanel'
import { useTheme } from '@/shared/theme/ThemeProvider'

interface HeaderProps {
  onToggleSidebar: () => void
  workspaceSlug: string
}

export function Header({ onToggleSidebar, workspaceSlug }: HeaderProps) {
  const { theme, toggle } = useTheme()
  const { user, logout } = useAuth()
  const [changingPassword, setChangingPassword] = useState(false)
  const navigate = useNavigate()
  const params = useParams<{ slug?: string }>()
  const [query, setQuery] = useState('')
  // 목록 패널을 쓰는 화면에서만 단추가 뜬다 — 없는 것을 여는 단추가 남아 있으면
  // 눌러도 아무 일이 안 일어나고, 그때 사람은 화면이 고장 난 줄 안다.
  const panel = useLeftPanel()

  // **상단은 넘기기만 한다.** 결과를 여기서 그리면 화면마다 다른 자리에 뜨고,
  // 주소로 공유할 수도 없다 — /search?q= 가 곧 그 검색이다.
  function submitSearch(event: FormEvent) {
    event.preventDefault()
    const wanted = query.trim()
    navigate(wanted ? `/search?q=${encodeURIComponent(wanted)}` : '/search')
  }

  const memberships = user?.memberships ?? []
  const current = memberships.find((one) => one.slug === workspaceSlug)

  async function signOut() {
    await logout()
    navigate('/login', { replace: true })
  }

  function switchTo(slug: string) {
    // 부서 스코프 화면에 있으면 같은 화면의 다른 부서로, 아니면 그 부서 홈으로.
    const suffix = params.slug ? window.location.pathname.split(`/w/${params.slug}`)[1] : ''
    navigate(`/w/${slug}${suffix ?? ''}`)
  }

  return (
    <header className="bg-background flex h-14 shrink-0 items-center gap-2 border-b px-3">
      <Button
        variant="ghost"
        size="icon"
        onClick={onToggleSidebar}
        aria-label="사이드바 접기/펼치기"
      >
        <PanelLeft className="size-4" />
      </Button>

      {panel.label && (
        <Button
          variant="ghost"
          size="icon"
          onClick={panel.toggle}
          aria-label={`${panel.label} 목록 접기/펼치기`}
          aria-pressed={panel.open}
        >
          <List className="size-4" />
        </Button>
      )}

      <Separator orientation="vertical" className="mx-1 h-6" />

      {/* **고를 것이 없으면 고르는 물건을 두지 않는다.** 소속이 하나뿐인 사람에게 선택기는
          아무 일도 안 하면서 「뭔가 더 있나」 를 계속 생각하게 한다 — 그때는 이름만 적는다.

          **경로로 보인다.** 소속이 여러 곳이면 같은 이름의 팀이 둘일 수 있고, 이름만
          보여 주면 지금 어느 부서에 있는지 알 수 없다. */}
      {memberships.length > 1 ? (
        <Select value={workspaceSlug} onValueChange={switchTo}>
          <SelectTrigger
            className="h-8 max-w-64 border-0 shadow-none"
            // **무엇이 바뀌는지 적는다.** 상단에 있으니 「지금 이 부서 안에 있다」 로
            // 읽히는데, 실제로 따르는 화면은 둘뿐이다 — 누르기 전에 알아야 한다.
            title="부서 홈과 부서 멤버 화면이 이 부서의 것으로 바뀝니다. 장비·시험 목록은 부서와 무관하게 전부 보입니다."
            aria-label="부서 홈·멤버를 볼 부서"
          >
            <SelectValue placeholder={workspaceSlug} />
          </SelectTrigger>
          <SelectContent>
            <p className="text-muted-foreground px-2 py-1.5 text-xs">
              부서 홈·멤버 화면이 바뀝니다
            </p>
            {memberships.map((one) => (
              <SelectItem key={one.slug} value={one.slug}>
                {one.path}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : memberships.length === 1 ? (
        <span className="max-w-64 truncate text-sm" title={memberships[0].path}>
          {memberships[0].path}
        </span>
      ) : (
        <span className="text-muted-foreground text-sm">소속된 부서가 없습니다</span>
      )}

      {current?.role === 'manager' && (
        <span className="text-muted-foreground text-xs">부서 관리자</span>
      )}

      <div className="flex-1" />

      {/* **한 칸으로 무엇이든 찾는다.** Enter 로 장비 찾기 화면에 넘긴다 —
          결과를 좁은 드롭다운에 미리 떨구면 무엇을 찾았는지 안 보인다. */}
      <form onSubmit={submitSearch} className="relative mr-1 hidden sm:block">
        <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-2 size-4 -translate-y-1/2" />
        <Input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="장비·시험법 검색"
          aria-label="장비·시험법 검색"
          className="h-8 w-44 pl-8 lg:w-64"
        />
      </form>

      <NotificationBell />

      <Button variant="ghost" size="icon" onClick={toggle} aria-label="테마 전환">
        {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
      </Button>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm">
            <User className="size-4" />
            {user?.display_name ?? '계정'}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel className="font-normal">
            <p className="text-sm font-medium">{user?.display_name}</p>
            <p className="text-muted-foreground truncate text-xs">{user?.email}</p>
            {user?.is_system_admin && (
              <p className="text-muted-foreground mt-1 text-xs">시스템 관리자</p>
            )}
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => navigate('/me')}>
            <UserCog className="size-4" />내 정보
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => setChangingPassword(true)}>
            <KeyRound className="size-4" />
            비밀번호 변경
          </DropdownMenuItem>
          <DropdownMenuItem onClick={signOut}>
            <LogOut className="size-4" />
            로그아웃
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* 바꾸고 나면 서버가 세션을 전부 끊는다 — 클라이언트 상태도 맞춘다. */}
      <ChangePasswordDialog
        open={changingPassword}
        onClose={() => setChangingPassword(false)}
        onChanged={async () => {
          setChangingPassword(false)
          await logout()
        }}
      />
    </header>
  )
}

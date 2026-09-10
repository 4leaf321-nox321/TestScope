/**
 * 화면 제목 줄. 제목·설명·오른쪽 액션의 배치를 화면마다 다시 정하지 않는다.
 *
 * **스크롤에서 빠진다.** 목록을 내려 보다가 「등록」 을 누르려고 맨 위까지 되감는
 * 일이 없어야 하고, 긴 표에서는 지금 보는 것이 무슨 화면인지도 함께 사라진다.
 * 그래서 이 줄은 본문 스크롤 통(`AppShell` 의 `main`) 꼭대기에 붙어 있고, **그
 * 아래부터** 스크롤한다.
 *
 * 좌우로 `-mx-6` 만큼 넓히는 이유: 본문 상자의 좌우 여백만큼 배경이 모자라면, 밑으로
 * 지나가는 표가 머리글 양옆으로 비어져 보인다.
 */

import type { ReactNode } from 'react'
import { ChevronLeft } from 'lucide-react'
import { Link } from 'react-router-dom'

interface PageHeaderProps {
  title: ReactNode
  /** 제목 아래 한 줄. 이 화면이 무엇에 답하는지 적는다. */
  description?: ReactNode
  actions?: ReactNode
  /**
   * 돌아갈 곳. **브라우저 뒤로가기에 기대지 않는다.**
   *
   * 링크를 새 탭으로 열었거나 주소를 붙여 넣었으면 히스토리가 아예 없다. 어디로
   * 가는지 **이름이 적힌 링크**를 두면 어떤 경로로 들어왔든 같은 곳으로 간다.
   */
  back?: { to: string; label: string }
}

export function PageHeader({ title, description, actions, back }: PageHeaderProps) {
  return (
    <div className="bg-background sticky top-0 z-20 -mx-6 mb-6 border-b px-6 pt-6 pb-4">
      {back && (
        <Link
          to={back.to}
          className="text-muted-foreground hover:text-foreground mb-2 -ml-1 inline-flex items-center gap-1 text-sm"
        >
          <ChevronLeft className="size-4" />
          {back.label}
        </Link>
      )}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
          {description && <p className="text-muted-foreground mt-1 text-sm">{description}</p>}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
    </div>
  )
}

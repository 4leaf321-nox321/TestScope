/** 화면 제목 줄. 제목·설명·오른쪽 액션의 배치를 화면마다 다시 정하지 않는다. */

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
    <div className="mb-6">
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

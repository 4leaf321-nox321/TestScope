/**
 * 카드의 목차 — **스물두 칸을 세로로 늘어놓으면 어디까지 읽었는지 사람이 잃는다.**
 *
 * 왼쪽에 갈래와 칸을 순서대로 세우고, 누르면 그 자리로 간다. 보기 창과 수정 창이 같은
 * 것을 쓴다 — 두 벌로 두면 칸이 하나 늘 때 한쪽만 고쳐지고, 그때부터 같은 카드가 자리에
 * 따라 다른 순서로 읽힌다.
 *
 * **값이 있는 칸에 표를 단다.** 목차가 스물둘을 똑같이 보여 주면 「무엇이 채워졌나」 를
 * 다시 본문에서 찾아야 한다 — 그 한 가지가 목차를 두는 이유의 절반이다.
 */

import type { ReactNode } from 'react'

export interface OutlineItem {
  /** 스크롤할 자리의 id(`anchorOf`). */
  anchor: string
  label: string
  /** 아래 딸린 칸들. 갈래에만 있다. */
  children?: { anchor: string; label: string; filled?: boolean }[]
}

/** 그 자리로 굴린다. **모달 안에서도 된다** — 가장 가까운 굴림 상자를 브라우저가 찾는다. */
function goTo(anchor: string) {
  const target = document.getElementById(anchor)
  if (!target) return
  target.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

export function CardOutline({
  items,
  title = '목차',
  footer,
}: {
  items: OutlineItem[]
  title?: string
  /** 목차 아래에 덧붙일 것 — 후보 띠 같은 것. */
  footer?: ReactNode
}) {
  if (items.length === 0) return null
  return (
    // **붙박이다.** 목차가 본문과 함께 굴러가면 긴 카드에서 정작 필요할 때 화면 밖에 있다.
    <nav
      aria-label={title}
      className="sticky top-0 hidden h-fit w-52 shrink-0 self-start lg:block"
    >
      <p className="text-muted-foreground mb-2 text-xs font-medium">{title}</p>
      <ol className="space-y-1 text-sm">
        {items.map((one) => (
          <li key={one.anchor}>
            <button
              type="button"
              className="hover:text-foreground text-muted-foreground w-full text-left font-medium"
              onClick={() => goTo(one.anchor)}
            >
              {one.label}
            </button>
            {one.children && one.children.length > 0 && (
              <ol className="mt-0.5 space-y-0.5 border-l pl-2.5">
                {one.children.map((kid) => (
                  <li key={kid.anchor}>
                    <button
                      type="button"
                      className={
                        kid.filled
                          ? 'hover:text-foreground w-full text-left text-xs'
                          : 'text-muted-foreground/60 hover:text-foreground w-full text-left text-xs'
                      }
                      onClick={() => goTo(kid.anchor)}
                      // **채워진 칸을 굵게 하지 않는다** — 안 채운 칸을 흐리게 한다.
                      // 굵게 하면 「중요한 칸」 으로 읽히는데, 그런 뜻이 아니다.
                      title={kid.filled ? undefined : '아직 안 적음'}
                    >
                      {kid.label}
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </li>
        ))}
      </ol>
      {footer && <div className="mt-3">{footer}</div>}
    </nav>
  )
}

import * as React from "react"

import { cn } from "@/shared/lib/utils"

/**
 * `viewport` — **가로 스크롤 막대에 닿을 수 있게 한다.**
 *
 * 기본 꼴은 표 전체가 세로로 늘어나고 가로 막대는 그 **맨 아래**에 붙는다. 줄이 쉰이고
 * 열이 스물이면, 오른쪽 열을 보려고 먼저 세로로 끝까지 내려가서 막대를 잡고, 옆으로 민
 * 다음, 다시 위로 올라와야 한다. 실제로 그렇게 썼다(2026-09-30).
 *
 * 켜면 표를 **화면 높이에 가둔다**: 두 막대가 늘 제자리에 있고, 머리글이 위에 붙어 있어
 * 스무 번째 열이 무슨 열인지 알 수 있다. 열이 몇 개 안 되는 표에는 안 켠다 — 가둘 이유가
 * 없는 표를 가두면 아래에 빈 공간만 생긴다.
 *
 * 높이는 **위아래를 다 재서** 정한다(`calc(100vh - 20rem)` 같은 어림도, 꼬리 몇 픽셀
 * 같은 어림도 아니다). 표 위에 오는 것은 화면마다 다르고 — 제목·설명·거르기 칩·대량 처리
 * 줄 — 아래에 오는 것도 다르다(쪽 넘기기 줄이 있을 때와 없을 때). 어림잡으면 둘 중 하나가
 * 난다: 모자라면 표 바닥이 화면 밖으로 내려가 **고치려던 문제가 돌아오고**, 남으면 표
 * 아래가 빈 채로 남는다. 그래서 「본문 바닥 − 표 시작점 − 표 아래에 이미 있는 것」 을
 * 그대로 잰다.
 *
 * **「아래에 있는 것」 은 표의 높이와 무관하게 잰다.** 스크롤 높이로 재 봤더니 두 번
 * 틀렸다(2026-09-30): 줄이 오기 전(목록이 비어 있을 때) 한 번 재고 나면 본문 크기가 안
 * 바뀌어 다시 잴 일이 없었고, 그래서 표가 바닥값 240px 에 갇혔다 — 쪽 넘기기 단추 아래가
 * 통째로 비었다. 지금은 조상마다 「부모 바닥 − 내 바닥」 을 더한다: 내가 커지면 부모도 같이
 * 커지므로 이 값은 **처음부터 끝까지 같다.** 줄이 없어도 맞는 답이 나온다.
 */
/** 아무리 좁아도 이만큼은 — 이보다 작으면 표가 아니라 창이 된다. */
const VIEWPORT_FLOOR = 240

/** 표를 감싼 **스크롤 칸.** 없으면 창 자체가 스크롤한다. */
function scrollerOf(node: HTMLElement): HTMLElement | null {
  for (let at = node.parentElement; at; at = at.parentElement) {
    const how = getComputedStyle(at).overflowY
    if (how === "auto" || how === "scroll") return at
  }
  return null
}

/**
 * 표 **아래**에 이미 있는 것 — 쪽 넘기기 줄 · 그 사이 간격 · 본문 아래 여백.
 *
 * 조상마다 「부모 바닥 − 내 바닥」 을 더한다. 뒤따르는 형제와 그 사이 간격, 부모의 아래
 * 여백이 거기 다 든다. **표가 커지면 부모도 같이 커지므로 이 값은 안 변한다** — 그래서
 * 표 높이를 정하는 데 쓸 수 있고, 재고 또 재는 되먹임도 없다.
 */
function spaceBelow(node: HTMLElement, scroller: HTMLElement | null): number {
  let total = 0
  let at: HTMLElement = node
  while (at.parentElement && at.parentElement !== scroller) {
    const parent = at.parentElement
    total += parent.getBoundingClientRect().bottom - at.getBoundingClientRect().bottom
    at = parent
  }
  if (scroller) total += parseFloat(getComputedStyle(scroller).paddingBottom) || 0
  return Math.max(0, total)
}

function Table({
  className,
  viewport = false,
  ...props
}: React.ComponentProps<"table"> & { viewport?: boolean }) {
  const box = React.useRef<HTMLDivElement>(null)
  const [tall, setTall] = React.useState<number | null>(null)

  React.useLayoutEffect(() => {
    const node = box.current
    if (!viewport || !node) return
    const scroller = scrollerOf(node)
    const measure = () => {
      const bottom = scroller
        ? scroller.getBoundingClientRect().bottom
        : window.innerHeight
      const room = bottom - node.getBoundingClientRect().top - spaceBelow(node, scroller)
      setTall(Math.max(VIEWPORT_FLOOR, Math.round(room)))
    }
    measure()
    window.addEventListener("resize", measure)
    const watch =
      typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure)
    // **속 표를 본다** — 줄이 늦게 오면(목록은 비어서 그려진다) 가둔 칸의 크기는 안 바뀌고
    // 속 표만 자란다. 이것을 안 보면 처음 잰 값에 갇힌다.
    if (node.firstElementChild) watch?.observe(node.firstElementChild)
    // 위아래가 자라면(칩 한 줄, 진단 한 줄, 쪽 넘기기 줄) 시작점과 아래가 함께 바뀐다.
    if (node.parentElement) watch?.observe(node.parentElement)
    if (scroller) watch?.observe(scroller)
    return () => {
      window.removeEventListener("resize", measure)
      watch?.disconnect()
    }
  }, [viewport])

  return (
    <div
      ref={box}
      data-slot="table-container"
      style={tall === null ? undefined : { maxHeight: tall }}
      className={cn(
        "relative w-full overflow-x-auto",
        viewport &&
          "overflow-y-auto rounded-md border" +
            // 머리글은 `thead` 째로 붙인다 — `th` 만 붙이면 줄의 아래 선이 제자리에
            // 남아, 스크롤할 때 선 하나가 표 한가운데를 가로지른다.
            " [&>table>thead]:bg-background [&>table>thead]:sticky [&>table>thead]:top-0 [&>table>thead]:z-20"
      )}
    >
      <table
        data-slot="table"
        className={cn("w-full caption-bottom text-sm", className)}
        {...props}
      />
    </div>
  )
}

function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return (
    <thead
      data-slot="table-header"
      className={cn("[&_tr]:border-b", className)}
      {...props}
    />
  )
}

function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return (
    <tbody
      data-slot="table-body"
      className={cn("[&_tr:last-child]:border-0", className)}
      {...props}
    />
  )
}

function TableFooter({ className, ...props }: React.ComponentProps<"tfoot">) {
  return (
    <tfoot
      data-slot="table-footer"
      className={cn(
        "border-t bg-muted/50 font-medium [&>tr]:last:border-b-0",
        className
      )}
      {...props}
    />
  )
}

function TableRow({ className, ...props }: React.ComponentProps<"tr">) {
  return (
    <tr
      data-slot="table-row"
      className={cn(
        "border-b transition-colors hover:bg-muted/50 has-aria-expanded:bg-muted/50 data-[state=selected]:bg-muted",
        className
      )}
      {...props}
    />
  )
}

function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return (
    <th
      data-slot="table-head"
      className={cn(
        "h-10 px-2 text-left align-middle font-medium whitespace-nowrap text-foreground [&:has([role=checkbox])]:pr-0",
        className
      )}
      {...props}
    />
  )
}

function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return (
    <td
      data-slot="table-cell"
      className={cn(
        "p-2 align-middle whitespace-nowrap [&:has([role=checkbox])]:pr-0",
        className
      )}
      {...props}
    />
  )
}

function TableCaption({
  className,
  ...props
}: React.ComponentProps<"caption">) {
  return (
    <caption
      data-slot="table-caption"
      className={cn("mt-4 text-sm text-muted-foreground", className)}
      {...props}
    />
  )
}

export {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
  TableCaption,
}

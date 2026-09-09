"use client"

import * as React from "react"
import { Dialog as DialogPrimitive } from "radix-ui"

import { cn } from "@/shared/lib/utils"
import { Button } from "@/shared/components/ui/button"
import { XIcon } from "lucide-react"

function Dialog({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Root>) {
  return <DialogPrimitive.Root data-slot="dialog" {...props} />
}

function DialogTrigger({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Trigger>) {
  return <DialogPrimitive.Trigger data-slot="dialog-trigger" {...props} />
}

function DialogPortal({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Portal>) {
  return <DialogPrimitive.Portal data-slot="dialog-portal" {...props} />
}

function DialogClose({
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Close>) {
  return <DialogPrimitive.Close data-slot="dialog-close" {...props} />
}

function DialogOverlay({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Overlay>) {
  return (
    <DialogPrimitive.Overlay
      data-slot="dialog-overlay"
      className={cn(
        "fixed inset-0 isolate z-50 bg-black/10 duration-100 supports-backdrop-filter:backdrop-blur-xs data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0",
        className
      )}
      {...props}
    />
  )
}

/**
 * 모달을 **머리글을 잡아 옮긴다.**
 *
 * 옮길 수 있어야 하는 이유: 모달이 가린 자리를 봐야 채울 수 있는 칸이 있다. 장비를
 * 등록하면서 뒤의 목록에서 자산번호를 확인하는 것이 그렇다 — 지금은 닫았다 다시
 * 열어야 하고, 그러면 적던 것이 사라진다.
 *
 * ## transform 이 아니라 여백으로 옮긴다
 *
 * 모달은 `left-1/2 -translate-x-1/2` 로 가운데 선다. 그 위에 인라인 transform 을
 * 얹으면 **여는 애니메이션(zoom-in)이 죽는다** — 인라인이 클래스를 이긴다. 여백은
 * transform 과 다른 축이라 둘이 안 부딪친다.
 *
 * ## 화면 밖으로는 못 나간다
 *
 * 끝까지 밀어 놓으면 되돌릴 방법이 없다 — 모달은 스크롤로 따라갈 수 없다.
 */
function useDragOffset(): {
  offset: { x: number; y: number }
  onPointerDown: (event: React.PointerEvent) => void
  dragging: boolean
} {
  const [offset, setOffset] = React.useState({ x: 0, y: 0 })
  const [dragging, setDragging] = React.useState(false)
  const from = React.useRef({ x: 0, y: 0, ox: 0, oy: 0 })

  const onPointerDown = React.useCallback(
    (event: React.PointerEvent) => {
      // 머리글 안의 단추·입력에서 시작한 것은 드래그가 아니다 — 닫기 단추를
      // 누르려다 모달이 따라오면 그 단추는 못 누른다.
      if ((event.target as HTMLElement).closest("button, a, input, textarea, select")) {
        return
      }
      if (event.button !== 0) return
      event.preventDefault()
      from.current = { x: event.clientX, y: event.clientY, ox: offset.x, oy: offset.y }
      setDragging(true)
    },
    [offset.x, offset.y],
  )

  React.useEffect(() => {
    if (!dragging) return
    function move(event: PointerEvent) {
      const next = {
        x: from.current.ox + event.clientX - from.current.x,
        y: from.current.oy + event.clientY - from.current.y,
      }
      // **화면 안에 머리글이 남게 한다.** 절반쯤은 나가도 되지만 붙잡을 곳은 남아야 한다.
      const room = { x: window.innerWidth / 2, y: window.innerHeight / 2 }
      setOffset({
        x: Math.max(-room.x, Math.min(room.x, next.x)),
        y: Math.max(-room.y + 40, Math.min(room.y - 40, next.y)),
      })
    }
    function stop() {
      setDragging(false)
    }
    window.addEventListener("pointermove", move)
    window.addEventListener("pointerup", stop)
    window.addEventListener("pointercancel", stop)
    return () => {
      window.removeEventListener("pointermove", move)
      window.removeEventListener("pointerup", stop)
      window.removeEventListener("pointercancel", stop)
    }
  }, [dragging])

  return { offset, onPointerDown, dragging }
}

/**
 * 기본 폭은 **512px(`lg`)** 이다. 전에는 384px(`sm`) 이었는데, 그 안에 2열·3열
 * 폼이 들어가 있었다 — 시편 추가는 「실측 두께 (mm)」 같은 라벨 셋을 **각 110px**
 * 칸에 욱여넣었고, 라벨이 칸보다 길었다.
 *
 * 384px 로 두면 **아무것도 안 적은 모달이 제일 좁아진다.** 폼이 대부분인데
 * 기본값이 확인창 크기였던 셈이다. 확인창은 짧은 문장 하나와 단추 둘이라
 * 좁아야 맞고, 그건 **그쪽이 `sm:max-w-sm` 을 적는 것**이 옳다.
 *
 * 내용에 따라 넓히는 것은 자유다(2열은 `xl`, 3열이나 표는 `2xl` 이상). 다만
 * **좁히려면 이유가 있어야 한다** — 기본값이 폼에 맞춰져 있으므로.
 */
function DialogContent({
  className,
  children,
  showCloseButton = true,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Content> & {
  showCloseButton?: boolean
}) {
  const drag = useDragOffset()
  const pinned = usePinnedLayout(children, drag.onPointerDown)
  return (
    <DialogPortal>
      <DialogOverlay />
      <DialogPrimitive.Content
        data-slot="dialog-content"
        className={cn(
          // **키가 화면을 넘으면 가운데만 굴린다.** 안 넣으면 모달이 화면
          // 밖으로 자라고 **아래쪽 버튼을 누를 방법이 사라진다** — 기준정보에서
          // 값을 여러 개 적으면 '추가' 버튼이 그렇게 됐다.
          //
          // 바깥을 통째로 굴리지 않는다. 그러면 **확인·취소가 내용과 함께
          // 위로 사라진다** — 누르려면 끝까지 굴려야 하고, 긴 모달일수록
          // 그 거리가 멀다. 머리글과 바닥글은 붙박이고 가운데만 움직인다.
          //
          // 여기(프리미티브)에 두는 이유: 모달마다 적게 하면 새 모달을 만들
          // 때마다 잊는다. 실제로 21개 중 13개가 빠져 있었고, 빠진 것은
          // **내용이 길어지기 전까지 안 보인다.**
          "fixed top-1/2 left-1/2 z-50 flex max-h-[85vh] w-full max-w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 flex-col gap-4 overflow-hidden rounded-xl bg-popover p-4 text-sm text-popover-foreground ring-1 ring-foreground/10 duration-100 outline-none sm:max-w-lg data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",
          className
        )}
        // **transform 이 아니라 여백으로 옮긴다.** 인라인 transform 은 여는
        // 애니메이션(zoom-in)을 덮어 죽인다 — 여백은 다른 축이라 안 부딪친다.
        style={{
          marginLeft: drag.offset.x,
          marginTop: drag.offset.y,
          ...(drag.dragging ? { userSelect: "none" } : {}),
          ...props.style,
        }}
        {...props}
      >
        {pinned}
        {showCloseButton && (
          <DialogPrimitive.Close data-slot="dialog-close" asChild>
            <Button
              variant="ghost"
              className="absolute top-2 right-2"
              size="icon-sm"
            >
              <XIcon
              />
              <span className="sr-only">Close</span>
            </Button>
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Content>
    </DialogPortal>
  )
}

/**
 * 머리글·바닥글은 붙박이로 두고 **가운데만 굴린다.** 머리글은 옮기는 손잡이가 된다.
 *
 * ## 왜 감싸 주는가 — 각 모달이 적게 하지 않고
 *
 * 굴릴 영역을 모달마다 손으로 감싸게 하면 **새 모달을 만들 때마다 잊는다.**
 * 스크롤 자체가 그렇게 빠져 있었다(21개 중 13개). 같은 실수를 한 겹 안쪽에서
 * 되풀이할 이유가 없다.
 *
 * ## 폼 한 겹 안을 들여다본다
 *
 * 대부분의 등록 모달은 `<form>` 으로 통째로 감싼다. 직접 자식만 보면 그런 모달에는
 * **머리글도 바닥글도 없는 것으로 보이고**, 붙박이도 드래그도 조용히 안 걸린다 —
 * 그리고 안 걸린다는 사실은 내용이 길어지기 전까지 안 보인다(실측: 등록 모달 셋이
 * 전부 그랬다). 감싼 것을 다시 만들어 주므로 `onSubmit` 은 그대로 산다.
 *
 * ## 바닥글이 없으면 아무 일도 안 한다
 *
 * `DialogFooter` 를 안 쓰는 모달이 있다. 그런 모달은 내용 전체가 굴러가고, 그것은
 * 이 함수가 없을 때와 같다 — **못 쓰게 만들지 않는다.**
 */
function usePinnedLayout(
  children: React.ReactNode,
  onPointerDown?: (event: React.PointerEvent) => void
): React.ReactNode {
  /** 조각(`<>…</>`)을 펼친다. **안 펼치면 그 안의 머리글이 안 보이고**, 붙박이도
   *  드래그도 조용히 안 걸린다 — 안 걸린다는 사실은 내용이 길어지기 전까지 안 보인다. */
  function flatten(nodes: React.ReactNode): React.ReactNode[] {
    return React.Children.toArray(nodes).flatMap((one) =>
      React.isValidElement<{ children?: React.ReactNode }>(one) &&
      one.type === React.Fragment
        ? flatten(one.props.children)
        : [one]
    )
  }

  function split(items: React.ReactNode[]) {
    const head = items.filter(
      (one) => React.isValidElement(one) && one.type === DialogHeader
    )
    const foot = items.filter(
      (one) => React.isValidElement(one) && one.type === DialogFooter
    )
    return {
      head,
      foot,
      body: items.filter((one) => !head.includes(one) && !foot.includes(one)),
    }
  }

  function build(parts: ReturnType<typeof split>) {
    // 머리글이 손잡이가 된다. **모달마다 적게 하지 않는다** — 새 모달을 만들 때마다
    // 잊고, 잊은 모달만 안 움직이면 사람은 그것을 버그로 읽는다.
    const handle = parts.head.map((one) =>
      React.isValidElement<React.ComponentProps<"div">>(one)
        ? React.cloneElement(one, {
            onPointerDown,
            className: cn("cursor-move touch-none select-none", one.props.className),
          })
        : one
    )
    return (
      <>
        {handle}
        {/* `-mx-4 px-4` 는 굴리는 영역이 모달의 좌우 여백까지 쓰게 한다 —
            안 그러면 스크롤바가 안쪽으로 들어와 내용과 겹쳐 보인다. */}
        <div className="-mx-4 flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4">
          {parts.body}
        </div>
        {parts.foot}
      </>
    )
  }

  const items = flatten(children)
  const direct = split(items)
  if (direct.head.length || direct.foot.length) return build(direct)

  const only = items.length === 1 && React.isValidElement(items[0]) ? items[0] : null
  if (only) {
    const wrapper = only as React.ReactElement<{ children?: React.ReactNode }>
    const inner = split(flatten(wrapper.props.children))
    if (inner.head.length || inner.foot.length) {
      // 감싼 것을 그대로 다시 만든다 — `<form>` 이 사라지면 엔터로 저장이 안 된다.
      return React.cloneElement(wrapper, undefined, build(inner))
    }
  }
  return build(direct)
}

function DialogHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="dialog-header"
      className={cn("flex flex-col gap-2", className)}
      {...props}
    />
  )
}

function DialogFooter({
  className,
  showCloseButton = false,
  children,
  ...props
}: React.ComponentProps<"div"> & {
  showCloseButton?: boolean
}) {
  return (
    <div
      data-slot="dialog-footer"
      className={cn(
        "-mx-4 -mb-4 flex flex-col-reverse gap-2 rounded-b-xl border-t bg-muted/50 p-4 sm:flex-row sm:justify-end",
        className
      )}
      {...props}
    >
      {children}
      {showCloseButton && (
        <DialogPrimitive.Close asChild>
          <Button variant="outline">Close</Button>
        </DialogPrimitive.Close>
      )}
    </div>
  )
}

function DialogTitle({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title
      data-slot="dialog-title"
      className={cn(
        "font-heading text-base leading-none font-medium",
        className
      )}
      {...props}
    />
  )
}

function DialogDescription({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description
      data-slot="dialog-description"
      className={cn(
        "text-sm text-muted-foreground *:[a]:underline *:[a]:underline-offset-3 *:[a]:hover:text-foreground",
        className
      )}
      {...props}
    />
  )
}

export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
}

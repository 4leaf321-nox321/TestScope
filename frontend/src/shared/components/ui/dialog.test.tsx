/**
 * 모달을 **머리글로 잡아 옮긴다.**
 *
 * 옮길 수 있어야 하는 이유: 모달이 가린 자리를 봐야 채울 수 있는 칸이 있다.
 * 여기서 지키는 것 셋 — 옮겨진다 · 화면 밖으로 안 나간다 · 단추에서는 안 끌린다.
 */

import { describe, expect, it } from 'vitest'
import { act, render, screen } from '@testing-library/react'

import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
import { Button } from '@/shared/components/ui/button'

/** 등록 모달은 대부분 `<form>` 으로 통째로 감싼다. **그 안을 들여다봐야** 머리글이
 *  손잡이가 되고 바닥글이 붙박이가 된다 — 안 그러면 셋 다 조용히 안 걸린다. */
function open(wrap: boolean = false) {
  const inside = (
    <>
      <DialogHeader>
        <DialogTitle>옮길 수 있는 모달</DialogTitle>
        <Button>머리글 안 단추</Button>
      </DialogHeader>
      <p>본문</p>
      <DialogFooter>
        <Button>확인</Button>
      </DialogFooter>
    </>
  )
  render(
    <Dialog open>
      <DialogContent>{wrap ? <form>{inside}</form> : inside}</DialogContent>
    </Dialog>,
  )
  const content = document.querySelector('[data-slot="dialog-content"]') as HTMLElement
  const header = document.querySelector('[data-slot="dialog-header"]') as HTMLElement
  return { content, header }
}

function drag(target: HTMLElement, from: [number, number], to: [number, number]) {
  // **누른 뒤 한 번 흘려보내야 한다.** pointermove 를 듣는 자리는 「끄는 중」 상태가
  // 그려진 뒤에 붙는다 — 브라우저에서는 손이 움직이는 사이에 그것이 끝나지만,
  // 시험은 같은 순간에 둘을 던지므로 사이를 비워 줘야 한다.
  act(() => {
    target.dispatchEvent(
      new PointerEvent('pointerdown', {
        bubbles: true,
        button: 0,
        clientX: from[0],
        clientY: from[1],
      }),
    )
  })
  act(() => {
    window.dispatchEvent(
      new PointerEvent('pointermove', { bubbles: true, clientX: to[0], clientY: to[1] }),
    )
  })
  act(() => {
    window.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }))
  })
}

describe('모달 옮기기', () => {
  it('머리글을 끌면 그만큼 옮겨진다', () => {
    const { content, header } = open()
    expect(content.style.marginLeft).toBe('0px')

    drag(header, [100, 100], [180, 140])

    // **transform 이 아니라 여백으로 옮긴다** — 인라인 transform 은 여는
    // 애니메이션을 덮어 죽인다.
    expect(content.style.marginLeft).toBe('80px')
    expect(content.style.marginTop).toBe('40px')
  })

  it('화면 밖으로는 못 나간다', () => {
    const { content, header } = open()
    // 끝까지 밀어 놓으면 되돌릴 방법이 없다 — 모달은 스크롤로 따라갈 수 없다.
    drag(header, [0, 0], [100000, 100000])

    const x = Number.parseFloat(content.style.marginLeft)
    const y = Number.parseFloat(content.style.marginTop)
    expect(x).toBeLessThanOrEqual(window.innerWidth / 2)
    expect(y).toBeLessThanOrEqual(window.innerHeight / 2)
  })

  it('폼으로 감싼 모달도 머리글로 옮겨진다', () => {
    // 등록 모달은 대부분 `<form>` 으로 감싼다. 직접 자식만 보면 그런 모달에는
    // 머리글이 없는 것으로 보이고, 붙박이도 드래그도 조용히 안 걸린다.
    const { content, header } = open(true)
    expect(content.querySelector('form')).not.toBeNull()

    drag(header, [0, 0], [60, 30])
    expect(content.style.marginLeft).toBe('60px')
    expect(content.style.marginTop).toBe('30px')
  })

  it('머리글 안 단추에서는 안 끌린다', () => {
    const { content } = open()
    // 닫기 단추를 누르려다 모달이 따라오면 그 단추는 못 누른다.
    drag(screen.getByRole('button', { name: '머리글 안 단추' }), [10, 10], [90, 90])
    expect(content.style.marginLeft).toBe('0px')
  })
})

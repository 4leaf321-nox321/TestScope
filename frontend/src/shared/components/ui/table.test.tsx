/**
 * 표를 **화면에 딱 맞게 가둔다** — 가로 스크롤 막대에 닿을 수 있게, 그리고 아래를 안 남기고.
 *
 * 열이 스무 개인 표에서, 기본 꼴은 가로 막대가 표 **맨 아래**에 붙는다: 오른쪽 열을 보려면
 * 먼저 세로로 끝까지 내려가 막대를 잡고, 옆으로 민 다음, 다시 올라와야 한다.
 *
 * 여기서 지키는 것:
 *
 * 1. `viewport` 를 켠 표만 가둔다 — 짧은 표까지 가두면 아래에 빈 공간만 생긴다.
 * 2. 높이는 **위아래를 다 재서** 정한다. 어림잡으면 둘 중 하나가 난다: 모자라면 표 바닥이
 *    화면 밖으로 내려가 고치려던 문제가 돌아오고, 남으면 **표 아래가 빈 채로 남는다.**
 *    두 번째가 두 번 났다 — 꼬리를 96px 로 어림잡았을 때, 그리고 스크롤 높이로 쟀을 때
 *    (목록이 비어 있는 동안 재고 나면 다시 잴 일이 없어 240px 에 갇혔다).
 * 3. 표 아래에 있는 것이 줄면(쪽 넘기기 줄이 없는 사업부) 그만큼 표가 **더 커진다.**
 * 4. 창이 아무리 좁아도 바닥값 아래로는 안 줄인다.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, render } from '@testing-library/react'

import { Table, TableBody, TableCell, TableRow } from '@/shared/components/ui/table'

/** jsdom 에는 배치가 없다 — 잴 자리를 `data-rect` 로 직접 준다. */
function rects() {
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (
    this: HTMLElement,
  ) {
    const said = this.dataset.rect
    const box = said
      ? (JSON.parse(said) as { top: number; bottom: number })
      : { top: 0, bottom: 0 }
    return {
      ...box,
      left: 0,
      right: 0,
      width: 0,
      height: 0,
      x: 0,
      y: box.top,
      toJSON: () => ({}),
    }
  })
}

interface Scene {
  /** 스크롤 칸(본문)의 위·아래 — 머리줄 아래부터 창 바닥까지. */
  frame?: { top: number; bottom: number }
  /** 표가 시작하는 자리와, 안 가뒀을 때의 끝. */
  table: { top: number; bottom: number }
  /** 표를 감싼 쪽의 바닥 — **표 아래에 무엇이 얼마나 있는지**가 이 차이에서 나온다. */
  page: number
}

function show(viewport: boolean, scene: Scene) {
  rects()
  const view = render(
    <div data-testid="scroller" style={{ overflowY: 'auto' }}>
      <div data-testid="page">
        <Table viewport={viewport}>
          <TableBody>
            <TableRow>
              <TableCell>줄</TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <div>쪽 넘기기</div>
      </div>
    </div>,
  )
  const box = view.container.querySelector<HTMLElement>('[data-slot="table-container"]')
  const page = view.container.querySelector<HTMLElement>('[data-testid="page"]')
  const scroller = view.container.querySelector<HTMLElement>('[data-testid="scroller"]')
  if (!box || !page || !scroller) throw new Error('표나 스크롤 칸이 없습니다')

  box.dataset.rect = JSON.stringify(scene.table)
  page.dataset.rect = JSON.stringify({ top: 0, bottom: scene.page })
  scroller.dataset.rect = JSON.stringify(scene.frame ?? { top: 60, bottom: 900 })
  act(() => {
    window.dispatchEvent(new Event('resize'))
  })
  return box
}

afterEach(() => vi.restoreAllMocks())

describe('표 가두기', () => {
  it('안 켠 표는 안 가둔다 — 짧은 표를 가두면 빈 공간만 생긴다', () => {
    const box = show(false, { table: { top: 300, bottom: 1400 }, page: 1460 })
    expect(box.style.maxHeight).toBe('')
  })

  it('위아래를 다 재서 창을 딱 채운다', () => {
    // 본문 60~900, 표는 300 에서 시작하고, 표 아래에 60(쪽 넘기기 줄 + 여백)이 있다.
    const box = show(true, { table: { top: 300, bottom: 1400 }, page: 1460 })
    expect(box.style.maxHeight).toBe('540px')
  })

  it('아래에 있는 것이 줄면 표가 그만큼 커진다 — 남는 공간을 안 버린다', () => {
    // 쪽 넘기기 줄이 없는 사업부: 표 아래에 본문 여백 24px 뿐이다.
    const box = show(true, { table: { top: 300, bottom: 1400 }, page: 1424 })
    // **어림잡은 꼬리라면 여기서도 같은 값이 나온다** — 그것이 아래를 비워 둔 원인이었다.
    expect(box.style.maxHeight).toBe('576px')
  })

  it('줄이 아직 안 왔어도 맞는 높이가 나온다 — 빈 표에 갇히지 않는다', () => {
    /**
     * 목록은 **비어서 그려지고** 줄은 나중에 온다. 스크롤 높이로 재면 그때의 본문이
     * 화면보다 짧아서 표 몫이 0 으로 나오고, 바닥값 240px 에 갇힌 채 다시 잴 일이
     * 없었다 — 쪽 넘기기 단추 아래가 통째로 비었다(2026-09-30).
     */
    const box = show(true, { table: { top: 300, bottom: 300 }, page: 360 })
    expect(box.style.maxHeight).toBe('540px')
  })

  it('위가 자란 만큼 표가 줄어든다 — 바닥은 언제나 화면 안이다', () => {
    // 칩 한 줄이 늘어 표가 60px 내려갔다.
    const box = show(true, { table: { top: 360, bottom: 1400 }, page: 1460 })
    expect(box.style.maxHeight).toBe('480px')
  })

  it('창이 좁아도 바닥값 아래로는 안 줄인다', () => {
    const box = show(true, {
      frame: { top: 60, bottom: 400 },
      table: { top: 340, bottom: 900 },
      page: 960,
    })
    // 남는 것이 몇 픽셀뿐이라도 그만큼만 주면 표가 아니라 창이 된다.
    expect(box.style.maxHeight).toBe('240px')
  })

  it('머리글이 위에 붙는다 — 스무 번째 열이 무슨 열인지 알아야 한다', () => {
    const box = show(true, { table: { top: 300, bottom: 1400 }, page: 1460 })
    expect(box.className).toContain('[&>table>thead]:sticky')
    expect(box.className).toContain('overflow-y-auto')
  })
})

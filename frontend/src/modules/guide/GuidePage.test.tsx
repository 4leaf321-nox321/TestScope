/**
 * 가이드 — **글이 가리키는 곳이 실제로 있어야 한다.**
 *
 * 가이드의 값은 「저기로 가 보세요」 에 있는데, 그 주소가 없으면 읽는 사람은 자기가 뭘
 * 잘못 눌렀다고 생각한다. 그리고 그런 링크는 화면을 지우거나 주소를 바꾼 **다른 PR** 에서
 * 생기므로, 가이드를 고친 사람은 모른다 — 그래서 라우터와 대조한다.
 *
 * 여기서 지키는 것:
 *
 * 1. 쪽마다 제목이 있고 차례에 선다 — 번호만 바꾼 파일이 조용히 안 보이면 안 된다.
 * 2. 본문이 그려진다(표·코드 블록 포함).
 * 3. **내부 링크가 라우터에 있는 주소다.**
 * 4. 없는 쪽을 열면 길을 알려 준다.
 */

import { describe, expect, it } from 'vitest'
import { act, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { GUIDE_PAGES } from '@/modules/guide/pages'
import { NAV_GROUPS } from '@/shared/layout/navigation'

const { default: GuidePage } = await import('@/modules/guide/GuidePage')

async function show(at: string) {
  await act(async () => {
    render(
      <MemoryRouter initialEntries={[at]}>
        <Routes>
          <Route path="/guide" element={<GuidePage />} />
          <Route path="/guide/:slug" element={<GuidePage />} />
        </Routes>
      </MemoryRouter>,
    )
  })
}

describe('가이드', () => {
  it('쪽마다 제목이 있고 차례에 선다', () => {
    expect(GUIDE_PAGES.length).toBeGreaterThan(2)
    for (const one of GUIDE_PAGES) {
      expect(one.title).not.toBe('(제목 없음)')
      // 주소에 번호가 남으면 글 차례를 바꿀 때마다 링크가 깨진다.
      expect(one.slug).not.toMatch(/^\d/)
    }
    expect(new Set(GUIDE_PAGES.map((one) => one.slug)).size).toBe(GUIDE_PAGES.length)
  })

  it('주소 없이 들어가면 첫 쪽을 보여 준다', async () => {
    await show('/guide')
    // 본문 렌더러는 lazy 다 — 붙을 때까지 기다린다.
    expect(
      await screen.findByRole('heading', { level: 1, name: GUIDE_PAGES[0].title }),
    ).toBeTruthy()
  })

  it('표와 사슬 그림이 그려진다 — 둘 다 이 가이드의 설명 수단이다', async () => {
    await show('/guide')
    await waitFor(() => expect(document.querySelector('table')).not.toBeNull())
    expect(document.querySelector('pre')).not.toBeNull()
  })

  it('안에서 가리키는 주소가 라우터에 있다', async () => {
    // 라우터가 아는 주소 — 사이드바가 거는 곳이면 적어도 있다.
    const known = new Set<string>()
    for (const group of NAV_GROUPS) {
      for (const item of group.items) {
        if (item.to) known.add(item.to)
      }
    }
    for (const one of GUIDE_PAGES) known.add(`/guide/${one.slug}`)

    const bad: string[] = []
    for (const page of GUIDE_PAGES) {
      for (const [, to] of page.body.matchAll(/]\((\/[^)]*)\)/g)) {
        if (!known.has(to)) bad.push(`${page.slug}: ${to}`)
      }
    }
    expect(bad, '가이드가 없는 주소를 가리킨다').toEqual([])
  })

  it('없는 쪽을 열면 길을 알려 준다 — 빈 화면은 고장으로 읽힌다', async () => {
    await show('/guide/없는쪽')
    expect(screen.getByText(/해당 가이드 쪽 없음/)).toBeTruthy()
    expect(screen.getByRole('link', { name: '처음으로' })).toBeTruthy()
  })
})

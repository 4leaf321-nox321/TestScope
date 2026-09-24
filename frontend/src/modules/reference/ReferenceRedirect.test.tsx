/**
 * 예전 주소 — **쓰던 주소가 죽으면 안 된다.**
 *
 * 화면이 「공통 → 기준정보」(`/reference`)에서 「관리 → 온톨로지」(`/admin/ontology`)로
 * 옮겨 갔다. 북마크와 남이 붙여 둔 링크는 그대로 남아 있고, 그 링크에는 대개 고르던 객체
 * 종류(`?kind=…`)가 붙어 있다 — 그것까지 실어 보내지 않으면 「눌렀더니 맨 앞으로 갔다」 가
 * 된다.
 */

import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

import { ReferenceRedirect } from '@/modules/reference/ReferenceHubPage'

function Landed() {
  const { pathname, search } = useLocation()
  return <p>{`${pathname}${search}`}</p>
}

function go(url: string) {
  render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/reference" element={<ReferenceRedirect />} />
        <Route path="/admin/ontology" element={<Landed />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('예전 주소', () => {
  it('새 자리로 보낸다', () => {
    go('/reference')
    expect(screen.getByText('/admin/ontology')).toBeTruthy()
  })

  it('고르던 종류를 실어 보낸다 — 맨 앞으로 되돌리지 않는다', () => {
    go('/reference?kind=axis:test_item')
    expect(screen.getByText('/admin/ontology?kind=axis:test_item')).toBeTruthy()
  })
})

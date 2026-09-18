/**
 * 지식 그래프 화면 — **구조는 응답이 곧 정의, 탐색은 상한과 「+N」.**
 *
 * 여기서 지키는 것 — 구조 그림의 종류·관계 종류가 overview 에서 온다 · 종류를 고르면 관계와 수가
 * 옆 판에 선다 · 검색으로 시작점을 고르면 주소에 focus 가 적히고 이웃을 든다 · 잘린 노드는
 * 「+N」 배지를 달고 상세 판이 「여기서 확장」 을 낸다.
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Neighborhood, NodeDetail, Overview } from '@/modules/graph/api'

vi.mock('@/shared/auth/AuthContext', () => ({
  useAuth: () => ({ user: { memberships: [], is_system_admin: true } }),
}))
vi.mock('@/shared/theme/ThemeProvider', () => ({
  useTheme: () => ({ theme: 'light', setTheme: () => undefined }),
}))
// 캔버스는 노드 이름만 적는 가짜 — force 배치는 시험할 것이 아니다.
vi.mock('@/modules/graph/GraphCanvas', () => ({
  GraphCanvas: ({
    nodes,
    onNodeClick,
    overlay,
  }: {
    nodes: { id: string; label: string; badge?: string | null }[]
    onNodeClick?: (id: string) => void
    overlay?: React.ReactNode
  }) => (
    <div data-testid="canvas">
      {nodes.map((one) => (
        <button key={one.id} type="button" onClick={() => onNodeClick?.(one.id)}>
          {one.label}
          {one.badge ? ` ${one.badge}` : ''}
        </button>
      ))}
      {overlay}
    </div>
  ),
}))

const OVERVIEW: Overview = {
  nodes: [
    {
      slug: 'test_item',
      label: '시험 항목',
      icon: 'list-checks',
      layer: 'vocabulary',
      count: 96,
      detail_path: '/catalog/test-items',
    },
    {
      slug: 'series',
      label: '장비 계열',
      icon: 'boxes',
      layer: 'catalog',
      count: 433,
      detail_path: '/catalog/equipment-series',
    },
    {
      slug: 'equipment',
      label: '보유 장비',
      icon: 'wrench',
      layer: 'operations',
      count: 0,
      detail_path: '/equipment',
    },
  ],
  edges: [
    {
      relation: 'performs',
      label: '수행 가능 시험 항목',
      inverse_label: '수행 가능 계열',
      directed: true,
      src_type: 'series',
      dst_type: 'test_item',
      count: 964,
    },
    {
      relation: 'performs_item',
      label: '수행 시험 항목',
      inverse_label: '수행 장비',
      directed: true,
      src_type: 'equipment',
      dst_type: 'test_item',
      count: 0,
    },
  ],
  object_count: 529,
  edge_count: 964,
}

const NEIGHBORHOOD: Neighborhood = {
  focus: 'test_item:11111111-1111-1111-1111-111111111111',
  nodes: [
    {
      id: 'test_item:11111111-1111-1111-1111-111111111111',
      label: '인장',
      key: 'tensile',
      sublabel: null,
      type_slug: 'test_item',
      type_label: '시험 항목',
      status: 'active',
      owner_workspace_slug: null,
      degree: 3,
      truncated: true,
      detail_path: '/catalog/test-items/11111111-1111-1111-1111-111111111111',
    },
    {
      id: 'series:22222222-2222-2222-2222-222222222222',
      label: '6800',
      key: null,
      sublabel: 'Instron',
      type_slug: 'series',
      type_label: '장비 계열',
      status: 'active',
      owner_workspace_slug: null,
      degree: 1,
      truncated: false,
      detail_path: '/catalog/equipment-series/22222222-2222-2222-2222-222222222222',
    },
  ],
  edges: [
    {
      id: 'performs:1',
      relation: 'performs',
      label: '수행 가능 시험 항목',
      inverse_label: '수행 가능 계열',
      directed: true,
      src: 'series:22222222-2222-2222-2222-222222222222',
      dst: 'test_item:11111111-1111-1111-1111-111111111111',
    },
  ],
  depth: 1,
  fanout: 30,
  node_limit: 300,
  truncated: true,
}

const DETAIL: NodeDetail = {
  id: NEIGHBORHOOD.focus,
  label: '인장',
  key: 'tensile',
  type_slug: 'test_item',
  type_label: '시험 항목',
  status: 'active',
  detail_path: '/catalog/test-items/11111111-1111-1111-1111-111111111111',
  facts: [{ label: '코드', value: 'tensile' }],
  related: [
    {
      relation: 'performs',
      label: '수행 가능 계열',
      outgoing: false,
      node_id: 'series:22222222-2222-2222-2222-222222222222',
      node_label: '6800',
      node_type_label: '장비 계열',
    },
    {
      relation: 'measures',
      label: '측정 물성',
      outgoing: true,
      node_id: 'property:33333333-3333-3333-3333-333333333333',
      node_label: '인장강도',
      node_type_label: '물성 항목',
    },
  ],
  related_total: 3,
}

const calls: string[] = []
vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (path: string) => {
      calls.push(path)
      if (path.startsWith('/graph/overview')) return OVERVIEW
      if (path.startsWith('/graph/search')) {
        return [
          {
            id: NEIGHBORHOOD.focus,
            label: '인장',
            key: 'tensile',
            sublabel: null,
            type_slug: 'test_item',
            type_label: '시험 항목',
          },
        ]
      }
      if (path.startsWith('/graph/neighborhood')) return NEIGHBORHOOD
      if (path.startsWith('/graph/node')) return DETAIL
      if (path.startsWith('/graph/browse'))
        return { items: [], total: 0, limit: 20, offset: 0 }
      throw new Error(`unexpected ${path}`)
    }),
  },
  ApiError: class extends Error {},
}))

import GraphPage from '@/modules/graph/GraphPage'

function open(url = '/graph') {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <GraphPage />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  calls.length = 0
})

describe('지식 그래프', () => {
  it('구조 그림은 종류와 관계 종류를 그리고, 종류를 고르면 관계와 수가 선다', async () => {
    open()
    await waitFor(() => expect(screen.getByText('장비 계열')).toBeTruthy())
    expect(screen.getByText(/종류 3 · 관계 종류 2 · 객체 529/)).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: '장비 계열' }))
    // 옆 판 — 객체 수와 걸린 관계 종류.
    expect(screen.getByText('433')).toBeTruthy()
    expect(screen.getAllByText(/수행 가능 시험 항목/).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: /이 종류 전체 그리기/ })).toBeTruthy()
  })

  it('검색으로 시작점을 고르면 이웃을 들고, 잘린 노드에 +N 이 붙으며 상세가 확장을 낸다', async () => {
    open('/graph?focus=' + NEIGHBORHOOD.focus)
    await waitFor(() => expect(screen.getByRole('button', { name: /인장 \+2/ })).toBeTruthy())
    expect(calls.some((one) => one.startsWith('/graph/neighborhood?focus=test_item'))).toBe(
      true,
    )
    // 시작점은 고른 채로 뜬다 — 상세 판에 「여기서 확장 (+2)」.
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /여기서 확장 \(\+2\)/ })).toBeTruthy(),
    )
    expect(screen.getByText('수행 가능 계열')).toBeTruthy()
    expect(screen.getByText(/일부만 실었습니다/)).toBeTruthy()
  })
})

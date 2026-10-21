/**
 * 허브 연계 — **토큰은 다시 안 보이고, 받을 타입을 고르고, 수동 실행이 워커로 간다.**
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const sent: { method: string; url: string; body?: unknown }[] = []

const connection = {
  base_url: 'https://hub.example/api',
  has_token: true,
  token_readable: true,
  token_set_at: '2026-10-21T00:00:00Z',
  ca_bundle: null,
  selected_types: null,
  nightly_at: '01:00',
  enabled: true,
  catalog_revision: '3-1',
  catalog_as_of: '2026-10-21T00:00:00.000000Z',
  catalog_changed_at: '2026-10-21T01:00:00Z',
  types: [
    {
      slug: 'plm_model',
      label: '개발모델',
      description: '',
      count: 6133,
      properties: 3,
      relations: [],
      selected: true,
    },
    {
      slug: 'plm_task',
      label: '과제',
      description: '',
      count: 120,
      properties: 2,
      relations: [],
      selected: true,
    },
  ],
}

const status = {
  configured: true,
  enabled: true,
  nightly_at: '01:00',
  catalog_changed_at: '2026-10-21T01:00:00Z',
  pending_job: null,
  last_run: null,
  types: [
    {
      slug: 'plm_model',
      label: '개발모델',
      axis_slug: 'hub_plm_model',
      selected: true,
      catalog_count: 6133,
      received: 6133,
      active: 6133,
      relations: 12,
      rows: {
        as_of: '2026-10-21T00:00:00.000000Z',
        last_run_at: '2026-10-21T00:00:00Z',
        last_status: 'ok',
        last_error: null,
        last_full_at: null,
        stopped: false,
      },
      relation_state: null,
    },
  ],
}

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (url: string) => {
      if (url === '/hub/connection') return connection
      if (url === '/hub/status') return status
      if (url.startsWith('/hub/runs'))
        return [
          {
            id: 'r1',
            started_at: '2026-10-21T00:00:00Z',
            finished_at: '2026-10-21T00:01:00Z',
            trigger: 'schedule',
            full: false,
            status: 'partial',
            triggered_by: '야간 자동',
            counts: { plm_model: { created: 2, updated: 1 } },
            errors: [{ type: 'plm_task', message: '허브 내부 오류' }],
            request_ids: ['req-1'],
            duration_ms: 1500,
          },
        ]
      return []
    }),
    put: vi.fn(async (url: string, body: unknown) => {
      sent.push({ method: 'put', url, body })
      return connection
    }),
    post: vi.fn(async (url: string, body?: unknown) => {
      sent.push({ method: 'post', url, body })
      if (url === '/hub/run') return { job_id: 'j1', full: false }
      return null
    }),
  },
  ApiError: class extends Error {},
}))

import HubAdminPage from '@/modules/hub/HubAdminPage'

async function open() {
  await act(async () => {
    render(
      <MemoryRouter>
        <HubAdminPage />
      </MemoryRouter>,
    )
  })
}

beforeEach(() => {
  sent.length = 0
})

describe('허브 연계', () => {
  it('토큰은 다시 안 보이고, 고른 타입만 받도록 저장한다', async () => {
    await open()
    const token = screen.getByLabelText(/토큰/) as HTMLInputElement
    expect(token.value).toBe('')
    expect(token.placeholder).toContain('설정됨')
    await act(async () => {
      fireEvent.click(screen.getByLabelText('고른 타입만'))
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('checkbox', { name: /과제/ }))
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '저장' }))
    })
    expect(sent[0]).toMatchObject({
      method: 'put',
      url: '/hub/connection',
      body: { selected_types: ['plm_model'], token: null, nightly_at: '01:00', enabled: true },
    })
  })

  it('현황 · 구조 변경 · 이력을 보이고 수동 실행은 워커로 보낸다', async () => {
    await open()
    expect(screen.getByText(/허브 구조\(타입·칸·관계 종류\) 변경 감지/)).toBeTruthy()
    expect(screen.getByText('일부 실패')).toBeTruthy()
    expect(screen.getByText(/1건: 허브 내부 오류/)).toBeTruthy()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '지금 받기' }))
    })
    expect(sent).toContainEqual({ method: 'post', url: '/hub/run', body: { full: false } })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '확인함' }))
    })
    expect(sent.some((one) => one.url === '/hub/catalog-seen')).toBe(true)
  })
})

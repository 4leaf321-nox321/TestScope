/**
 * 신뢰성 시험 보기 창 — **읽는 자리에는 입력칸이 없다.**
 *
 * 여기서 지키는 것:
 *
 * 1. 글상자도 「그림 넣기」 도 없다. 읽으려고 연 창에서 값을 건드리면 안 된다.
 * 2. 칸이 **등록 창과 같은 갈래**로 묶여 온다 — 자리마다 순서가 다르면 「어디 적혀
 *    있었더라」 를 매번 다시 찾는다.
 * 3. 절차의 줄바꿈이 살아 있다. 네 단계가 한 줄로 붙으면 그것은 절차가 아니다.
 * 4. 짝(등급별 수량)은 표로 펴진다.
 * 5. 고칠 수 없는 사람에게는 「수정」 이 없다. 그래도 **카드는 읽힌다** — 그것이 이 창이
 *    생긴 이유다.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'

const DEFS = [
  { id: 'd-type', key: 'reliability_type', label: '유형', kind: 'term', status: 'standard' },
  {
    id: 'd-temp',
    key: 'reliability_temperature',
    label: '시험 온도',
    kind: 'condition',
    status: 'standard',
  },
  {
    id: 'd-proc',
    key: 'reliability_procedure',
    label: '시험 절차',
    kind: 'text',
    status: 'standard',
  },
  {
    id: 'd-grade',
    key: 'reliability_grade_counts',
    label: '등급별 수량',
    kind: 'pairs',
    status: 'standard',
  },
]

const get = vi.fn(async (path: string) => (path.includes('attribute-definitions') ? DEFS : []))

vi.mock('@/shared/api/client', () => ({
  api: { get: (path: string) => get(path), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  fetchBlobUrl: vi.fn(async () => 'blob:그림'),
  ApiError: class extends Error {},
}))

const { ReliabilityTestViewDialog } =
  await import('@/modules/reliability/ReliabilityTestViewDialog')
const { reliabilityApi } = await import('@/modules/reliability/api')
type ReliabilityTest = Awaited<ReturnType<typeof reliabilityApi.read>>

const PROCEDURE = '1. 상온에서 안정화한다.\n2. 85 degC 로 올린다.'

function test(over: Partial<ReliabilityTest> = {}): ReliabilityTest {
  return {
    id: 'r1',
    workspace_slug: 'lab',
    workspace_name: '신뢰성팀',
    name: '고온고습 저장 1000h',
    purpose: '장기 보관 시 열화 확인',
    status: 'confirmed',
    submitted_via: null,
    confirmed_by: '박용진',
    confirmed_at: '2026-09-24T00:00:00Z',
    test_items: [{ term_id: 't1', value: '항온항습(습열)', equipment_count: 0 }],
    attributes: [
      {
        definition_id: 'd-grade',
        label: '등급별 수량',
        kind: 'pairs',
        status: 'standard',
        unit: '개',
        display: 'A등급 4 개 · B등급 4 개',
        json_value: [
          { label: 'A등급', value: 4 },
          { label: 'B등급', value: 4 },
        ],
      },
      {
        definition_id: 'd-proc',
        label: '시험 절차',
        kind: 'text',
        status: 'standard',
        unit: '',
        display: PROCEDURE,
        text_value: PROCEDURE,
      },
      {
        definition_id: 'd-temp',
        label: '시험 온도',
        kind: 'condition',
        status: 'standard',
        unit: 'degC',
        display: '85 ~ 85 degC',
        num_min: 85,
        num_max: 85,
      },
    ],
    attachment_count: 0,
    can_edit: true,
    created_at: '2026-09-24T00:00:00Z',
    updated_at: '2026-09-24T00:00:00Z',
    ...over,
  } as ReliabilityTest
}

async function show(row: ReliabilityTest | null, onEdit?: () => void) {
  await act(async () => {
    render(
      <ReliabilityTestViewDialog
        test={row}
        onClose={() => {}}
        onEdit={onEdit}
        onChanged={() => {}}
      />,
    )
  })
}

afterEach(() => vi.clearAllMocks())

describe('보기 창', () => {
  it('입력칸이 하나도 없다 — 읽으려고 연 창이다', async () => {
    await show(test())
    expect(screen.queryAllByRole('textbox')).toHaveLength(0)
    expect(screen.queryByText('이미지 첨부')).toBeNull()
    // 값은 보인다.
    expect(screen.getByText('85 ~ 85 degC')).toBeTruthy()
  })

  it('등록 창과 같은 갈래로 묶인다', async () => {
    await show(test())
    // **제목 쪽만 본다.** 왼쪽 목차에도 같은 이름이 서므로 `getByText` 는 둘을 만난다.
    const titles = [...document.querySelectorAll('h3')].map((one) => one.textContent?.trim())
    // 조건은 「시험 조건」, 절차·판정은 「방법과 판정」, 수량은 「대상과 수량」.
    expect(titles).toContain('시험 조건')
    expect(titles).toContain('대상과 수량')
    expect(titles).toContain('방법과 판정')
    // 값이 없는 갈래는 아예 안 선다 — 빈 제목만 줄줄이 있으면 카드가 안 읽힌다.
    expect(titles).not.toContain('시험 구분')
    expect(titles).not.toContain('근거')
  })

  it('왼쪽 목차가 적힌 칸을 순서대로 세운다', async () => {
    /**
     * 스물두 칸을 세로로 늘어놓으면 어디까지 읽었는지 사람이 잃는다. 목차는 **본문과
     * 같은 표**(`groupDefinitions`)를 보므로 칸이 하나 늘어도 한쪽만 고쳐지지 않는다.
     */
    await show(test())
    const outline = screen.getByRole('navigation', { name: '목차' })
    const labels = [...outline.querySelectorAll('button')].map((one) =>
      one.textContent?.trim(),
    )
    // 고정 칸이 먼저, 그다음 갈래와 그 아래 칸.
    expect(labels.slice(0, 2)).toEqual(['목적', '적용 시험 항목'])
    expect(labels).toContain('시험 온도')
    expect(labels).toContain('시험 절차')
    // **보기 창은 적힌 칸만 세운다** — 없는 칸으로 보내면 「왜 빈 자리로 가지」 가 된다.
    expect(labels).not.toContain('판정 기준')
  })

  it('절차의 줄바꿈이 살아 있다', async () => {
    await show(test())
    const shown = screen.getByText(/상온에서 안정화한다/)
    expect(shown.className).toContain('whitespace-pre-line')
    expect(shown.textContent).toContain('\n')
  })

  it('등급별 수량은 표로 펴진다 — 한 줄 글이 아니다', async () => {
    await show(test())
    expect(screen.getByText('A등급')).toBeTruthy()
    expect(screen.getByText('B등급')).toBeTruthy()
    // 서버가 만든 한 줄(`display`)을 그대로 쓰지 않는다.
    expect(screen.queryByText('A등급 4 개 · B등급 4 개')).toBeNull()
  })

  it('고칠 수 없는 사람에게는 수정이 없고, 카드는 읽힌다', async () => {
    await show(test({ can_edit: false }), () => {})
    expect(screen.queryByRole('button', { name: '수정' })).toBeNull()
    expect(screen.getByText(/장기 보관 시 열화 확인/)).toBeTruthy()
    expect(screen.getByText('항온항습(습열)')).toBeTruthy()
  })

  it('닫혀 있으면 아무것도 안 그린다', async () => {
    await show(null)
    expect(screen.queryByText(/고온고습/)).toBeNull()
  })
})

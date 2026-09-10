/**
 * 일괄 반입 창 — **표에 붙여넣고, 표에서 고치고, 문제가 있으면 안 넣는다.**
 *
 * 파일이 아니라 붙여넣기인 이유는 DRM 이다 — 문서 보안이 걸린 환경에서는 서식을
 * 내려받는 것은 되는데 그 파일을 다시 고르는 것이 막힌다.
 *
 * 글상자가 아니라 표인 이유는 **어느 칸이 틀렸는지**와 **그 자리에서 고치기**다.
 *
 * 이 창이 잘못 동작하면 한 번에 수백 대가 잘못 들어간다. 그리고 잘못 들어간 장비는
 * 지우기 전까지 검색이 계속 그것으로 답한다.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'

const calls: { path: string; body: unknown }[] = []
let answer: Record<string, unknown> = {}

const COLUMNS = [
  { key: 'asset_no', label: '자산번호', required: true },
  { key: 'name', label: '장비명', required: true },
  { key: 'site', label: '거점', required: true },
  { key: 'note', label: '비고', required: false },
]

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async (path: string) => {
      if (path.includes('/import/columns')) return COLUMNS
      return []
    }),
    post: vi.fn(async (path: string, body: unknown) => {
      calls.push({ path, body })
      return answer
    }),
  },
  downloadFile: vi.fn(async () => undefined),
  ApiError: class extends Error {},
}))

import { EquipmentImportDialog } from '@/modules/equipment/EquipmentImportDialog'

/** 서버가 돌려주는 한 줄. 값은 **서버가 읽은 그대로**다. */
function row(over: Record<string, unknown> = {}) {
  return {
    line: 2,
    cells: { asset_no: 'A-1', name: '만능기', site: '본사', note: '' },
    asset_no: 'A-1',
    name: '만능기',
    model_linked: true,
    problems: [],
    ...over,
  }
}

async function open() {
  await act(async () => {
    render(<EquipmentImportDialog open onClose={() => {}} onDone={() => {}} />)
  })
}

/** 그 열의 칸 하나. */
function cell(label: string, line = 0): HTMLInputElement {
  const index = COLUMNS.findIndex((one) => one.label === label)
  const rows = document.querySelectorAll('tbody tr')
  return rows[line].querySelectorAll('input')[index] as HTMLInputElement
}

/** 표의 첫 칸에서 붙여넣는다. 엑셀에서 온 것은 **범위**라 표 전체를 갈아 끼운다. */
async function paste(text = '자산번호\t장비명\nA-1\t만능기') {
  await act(async () => {
    fireEvent.paste(cell('자산번호'), { clipboardData: { getData: () => text } })
  })
}

function commitButton(): HTMLButtonElement {
  return screen
    .getAllByRole('button')
    .find((one) => /넣기|넣는 중/.test(one.textContent ?? '')) as HTMLButtonElement
}

beforeEach(() => {
  calls.length = 0
  vi.useFakeTimers({ shouldAdvanceTime: true })
})

describe('빈 표', () => {
  it('창을 열면 곧바로 표가 있다', async () => {
    await open()
    // 글상자에 붙이고 그 다음에 표가 나타나면 「어디에 붙이나」 를 한 번 더 묻게 된다.
    expect(document.querySelectorAll('tbody tr').length).toBeGreaterThan(0)
    expect(screen.getByText('자산번호')).toBeTruthy()
    // 비우면 그 줄을 못 넣는 칸은 표시가 있어야 한다 — 없으면 다 채워야 하는 줄 안다.
    expect(screen.getAllByText('*').length).toBe(3)
  })

  it('비어 있으면 서버를 안 부른다', async () => {
    await open()
    await act(async () => {
      vi.advanceTimersByTime(1000)
    })
    // 빈 표를 보내면 서버가 400 을 돌려주고, 아직 아무것도 안 한 사람에게 빨간
    // 오류가 뜬다.
    expect(calls).toHaveLength(0)
    expect(commitButton().disabled).toBe(true)
  })

  it('한 칸만 쳐도 서버가 읽는다', async () => {
    answer = { total: 1, ready: 0, problems: 1, created: 0, rows: [row()] }
    await open()
    await act(async () => {
      fireEvent.change(cell('자산번호'), { target: { value: 'A-1' } })
    })
    await act(async () => {
      vi.advanceTimersByTime(600)
    })
    expect(calls).toHaveLength(1)
    // **내용이 있는 줄만 보낸다** — 빈 줄까지 보내면 서버가 건너뛰고, 그러면
    // 응답의 순서와 표의 줄이 어긋난다.
    const sent = (calls[0].body as { text: string }).text
    expect(sent.split('\n')).toHaveLength(2)
  })
})

describe('붙여넣기', () => {
  it('표에 붙여넣으면 서버가 먼저 읽는다', async () => {
    answer = { total: 1, ready: 1, problems: 0, created: 0, rows: [row()] }
    await open()
    await paste()
    // **넣기 전에 본다.** 300줄 중 틀린 12줄을 넣고 나서 알면 늦다.
    expect(calls[0].path).toContain('dry_run=true')
  })

  it('서버가 읽은 값을 표로 그린다', async () => {
    answer = { total: 1, ready: 1, problems: 0, created: 0, rows: [row()] }
    await open()
    await paste()
    // 화면이 다시 파싱하면 규칙이 두 벌이 되고, 그때 사람은 자기가 붙여넣은 것과
    // 다른 표를 본다.
    expect(screen.getByDisplayValue('만능기')).toBeTruthy()
    expect(screen.getByDisplayValue('본사')).toBeTruthy()
  })

  it('한 칸짜리 값은 그 칸에 그냥 붙는다', async () => {
    await open()
    await act(async () => {
      fireEvent.paste(cell('장비명'), { clipboardData: { getData: () => '만능기' } })
    })
    // 탭도 줄바꿈도 없으면 범위가 아니다 — 가로채면 한 낱말 붙여넣기가 표를 지운다.
    expect(calls).toHaveLength(0)
  })
})

describe('틀린 칸', () => {
  it('그 칸만 붉게 칠한다', async () => {
    answer = {
      total: 1,
      ready: 0,
      problems: 1,
      created: 0,
      rows: [
        row({
          cells: { asset_no: 'A-1', name: '만능기', site: '없는거점', note: '' },
          problems: [{ field: 'site', message: '거점: 「없는거점」 가 기준정보에 없습니다' }],
        }),
      ],
    }
    await open()
    await paste()

    const bad = cell('거점')
    // 줄 단위로만 말하면 열여덟 칸 중 어디를 고칠지 사람이 되짚어야 한다.
    expect(bad.className).toMatch(/red/)
    expect(bad.title).toMatch(/기준정보에 없습니다/)
    // 멀쩡한 칸은 안 칠한다 — 다 붉으면 아무것도 안 가리킨 것과 같다.
    expect(cell('장비명').className).not.toMatch(/red/)
  })

  it('한 칸에 못 붙이는 문제는 줄 끝에 적는다', async () => {
    answer = {
      total: 1,
      ready: 0,
      problems: 1,
      created: 0,
      rows: [row({ problems: [{ field: null, message: '자산번호가 2번째 줄과 겹칩니다' }] })],
    }
    await open()
    await paste()
    expect(screen.getByText(/2번째 줄과 겹칩니다/)).toBeTruthy()
  })

  it('문제가 있으면 넣는 단추가 안 눌린다', async () => {
    answer = {
      total: 1,
      ready: 0,
      problems: 1,
      created: 0,
      rows: [row({ problems: [{ field: 'site', message: '거점: 없습니다' }] })],
    }
    await open()
    await paste()
    // **전부 되거나 전부 안 되거나.**
    expect(commitButton().disabled).toBe(true)
  })
})

describe('표에서 고치기', () => {
  it('칸을 고치면 서버가 다시 읽는다', async () => {
    answer = {
      total: 1,
      ready: 0,
      problems: 1,
      created: 0,
      rows: [
        row({
          cells: { asset_no: 'A-1', name: '만능기', site: '없는거점', note: '' },
          problems: [{ field: 'site', message: '거점: 없습니다' }],
        }),
      ],
    }
    await open()
    await paste()
    calls.length = 0

    answer = { total: 1, ready: 1, problems: 0, created: 0, rows: [row()] }
    await act(async () => {
      fireEvent.change(cell('거점'), { target: { value: '본사' } })
    })
    await act(async () => {
      vi.advanceTimersByTime(600)
    })

    // **판정은 서버가 한다.** 화면이 스스로 「이제 됩니다」 라고 하면 저장에서 막힌다.
    expect(calls).toHaveLength(1)
    expect(calls[0].path).toContain('dry_run=true')
    // 표를 머리글까지 붙여 다시 보낸다 — 파싱 규칙은 서버 한 곳에만 있다.
    const sent = (calls[0].body as { text: string }).text
    expect(sent.split('\n')[0]).toBe('자산번호\t장비명\t거점\t비고')
    expect(sent).toContain('본사')
    expect(commitButton().disabled).toBe(false)
  })

  it('고친 값을 서버가 읽은 값으로 덮지 않는다', async () => {
    answer = { total: 1, ready: 1, problems: 0, created: 0, rows: [row()] }
    await open()
    await paste()
    // 서버 응답의 `cells` 로 표를 덮으면 사람이 치던 칸이 되돌아가고 커서가 튄다.
    await act(async () => {
      fireEvent.change(cell('장비명'), { target: { value: '충격기' } })
    })
    await act(async () => {
      vi.advanceTimersByTime(600)
    })
    expect(cell('장비명').value).toBe('충격기')
  })

  it('같은 표를 두 번 보내지 않는다', async () => {
    answer = { total: 1, ready: 1, problems: 0, created: 0, rows: [row()] }
    await open()
    await paste()
    calls.length = 0
    // 응답이 판정을 갈아 끼우면 표 글자가 다시 계산된다. 그것이 또 조회를
    // 부르면 끝이 없다.
    await act(async () => {
      vi.advanceTimersByTime(2000)
    })
    expect(calls).toHaveLength(0)
  })
})

describe('넣는 동안', () => {
  it('「읽는 중」 이 아니라 「넣는 중」 이라고 말한다', async () => {
    answer = { total: 3, ready: 3, problems: 0, created: 0, rows: [row()] }
    await open()
    await paste()

    let release: (value: unknown) => void = () => {}
    const held = new Promise((resolve) => {
      release = resolve
    })
    const client = await import('@/shared/api/client')
    vi.mocked(client.api.post).mockImplementationOnce(async () => held)

    await act(async () => {
      commitButton().click()
    })
    // **한 낱말로 뭉치면 넣는 10초 동안 화면이 거짓말한다.** 실제로 그랬다.
    expect(screen.getByText(/넣는 중입니다/)).toBeTruthy()
    expect(screen.queryByText('읽는 중…')).toBeNull()
    const close = screen.getAllByRole('button').find((one) => one.textContent === '닫기')
    expect((close as HTMLButtonElement).disabled).toBe(true)

    await act(async () => {
      release({ total: 3, ready: 3, problems: 0, created: 3, rows: [] })
      await held
    })
    expect(screen.getByText(/등록했습니다/)).toBeTruthy()
  })

  it('오래 걸릴 것 같으면 넣기 전에 말한다', async () => {
    answer = { total: 900, ready: 900, problems: 0, created: 0, rows: [row()] }
    await open()
    await paste()
    // 900대면 5초쯤. 말 안 하면 사람은 멈춘 줄 알고 창을 닫는다.
    expect(commitButton().textContent).toMatch(/초쯤 걸립니다/)
  })
})

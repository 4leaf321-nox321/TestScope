/**
 * 일괄 반입 창 — **붙여넣고, 넣기 전에 보여 주고, 문제가 있으면 안 넣는다.**
 *
 * 파일이 아니라 붙여넣기인 이유는 DRM 이다 — 문서 보안이 걸린 환경에서는 서식을
 * 내려받는 것은 되는데 그 파일을 다시 고르는 것이 막힌다.
 *
 * 이 창이 잘못 동작하면 한 번에 수백 대가 잘못 들어간다. 그리고 잘못 들어간 장비는
 * 지우기 전까지 검색이 계속 그것으로 답한다.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'

const calls: { path: string; body: unknown }[] = []
let answer: Record<string, unknown> = {}

vi.mock('@/shared/api/client', () => ({
  api: {
    get: vi.fn(async () => []),
    post: vi.fn(async (path: string, body: unknown) => {
      calls.push({ path, body })
      return answer
    }),
  },
  downloadFile: vi.fn(async () => undefined),
  ApiError: class extends Error {},
}))

import { EquipmentImportDialog } from '@/modules/equipment/EquipmentImportDialog'

const PASTED = '자산번호\t장비명\nA-1\t만능기'

async function open() {
  await act(async () => {
    render(<EquipmentImportDialog open onClose={() => {}} onDone={() => {}} />)
  })
}

/** 엑셀에서 복사해 붙여넣은 것처럼. 창은 400ms 뒤에 미리보기를 부른다. */
async function paste(text = PASTED) {
  const box = screen.getByRole('textbox')
  await act(async () => {
    fireEvent.change(box, { target: { value: text } })
  })
  await act(async () => {
    vi.advanceTimersByTime(500)
  })
}

function commitButton(): HTMLButtonElement {
  return screen
    .getAllByRole('button')
    .find((one) => one.textContent?.includes('넣기')) as HTMLButtonElement
}

beforeEach(() => {
  calls.length = 0
  vi.useFakeTimers({ shouldAdvanceTime: true })
})

describe('일괄 반입', () => {
  it('붙여넣으면 먼저 미리보기를 부른다', async () => {
    answer = { total: 1, ready: 1, problems: 0, created: 0, rows: [] }
    await open()
    await paste()
    // **넣기 전에 본다.** 300줄 중 틀린 12줄을 넣고 나서 알면 늦다.
    expect(calls[0].path).toContain('dry_run=true')
    // 파일이 아니라 **글자**로 간다 — DRM 이 파일을 막는다.
    expect(calls[0].body).toEqual({ text: PASTED })
  })

  it('문제가 있으면 넣는 단추가 안 눌린다', async () => {
    answer = {
      total: 2,
      ready: 1,
      problems: 1,
      created: 0,
      rows: [
        { line: 2, asset_no: 'A-1', name: '만능기', model_linked: true, problems: [] },
        {
          line: 3,
          asset_no: null,
          name: null,
          model_linked: false,
          problems: ['자산번호: 비어 있습니다'],
        },
      ],
    }
    await open()
    await paste()
    // **전부 되거나 전부 안 되거나.** 되는 것만 넣으면 사람은 고쳐 다시 붙여넣다가
    // 이미 들어간 줄에서 「이미 등록된 자산번호」 를 만난다.
    expect(commitButton().disabled).toBe(true)
    expect(screen.getByText(/아무것도 넣지 않았습니다/)).toBeTruthy()
  })

  it('문제를 줄 번호로 보여 준다', async () => {
    answer = {
      total: 1,
      ready: 0,
      problems: 1,
      created: 0,
      rows: [
        {
          line: 12,
          asset_no: 'A-9',
          name: null,
          model_linked: false,
          problems: ['거점: 「본사」 가 기준정보에 없습니다'],
        },
      ],
    }
    await open()
    await paste()
    // 「12번째 줄」 이라고 말해 줘야 사람이 엑셀에서 찾는다.
    expect(screen.getByText('12번째 줄')).toBeTruthy()
    expect(screen.getByText(/기준정보에 없습니다/)).toBeTruthy()
  })

  it('기종에 안 이어진 줄이 몇인지 넣기 전에 말한다', async () => {
    answer = {
      total: 2,
      ready: 2,
      problems: 0,
      created: 0,
      rows: [
        { line: 2, asset_no: 'A-1', name: '가', model_linked: true, problems: [] },
        { line: 3, asset_no: 'A-2', name: '나', model_linked: false, problems: [] },
      ],
    }
    await open()
    await paste()
    // 막지는 않는다(자작 장비가 실제로 있다). 다만 **검색에 안 걸린다**는 사실은
    // 넣기 전에 알아야 한다 — 나중에 알면 대장에만 있고 아무도 못 찾는 장비가 된다.
    expect(screen.getByText(/검색에 걸리지 않습니다/)).toBeTruthy()
    expect(commitButton().disabled).toBe(false)
  })

  it('확인하면 같은 글자를 dry_run 없이 다시 보낸다', async () => {
    answer = { total: 1, ready: 1, problems: 0, created: 0, rows: [] }
    await open()
    await paste()
    answer = { total: 1, ready: 1, problems: 0, created: 1, rows: [] }
    await act(async () => {
      commitButton().click()
    })
    // 서버가 미리보기 결과를 들고 있지 않다 — 그 사이 남이 같은 자산번호를 넣었어도
    // 여기서 다시 걸린다.
    expect(calls[1].path).toContain('dry_run=false')
    expect(calls[1].body).toEqual({ text: PASTED })
    expect(screen.getByText(/등록했습니다/)).toBeTruthy()
  })

  it('비우면 아무것도 안 부른다', async () => {
    answer = { total: 0, ready: 0, problems: 0, created: 0, rows: [] }
    await open()
    await paste('   ')
    // 창을 열자마자, 또는 지우는 중에 빈 요청이 나가면 서버가 400 을 돌려주고
    // 화면에는 아직 아무것도 안 한 사람에게 빨간 오류가 뜬다.
    expect(calls).toHaveLength(0)
  })
})

describe('넣는 동안', () => {
  it('「읽는 중」 이 아니라 「넣는 중」 이라고 말한다', async () => {
    // **한 낱말로 뭉치면 넣는 10초 동안 화면이 거짓말한다.** 실제로 그랬다.
    answer = { total: 3, ready: 3, problems: 0, created: 0, rows: [] }
    await open()
    await paste()

    // 답을 붙잡아 둔 채로 「넣기」 를 누른다 — 그 사이가 사람이 보는 화면이다.
    let release: (value: unknown) => void = () => {}
    const held = new Promise((resolve) => {
      release = resolve
    })
    const client = await import('@/shared/api/client')
    vi.mocked(client.api.post).mockImplementationOnce(async () => held)

    await act(async () => {
      commitButton().click()
    })
    expect(screen.getByText(/넣는 중입니다/)).toBeTruthy()
    expect(screen.queryByText('읽는 중…')).toBeNull()
    // 도중에 닫으면 요청은 계속 가는데 결과를 못 본다.
    const close = screen.getAllByRole('button').find((one) => one.textContent === '닫기')
    expect((close as HTMLButtonElement).disabled).toBe(true)

    await act(async () => {
      release({ total: 3, ready: 3, problems: 0, created: 3, rows: [] })
      await held
    })
    expect(screen.getByText(/등록했습니다/)).toBeTruthy()
  })

  it('오래 걸릴 것 같으면 넣기 전에 말한다', async () => {
    answer = { total: 900, ready: 900, problems: 0, created: 0, rows: [] }
    await open()
    await paste()
    // 900대면 5초쯤. 말 안 하면 사람은 멈춘 줄 알고 창을 닫는다.
    expect(screen.getByText(/초쯤 걸립니다/)).toBeTruthy()
  })

  it('짧으면 시간을 말하지 않는다', async () => {
    answer = { total: 3, ready: 3, problems: 0, created: 0, rows: [] }
    await open()
    await paste()
    // 「1초쯤 걸립니다」 는 아무 도움이 안 되면서 읽을 것만 늘린다.
    expect(screen.queryByText(/초쯤 걸립니다/)).toBeNull()
  })
})

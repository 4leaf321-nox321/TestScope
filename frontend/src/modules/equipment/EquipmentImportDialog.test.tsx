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
  { key: 'asset_no', label: '자산번호', required: true, aliases: ['자산번호', 'asset_no'] },
  { key: 'name', label: '장비명', required: true, aliases: ['장비명', '이름'] },
  { key: 'site', label: '거점', required: true, aliases: ['거점', '보유 거점'] },
  { key: 'note', label: '비고', required: false, aliases: ['비고', 'note'] },
]

const made: { slug: string; value: string }[] = []
const copied: string[] = []

vi.mock('@/shared/lib/clipboard', () => ({
  copyText: vi.fn(async (text: string) => {
    copied.push(text)
  }),
}))

vi.mock('@/modules/vocabulary/api', () => ({
  vocabularyApi: {
    createTerm: vi.fn(async (slug: string, body: { value: string }) => {
      made.push({ slug, value: body.value })
      return { id: 'new' }
    }),
  },
}))

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
  made.length = 0
  copied.length = 0
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

describe('머리글 없이 붙여넣기', () => {
  it('값만 붙이면 커서가 있는 칸부터 채운다', async () => {
    answer = { total: 2, ready: 0, problems: 2, created: 0, rows: [row(), row()] }
    await open()
    // **값만 긁어 오는 것이 실은 더 흔하다.** 표 전체를 갈아 끼우면 첫 줄이
    // 머리글로 읽혀 한 대가 통째로 사라진다.
    await act(async () => {
      fireEvent.paste(cell('장비명', 1), {
        clipboardData: { getData: () => ['만능기\t본사', '충격기\t공장'].join('\n') },
      })
    })
    // 둘째 줄 「장비명」 부터 오른쪽·아래로.
    expect(cell('장비명', 1).value).toBe('만능기')
    expect(cell('거점', 1).value).toBe('본사')
    expect(cell('장비명', 2).value).toBe('충격기')
    expect(cell('거점', 2).value).toBe('공장')
    // 첫 줄은 그대로 비어 있다.
    expect(cell('장비명', 0).value).toBe('')
  })

  it('머리글이 붙어 오면 표를 통째로 갈아 끼운다', async () => {
    answer = { total: 1, ready: 1, problems: 0, created: 0, rows: [row()] }
    await open()
    await act(async () => {
      fireEvent.paste(cell('장비명', 2), {
        clipboardData: { getData: () => ['자산번호\t장비명', 'A-1\t만능기'].join('\n') },
      })
    })
    // 커서가 어디 있든 머리글이 있으면 그것이 표 전체다.
    expect(calls[0].path).toContain('dry_run=true')
    expect(cell('자산번호', 0).value).toBe('A-1')
  })

  it('붙일 것이 남은 줄보다 많으면 줄을 늘린다', async () => {
    await open()
    const before = document.querySelectorAll('tbody tr').length
    const many = Array.from({ length: 12 }, (_, i) => `장비${i}`).join('\n')
    await act(async () => {
      fireEvent.paste(cell('장비명', 0), { clipboardData: { getData: () => many } })
    })
    // 모자라서 잘리면 사람은 그 사실을 모른 채 넣는다.
    expect(document.querySelectorAll('tbody tr').length).toBeGreaterThanOrEqual(12)
    expect(before).toBeLessThan(12)
    expect(cell('장비명', 11).value).toBe('장비11')
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

describe('없는 거점·분류 만들기', () => {
  const missing = (value: string) => ({
    total: 1,
    ready: 0,
    problems: 1,
    created: 0,
    rows: [
      row({
        cells: { asset_no: 'A-1', name: '만능기', site: value, note: '' },
        problems: [
          {
            field: 'site',
            message: `거점: 「${value}」 가 기준정보에 없습니다`,
            make_axis: 'site',
            make_value: value,
          },
        ],
      }),
    ],
  })

  it('그 자리에서 만들 수 있다고 말한다', async () => {
    answer = missing('3공장')
    await open()
    await paste()
    // 「기준정보에서 먼저 만드세요」 하고 멈추면 창을 닫고 나갔다 와야 하고,
    // 그 사이 표에서 고치던 것을 잃는다.
    expect(screen.getByRole('button', { name: /거점 「3공장」 만들기/ })).toBeTruthy()
  })

  it('누르면 축에 값을 만들고 다시 판정받는다', async () => {
    answer = missing('3공장')
    await open()
    await paste()
    calls.length = 0
    answer = { total: 1, ready: 1, problems: 0, created: 0, rows: [row()] }

    await act(async () => {
      screen.getByRole('button', { name: /만들기/ }).click()
    })
    // **반입이 스스로 만들지는 않는다** — 사람이 눌러서 만든다.
    expect(made).toEqual([{ slug: 'site', value: '3공장' }])
    // 표 글자는 안 바뀌었으므로 강제로 다시 물어야 판정이 갱신된다.
    expect(calls).toHaveLength(1)
    expect(commitButton().disabled).toBe(false)
  })

  it('같은 값이 여러 줄에 있어도 단추는 하나다', async () => {
    const one = missing('3공장').rows[0]
    answer = {
      total: 3,
      ready: 0,
      problems: 3,
      created: 0,
      rows: [one, { ...one }, { ...one }],
    }
    await open()
    await paste()
    // 300줄에 같은 거점이 50번 나와도 단추가 50개면 그 줄은 못 읽는다.
    expect(screen.getAllByRole('button', { name: /만들기/ })).toHaveLength(1)
    expect(screen.getByText(/기준정보에 없는 값 1개/)).toBeTruthy()
  })

  it('만들 수 없는 문제에는 단추를 안 준다', async () => {
    answer = {
      total: 1,
      ready: 0,
      problems: 1,
      created: 0,
      rows: [
        row({
          problems: [
            { field: 'model', message: '기종: 하나로 정할 수 없습니다', make_axis: null },
          ],
        }),
      ],
    }
    await open()
    await paste()
    // 카탈로그의 기종은 여기서 만들 수 있는 것이 아니다 — 계열도 사양도 없다.
    expect(screen.queryAllByRole('button', { name: /만들기/ })).toHaveLength(0)
  })
})

describe('엑셀로 되가져가기', () => {
  function copyButton(): HTMLButtonElement {
    return screen
      .getAllByRole('button')
      .find((one) => /복사/.test(one.textContent ?? '')) as HTMLButtonElement
  }

  it('머리글과 값을 탭으로 이어 복사한다', async () => {
    answer = { total: 1, ready: 1, problems: 0, created: 0, rows: [row()] }
    await open()
    await paste()
    await act(async () => {
      copyButton().click()
    })
    const lines = copied[0].split('\n')
    // 엑셀에 붙이면 바로 표가 되어야 한다.
    expect(lines[0].split('\t')).toEqual(['자산번호', '장비명', '거점', '비고', '확인 필요'])
    expect(lines[1].split('\t').slice(0, 3)).toEqual(['A-1', '만능기', '본사'])
  })

  it('문제도 함께 나간다', async () => {
    answer = {
      total: 1,
      ready: 0,
      problems: 1,
      created: 0,
      rows: [
        row({
          problems: [{ field: 'site', message: '거점: 「없는거점」 가 기준정보에 없습니다' }],
        }),
      ],
    }
    await open()
    await paste()
    await act(async () => {
      copyButton().click()
    })
    // 값만 돌려주면 무엇이 틀렸는지가 화면 안에만 남고, 그러면 되가져가는 뜻이 없다.
    expect(copied[0]).toContain('기준정보에 없습니다')
  })

  it('빈 줄은 안 내보낸다', async () => {
    answer = { total: 1, ready: 1, problems: 0, created: 0, rows: [row()] }
    await open()
    await paste()
    await act(async () => {
      copyButton().click()
    })
    // 빈 줄 다섯이 엑셀에 붙으면 지저분하고, 그 줄은 애초에 아무것도 아니다.
    expect(copied[0].split('\n')).toHaveLength(2)
  })

  it('아무것도 안 적었으면 못 누른다', async () => {
    await open()
    expect(copyButton().disabled).toBe(true)
  })

  it('몇 줄을 복사했는지 말해 준다', async () => {
    answer = { total: 1, ready: 1, problems: 0, created: 0, rows: [row()] }
    await open()
    await paste()
    await act(async () => {
      copyButton().click()
    })
    // 말해 주지 않으면 눌렀는지도 모른다.
    expect(copyButton().textContent).toMatch(/1줄 복사했습니다/)
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

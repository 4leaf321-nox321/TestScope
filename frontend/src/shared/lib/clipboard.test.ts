/**
 * 클립보드 — **배포는 평문 http 라 표준 API 가 없다.**
 *
 * 개발은 localhost 라 `navigator.clipboard` 가 멀쩡히 있고, 배포는
 * `http://<서버>:8020` 이라 **아예 없다.** 손으로 한 번 눌러 보는 것으로는 안 걸리는
 * 종류의 고장이라, 두 길을 시험으로 못박는다.
 */

import { describe, expect, it, vi, afterEach } from 'vitest'

import { copyText } from '@/shared/lib/clipboard'

function secure(value: boolean) {
  Object.defineProperty(window, 'isSecureContext', { value, configurable: true })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('글자 복사', () => {
  it('보안 문맥이면 표준 API 를 쓴다', async () => {
    secure(true)
    const written: string[] = []
    vi.stubGlobal('navigator', {
      clipboard: {
        writeText: async (text: string) => {
          written.push(text)
        },
      },
    })
    await copyText('가\t나')
    expect(written).toEqual(['가\t나'])
  })

  it('평문 http 면 옛 길로 간다', async () => {
    // **여기가 사내 배포다.** `navigator.clipboard` 를 그냥 부르면 예외로 죽는다.
    secure(false)
    vi.stubGlobal('navigator', {})
    const asked: string[] = []
    document.execCommand = vi.fn((command: string) => {
      asked.push(command)
      return true
    }) as unknown as typeof document.execCommand

    await copyText('가\t나')
    expect(asked).toEqual(['copy'])
    // 빌려 쓴 칸은 되돌려 놓는다 — 안 지우면 누를 때마다 쌓인다.
    expect(document.querySelectorAll('textarea')).toHaveLength(0)
  })

  it('브라우저가 거절하면 그렇게 말한다', async () => {
    secure(false)
    vi.stubGlobal('navigator', {})
    document.execCommand = vi.fn(() => false) as unknown as typeof document.execCommand
    // 조용히 실패하면 사람은 복사된 줄 알고 엑셀에서 옛 것을 붙인다.
    await expect(copyText('가')).rejects.toThrow(/거절/)
    expect(document.querySelectorAll('textarea')).toHaveLength(0)
  })
})

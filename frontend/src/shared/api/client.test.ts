/**
 * 오류를 읽다가 오류가 나지 않는다.
 *
 * 서버가 봉투가 아닌 것을 내면 `body.error.message` 가 터지고, 화면에는 원인 대신
 * 자바스크립트 예외가 뜬다 — 사람은 요청이 왜 실패했는지가 아니라 **프론트가
 * 깨졌다고** 읽는다. 이 시험이 그 자리를 지킨다.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api, fetchBlobUrl, session } from './client'

function reply(status: number, body: unknown, ok = false): Response {
  return {
    ok,
    status,
    json: async () => body,
  } as Response
}

describe('오류 응답', () => {
  beforeEach(() => {
    session.setToken(null)
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('봉투는 코드와 요청 ID 까지 살린다', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        reply(409, {
          error: {
            code: 'TSC-EQUIPMENT-0003',
            message: '이미 등록된 자산번호입니다: UTM-001',
            request_id: 'abc123',
            details: { asset_no: 'UTM-001' },
          },
        }),
      ),
    )

    const caught = await api.get('/equipment').catch((error: unknown) => error)
    expect(caught).toBeInstanceOf(ApiError)
    const error = caught as ApiError
    expect(error.code).toBe('TSC-EQUIPMENT-0003')
    expect(error.requestId).toBe('abc123')
    expect(error.message).toContain('UTM-001')
    expect(error.details.asset_no).toBe('UTM-001')
  })

  it('봉투가 아니어도 서버가 한 말을 살린다', async () => {
    // FastAPI 가 detail 로 내는 경우. 그 말을 버리면 무엇이 잘못됐는지가 통째로
    // 사라진다.
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => reply(405, { detail: 'Method Not Allowed' })),
    )

    const error = (await api.get('/equipment').catch((one: unknown) => one)) as ApiError
    expect(error).toBeInstanceOf(ApiError)
    expect(error.code).toBe('TSC-CLIENT-0001')
    expect(error.message).toContain('Method Not Allowed')
    expect(error.message).toContain('405')
  })

  it('JSON 이 아니어도 터지지 않는다', async () => {
    // HTML 오류 페이지나 빈 본문. 여기서 예외가 나면 원인이 완전히 묻힌다.
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          ({
            ok: false,
            status: 502,
            json: async () => {
              throw new Error('not json')
            },
          }) as unknown as Response,
      ),
    )

    const error = (await api.get('/equipment').catch((one: unknown) => one)) as ApiError
    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(502)
  })
})

describe('요청', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    session.setToken(null)
  })

  it('토큰이 있으면 헤더에 싣고 상대주소로 부른다', async () => {
    // **인자를 받는 모양으로 선언한다.** 인자 없는 mock 은 calls[0] 이 빈
    // 튜플로 잡혀서, 꺼내 쓰려면 unknown 을 거치는 이중 캐스트가 된다 — 그러면
    // 시험이 실제 호출 모양과 어긋나도 타입이 안 잡아 준다.
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) =>
      reply(200, { items: [] }, true),
    )
    vi.stubGlobal('fetch', fetchMock)
    session.setToken('token-value')

    await api.get('/equipment')

    const [url, init] = fetchMock.mock.calls[0]
    // **절대주소를 갖지 않는다.** 구우면 값이 빠졌을 때 사용자 브라우저가 자기
    // PC 를 부른다.
    expect(url).toBe('/api/equipment')
    const headers = init?.headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer token-value')
    expect(init?.credentials).toBe('same-origin')
  })

  it('204 는 본문을 읽지 않는다', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          ({
            ok: true,
            status: 204,
            json: async () => {
              throw new Error('본문이 없다')
            },
          }) as unknown as Response,
      ),
    )
    await expect(api.delete('/equipment/1')).resolves.toBeUndefined()
  })
})

describe('파일 받아 오기', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    session.setToken(null)
  })

  it('서버가 준 주소를 **그대로** 부른다 — `/api` 를 또 붙이지 않는다', async () => {
    /**
     * 실측(2026-09-24): `fetchBlobUrl` 이 `send()` 를 거치면서 BASE(`/api`)를 한 번 더
     * 붙여 `/api/api/attachments/…` 로 나갔다. 404 가 나고 화면에는 「못 읽음」 네모만
     * 떠서, 첨부 기능이 나간 뒤로 **이미지가 한 장도 안 보였다.**
     *
     * 화면 시험은 `fetchBlobUrl` 을 통째로 흉내 내고 있어서 이 자리를 못 봤다. 주소를
     * 만드는 것은 클라이언트의 일이므로 그 시험이 여기 있어야 한다.
     */
    const seen: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        seen.push(url)
        return {
          ok: true,
          status: 200,
          blob: async () => new Blob([new Uint8Array([1, 2, 3])], { type: 'image/png' }),
        } as unknown as Response
      }),
    )
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: () => 'blob:그림',
    })

    await fetchBlobUrl('/api/attachments/a1/file')
    expect(seen).toEqual(['/api/attachments/a1/file'])
  })

  it('자격을 싣는다 — 안 실으면 401 이고, 그 오류는 화면에 안 남는다', async () => {
    let sent: HeadersInit | undefined
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init?: RequestInit) => {
        sent = init?.headers
        return {
          ok: true,
          status: 200,
          blob: async () => new Blob([]),
        } as unknown as Response
      }),
    )
    vi.stubGlobal('URL', { ...URL, createObjectURL: () => 'blob:그림' })

    session.setToken('토큰')
    await fetchBlobUrl('/api/attachments/a1/file')
    expect((sent as Record<string, string>).Authorization).toBe('Bearer 토큰')
  })

  it('못 받으면 봉투 오류로 던진다 — 조용히 빈 그림을 두지 않는다', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => reply(404, { error: { code: 'TSC-ATTACH-0001', message: '없음' } })),
    )
    const caught = await fetchBlobUrl('/api/attachments/없는것/file').catch(
      (error: unknown) => error,
    )
    expect(caught).toBeInstanceOf(ApiError)
    expect((caught as ApiError).status).toBe(404)
  })
})

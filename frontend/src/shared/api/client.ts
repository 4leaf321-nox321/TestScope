/**
 * API 클라이언트.
 *
 * **절대 주소를 갖지 않는다.** 개발에서는 Vite 프록시가, 배포에서는 같은 프로세스가
 * /api 를 받는다. 빌드 시 API 주소를 굽는 방식은 값이 빠지면 사용자 브라우저가
 * 자기 PC 를 부르는 사고가 나고, 그걸 막으려면 빌드 산출물을 검사하는 단계를 따로
 * 둬야 한다. 상대경로면 그 사고 자체가 없다.
 *
 * **access 토큰은 여기 메모리에만 둔다.** localStorage 에 두면 XSS 한 번에
 * 탈취된다. 새로고침하면 사라지지만, refresh 쿠키(httpOnly)로 다시 받아온다.
 */

const BASE = '/api'

/** 백엔드 오류 규약 (app/shared/errors.py 와 짝) */
export interface ApiErrorBody {
  error: {
    code: string
    message: string
    request_id?: string
    details?: Record<string, unknown>
  }
}

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly requestId: string | undefined
  readonly details: Record<string, unknown>

  constructor(status: number, body: ApiErrorBody) {
    super(body.error.message)
    this.name = 'ApiError'
    this.status = status
    this.code = body.error.code
    this.requestId = body.error.request_id
    this.details = body.error.details ?? {}
  }
}

let accessToken: string | null = null
let onSessionLost: (() => void) | null = null

export const session = {
  setToken(token: string | null) {
    accessToken = token
  },
  getToken() {
    return accessToken
  },
  /** 갱신까지 실패했을 때 호출된다 — AuthContext 가 로그인 화면으로 보낸다. */
  onLost(handler: (() => void) | null) {
    onSessionLost = handler
  },
}

/** 봉투인가. **모양을 확인하고 나서 읽는다.** */
function isEnvelope(value: unknown): value is ApiErrorBody {
  const error = (value as ApiErrorBody | null)?.error
  return typeof error?.code === 'string' && typeof error?.message === 'string'
}

/**
 * 서버가 봉투 대신 무언가를 말했다면 **그 말을 살린다.**
 *
 * FastAPI 는 detail 로 낸다. 그것을 버리고 "예상하지 못한 응답" 만 띄우면 무엇이
 * 잘못됐는지가 통째로 사라진다.
 */
function said(value: unknown): string {
  const detail = (value as { detail?: unknown } | null)?.detail
  return typeof detail === 'string' && detail ? ` — ${detail}` : ''
}

/**
 * 오류 응답을 ApiError 로. **여기서 오류가 나면 안 된다.**
 *
 * 봉투가 아닌 JSON 이 오면 body.error.message 가 터지고, 화면에는 원인 대신
 * 자바스크립트 예외가 뜬다 — 사람은 요청이 왜 실패했는지가 아니라 프론트가
 * 깨졌다고 읽는다.
 */
async function parseError(response: Response): Promise<ApiError> {
  let parsed: unknown = null
  try {
    parsed = await response.json()
  } catch {
    // JSON 도 아니다 — HTML 오류 페이지나 빈 본문.
  }
  if (isEnvelope(parsed)) return new ApiError(response.status, parsed)
  return new ApiError(response.status, {
    error: {
      code: 'TSC-CLIENT-0001',
      message: `서버가 예상하지 못한 응답을 보냈습니다 (HTTP ${response.status})${said(parsed)}`,
    },
  })
}

async function send(path: string, init?: RequestInit): Promise<Response> {
  // FormData 일 때 Content-Type 을 직접 넣으면 **안 된다.** multipart 는 본문에
  // boundary 문자열이 필요한데, 브라우저가 헤더를 만들 때 그것을 붙여 준다.
  const isForm = init?.body instanceof FormData
  return fetch(`${BASE}${path}`, {
    ...init,
    credentials: 'same-origin', // refresh 쿠키
    headers: {
      ...(isForm ? {} : { 'Content-Type': 'application/json' }),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...init?.headers,
    },
  })
}

/** refresh 한 번의 결과 — 본문은 한 번만 읽히므로 읽어서 나눠 준다. */
interface RefreshOutcome {
  ok: boolean
  status: number
  body: unknown
}

let refreshing: Promise<RefreshOutcome> | null = null

/**
 * **refresh 는 한 번에 하나만 나간다.**
 *
 * React StrictMode 는 effect 를 두 번 돌린다. 앱이 뜰 때 /auth/refresh 가 같은
 * 쿠키로 둘 나가면, 서버는 회전 직후의 옛 값이 다시 쓰인 것을 보고 그것을 탈취로
 * 판정해 세션을 전부 끊는다 — 다시 로그인해도 다음 로드에서 또 끊긴다.
 *
 * 서버도 회전 직후의 옛 값을 봐 주지만(유예 창), 애초에 둘을 보내지 않는 것이
 * 맞다. 진행 중인 요청이 있으면 그 약속을 같이 기다린다.
 */
function refreshOnce(): Promise<RefreshOutcome> {
  if (!refreshing) {
    refreshing = fetch(`${BASE}/auth/refresh`, { method: 'POST', credentials: 'same-origin' })
      .then(async (response) => {
        let body: unknown = null
        try {
          body = await response.json()
        } catch {
          // 본문 없는 401 등. 아래에서 상태만으로 판단한다.
        }
        const token = (body as { access_token?: unknown } | null)?.access_token
        if (response.ok && typeof token === 'string') accessToken = token
        return { ok: response.ok, status: response.status, body }
      })
      .finally(() => {
        refreshing = null
      })
  }
  return refreshing
}

/** 조용한 갱신. 성공하면 새 access 토큰을 보관한다. */
export async function tryRefresh(): Promise<boolean> {
  return (await refreshOnce()).ok
}

/**
 * 앱 기동 때의 갱신 — 세션(사용자 정보)까지 돌려준다.
 *
 * api.post 와 같은 일이지만 **동시 호출을 하나로 합친다**(위 주석 참고).
 */
export async function refreshSession<T>(): Promise<T> {
  const outcome = await refreshOnce()
  if (!outcome.ok) {
    if (isEnvelope(outcome.body)) throw new ApiError(outcome.status, outcome.body)
    throw new ApiError(outcome.status, {
      error: {
        code: 'TSC-CLIENT-0001',
        message: `세션을 되살리지 못했습니다 (HTTP ${outcome.status})${said(outcome.body)}`,
      },
    })
  }
  return outcome.body as T
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response = await send(path, init)

  // access 는 12시간이면 만료된다. 사용자가 그 순간 하던 일을 잃지 않도록 한 번만
  // 조용히 갱신하고 재시도한다. /auth/* 는 제외 — 갱신 자체가 실패한 상황에서
  // 무한 재귀가 된다.
  if (response.status === 401 && !path.startsWith('/auth/')) {
    if (await tryRefresh()) {
      response = await send(path, init)
    } else {
      onSessionLost?.()
    }
  }

  if (!response.ok) throw await parseError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/**
 * 파일 내려받기. **평범한 링크로는 안 된다.**
 *
 * access 토큰은 메모리에만 있고 쿠키가 아니므로, 브라우저가 스스로 여는 주소
 * (a href · img src · iframe)에는 실리지 않는다. 그래서 그런 링크는 항상 401 이
 * 나는데, 그 오류는 새 탭에서 나므로 **화면에는 아무 표시도 안 뜬다** — 사용자는
 * 아무 일도 안 일어난 것처럼 본다.
 */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const response = await send(path)
  if (!response.ok) throw await parseError(response)

  const url = URL.createObjectURL(await response.blob())
  try {
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    anchor.click()
  } finally {
    // 즉시 해제하면 저장이 시작되기 전에 사라지는 브라우저가 있다.
    setTimeout(() => URL.revokeObjectURL(url), 10_000)
  }
}

/**
 * 그림을 화면에 그릴 주소. **`<img src>` 에 API 주소를 그대로 못 쓴다** —
 * 위의 `downloadFile` 과 같은 이유다: 토큰이 메모리에만 있어 브라우저가 스스로 여는
 * 주소에는 안 실리고, 그러면 401 이 나는데 그 오류는 화면에 아무 표시도 안 남긴다
 * (사용자는 그냥 깨진 그림을 본다).
 *
 * 그래서 자격을 실어 받아 온 뒤 blob 주소를 만든다. **쓰고 나면 돌려줘야 한다** —
 * 부르는 쪽이 `URL.revokeObjectURL` 을 하지 않으면 그 탭이 살아 있는 동안 메모리에 남는다.
 */
export async function fetchBlobUrl(path: string): Promise<string> {
  const response = await send(path)
  if (!response.ok) throw await parseError(response)
  return URL.createObjectURL(await response.blob())
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body ?? {}) }),
  /** 한 벌을 통째로 갈아 끼우는 자원에 쓴다(조건 한 칸 같은 것). */
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body ?? {}) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body ?? {}) }),
  delete: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'DELETE',
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    }),
  /** 파일 올리기. **Content-Type 을 우리가 정하지 않는다** — 브라우저가 multipart
   *  경계 문자열과 함께 넣는다. 손으로 적으면 서버가 본문을 못 가른다. */
  upload: <T>(path: string, form: FormData) =>
    request<T>(path, { method: 'POST', body: form }),
}

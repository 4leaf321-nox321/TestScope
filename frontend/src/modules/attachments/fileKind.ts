/**
 * 이 파일을 화면에서 어떻게 다루나 — **그릴 수 있는 것과 없는 것.**
 *
 * 사내 규격서 원본은 한글·워드·엑셀로 온다. 브라우저는 그 형식들을 못 그리고, MS·구글의
 * 온라인 뷰어는 파일이 인터넷에 공개돼 있어야 해서 사내망에서는 원리상 못 쓴다 — 그래서
 * **받아 두고 내려받게 하는 것**이 지금의 답이고, 화면이 그렇게 말해야 한다. 안 말하면
 * `<img>` 가 워드 파일을 그리려다 깨진 그림을 보이고, 사람은 「올리기가 잘못됐나」 한다.
 *
 * 판정을 세 군데(줄·크게 보기·고르기)에 나눠 두면 갈라진다 — 여기 한 벌만 둔다.
 */

export type FileKind = 'image' | 'pdf' | 'document'

const BY_EXTENSION: Record<string, FileKind> = {
  png: 'image',
  jpg: 'image',
  jpeg: 'image',
  webp: 'image',
  gif: 'image',
  pdf: 'pdf',
  doc: 'document',
  docx: 'document',
  xls: 'document',
  xlsx: 'document',
  ppt: 'document',
  pptx: 'document',
  hwp: 'document',
  hwpx: 'document',
}

/** 무엇으로 여는가 — 상자에 쓰는 말은 `application/msword` 가 아니라 「워드」 다. */
const PROGRAMS: Record<string, string> = {
  doc: '워드',
  docx: '워드',
  xls: '엑셀',
  xlsx: '엑셀',
  ppt: '파워포인트',
  pptx: '파워포인트',
  hwp: '한글',
  hwpx: '한글',
}

/** 고르기 창이 여는 형식. **확장자로 적는다** — 한글(.hwp)은 브라우저가 형식을 모른다. */
export const ACCEPT =
  '.png,.jpg,.jpeg,.webp,.gif,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.hwp,.hwpx'

/** 사람에게 말하는 형식. 열네 개를 다 적으면 아무도 안 읽는다. */
export const ACCEPT_WORDS = 'pdf · png · jpg · 워드 · 엑셀 · 한글'

export function extensionOf(name: string): string {
  const at = name.lastIndexOf('.')
  return at <= 0 ? '' : name.slice(at + 1).toLowerCase()
}

/**
 * 이 줄을 어떻게 그릴까.
 *
 * **이름을 먼저 본다** — 형식은 바이트의 것이고 이름은 붙은 줄의 것이다. 같은 내용은 한
 * 벌로 모이므로(sha256) `content_type` 은 그 바이트를 **처음 올린 줄**의 것이 된다.
 */
export function kindOf(row: { content_type: string; original_name: string }): FileKind {
  const known = BY_EXTENSION[extensionOf(row.original_name)]
  if (known) return known
  if (row.content_type === 'application/pdf') return 'pdf'
  if (row.content_type.startsWith('image/')) return 'image'
  return 'document'
}

/** 상자에 쓸 짧은 말 — 「무엇으로 여는가」. */
export function programOf(row: { content_type: string; original_name: string }): string {
  const extension = extensionOf(row.original_name)
  if (!extension) return kindOf(row) === 'pdf' ? 'PDF' : '파일'
  return PROGRAMS[extension] ?? extension.toUpperCase()
}

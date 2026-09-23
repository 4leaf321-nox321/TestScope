/**
 * 항목 종류 — 화면의 말, 그리고 **친 글자에서 종류를 알아맞히기.**
 *
 * 종류를 고르라고 하면 사람은 귀찮아서 전부 「문장」 으로 넣는다. 그러면 `85℃` 가 글자로
 * 저장되고 나중에 「80 이상」 을 못 묻는다. 그래서 값 칸에 친 글자의 **모양**을 보고 종류를
 * 제안한다 — `85℃` → 수치 85 · 단위 ℃, `-40~125` → 구간, `2024-03-01` → 날짜. 사람은 확인만.
 */

export type AttributeKind =
  | 'number'
  | 'range'
  | 'text'
  | 'boolean'
  | 'date'
  | 'choice'
  | 'condition'
  | 'term'
  | 'method'
  | 'pairs'
  | 'matrix'

export const KIND_LABEL: Record<AttributeKind, string> = {
  number: '수치',
  range: '구간',
  text: '문장',
  boolean: '있음/없음',
  date: '날짜',
  choice: '선택',
  condition: '시험 조건',
  term: '기준정보',
  method: '규격',
  pairs: '이름별 수량',
  matrix: '사양별 수량',
}

/** 짝의 목록을 쓰는 종류 — 값이 하나가 아니라 `json_value` 에 담긴다. */
export function isPaired(kind: string): boolean {
  return kind === 'pairs' || kind === 'matrix'
}

/** `pairs` 의 한 줄. 이름 없는 숫자는 서버가 거절한다. */
export interface Pair {
  label: string
  value: number | null
}

/** `matrix` 의 한 줄 — 사양 하나에 그 사양의 짝들. */
export interface MatrixRow {
  label: string
  entries: Pair[]
}

/** 새 초안으로 만들 수 있는 종류. 축·선택지가 필요한 것은 관리자가 정의부터 만든다. */
export const DRAFT_KINDS: AttributeKind[] = ['number', 'range', 'text', 'boolean', 'date']

/** 수치 칸을 쓰는 종류 — 단위는 이들만 뜻이 있다. */
export function isNumeric(kind: string): boolean {
  return kind === 'number' || kind === 'range' || kind === 'condition'
}

export interface Detected {
  kind: 'number' | 'range' | 'date' | 'text'
  numValue?: number
  numMin?: number
  numMax?: number
  unit?: string
  text?: string
}

const NUMBER = String.raw`[-+]?\d+(?:[.,]\d+)?`
const RANGE = new RegExp(
  `^\\s*(${NUMBER})\\s*(?:~|〜|-|–|—|to|~)\\s*(${NUMBER})\\s*([^\\d\\s].*)?$`,
  'i',
)
// 단위는 숫자·부호로 시작하지 않는다 — 「-40-125」 가 「-40 에 단위 -125」 로 읽히지 않게.
const SINGLE = new RegExp(`^\\s*(${NUMBER})\\s*([^\\d\\s+\\-].*)?$`)
const DATE = /^\s*(\d{4})[-./](\d{1,2})[-./](\d{1,2})\s*$/

function num(raw: string): number {
  return Number(raw.replace(',', '.'))
}

/**
 * 친 글자에서 종류와 값을 뽑는다. 못 알아보면 문장.
 *
 * `-40~125 ℃` 처럼 앞의 음수와 구간의 하이픈이 섞이는 것은 `~` 를 우선해 가른다 — 하이픈만
 * 있는 `-40-125` 는 구간으로 읽지 않는다(음수 둘인지 구간인지 사람도 모른다).
 */
export function detect(raw: string): Detected {
  const text = raw.trim()
  if (!text) return { kind: 'text', text: '' }
  const date = DATE.exec(text)
  if (date) {
    const [, y, m, d] = date
    return { kind: 'date', text: `${y}-${m.padStart(2, '0')}-${d.padStart(2, '0')}` }
  }
  if (/[~〜–—]|\bto\b/i.test(text)) {
    const range = RANGE.exec(text)
    if (range) {
      return {
        kind: 'range',
        numMin: num(range[1]),
        numMax: num(range[2]),
        unit: (range[3] ?? '').trim(),
      }
    }
  }
  const single = SINGLE.exec(text)
  if (single) {
    const unit = (single[2] ?? '').trim()
    // 단위 자리에 글이 길게 오면 수치가 아니라 문장이다 — 「5개 이상 준비」.
    if (unit.length <= 12) return { kind: 'number', numValue: num(single[1]), unit }
  }
  return { kind: 'text', text }
}

/** 단위 표기를 서버가 아는 꼴로. `℃` · `°C` → degC. 화면은 친 대로 보여 주고 저장만 이걸로. */
export function normalizeUnitInput(raw: string): string {
  return raw.trim().replace(/℃|°C/gi, 'degC').replace(/µ/g, 'u')
}

/** 단위 자동완성 후보 — 조건 축·사양 정의에 있는 단위와 겹치는 흔한 것들. */
export const COMMON_UNITS = [
  'degC',
  '%',
  'h',
  'min',
  's',
  'cycle',
  'kN',
  'N',
  'MPa',
  'mm',
  'mm/min',
  'Hz',
  'V',
  'A',
  'g',
  'kg',
  '개',
]

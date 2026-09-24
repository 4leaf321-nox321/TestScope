/**
 * 단위 환산 — **원문 단위로 적게 두고, 저장 단위로 바꾼다.**
 *
 * 사양을 채우는 사람은 카탈로그를 보며 옮겨 적는다. 카탈로그는 「4,000 cP」 라고 적혀
 * 있는데 우리 사양 정의는 Pa·s 다. 지금까지는 사람이 머리로 1 cP = 0.001 Pa·s 를 곱해야
 * 했고, **그 자리가 자릿수를 틀리는 자리**다 — 1,600,000,000 cP 를 옮기며 0 을 하나
 * 빠뜨리면 검색은 그 틀린 값으로 자신 있게 답한다.
 *
 * 그래서 값 칸이 「4000 cP」 를 그대로 받는다. 아는 단위면 바꿔 넣고 **무엇을 무엇으로
 * 바꿨는지 화면에 적는다**; 모르는 단위면 **거절한다** — 조용히 숫자만 취하면 cP 를
 * Pa·s 로 읽은 값이 천 배 틀린 채로 들어간다.
 *
 * ## 온도는 곱셈이 아니다
 *
 * K 와 °C 는 배율이 아니라 **자리 옮김**이다(K = °C + 273.15). 같은 표에 배율로 적으면
 * 0 °C 가 0 K 가 된다 — 그래서 따로 다룬다.
 *
 * ## 여기 없는 단위는 모른다고 말한다
 *
 * 표를 부풀리는 대신 **모르면 모른다**고 한다. 아는 척해서 틀린 값을 넣는 것보다, 사람이
 * 직접 환산해 적는 편이 낫다(ADR 0003).
 */

/** 단위 하나 — 어느 차원의 것이고, 기준 단위로 가려면 얼마를 곱하나. */
interface Unit {
  dimension: string
  /** 기준 단위로 가는 배율. 기준 단위 자신은 1. */
  factor: number
}

/** 표기 흔들림을 하나로. `°C` · `degC`, `µm` · `um`, `N·m` · `Nm`. */
export function normalizeUnit(raw: string): string {
  return raw
    .trim()
    .replace(/°C/gi, 'degc')
    .replace(/℃/g, 'degc')
    .replace(/µ/g, 'u')
    .replace(/·/g, '')
    .replace(/\s+/g, '')
    .replace(/\^/g, '')
    .toLowerCase()
}

/** 아는 단위들. 차원마다 기준 단위 하나를 두고 나머지는 배율로 건다. */
const UNITS: Record<string, Unit> = {}

function define(dimension: string, table: Record<string, number>) {
  for (const [name, factor] of Object.entries(table)) {
    UNITS[normalizeUnit(name)] = { dimension, factor }
  }
}

define('force', {
  N: 1,
  kN: 1000,
  MN: 1e6,
  mN: 1e-3,
  uN: 1e-6,
  nN: 1e-9,
  kgf: 9.80665,
  gf: 0.00980665,
})
define('length', {
  m: 1,
  km: 1000,
  cm: 0.01,
  mm: 1e-3,
  µm: 1e-6,
  um: 1e-6,
  nm: 1e-9,
  pm: 1e-12,
})
define('mass', { kg: 1, g: 1e-3, mg: 1e-6, t: 1000 })
// 압력과 응력은 같은 차원이다 — 「20 MPa 이상」 과 「20 MPa 까지」 는 같은 단위를 쓴다.
define('pressure', {
  Pa: 1,
  kPa: 1000,
  MPa: 1e6,
  GPa: 1e9,
  bar: 1e5,
  mbar: 100,
  psi: 6894.757,
})
define('time', { s: 1, ms: 1e-3, us: 1e-6, ns: 1e-9, min: 60, h: 3600 })
define('frequency', { Hz: 1, kHz: 1000, MHz: 1e6, GHz: 1e9 })
define('voltage', { V: 1, mV: 1e-3, kV: 1000, uV: 1e-6 })
define('current', { A: 1, mA: 1e-3, uA: 1e-6, kA: 1000 })
define('power', { W: 1, mW: 1e-3, kW: 1000, MW: 1e6 })
define('torque', {
  'N·m': 1,
  Nm: 1,
  'mN·m': 1e-3,
  mNm: 1e-3,
  'nN·m': 1e-9,
  nNm: 1e-9,
  kgfcm: 0.0980665,
})
define('energy', { J: 1, kJ: 1000, mJ: 1e-3, Wh: 3600, kWh: 3.6e6 })
// 점도 — 카탈로그가 cP 로 적는 일이 많고(1 cP = 1 mPa·s), 우리 정의는 Pa·s 다.
define('viscosity', {
  'Pa·s': 1,
  Pas: 1,
  'mPa·s': 1e-3,
  mPas: 1e-3,
  cP: 1e-3,
  P: 0.1,
  cSt: NaN,
})
define('angle', { deg: 1, '°': 1, rad: 57.29577951308232 })
define('volume', { L: 1, mL: 1e-3, 'm³': 1000, m3: 1000, cc: 1e-3 })
define('speed', { 'mm/min': 1, 'mm/s': 60, 'm/min': 1000, 'm/s': 60000, 'um/min': 1e-3 })
define('ratio', { '%': 1, pct: 1, ppm: 1e-4 })

// cSt(동점도)는 점도가 아니다 — 밀도를 알아야 Pa·s 가 된다. 표에서 지운다: 남겨 두면
// NaN 이 조용히 흘러 들어간다.
delete UNITS[normalizeUnit('cSt')]

/** 온도는 자리 옮김이라 따로 본다. */
const TEMPERATURE: Record<string, { toC: (value: number) => number }> = {
  degc: { toC: (value) => value },
  c: { toC: (value) => value },
  k: { toC: (value) => value - 273.15 },
  f: { toC: (value) => ((value - 32) * 5) / 9 },
  degf: { toC: (value) => ((value - 32) * 5) / 9 },
}

function fromC(value: number, unit: string): number | null {
  switch (unit) {
    case 'degc':
    case 'c':
      return value
    case 'k':
      return value + 273.15
    case 'f':
    case 'degf':
      return (value * 9) / 5 + 32
    default:
      return null
  }
}

export interface Converted {
  value: number
  /** 바꿨으면 사람이 읽는 말 — 「4000 cP → 4 Pa·s」. 안 바꿨으면 없다. */
  note?: string
}

export interface ConvertError {
  error: string
}

export type ConvertResult = Converted | ConvertError | null

export function isError(result: ConvertResult): result is ConvertError {
  return result !== null && 'error' in result
}

/** 사람이 읽기 좋은 자릿수로. 1.6e6 을 「1600000」 으로, 4.0000000001 을 「4」 로. */
function tidy(value: number): number {
  if (!Number.isFinite(value)) return value
  const rounded = Number(value.toPrecision(12))
  return Object.is(rounded, -0) ? 0 : rounded
}

/**
 * 사람이 친 글자를 그 칸의 단위로 바꾼다.
 *
 * - 빈 칸이면 `null` — 안 적은 것이다.
 * - 숫자만 있으면 그대로(그 칸의 단위로 적었다고 본다).
 * - 「4000 cP」 처럼 단위가 붙었고 바꿀 수 있으면 바꾼 값과 그 사실을 돌려준다.
 * - 모르는 단위거나 차원이 다르면 **거절한다**.
 */
export function convertValue(raw: string, targetUnit: string): ConvertResult {
  const text = raw.trim()
  if (!text) return null

  const match = /^([-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?)\s*(.*)$/.exec(text)
  if (!match) return { error: '숫자로 시작해야 합니다' }
  const value = Number(match[1].replace(',', '.'))
  if (!Number.isFinite(value)) return { error: '숫자가 아닙니다' }

  const typed = match[2].trim()
  if (!typed) return { value }

  const from = normalizeUnit(typed)
  const to = normalizeUnit(targetUnit || '')
  if (from === to) return { value }

  // 온도 먼저 — 배율이 아니라 자리 옮김이다.
  if (TEMPERATURE[from] && TEMPERATURE[to]) {
    const celsius = TEMPERATURE[from].toC(value)
    const out = fromC(celsius, to)
    if (out === null) return { error: `${targetUnit} 로 바꿀 수 없습니다` }
    return { value: tidy(out), note: `${text} → ${tidy(out)} ${targetUnit}` }
  }

  const source = UNITS[from]
  const target = UNITS[to]
  if (!source)
    return {
      error: `모르는 단위입니다 (${typed}) — 이 칸의 단위(${targetUnit || '없음'})로 적으십시오`,
    }
  if (!target) return { error: `이 칸은 단위가 ${targetUnit || '없음'} 이라 바꿀 수 없습니다` }
  if (source.dimension !== target.dimension) {
    return { error: `${typed} 는 ${targetUnit} 로 바꿀 수 없습니다 — 재는 것이 다릅니다` }
  }
  const out = tidy((value * source.factor) / target.factor)
  return { value: out, note: `${text} → ${out} ${targetUnit}` }
}

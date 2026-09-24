/**
 * 온톨로지에서 온 사람에게만 「← 온톨로지」 를 준다.
 *
 * 목록 화면(장비 계열·기종·시험법·보유 장비 …)은 사이드바로도 오는 곳이라 늘 되돌아가는 문을
 * 달면 「이 화면은 온톨로지의 하위인가」 로 읽힌다. 온톨로지의 「목록 · 등록」 으로 왔을 때만
 * (`?from=reference:<종류>`) 문이 서고, 돌아가면 그 종류가 골라져 있다.
 */

import { useSearchParams } from 'react-router-dom'

export function useBackFromReference(): { to: string; label: string } | undefined {
  const [params] = useSearchParams()
  const from = params.get('from')
  if (!from || !from.startsWith('reference')) return undefined
  const kind = from.includes(':') ? from.slice(from.indexOf(':') + 1) : ''
  return {
    to: kind ? `/admin/ontology?kind=${encodeURIComponent(kind)}` : '/admin/ontology',
    label: '온톨로지',
  }
}

/** 온톨로지에서 목록으로 가는 주소 — 되돌아올 표식을 붙인다. */
export function fromReference(path: string, kind: string): string {
  const joiner = path.includes('?') ? '&' : '?'
  return `${path}${joiner}from=${encodeURIComponent(`reference:${kind}`)}`
}

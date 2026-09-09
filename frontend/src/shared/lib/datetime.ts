/**
 * 날짜·시각 표시 — **절대 시각으로 적는다.**
 *
 * "3일 전" 은 읽는 시점에 따라 달라져서, 화면을 캡처해 주고받는 순간 뜻을 잃는다.
 */

/** 2026-09-08. 목록의 날짜 칸. */
export function shownDate(raw: string | null | undefined): string {
  if (!raw) return '—'
  const when = new Date(raw)
  return Number.isNaN(when.getTime()) ? raw : when.toLocaleDateString('ko-KR')
}

/** 2026-09-08 14:32. 로그처럼 시각이 필요한 자리에만. */
export function shownDateTime(raw: string | null | undefined): string {
  if (!raw) return '—'
  const when = new Date(raw)
  if (Number.isNaN(when.getTime())) return raw
  return `${when.toLocaleDateString('ko-KR')} ${when.toLocaleTimeString('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
  })}`
}

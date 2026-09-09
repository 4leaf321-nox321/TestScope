/**
 * 상태 배지 — **말과 색을 한 곳에서 정한다.**
 *
 * 장비 상태·역량 신뢰도·계정 상태가 화면마다 제 색을 고르면, 같은 "점검 중" 이
 * 목록에서는 회색이고 상세에서는 노랑이 된다. 그러면 색이 아무 뜻도 못 갖는다.
 */

import { cn } from '@/shared/lib/utils'

type Tone = 'neutral' | 'good' | 'warn' | 'bad'

const TONE_CLASS: Record<Tone, string> = {
  neutral: 'bg-muted text-muted-foreground',
  good: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
  warn: 'bg-amber-500/10 text-amber-700 dark:text-amber-400',
  bad: 'bg-destructive/10 text-destructive',
}

/** 장비 상태. **폐기는 나쁨이 아니라 중립이다** — 사고가 아니라 생애의 끝이다. */
const EQUIPMENT: Record<string, { label: string; tone: Tone }> = {
  operational: { label: '가동', tone: 'good' },
  maintenance: { label: '점검·교정', tone: 'warn' },
  repair: { label: '고장', tone: 'bad' },
  retired: { label: '폐기', tone: 'neutral' },
}

/** 역량을 어디까지 믿을 수 있나. */
const CONFIDENCE: Record<string, { label: string; tone: Tone }> = {
  verified: { label: '검증됨', tone: 'good' },
  catalog: { label: '사양서', tone: 'neutral' },
  limited: { label: '조건부', tone: 'warn' },
}

const ACCOUNT: Record<string, { label: string; tone: Tone }> = {
  active: { label: '정상', tone: 'good' },
  pending: { label: '승인 대기', tone: 'warn' },
  suspended: { label: '정지', tone: 'bad' },
}

/** 검색 결과 한 줄의 판정. **모름을 됨과 섞지 않는 것이 이 화면의 핵심이다.** */
const VERDICT: Record<string, { label: string; tone: Tone }> = {
  match: { label: '조건 충족', tone: 'good' },
  partial: { label: '일부 미상', tone: 'warn' },
  unknown: { label: '조건 미상', tone: 'neutral' },
}

const TABLES = {
  equipment: EQUIPMENT,
  confidence: CONFIDENCE,
  account: ACCOUNT,
  verdict: VERDICT,
} as const

export function StatusBadge({
  kind,
  value,
  className,
}: {
  kind: keyof typeof TABLES
  value: string
  className?: string
}) {
  // 모르는 값도 **그대로 보여 준다.** 빈 칸으로 두면 데이터가 없는 것처럼 읽히는데,
  // 실제로는 표에 없는 새 값이 들어온 것이다.
  const found = TABLES[kind][value] ?? { label: value, tone: 'neutral' as Tone }
  return (
    <span
      className={cn(
        'inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium',
        TONE_CLASS[found.tone],
        className,
      )}
    >
      {found.label}
    </span>
  )
}

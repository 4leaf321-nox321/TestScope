/**
 * 장비 상태의 **말과 순서를 한 곳에서 정한다.**
 *
 * 등록 폼·수정 폼·목록 필터가 각자 목록을 적으면, 한 화면에만 「유휴」 가 빠지는 날이
 * 온다 — 그러면 그 상태의 장비는 그 화면에서 영영 안 만들어지고 안 걸러진다.
 *
 * 색은 `StatusBadge` 가 갖는다(같은 상태가 화면마다 다른 색이면 색이 뜻을 잃는다).
 * 여기는 **고를 것의 목록**이다.
 */

export interface StatusOption {
  value: string
  label: string
}

/**
 * 생애의 순서대로. 들어와서(입고) 돌다가(가동·미가동·미사용) 멈추고(점검·고장) 끝난다(폐기).
 *
 * **뒤의 둘은 생애가 아니라 대장의 사정이다.** 「취소선」 은 원본 대장에서 줄이 그어진
 * 것이고(폐기와 다르다 — 왜 그었는지는 대장이 안 말한다), 「미기재」 는 상태 칸이 비어
 * 있던 것이다. 둘 다 지어내는 것보다 그대로 두는 편이 낫다.
 */
export const EQUIPMENT_STATUS_OPTIONS: StatusOption[] = [
  { value: 'incoming', label: '입고' },
  { value: 'operational', label: '가동' },
  { value: 'stopped', label: '미가동' },
  { value: 'idle', label: '미사용' },
  { value: 'maintenance', label: '점검·교정' },
  { value: 'repair', label: '고장 수리중' },
  { value: 'retired', label: '폐기' },
  { value: 'struck', label: '취소선' },
  { value: 'unknown', label: '미기재' },
]

/**
 * 검색과 목록이 「쓸 수 있다」 로 세는 상태. **서버의 `AVAILABLE_STATUSES` 와 같다.**
 *
 * 미사용·미가동이 들어간다 — 안 쓰고 있다는 것은 못 쓴다는 뜻이 아니다. 고장 수리중·
 * 점검·교정은 뺀다: 지금 못 돌리는 장비를 「됩니다」 로 답하면 그 답을 믿고 일정을 짠
 * 사람이 막힌다. 입고·폐기·취소선도 같은 이유로 뺀다.
 *
 * **미기재가 들어간다**(2026-10-01, 운영 판단) — 상태를 안 적었다고 검색에서 빼면
 * 대장에 있는 장비가 없는 것이 된다.
 */
export const AVAILABLE_STATUSES = ['operational', 'idle', 'stopped', 'unknown']

/**
 * 근거를 **물어야 하는** 상태 — 「왜 그 상태인가」 가 있어야 할 일이 정해지는 것들.
 *
 *     고장 수리중  무엇이 고장인가 · 부품을 기다리나 · 고칠 수 있나
 *     미사용·미가동 과제가 끝나서인가 · 자리를 옮기는 중인가
 *     폐기        왜 버렸나 — 반년 뒤 「그 장비 어디 갔냐」 를 묻는 사람이 반드시 있다
 *     취소선      원본 대장에서 왜 그어졌나 — 그 답은 대장에 없다
 *
 * 가동·입고는 뺀다. 전부에 「미입력」 을 칠하면 그 표시가 아무 뜻도 없어진다. **미기재도
 * 뺀다** — 상태 자체를 모르는 줄에 「근거를 적으라」 고 하는 것은 순서가 거꾸로다.
 */
export const NEEDS_REASON = new Set([
  'stopped',
  'idle',
  'maintenance',
  'repair',
  'retired',
  'struck',
])

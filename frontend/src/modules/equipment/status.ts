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

/** 생애의 순서대로. 들어와서(입고) 돌다가(가동·유휴) 멈추고(점검·수리) 끝난다(폐기). */
export const EQUIPMENT_STATUS_OPTIONS: StatusOption[] = [
  { value: 'incoming', label: '입고' },
  { value: 'operational', label: '가동' },
  { value: 'idle', label: '유휴' },
  { value: 'maintenance', label: '점검·교정' },
  { value: 'repair', label: '고장' },
  { value: 'retired', label: '폐기' },
]

/**
 * 검색과 목록이 「쓸 수 있다」 로 세는 상태. **서버의 `AVAILABLE_STATUSES` 와 같다.**
 *
 * 유휴가 들어간다 — 안 쓰고 있다는 것은 못 쓴다는 뜻이 아니다. 입고는 아직 자리에
 * 안 앉았으므로 뺀다.
 */
export const AVAILABLE_STATUSES = ['operational', 'idle']

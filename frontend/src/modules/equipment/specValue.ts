/**
 * 사양 값 한 칸을 글자로. **한 곳에만 둔다.**
 *
 * 목록(대표 사양)과 상세(사양표)가 같은 값을 그린다. 각자 적으면 언젠가 한쪽만
 * 고쳐지고, 그때 「제한 없음」 이 한 화면에서는 0 으로 보인다 — 그 둘은 장비를
 * 고르는 사람에게 정반대다.
 */

/** 값 칸의 모양. 사양표의 값과 목록의 대표 사양이 둘 다 이 모양이다. */
export interface SpecValueShape {
  kind: string
  si_unit: string
  display_unit: string
  num_value: number | null
  num_min: number | null
  num_max: number | null
  text_value: string | null
  bool_value: boolean | null
}

/** 종류마다 읽는 칸이 다르다. 한 칸에 다 담았으면 이 함수가 필요 없었을 것이다. */
export function shownSpecValue(item: SpecValueShape): string {
  const unit = item.display_unit || item.si_unit
  const withUnit = (value: number) => `${value}${unit ? ` ${unit}` : ''}`
  switch (item.kind) {
    case 'range': {
      // **비운 쪽은 "제한 없음" 이다.** 0 으로 적으면 하한이 0 인 것과 구별되지 않는다.
      const low = item.num_min === null ? '제한 없음' : withUnit(item.num_min)
      const high = item.num_max === null ? '제한 없음' : withUnit(item.num_max)
      return `${low} ~ ${high}`
    }
    case 'boolean':
      return item.bool_value ? '있음' : '없음'
    case 'number':
      return item.num_value === null ? '—' : withUnit(item.num_value)
    default:
      return item.text_value ?? '—'
  }
}

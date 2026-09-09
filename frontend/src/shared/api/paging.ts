/** 목록 응답 봉투 (app/shared/pagination.py 의 Page 와 짝). */
export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

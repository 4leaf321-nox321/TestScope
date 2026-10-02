/**
 * 쪽을 끝까지 받아 **하나로 잇는다** — 「전부 보기」 가 거짓말을 안 하게.
 *
 * 서버는 한 번에 줄 수 있는 줄 수를 제한한다(`app/shared/pagination.py`). 그 상한까지만
 * 받아 놓고 「전부」 라고 그리면 **나머지가 조용히 사라진다** — 그리고 그 사실은 화면
 * 어디에도 안 남는다. 실제로 그랬다: 기종 선택기가 563기종 중 200기종만 보여 주던 때,
 * 못 찾은 사람은 「카탈로그에 없구나」 하고 기종을 빈 칸으로 저장했다
 * (`ModelPicker` 주석).
 *
 * 그래서 **`total` 에 닿을 때까지** 받는다. 한 번에 받는 양은 서버가 정하므로, 돌려받은
 * 줄 수로 다음 자리를 잡는다 — 우리가 보낸 `limit` 을 믿고 더하면 서버가 잘랐을 때
 * 자리가 어긋나 같은 줄을 또 받거나 중간을 건너뛴다.
 *
 * ## 못 받았으면 **못 받았다고 말한다**
 *
 * 왕복 횟수에 상한이 있다(`ROUNDS`). 거기서 멈추면 `done: false` 로 돌려주고, 부르는
 * 화면은 그것을 사람에게 적어야 한다. 조용히 끊는 것이 이 함수가 없애려는 바로 그
 * 고장이므로, 여기서 다시 만들지 않는다.
 *
 * 줄이 안 오는데 `total` 에 못 닿는 경우도 멈춘다 — 안 그러면 영원히 돈다.
 */

/** 서버가 한 쪽에 담아 주는 모양. */
export interface Paged<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface FetchedAll<T> {
  items: T[]
  total: number
  /** `false` 면 **덜 받았다.** 화면이 그 사실을 적어야 한다. */
  done: boolean
}

/** 한 번에 달라고 할 줄 수. 서버의 카탈로그 상한(5000)보다 작게 둔다. */
const CHUNK = 2000

/** 왕복 상한. 2000 × 25 = 5만 줄 — 그보다 큰 목록은 쪽으로 봐야 한다. */
const ROUNDS = 25

export async function fetchAll<T>(
  page: (limit: number, offset: number) => Promise<Paged<T>>,
  { chunk = CHUNK, rounds = ROUNDS }: { chunk?: number; rounds?: number } = {},
): Promise<FetchedAll<T>> {
  const items: T[] = []
  let total = 0

  for (let round = 0; round < rounds; round += 1) {
    // **돌려받은 줄 수로 자리를 잡는다** — 보낸 limit 을 믿으면 서버가 잘랐을 때 어긋난다.
    const got = await page(chunk, items.length)
    total = got.total
    items.push(...got.items)
    if (items.length >= total) return { items, total, done: true }
    // 줄이 안 오는데 total 에 못 닿았다 — 더 돌아도 같다.
    if (got.items.length === 0) return { items, total, done: false }
  }
  return { items, total, done: false }
}

/**
 * 「전부 보기」 는 **거짓말을 안 한다.**
 *
 * 무는 것 넷:
 *   total 에 닿을 때까지 받는다   상한까지만 받아 「전부」 라고 그리면 나머지가 사라진다
 *   돌려받은 줄 수로 자리를 잡는다 서버가 잘랐을 때 보낸 limit 을 믿으면 어긋난다
 *   못 받았으면 done:false       조용히 끊는 것이 이 함수가 없애려는 그 고장이다
 *   줄이 안 오면 멈춘다           영원히 도는 것보다 덜 받았다고 말하는 게 낫다
 */

import { describe, expect, it } from 'vitest'

import { fetchAll } from '@/shared/api/fetchAll'

/** 서버 흉내 — `cap` 보다 많이 달라고 하면 **잘라서** 준다. */
function server(total: number, cap: number) {
  const asked: { limit: number; offset: number }[] = []
  return {
    asked,
    page: async (limit: number, offset: number) => {
      asked.push({ limit, offset })
      const give = Math.min(limit, cap)
      return {
        items: Array.from(
          { length: Math.max(0, Math.min(give, total - offset)) },
          (_, at) => offset + at,
        ),
        total,
        limit: give,
        offset,
      }
    },
  }
}

describe('fetchAll', () => {
  it('한 번에 다 오면 한 번만 묻는다', async () => {
    const one = server(120, 2000)
    const got = await fetchAll(one.page)
    expect(got.items).toHaveLength(120)
    expect(got.done).toBe(true)
    expect(one.asked).toHaveLength(1)
  })

  it('서버가 자르면 **돌려받은 수로** 이어 받는다 — 보낸 limit 을 믿으면 어긋난다', async () => {
    // 2000 을 달라 했는데 200 만 준다. 보낸 수로 자리를 잡으면 두 번째 요청이
    // offset 2000 으로 가서 1800줄이 조용히 빠진다.
    const one = server(1608, 200)
    const got = await fetchAll(one.page)
    expect(got.done).toBe(true)
    expect(got.items).toHaveLength(1608)
    // 같은 줄을 두 번 받지도, 중간을 건너뛰지도 않았다.
    expect(new Set(got.items).size).toBe(1608)
    expect(one.asked.map((a) => a.offset).slice(0, 3)).toEqual([0, 200, 400])
  })

  it('왕복 상한에서 멈추면 **덜 받았다고 말한다**', async () => {
    const one = server(10_000, 100)
    const got = await fetchAll(one.page, { chunk: 100, rounds: 3 })
    expect(got.done).toBe(false)
    expect(got.items).toHaveLength(300)
    expect(got.total).toBe(10_000)
  })

  it('줄이 안 오는데 total 에 못 닿으면 멈춘다 — 영원히 돌지 않는다', async () => {
    // total 은 500 이라고 하면서 줄을 안 준다(세다 지운 사이에 그럴 수 있다).
    let rounds = 0
    const got = await fetchAll(async (_limit, offset) => {
      rounds += 1
      return { items: [], total: 500, limit: 100, offset }
    })
    expect(got.done).toBe(false)
    expect(rounds).toBe(1)
  })
})

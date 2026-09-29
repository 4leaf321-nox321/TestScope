/**
 * 조직도 트리의 **판정** — 끌어다 놓기 자체는 브라우저 밖에서 못 돌린다.
 *
 * 그래서 「어디에 놓으면 어떤 자리가 되나」 만 떼어 여기서 본다(`removalState` 와 같은
 * 방식). 여기서 지키는 것:
 *
 * 1. 깊이 우선으로 펴진다 — 화면의 줄 순서가 곧 조직도다.
 * 2. **자기 자신과 제 하위에는 못 놓는다.** 놓이면 그 가지가 트리에서 통째로 사라지고,
 *    화면에 안 나오니 되돌릴 수도 없다.
 * 3. 옮기면 **형제 전부의 자리**가 다시 매겨진다 — 옮긴 줄만 보내면 새 자리가 그 사이
 *    어디인지 서버가 알 수 없다.
 */

import { describe, expect, it } from 'vitest'

import { forbiddenFor, movePlan, ordered } from './WorkspaceTree'
import type { Workspace } from './api'

function ws(slug: string, parent: string | null, order: number): Workspace {
  return {
    id: slug,
    slug,
    name: slug.toUpperCase(),
    parent_slug: parent,
    depth: 0,
    path: slug,
    sort_order: order,
    is_active: true,
    restricted: false,
    reliability_owner: false,
    member_count: 0,
    equipment_count: 0,
  } as unknown as Workspace
}

//   본부
//     팀가
//       파트1
//     팀나
//   따로
const ROWS = [
  ws('head', null, 0),
  ws('a', 'head', 0),
  ws('p1', 'a', 0),
  ws('b', 'head', 1),
  ws('loose', null, 1),
]

describe('조직도 펴기', () => {
  it('깊이 우선으로, 형제는 순서대로', () => {
    expect(ordered(ROWS).map((one) => [one.slug, one.level])).toEqual([
      ['head', 0],
      ['a', 1],
      ['p1', 2],
      ['b', 1],
      ['loose', 0],
    ])
  })

  it('순서가 같으면 이름으로 가른다 — 같은 값이 여럿인 옛 자료가 있다', () => {
    const tie = [ws('head', null, 0), ws('z', 'head', 0), ws('y', 'head', 0)]
    expect(ordered(tie).map((one) => one.slug)).toEqual(['head', 'y', 'z'])
  })
})

describe('놓으면 안 되는 자리', () => {
  it('자기 자신과 제 하위 전부', () => {
    expect(forbiddenFor(ROWS, 'a')).toEqual(new Set(['a', 'p1']))
    expect(forbiddenFor(ROWS, 'head')).toEqual(new Set(['head', 'a', 'p1', 'b']))
    expect(forbiddenFor(ROWS, null).size).toBe(0)
  })

  it('금지된 자리에 놓으면 아무 일도 안 일어난다', () => {
    // 본부를 제 손자 아래로 — 그대로 두면 그 가지가 화면에서 사라진다.
    expect(movePlan(ROWS, 'head', { kind: 'inside', slug: 'p1' })).toEqual([])
    expect(movePlan(ROWS, 'a', { kind: 'before', slug: 'p1' })).toEqual([])
  })
})

describe('놓은 자리로 새 순서 만들기', () => {
  it('줄 자체에 놓으면 그 부서의 마지막 자식이 된다', () => {
    const plan = movePlan(ROWS, 'loose', { kind: 'inside', slug: 'head' })
    expect(plan).toEqual([
      { slug: 'a', parent_slug: 'head', sort_order: 0 },
      { slug: 'b', parent_slug: 'head', sort_order: 1 },
      { slug: 'loose', parent_slug: 'head', sort_order: 2 },
    ])
  })

  it('띠에 놓으면 그 부서의 앞 형제가 된다', () => {
    const plan = movePlan(ROWS, 'loose', { kind: 'before', slug: 'b' })
    expect(plan.map((one) => one.slug)).toEqual(['a', 'loose', 'b'])
    expect(plan.every((one) => one.parent_slug === 'head')).toBe(true)
    expect(plan.map((one) => one.sort_order)).toEqual([0, 1, 2])
  })

  it('뿌리로도 올라간다 — 맨 위 형제의 앞에 놓으면 된다', () => {
    const plan = movePlan(ROWS, 'p1', { kind: 'before', slug: 'head' })
    expect(plan).toEqual([
      { slug: 'p1', parent_slug: null, sort_order: 0 },
      { slug: 'head', parent_slug: null, sort_order: 1 },
      { slug: 'loose', parent_slug: null, sort_order: 2 },
    ])
  })

  it('**형제 전부**를 보낸다 — 옮긴 줄만 보내면 새 자리를 서버가 모른다', () => {
    const plan = movePlan(ROWS, 'b', { kind: 'before', slug: 'a' })
    expect(plan).toHaveLength(2)
    expect(plan.map((one) => one.slug)).toEqual(['b', 'a'])
  })
})

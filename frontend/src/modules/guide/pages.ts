/**
 * 가이드 글 — **코드와 같은 커밋에 산다.**
 *
 * 글을 DB 에 두면 배포 없이 고칠 수 있지만, **기능이 바뀌어도 글은 안 바뀐다** — 누군가
 * 기억해서 고쳐야 하고 대개 안 고친다. 그러면 틀린 안내가 남고, 틀린 안내는 없는 것보다
 * 나쁘다(사람이 믿고 그대로 한다).
 *
 * 저장소에 두면 기능을 바꾼 PR 에서 글이 같이 바뀌고, **CI 가 「없는 화면을 가리키는
 * 링크」 를 잡을 수 있다**(`GuidePage.test.tsx`). 대신 현장에서 바로 못 다듬는다 —
 * 그쪽은 **공지**가 맡는다. 자주 바뀌는 말은 공지로, 틀의 구조는 여기로.
 *
 * ## 차례는 파일 이름이 정한다
 *
 * `01-…` · `02-…` 로 적고 글자순으로 세운다. 배열을 따로 두면 글을 더하고 그 배열에
 * 안 적는 날이 오고, 그러면 쓴 글이 어디에도 안 보인다.
 *
 * 제목은 글의 첫 `# ` 줄에서 뽑는다 — 두 벌로 적으면 한쪽만 고쳐진다.
 */

/** 글 파일 전부. **`eager` 다** — 다섯 쪽이고, 차례를 그리려면 어차피 제목이 다 필요하다. */
const FILES = import.meta.glob('./pages/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
})

export interface GuidePage {
  /** 주소에 쓰는 이름 — `01-how-it-fits.md` → `how-it-fits`. 번호는 차례용이라 뺀다. */
  slug: string
  title: string
  body: string
}

function titleOf(body: string): string {
  const line = body.split('\n').find((one) => one.startsWith('# '))
  return line ? line.slice(2).trim() : '(제목 없음)'
}

export const GUIDE_PAGES: GuidePage[] = Object.entries(FILES)
  .sort(([one], [other]) => one.localeCompare(other))
  .map(([path, body]) => ({
    slug: (path.split('/').pop() ?? '').replace(/^\d+-/, '').replace(/\.md$/, ''),
    title: titleOf(body as string),
    body: body as string,
  }))

export function guidePage(slug: string | undefined): GuidePage | undefined {
  return slug ? GUIDE_PAGES.find((one) => one.slug === slug) : GUIDE_PAGES[0]
}

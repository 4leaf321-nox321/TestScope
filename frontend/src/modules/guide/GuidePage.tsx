/**
 * 가이드 — **「이게 뭐랑 뭐랑 엮여 있지」 에 답하는 자리.**
 *
 * 이 틀은 표가 많고, 어느 칸이 어느 화면에 영향을 주는지가 눈에 안 보인다. 기종 사양 하나가
 * 「이 시험 되나요」 의 답을 바꾸는데 그 사슬이 화면 어디에도 안 그려져 있었다 — 새로 온
 * 사람은 물어봐야 알았고, 물어볼 사람이 없으면 비슷한 기종을 골라 넣었다.
 *
 * ## 글은 저장소에 있다
 *
 * `pages/*.md`. 기능을 바꾼 PR 에서 글도 같이 바뀐다(`pages.ts` 에 이유를 적어 두었다).
 *
 * ## 안에서 가리키는 곳은 **실제로 있는 화면**이어야 한다
 *
 * 가이드가 없는 주소를 가리키면 읽는 사람은 자기가 뭘 잘못 눌렀다고 생각한다. 그래서
 * 글 안의 내부 링크를 **시험이 라우터와 대조한다**(`GuidePage.test.tsx`).
 */

import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '@/shared/components/PageHeader'
import { cn } from '@/shared/lib/utils'
import GuideBody from '@/modules/guide/GuideBody'
import { GUIDE_PAGES, guidePage } from '@/modules/guide/pages'

// **본문 렌더러를 여기서 또 lazy 로 받지 않는다.** 라우터가 이 화면을 이미 lazy 로
// 받으므로(`router.tsx`) 마크다운 묶음은 어차피 가이드 덩어리에만 들어간다 — 안쪽에 한 겹
// 더 두면 얻는 것 없이 **시험이 느린 기계에서만 떨어진다**(단독으로는 통과하고 전체를
// 돌리면 1초를 넘겨 `findByRole` 이 포기했다, 2026-10-03). 그 흔들림은 원인을 없애는
// 쪽이 싸다.

export default function GuidePage() {
  const { slug } = useParams()
  const shown = guidePage(slug)

  return (
    <div className="space-y-6">
      <PageHeader
        title="가이드"
        description="이 틀이 어떻게 엮여 있고, 어느 칸이 무엇을 바꾸는가."
      />

      <div className="flex flex-col gap-6 lg:flex-row">
        {/* **차례를 늘 보인다.** 다섯 쪽뿐이라 접어 둘 이유가 없고, 지금 어디를 읽고
            있는지가 보여야 한다. */}
        <nav className="shrink-0 lg:w-56">
          <ul className="space-y-1">
            {GUIDE_PAGES.map((one) => (
              <li key={one.slug}>
                <Link
                  to={`/guide/${one.slug}`}
                  className={cn(
                    'block rounded-md px-3 py-2 text-sm',
                    one.slug === shown?.slug
                      ? 'bg-muted font-medium'
                      : 'text-muted-foreground hover:bg-muted/50',
                  )}
                >
                  {one.title}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <article className="min-w-0 flex-1">
          {shown === undefined ? (
            // **주소를 고쳐 들어온 사람에게 길을 준다.** 빈 화면만 두면 가이드가
            // 고장 난 것으로 읽힌다.
            <p className="text-muted-foreground text-sm">
              그런 가이드 쪽이 없습니다.{' '}
              <Link to="/guide" className="underline">
                처음으로
              </Link>
            </p>
          ) : (
            <GuideBody markdown={shown.body} />
          )}
        </article>
      </div>
    </div>
  )
}

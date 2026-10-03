/**
 * 가이드 본문 — 마크다운을 화면 서식으로.
 *
 * **서식을 `prose` 플러그인에 맡기지 않는다.** 이 앱의 표·코드 블록은 다른 화면과 같은
 * 모양이어야 하고, 플러그인을 하나 더 들이면 그 모양이 두 벌이 된다.
 *
 * 내부 링크(`/equipment` 같은)는 **라우터로** 넘긴다. `<a>` 로 두면 전체 새로고침이
 * 일어나 로그인 상태가 깜빡이고, 사람은 그것을 「느리다」 로 읽는다.
 */

import type { ComponentProps } from 'react'
import { Link } from 'react-router-dom'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

function Anchor({ href, children }: ComponentProps<'a'>) {
  const to = href ?? ''
  if (to.startsWith('/')) {
    return (
      <Link to={to} className="text-primary underline underline-offset-2">
        {children}
      </Link>
    )
  }
  // 밖으로 나가는 링크는 새 탭 — 읽던 자리를 잃지 않는다.
  return (
    <a
      href={to}
      target="_blank"
      rel="noreferrer"
      className="text-primary underline underline-offset-2"
    >
      {children}
    </a>
  )
}

export default function GuideBody({ markdown }: { markdown: string }) {
  return (
    <div className="max-w-3xl space-y-4 text-sm leading-7">
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="mt-0 mb-4 text-2xl font-semibold">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="mt-8 mb-2 border-t pt-6 text-lg font-semibold">{children}</h2>
          ),
          h3: ({ children }) => <h3 className="mt-6 mb-1 font-semibold">{children}</h3>,
          p: ({ children }) => <p>{children}</p>,
          ul: ({ children }) => <ul className="list-disc space-y-1 pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal space-y-1 pl-5">{children}</ol>,
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
          a: Anchor,
          code: ({ children }) => (
            <code className="bg-muted rounded px-1 py-0.5 font-mono text-[0.85em]">
              {children}
            </code>
          ),
          // 사슬 그림을 코드 블록으로 그린다 — 가로로 넘치면 **잘리지 않고 스크롤**한다.
          pre: ({ children }) => (
            <pre className="bg-muted overflow-x-auto rounded-md p-4 font-mono text-xs leading-6">
              {children}
            </pre>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border-b px-3 py-2 text-left align-top font-medium">{children}</th>
          ),
          td: ({ children }) => <td className="border-b px-3 py-2 align-top">{children}</td>,
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 pl-4 italic">{children}</blockquote>
          ),
        }}
      >
        {markdown}
      </Markdown>
    </div>
  )
}

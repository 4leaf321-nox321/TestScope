/**
 * 「<축 이름> 등록」 단추 — 온톨로지 축의 값을 **그 값이 쓰이는 화면에서** 만든다.
 *
 * 시험 항목·물성 항목은 온톨로지 축의 값이라 「관리 → 온톨로지」 에서 만들었는데, 카탈로그의
 * 시험 항목·물성 항목 화면에는 등록 단추가 없어 「여기서는 못 만드나」 로 읽혔다. 계열 등록·
 * 기종 등록과 같은 자리에 같은 이름의 단추가 서야 한다 — 새 기록을 만드는 단추는 어느
 * 화면이든 「<대상> 등록」 이다(AGENTS.md).
 *
 * 편집 창은 온톨로지의 것(TermEditorDialog)을 그대로 쓴다 — 값·코드·상위·별칭·칸이 같은 규칙으로
 * 만들어져야 두 화면이 갈리지 않는다. 축과 형제 값은 누를 때 읽는다(안 누르면 안 읽는다).
 */

import { useState } from 'react'
import { Plus } from 'lucide-react'

import { useAuth } from '@/shared/auth/AuthContext'
import { isSystemAdmin } from '@/shared/auth/roles'
import { Button } from '@/shared/components/ui/button'
import { useResource } from '@/shared/hooks/useResource'
import { TermEditorDialog } from '@/modules/vocabulary/TermEditorDialog'
import { vocabularyApi } from '@/modules/vocabulary/api'
import type { Term } from '@/modules/vocabulary/api'

export function NewTermButton({
  slug,
  onCreated,
}: {
  /** 축 slug — test_item · property … */
  slug: string
  /** 만든 뒤 목록을 다시 읽는다. */
  onCreated: () => void
}) {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const axes = useResource(() => (open ? vocabularyApi.list() : Promise.resolve([])), [open])
  const axis = axes.data?.find((one) => one.slug === slug) ?? null
  const terms = useResource(
    () => (axis ? vocabularyApi.terms(slug) : Promise.resolve<Term[]>([])),
    [axis?.slug],
  )
  const parents = useResource(
    () =>
      axis?.parent_slug ? vocabularyApi.terms(axis.parent_slug) : Promise.resolve<Term[]>([]),
    [axis?.parent_slug],
  )

  // **표시일 뿐 권한이 아니다.** 온톨로지 값은 시스템 관리자만 만든다 — 서버가 판정한다.
  if (!isSystemAdmin(user)) return null

  const label =
    axis?.label ??
    (slug === 'test_item' ? '시험 항목' : slug === 'property' ? '물성 항목' : '값')

  return (
    <>
      <Button onClick={() => setOpen(true)}>
        <Plus className="size-4" />
        {label} 등록
      </Button>
      {open && axis && (
        <TermEditorDialog
          term={null}
          axis={axis}
          siblings={terms.data ?? []}
          parentOptions={axis.parent_slug ? (parents.data ?? []) : (terms.data ?? [])}
          onClose={() => setOpen(false)}
          onChanged={() => {
            setOpen(false)
            onCreated()
          }}
        />
      )}
    </>
  )
}

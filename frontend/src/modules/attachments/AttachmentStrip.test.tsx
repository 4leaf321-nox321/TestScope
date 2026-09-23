/**
 * 그림 줄 — **그림은 플랫폼에 들어와 조회하는 사람의 것이다.**
 *
 * 여기서 지키는 것:
 *
 * 1. `<img src="/api/…">` 를 쓰지 않는다. 토큰이 메모리에만 있어 401 이 나고, 그 오류는
 *    화면에 아무 표시도 안 남긴다 — 사용자는 그냥 깨진 그림을 본다.
 * 2. 저장 전에는 붙일 자리가 없다고 **말한다.** 단추만 두면 눌러 보고 아무 일도 안 난다.
 * 3. 읽기만 되는 사람에게는 지우기·설명 칸이 안 보인다.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'

const fetchBlobUrl = vi.fn(async (_path: string) => 'blob:그림')

vi.mock('@/shared/api/client', () => ({
  api: { get: vi.fn(async () => []), upload: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  fetchBlobUrl: (path: string) => fetchBlobUrl(path),
  ApiError: class extends Error {},
}))

const { AttachmentStrip } = await import('@/modules/attachments/AttachmentStrip')
const { attachmentApi } = await import('@/modules/attachments/api')
type Attachment = Awaited<ReturnType<typeof attachmentApi.list>>[number]

function row(over: Partial<Attachment> = {}): Attachment {
  return {
    id: 'a1',
    target: 'reliability_test',
    object_id: 'r1',
    definition_id: null,
    definition_label: null,
    original_name: '장착.png',
    caption: '시편 장착 방향',
    content_type: 'image/png',
    bytes: 1234,
    sort_order: 1,
    url: '/api/attachments/a1/file',
    created_at: '2026-09-23T00:00:00Z',
    ...over,
  } as Attachment
}

afterEach(() => vi.clearAllMocks())

describe('그림 줄', () => {
  it('자격을 실어 받아 blob 으로 그린다 — API 주소를 img 에 안 쓴다', async () => {
    await act(async () => {
      render(
        <AttachmentStrip
          target="reliability_test"
          objectId="r1"
          rows={[row()]}
          canEdit
          onChanged={() => {}}
        />,
      )
    })

    expect(fetchBlobUrl).toHaveBeenCalledWith('/api/attachments/a1/file')
    const image = screen.getByAltText('시편 장착 방향') as HTMLImageElement
    // **API 주소가 아니라 blob 이다.**
    expect(image.src.startsWith('blob:')).toBe(true)
  })

  it('저장 전에는 붙일 자리가 없다고 말한다', async () => {
    await act(async () => {
      render(
        <AttachmentStrip
          target="reliability_test"
          objectId={null}
          rows={[]}
          canEdit
          onChanged={() => {}}
        />,
      )
    })
    expect(screen.getByText(/저장한 뒤에/)).toBeTruthy()
    expect(screen.queryByText('그림 넣기')).toBeNull()
  })

  it('읽기만 되는 사람에게는 고치는 자리가 없다', async () => {
    await act(async () => {
      render(
        <AttachmentStrip
          target="reliability_test"
          objectId="r1"
          rows={[row()]}
          canEdit={false}
          onChanged={() => {}}
        />,
      )
    })
    // 설명은 **보이되** 고칠 수 없다.
    expect(screen.getByText('시편 장착 방향')).toBeTruthy()
    expect(screen.queryByLabelText('장착.png 설명')).toBeNull()
    expect(screen.queryByLabelText('시편 장착 방향 빼기')).toBeNull()
  })
})

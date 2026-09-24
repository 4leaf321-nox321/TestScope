/**
 * 그림 줄 — **그림은 플랫폼에 들어와 조회하는 사람의 것이다.**
 *
 * 여기서 지키는 것:
 *
 * 1. `<img src="/api/…">` 를 쓰지 않는다. 토큰이 메모리에만 있어 401 이 나고, 그 오류는
 *    화면에 아무 표시도 안 남긴다 — 사용자는 그냥 깨진 그림을 본다.
 * 2. 저장 전에는 붙일 자리가 없다고 **말한다.** 단추만 두면 눌러 보고 아무 일도 안 난다.
 * 3. 읽기만 되는 사람에게는 지우기·설명 칸이 안 보인다.
 * 4. **눌러서 크게 본다.** 줄에 선 크기는 「있다」 는 표시일 뿐이다 — 그리고 크게 볼 때
 *    **다시 받지 않는다**(10 MB 사진을 두 번 받게 된다).
 * 5. 브라우저가 못 그리는 것(워드·한글)은 **그리는 시늉을 안 한다.** `<img>` 로 떠넘기면
 *    깨진 그림이 뜨고, 사람은 「올리기가 잘못됐나」 한다.
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

describe('이미지 줄', () => {
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
    expect(screen.queryByText('이미지 첨부')).toBeNull()
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
    expect(screen.queryByLabelText('시편 장착 방향 제거')).toBeNull()
  })

  it('누르면 크게 열리고, 받아 둔 blob 을 다시 받지 않는다', async () => {
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
    expect(fetchBlobUrl).toHaveBeenCalledTimes(1)

    await act(async () => {
      screen.getByRole('button', { name: '시편 장착 방향 크게 보기' }).click()
    })

    // 크게 보는 창이 떴다 — 파일 이름과 크기가 함께 선다.
    expect(screen.getByText(/장착.png/)).toBeTruthy()
    expect(screen.getByRole('link', { name: /내려받기/ })).toBeTruthy()
    // **다시 안 받는다.**
    expect(fetchBlobUrl).toHaveBeenCalledTimes(1)
  })
  it('워드·한글은 상자로 서고, 목록을 여는 것만으로는 안 내려온다', async () => {
    /** 50 MB 짜리 스캔본 열 장이 목록을 여는 것만으로 내려오면 사내망에서 바로 느껴진다. */
    await act(async () => {
      render(
        <AttachmentStrip
          target="spec_document"
          objectId="d1"
          rows={[
            row({
              id: 'a2',
              original_name: 'MX-REL-012_Rev2.hwp',
              caption: '',
              content_type: 'application/haansofthwp',
              url: '/api/attachments/a2/file',
            }),
          ]}
          canEdit={false}
          onChanged={() => {}}
        />,
      )
    })

    // **무엇으로 여는지 적힌 상자다.**
    expect(screen.getByText('한글')).toBeTruthy()
    // 깨진 그림이 안 선다 — 브라우저는 한글 파일을 못 그린다.
    expect(document.querySelector('img')).toBeNull()
    expect(fetchBlobUrl).not.toHaveBeenCalled()
  })

  it('문서를 누르면 그리는 시늉 대신 내려받기를 내민다', async () => {
    await act(async () => {
      render(
        <AttachmentStrip
          target="spec_document"
          objectId="d1"
          rows={[
            row({
              id: 'a2',
              original_name: 'MX-REL-012_Rev2.hwp',
              caption: '',
              content_type: 'application/haansofthwp',
              url: '/api/attachments/a2/file',
            }),
          ]}
          canEdit={false}
          onChanged={() => {}}
        />,
      )
    })

    await act(async () => {
      screen.getByRole('button', { name: 'MX-REL-012_Rev2.hwp 크게 보기' }).click()
    })

    // **누른 사람은 파일을 원한다** — 바이트는 그때 받는다.
    expect(fetchBlobUrl).toHaveBeenCalledTimes(1)
    expect(screen.getByText(/브라우저는 이 형식을 못 그립니다/)).toBeTruthy()
    expect(screen.getByRole('link', { name: /내려받기/ })).toBeTruthy()
    expect(document.querySelector('img')).toBeNull()
  })
})

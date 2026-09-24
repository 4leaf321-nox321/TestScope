/**
 * 무엇을 그릴 수 있나 — **이름이 형식보다 앞선다.**
 *
 * 같은 내용은 한 벌로 모이므로(sha256) `content_type` 은 그 바이트를 **처음 올린 줄**의
 * 것이 된다. 이름은 이 줄이 가진 것이라, 보는 자리에서는 이름이 앞선다.
 */

import { describe, expect, it } from 'vitest'

import { ACCEPT, kindOf, programOf } from './fileKind'

const row = (original_name: string, content_type: string) => ({ original_name, content_type })

describe('파일 갈래', () => {
  it('브라우저가 못 그리는 것은 문서로 본다', () => {
    expect(kindOf(row('규격서.hwp', 'application/haansofthwp'))).toBe('document')
    expect(
      kindOf(
        row(
          '표준.docx',
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        ),
      ),
    ).toBe('document')
    expect(kindOf(row('시료표.xlsx', 'application/vnd.ms-excel'))).toBe('document')
  })

  it('그릴 수 있는 것은 그대로다', () => {
    expect(kindOf(row('장착.png', 'image/png'))).toBe('image')
    expect(kindOf(row('원문.pdf', 'application/pdf'))).toBe('pdf')
  })

  it('이름이 형식보다 앞선다 — 형식은 바이트의 것이다', () => {
    // 같은 바이트를 먼저 올린 줄이 워드였어도, 이 줄의 이름이 png 면 그림이다.
    const wrong = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    expect(kindOf(row('장착.png', wrong))).toBe('image')
  })

  it('이름에 확장자가 없으면 형식을 본다', () => {
    expect(kindOf(row('스캔본', 'image/jpeg'))).toBe('image')
    expect(kindOf(row('스캔본', 'application/pdf'))).toBe('pdf')
    // 둘 다 모르면 문서다 — 모르는 것을 `<img>` 로 그리면 깨진 그림이 된다.
    expect(kindOf(row('스캔본', 'application/octet-stream'))).toBe('document')
  })

  it('무엇으로 여는지 사람의 말로 적는다', () => {
    expect(programOf(row('규격서.hwp', 'application/haansofthwp'))).toBe('한글')
    expect(programOf(row('표준.docx', ''))).toBe('워드')
    expect(programOf(row('시료표.xlsx', ''))).toBe('엑셀')
    expect(programOf(row('원문.pdf', 'application/pdf'))).toBe('PDF')
  })

  it('고르기 창이 한글 파일을 연다 — 확장자로 적는다', () => {
    // 브라우저는 .hwp 의 형식을 모른다. MIME 로만 적으면 고르기 창에서 회색으로 뜬다.
    expect(ACCEPT).toContain('.hwp')
    expect(ACCEPT).toContain('.docx')
    expect(ACCEPT).toContain('.pdf')
  })
})

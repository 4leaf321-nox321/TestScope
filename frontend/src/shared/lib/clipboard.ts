/**
 * 클립보드에 글자 넣기 — **사내 배포는 평문 http 다.**
 *
 * `navigator.clipboard` 는 보안 문맥(https 또는 localhost)에서만 있다. 배포는
 * `http://<서버>:8020` 이라 그 객체가 **아예 없고**, 그러면 `navigator.clipboard
 * .writeText(...)` 는 예외로 죽는다.
 *
 * 개발에서는 localhost 라 멀쩡히 되고 **배포에서만 안 된다** — 그래서 손으로 한 번
 * 눌러 보는 것으로는 안 걸리는 종류의 고장이다. 그런 것은 처음부터 두 길로 짠다.
 *
 * 옛 길(`execCommand('copy')`)은 폐기 예정이라고 적혀 있지만 아직 모든 브라우저가
 * 받는다. 그리고 평문 http 에서 쓸 수 있는 유일한 길이다.
 */

export async function copyText(text: string): Promise<void> {
  if (window.isSecureContext && navigator.clipboard) {
    await navigator.clipboard.writeText(text)
    return
  }

  const box = document.createElement('textarea')
  box.value = text
  // 화면 밖에 두되 **숨기지는 않는다** — `display:none` 이면 고를 수가 없어서
  // 복사가 조용히 빈 글자를 넣는다.
  box.style.position = 'fixed'
  box.style.left = '-9999px'
  box.setAttribute('readonly', '')
  document.body.appendChild(box)
  try {
    box.select()
    box.setSelectionRange(0, text.length) // iOS 는 select() 만으로는 안 잡힌다
    if (!document.execCommand('copy')) {
      throw new Error('복사를 브라우저가 거절했습니다')
    }
  } finally {
    document.body.removeChild(box)
  }
}

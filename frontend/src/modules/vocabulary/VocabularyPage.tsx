/**
 * 예전 주소 `/vocabulary` — **기준정보는 한 화면이다.** 이름 사전 보기는 허브(`/reference`)의
 * 오른쪽 판이 되었다. 여기로 온 링크(문서·즐겨찾기)를 그리로 보낸다.
 */

import { Navigate } from 'react-router-dom'

export default function VocabularyPage() {
  return <Navigate to="/reference" replace />
}

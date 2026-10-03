import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from '@/App'
import '@/index.css'

const container = document.getElementById('root')
if (!container) throw new Error('#root를 찾을 수 없음')

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

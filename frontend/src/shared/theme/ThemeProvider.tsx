/**
 * 밝게/어둡게.
 *
 * 저장은 브라우저에만 한다(localStorage). 서버가 알 일이 아니다 — 권한도 데이터도
 * 아니고 "이 사람이 이 PC 에서 어떻게 보고 싶은가" 다. 저장을 막은 브라우저에서도
 * **화면은 멀쩡해야 한다** — 기억을 못 할 뿐이다.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

type Theme = 'light' | 'dark'

const STORAGE_KEY = 'tas.theme'

interface ThemeContextValue {
  theme: Theme
  toggle: () => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

function readStored(): Theme | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    return raw === 'light' || raw === 'dark' ? raw : null
  } catch {
    // 사생활 보호 창이나 저장을 막은 브라우저.
    return null
  }
}

function systemTheme(): Theme {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => readStored() ?? systemTheme())

  useEffect(() => {
    // Tailwind 의 dark variant 가 이 클래스를 본다(index.css 의 custom-variant).
    document.documentElement.classList.toggle('dark', theme === 'dark')
    try {
      window.localStorage.setItem(STORAGE_KEY, theme)
    } catch {
      // 위와 같다.
    }
  }, [theme])

  const toggle = useCallback(() => {
    setTheme((value) => (value === 'dark' ? 'light' : 'dark'))
  }, [])

  const value = useMemo(() => ({ theme, toggle }), [theme, toggle])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const value = useContext(ThemeContext)
  if (!value) throw new Error('useTheme 는 ThemeProvider 안에서만 쓸 수 있습니다')
  return value
}

/**
 * 사이드바 옆에 붙는 목록 자리 — **다른 것을 보려고 뒤로 갈 필요가 없다.**
 *
 * 실사용에서 나왔다. 기종을 하나 열면 상세로 들어가는데, 옆 기종을 보려면 브라우저
 * 뒤로 가기밖에 길이 없었다. 같은 계열의 기종을 견주는 일(사양이 어디서 갈리나), 같은
 * 부서의 장비를 훑는 일은 늘 있는 일이라, 그때마다 목록 → 상세 → 뒤로 → 상세를 반복하게
 * 된다. 실제로 「매번 뒤로가서 보니까 너무 귀찮다」 는 말이 나왔다.
 *
 * ## 껍데기 층에 붙는다
 *
 * 왼쪽 사이드바 **바로 옆**이다. 본문(`main`) 안에 넣으면 본문의 여백 안으로 들어가고
 * 본문과 함께 스크롤된다 — 화면 끝에 붙어 제자리에 있어야 하는 것이라 껍데기가 자리를
 * 내주고 화면이 포털로 채운다.
 *
 * ## 내용은 화면이, 여닫기는 껍데기가
 *
 * 무엇을 목록에 담을지는 화면이 안다(장비·기종·계열은 거르는 조건이 다 다르다). 껍데기가
 * 그것까지 알면 껍데기가 장비 도메인을 알게 되고, 그때부터 그 모듈을 떼어 낼 수 없다.
 * 반대로 **여닫는 상태는 껍데기가 갖는다** — 여는 단추는 사이드바 토글 옆(상단 바)에
 * 있어야 하고, 그러려면 `Header` 가 그 상태를 볼 수 있어야 한다.
 *
 * 화면이 바뀌어 패널이 걷히면 단추도 같이 사라진다 — 없는 패널을 여는 단추가 남아 있으면
 * 눌러도 아무 일이 안 일어난다.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import type { ReactNode } from 'react'

const HOST_ID = 'left-panel-host'

export interface LeftPanelState {
  /** 지금 화면이 이 자리를 쓰는가. 쓰면 그 이름(상단 바 단추에 뜬다). */
  label: string | null
  open: boolean
  toggle: () => void
  register: (label: string | null) => void
}

const Ctx = createContext<LeftPanelState | null>(null)

export function LeftPanelProvider({ children }: { children: ReactNode }) {
  const [label, setLabel] = useState<string | null>(null)
  // **기본은 열림.** 목록을 보려고 있는 것인데 닫혀 있으면 뜻이 없다 — 들어갈 때마다
  // 열게 하면 뒤로 가기와 다를 바 없다.
  const [open, setOpen] = useState(true)

  const register = useCallback((next: string | null) => {
    setLabel(next)
  }, [])

  const value = useMemo(
    () => ({ label, open, toggle: () => setOpen((one) => !one), register }),
    [label, open, register],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

/** 상단 바가 쓴다. 패널이 없으면 `label` 이 `null` 이라 단추를 감춘다. */
export function useLeftPanel(): LeftPanelState {
  const value = useContext(Ctx)
  if (!value) throw new Error('LeftPanelProvider 안에서만 쓸 수 있습니다.')
  return value
}

/** 껍데기가 그리는 빈 자리. 아무 화면도 안 쓰면 폭이 0 이다. */
export function LeftPanelHost() {
  return <div id={HOST_ID} className="shrink-0" />
}

/**
 * 그 자리에 내용을 넣는다. 폭·테두리·스크롤은 **넣는 쪽이 정한다** — 화면마다 필요한
 * 폭이 다르고, 껍데기가 그것까지 알 이유가 없다.
 */
export function LeftPanel({ label, children }: { label: string; children: ReactNode }) {
  const panel = useLeftPanel()
  const { register } = panel
  const [host, setHost] = useState<HTMLElement | null>(null)

  useEffect(() => {
    register(label)
    return () => register(null)
  }, [register, label])

  // 껍데기의 빈 자리는 첫 그림 뒤에 생긴다 — 그때 다시 찾는다.
  useEffect(() => {
    setHost(document.getElementById(HOST_ID))
  }, [])

  if (!host || !panel.open) return null
  return createPortal(<>{children}</>, host)
}

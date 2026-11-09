import { useEffect } from 'react'
import { isChromium, type Brand } from './browser'

/** 크롬 계열일 때만 html에 liquid-glass 클래스를 붙인다. Safari·Firefox는 blur 글래스만. */
export function useLiquidGlass(): void {
  useEffect(() => {
    const nav = navigator as Navigator & { userAgentData?: { brands?: Brand[] } }
    if (!isChromium(nav.userAgent, nav.userAgentData?.brands)) return
    const root = document.documentElement
    root.classList.add('liquid-glass')
    return () => root.classList.remove('liquid-glass')
  }, [])
}

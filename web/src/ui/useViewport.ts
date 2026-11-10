/**
 * 화면 폭 단계 (P20 반응형):
 * - wide ≥ 1280px: 기본 배치 (좌측 패널 · 지도 · 우측 인스펙터 · 하단 타임라인)
 * - mid 1024~1279px: 좌측 패널은 기본 접힘(아이콘 줄), 인스펙터는 지도 위에 겹쳐 뜸
 * - narrow < 1024px: 보기 전용, 좌측 패널·인스펙터·타임라인은 하단 시트 안 탭
 * html[data-viewport]에도 적어 CSS(glass.css)가 같은 단계를 쓴다.
 */
import { useEffect, useState } from 'react'

export type Viewport = 'wide' | 'mid' | 'narrow'
export const WIDE_MIN = 1280
export const MID_MIN = 1024

export function viewportFor(width: number): Viewport {
  return width >= WIDE_MIN ? 'wide' : width >= MID_MIN ? 'mid' : 'narrow'
}

function current(): Viewport {
  return typeof window === 'undefined' ? 'wide' : viewportFor(window.innerWidth)
}

export function useViewport(): Viewport {
  const [vp, setVp] = useState<Viewport>(current)
  useEffect(() => {
    const qs = [`(min-width: ${WIDE_MIN}px)`, `(min-width: ${MID_MIN}px)`].map((q) => window.matchMedia(q))
    const on = () => setVp(current())
    qs.forEach((q) => q.addEventListener('change', on))
    return () => qs.forEach((q) => q.removeEventListener('change', on))
  }, [])
  useEffect(() => {
    document.documentElement.dataset.viewport = vp
  }, [vp])
  return vp
}

import { createPortal } from 'react-dom'

/** 리퀴드 글래스 굴절 필터 #lg. body에 한 번만 넣고 glass.css의 backdrop-filter: url(#lg)가 참조한다. */
export function LiquidGlassFilter() {
  return createPortal(
    <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true" focusable="false">
      <filter id="lg" x="0" y="0" width="100%" height="100%" colorInterpolationFilters="sRGB">
        <feTurbulence type="fractalNoise" baseFrequency="0.008 0.012" numOctaves="2" seed="7" result="noise" />
        <feGaussianBlur in="noise" stdDeviation="2" result="soft" />
        <feDisplacementMap in="SourceGraphic" in2="soft" scale="18" xChannelSelector="R" yChannelSelector="G" />
      </filter>
    </svg>,
    document.body,
  )
}

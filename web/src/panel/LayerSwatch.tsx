/** 레이어 색 칩: 지도 스타일과 같은 모양 (면·선·빗금·점선). 색은 tokens.css 변수만. */
import { SHAPE, svgDash } from '../map/layers'

export type SwatchKind = 'project' | 'impact' | 'parcel' | 'parcel-uncertain' | 'regulation' | 'reference' | 'apartment' | 'pending' | 'symbol' | 'raster'

const PROJECT = 'var(--color-layer-project)'
const REG = 'var(--color-layer-regulation)'
const REG_LINE = 'var(--color-layer-regulation-line)'
const MUTED = 'var(--color-ink-muted)'
const REF = 'var(--color-layer-ref)'
const APT = 'var(--color-layer-apartment)'

export function LayerSwatch({ kind, opacity = 1 }: { kind: SwatchKind; opacity?: number }) {
  const common = { width: 28, height: 16, viewBox: '0 0 28 16', 'aria-hidden': true as const, style: { opacity: Math.max(0.15, opacity) } }
  switch (kind) {
    case 'project':
      return (
        <svg {...common}>
          <rect x="1" y="1" width="26" height="14" rx="2" fill={PROJECT} fillOpacity="0.32" stroke={PROJECT} strokeWidth="2" />
        </svg>
      )
    case 'impact':
      return (
        <svg {...common}>
          <ellipse cx="14" cy="8" rx="12.5" ry="6.5" fill={PROJECT} fillOpacity={SHAPE.impact.fillOpacity}
            stroke={PROJECT} strokeOpacity={SHAPE.impact.lineOpacity} strokeWidth={SHAPE.impact.width} strokeDasharray={svgDash(SHAPE.impact)} />
        </svg>
      )
    case 'parcel':
      return (
        <svg {...common}>
          <rect x="2" y="2" width="24" height="12" fill={PROJECT} fillOpacity={SHAPE.parcelConfirmed.fillOpacity}
            stroke={PROJECT} strokeWidth={SHAPE.parcelConfirmed.width} />
        </svg>
      )
    case 'parcel-uncertain':
      return (
        <svg {...common}>
          <rect x="2" y="2" width="24" height="12" fill="none" stroke={PROJECT} strokeWidth={SHAPE.parcelUncertain.width}
            strokeDasharray={svgDash(SHAPE.parcelUncertain)} />
        </svg>
      )
    case 'regulation':
      return (
        <svg {...common}>
          <defs>
            <pattern id="sw-hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
              <rect width="2" height="5" fill={REG} />
            </pattern>
          </defs>
          <rect x="1" y="1" width="26" height="14" rx="2" fill="url(#sw-hatch)" stroke={REG_LINE} strokeWidth="2" />
        </svg>
      )
    case 'reference': // 공식 참고: 회색 점선 외곽선 + 면 8% (P15)
      return (
        <svg {...common}>
          <rect x="1" y="1" width="26" height="14" rx="2" fill={REF} fillOpacity="0.08" stroke={REF} strokeWidth="1.25" strokeDasharray="3 3" />
        </svg>
      )
    case 'apartment': // 아파트 단지 (P17): 면 28% + 외곽선 1px
      return (
        <svg {...common}>
          <rect x="1" y="1" width="26" height="14" rx="2" fill={APT} fillOpacity="0.28" stroke={APT} strokeWidth="1" />
        </svg>
      )
    case 'symbol':
      return (
        <svg {...common}>
          <circle cx="14" cy="8" r="6" fill="white" stroke={MUTED} strokeWidth="1.5" strokeDasharray="2 2" />
        </svg>
      )
    case 'raster':
    case 'pending':
    default:
      return (
        <svg {...common}>
          <rect x="1" y="1" width="26" height="14" rx="2" fill="none" stroke={MUTED} strokeWidth="1.25" strokeDasharray="2 2" />
        </svg>
      )
  }
}

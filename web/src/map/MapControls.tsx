import { Box, Layers } from 'lucide-react'
import { useMapStore } from '../state/useMapStore'
import { BASEMAP_ORDER, BASEMAPS } from './basemaps'
import type { Insets } from './insets'

/** 배경지도 4종 전환 + 3D 기울기 토글. 지도 보이는 영역의 오른쪽 위(인스펙터 왼쪽)에 뜬다. */
export function MapControls({ insets, hasKey }: { insets: Insets; hasKey: boolean }) {
  const basemap = useMapStore((s) => s.basemap)
  const setBasemap = useMapStore((s) => s.setBasemap)
  const tilt3d = useMapStore((s) => s.tilt3d)
  const toggleTilt3d = useMapStore((s) => s.toggleTilt3d)

  return (
    <div className="absolute flex flex-col items-end gap-2" style={{ top: insets.top, right: insets.right }}>
      <div
        className="glass flex items-center gap-1 p-1 text-xs"
        style={{ borderRadius: 999 }}
        role="radiogroup"
        aria-label="배경지도"
        data-testid="basemap-switch"
      >
        <Layers size={14} aria-hidden="true" className="mx-1 text-ink-muted" />
        {BASEMAP_ORDER.map((id) => {
          const on = basemap === id
          return (
            <button
              key={id}
              role="radio"
              aria-checked={on}
              data-basemap={id}
              onClick={() => setBasemap(id)}
              className={`rounded-full px-2.5 py-1 ${on ? 'glass-liquid map-chip-on font-semibold' : ''}`}
            >
              {BASEMAPS[id].label}
            </button>
          )
        })}
        <span className="mx-1 h-4 w-px bg-ink/15" aria-hidden="true" />
        <button
          onClick={toggleTilt3d}
          aria-pressed={tilt3d}
          data-testid="tilt-toggle"
          className={`flex items-center gap-1 rounded-full px-2.5 py-1 ${tilt3d ? 'glass-liquid map-chip-on font-semibold' : ''}`}
        >
          <Box size={14} aria-hidden="true" />
          3D
        </button>
      </div>
      {!hasKey && (
        <p className="glass px-3 py-1 text-xs" style={{ borderRadius: 999 }} role="status">
          배경지도 키(VITE_VWORLD_KEY)가 설정되지 않아 경계만 표시합니다
        </p>
      )}
    </div>
  )
}

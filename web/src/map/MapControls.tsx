import { Box } from 'lucide-react'
import { useMapStore } from '../state/useMapStore'
import type { Insets } from './insets'

/** 3D 기울기 토글. 지도 보이는 영역의 오른쪽 위(인스펙터 왼쪽). 배경지도 전환은 P14부터 좌측 레이어 패널(배경지도 그룹)에 있다. */
export function MapControls({ insets, hasKey }: { insets: Insets; hasKey: boolean }) {
  const tilt3d = useMapStore((s) => s.tilt3d)
  const toggleTilt3d = useMapStore((s) => s.toggleTilt3d)

  return (
    <div className="absolute flex flex-col items-end gap-2" style={{ top: insets.top, right: insets.right }}>
      <div className="glass flex items-center gap-1 p-1 text-xs" style={{ borderRadius: 999 }}>
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

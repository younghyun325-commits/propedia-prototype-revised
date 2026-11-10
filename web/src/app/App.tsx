import { lazy, Suspense, useMemo } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { UI } from '../copy/ui'
import { LeftPanel } from '../panel/LeftPanel'
import { useMapStore } from '../state/useMapStore'
import { featureId } from '../state/url'
import { useUrlSync } from '../state/useUrlSync'
import { GlassPanel } from '../ui/GlassPanel'
import { LiquidGlassFilter } from '../ui/LiquidGlassFilter'
import { useLiquidGlass } from '../ui/useLiquidGlass'
import { TopBar } from './TopBar'
import { useShellEffects } from './useShellEffects'
import type { Insets } from '../map/insets'

// 지도(MapLibre)는 따로 묶어 셸 다음에 불러온다: 셸이 먼저 뜨고 초기 JS 예산(gzip 400KB)을 지킨다
const MapView = lazy(() => import('../map/MapView'))
// 명령 팔레트는 Ctrl+K로 처음 열 때 불러온다
const CommandPalette = lazy(() => import('../search/CommandPalette'))

const GAP = 12 // 패널과 화면 가장자리 사이
const TOP_H = 56
const LEFT_W = 320
const RIGHT_W = 400
const TL_CLOSED = 44
const TL_OPEN = 200

export default function App() {
  useLiquidGlass()
  useShellEffects()
  useUrlSync()
  const s = useMapStore()
  const tlH = s.timelineOpen ? TL_OPEN : TL_CLOSED
  const sideTop = GAP + TOP_H + GAP
  const sideBottom = GAP + tlH + GAP
  // 지도 위 보이는 영역 (패널을 뺀 곳): 첫 화면 맞춤·지도 컨트롤 위치에 쓴다
  const insets: Insets = useMemo(
    () => ({
      top: sideTop,
      bottom: sideBottom,
      left: s.leftOpen ? GAP + LEFT_W + GAP : GAP,
      right: s.rightOpen ? GAP + RIGHT_W + GAP : GAP,
    }),
    [sideTop, sideBottom, s.leftOpen, s.rightOpen],
  )

  return (
    <div className="relative h-full w-full overflow-hidden">
      <LiquidGlassFilter />

      {/* 지도: 화면 전체. 패널은 그 위에 뜬 글래스 카드 */}
      <Suspense fallback={<div className="map-loading absolute inset-0" data-testid="map-loading" />}>
        <MapView insets={insets} />
      </Suspense>

      {/* 상단 바 56px */}
      <TopBar style={{ top: GAP, left: GAP, right: GAP, height: TOP_H }} />

      {/* 좌측 패널 320px (L) */}
      {s.leftOpen && <LeftPanel style={{ top: sideTop, bottom: sideBottom, left: GAP, width: LEFT_W }} />}

      {/* 우측 인스펙터 400px (I). 내용은 P16 — 이번에는 선택 상태만 */}
      {s.rightOpen && (
        <GlassPanel
          as="aside"
          data-testid="right-panel"
          aria-label={UI.inspector.title}
          className="absolute p-4 text-sm"
          style={{ top: sideTop, bottom: sideBottom, right: GAP, width: RIGHT_W }}
        >
          <h2 className="font-semibold">{UI.inspector.title}</h2>
          {s.selected ? (
            <div className="mt-2 space-y-1" data-testid="inspector-selected">
              <p>
                {UI.inspector.selected}: <code className="font-mono text-xs">{featureId(s.selected)}</code>
              </p>
              <p className="text-ink-muted">{UI.inspector.placeholder}</p>
            </div>
          ) : (
            <p className="mt-2 text-ink-muted">{UI.inspector.none}</p>
          )}
          <p className="mt-2 text-xs text-ink-muted">{UI.inspector.hint}</p>
        </GlassPanel>
      )}

      {/* 하단 타임라인 44px 접힘 / 200px 펼침 (T) */}
      <GlassPanel
        as="section"
        data-testid="timeline"
        data-open={s.timelineOpen}
        aria-label="타임라인"
        className="absolute px-4 text-sm"
        style={{ bottom: GAP, left: GAP, right: GAP, height: tlH }}
      >
        <button
          onClick={s.toggleTimeline}
          aria-expanded={s.timelineOpen}
          className="flex h-[44px] items-center gap-2 font-semibold"
        >
          {s.timelineOpen ? <ChevronDown size={16} aria-hidden="true" /> : <ChevronUp size={16} aria-hidden="true" />}
          타임라인
          <span className="font-normal text-ink-muted">(P19) · T 키로 펼치기</span>
        </button>
      </GlassPanel>

      {s.paletteOpen && (
        <Suspense fallback={null}>
          <CommandPalette />
        </Suspense>
      )}
    </div>
  )
}

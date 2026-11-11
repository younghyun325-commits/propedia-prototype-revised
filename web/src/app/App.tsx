import { lazy, Suspense, useDeferredValue, useEffect, useMemo, useState } from 'react'
import { UI } from '../copy/ui'
import { IconRail } from '../panel/IconRail'
import { LeftPanel } from '../panel/LeftPanel'
import { BottomSheet, sheetHeight, type SheetSnap, type SheetTab } from '../ui/BottomSheet'
import { useViewport } from '../ui/useViewport'
import { useMapStore } from '../state/useMapStore'
import { useUrlSync } from '../state/useUrlSync'
import { GlassPanel } from '../ui/GlassPanel'
import { ResizeHandle } from '../ui/ResizeHandle'
import { DEFAULT_WIDTHS, fitWidths, LEFT_RANGE, maxWidth, readWidths, RIGHT_RANGE, writeWidths, type Side, type Widths } from '../ui/panelSize'
import { LiquidGlassFilter } from '../ui/LiquidGlassFilter'
import { useLiquidGlass } from '../ui/useLiquidGlass'
import { TopBar } from './TopBar'
import { useShellEffects } from './useShellEffects'
import type { Insets } from '../map/insets'

// 지도(MapLibre)는 따로 묶어 셸 다음에 불러온다: 셸이 먼저 뜨고 초기 JS 예산(gzip 400KB)을 지킨다
const MapView = lazy(() => import('../map/MapView'))
// 명령 팔레트는 Ctrl+K로 처음 열 때 불러온다
const CommandPalette = lazy(() => import('../search/CommandPalette'))
// 인스펙터·원문 모달은 따로 묶는다 (P16, 초기 JS 예산)
const Inspector = lazy(() => import('../inspector/Inspector'))
const EvidenceModal = lazy(() => import('../ui/EvidenceModal'))
// 하단 타임라인 (P19): d3-scale·SVG는 따로 묶는다
const Timeline = lazy(() => import('../timeline/Timeline'))
// 단축키 도움말 (P20): ? 키로 처음 열 때 불러온다
const ShortcutsModal = lazy(() => import('../ui/ShortcutsModal'))

const GAP = 12 // 패널과 화면 가장자리 사이
const TOP_H = 56
const HANDLE_W = 12
const TL_CLOSED = 44
const TL_OPEN = 200
const RAIL_W = 52 // 접힌 좌측 패널 아이콘 줄 (P20, 1024~1279px)
const NOTICE_H = 30 // 1024px 미만 안내 줄

export default function App() {
  useLiquidGlass()
  useShellEffects()
  useUrlSync()
  const s = useMapStore()
  // 반응형 (P20): wide ≥1280 기본 / mid 1024~1279 좌측 접힘·인스펙터 겹침 / narrow <1024 보기 전용·하단 시트
  const vp = useViewport()
  const mid = vp === 'mid'
  const narrow = vp === 'narrow'
  // 단계가 바뀌면 좌측 패널 기본값: 넓으면 펼침, 좁으면 접힘. 1024px 미만은 반경 보기를 끈다
  useEffect(() => {
    useMapStore.setState({ leftOpen: vp === 'wide' })
    if (vp === 'narrow') {
      const st = useMapStore.getState()
      if (st.radiusTool) st.setRadiusTool(false)
    }
  }, [vp])
  const [sheet, setSheet] = useState<{ snap: SheetSnap; tab: SheetTab }>({ snap: 'collapsed', tab: 'info' })
  // 1024px 미만에서 대상을 고르면 시트를 '정보' 탭 절반 높이로
  const selKey = s.selected ? `${s.selected.kind}:${s.selected.id}` : s.parcel.status !== 'idle' ? 'parcel' : ''
  useEffect(() => {
    if (narrow && selKey) setSheet((v) => ({ tab: 'info', snap: v.snap === 'collapsed' ? 'half' : v.snap }))
  }, [narrow, selKey])
  const [vh, setVh] = useState(() => window.innerHeight)
  const [vw, setVw] = useState(() => window.innerWidth)
  useEffect(() => {
    const on = () => {
      setVh(window.innerHeight)
      setVw(window.innerWidth)
    }
    window.addEventListener('resize', on)
    return () => window.removeEventListener('resize', on)
  }, [])

  const tlH = s.timelineOpen ? TL_OPEN : TL_CLOSED
  const sideTop = GAP + TOP_H + GAP + (narrow ? NOTICE_H : 0)
  const sheetH = sheetHeight(sheet.snap, vh - sideTop)
  const sideBottom = narrow ? sheetH : GAP + tlH + GAP
  // mid: 인스펙터는 고른 것이 있을 때만, 지도 위에 겹쳐 뜬다 (지도 영역을 줄이지 않음)
  const hasSelection = !!selKey
  const showInspector = !narrow && s.rightOpen && (!mid || hasSelection)
  const shown = { left: !narrow && s.leftOpen, right: showInspector }
  const [want, setWant] = useState<Widths>(() => readWidths())
  useEffect(() => {
    const t = window.setTimeout(() => writeWidths(want), 250)
    return () => window.clearTimeout(t)
  }, [want])
  const eff = fitWidths(want, vw, shown)
  const LEFT_W = eff.left
  const RIGHT_W = eff.right
  const maxOf = (side: Side) => maxWidth(side, eff, vw, shown)
  const resize = (side: Side) => (w: number) =>
    setWant((prev) => {
      const cur = fitWidths(prev, vw, shown)
      const range = side === 'left' ? LEFT_RANGE : RIGHT_RANGE
      return { ...cur, [side]: Math.round(Math.min(maxWidth(side, cur, vw, shown), Math.max(range.min, w))) }
    })
  const reset = (side: Side) => () => setWant((prev) => ({ ...prev, [side]: DEFAULT_WIDTHS[side] }))
  const leftW = s.leftOpen ? GAP + LEFT_W + GAP : mid ? GAP + RAIL_W + GAP : GAP
  // 지도 위 보이는 영역 (패널을 뺀 곳): 첫 화면 맞춤·지도 컨트롤 위치에 쓴다
  const insets: Insets = useMemo(
    () => ({
      top: sideTop,
      bottom: narrow ? sideBottom + GAP : sideBottom,
      left: narrow ? GAP : leftW,
      right: !narrow && !mid && s.rightOpen ? GAP + RIGHT_W + GAP : GAP,
    }),
    [sideTop, sideBottom, narrow, mid, leftW, s.rightOpen, RIGHT_W],
  )
  const mapInsets = useDeferredValue(insets)

  return (
    <div className="relative h-full w-full overflow-hidden">
      <LiquidGlassFilter />

      {/* 지도: 화면 전체. 패널은 그 위에 뜬 글래스 카드 */}
      <Suspense fallback={<div className="map-loading absolute inset-0" data-testid="map-loading" aria-hidden="true" />}>
        <MapView insets={mapInsets} />
      </Suspense>

      {/* 상단 바 56px */}
      <TopBar compact={narrow} style={{ top: GAP, left: GAP, right: GAP, height: TOP_H }} />

      {/* 1024px 미만: 보기 전용 안내 (P20) */}
      {narrow && (
        <GlassPanel as="aside" aria-label={UI.shell.noticeLabel} data-testid="narrow-notice" className="absolute flex items-center justify-center px-3 text-meta"
          style={{ top: GAP + TOP_H + 4, left: GAP, right: GAP, height: NOTICE_H - 6, borderRadius: 999 }}>
          {UI.shell.narrowNotice}
        </GlassPanel>
      )}

      {/* 좌측 패널 320px (L). 1024~1279px는 접으면 아이콘 줄 */}
      {!narrow && s.leftOpen && <LeftPanel collapsible={mid} style={{ top: sideTop, bottom: sideBottom, left: GAP, width: LEFT_W }} />}
      {mid && !s.leftOpen && <IconRail style={{ top: sideTop, left: GAP, width: RAIL_W }} />}
      {shown.left && (
        <ResizeHandle side="left" label={UI.shell.leftWidth} value={LEFT_W} min={LEFT_RANGE.min} max={maxOf('left')}
          style={{ top: sideTop, bottom: sideBottom, left: GAP + LEFT_W - 2, width: HANDLE_W }}
          onChange={resize('left')} onReset={reset('left')} />
      )}

      {/* 우측 인스펙터 400px (I, P16). 1024~1279px는 지도 위에 겹쳐 뜬다 */}
      {showInspector && (
        <Suspense
          fallback={
            <GlassPanel
              as="aside"
              data-testid="right-panel"
              aria-label={UI.inspector.title}
              aria-busy="true"
              className="absolute"
              style={{ top: sideTop, bottom: sideBottom, right: GAP, width: RIGHT_W }}
            />
          }
        >
          <Inspector style={{ top: sideTop, bottom: sideBottom, right: GAP, width: RIGHT_W }} />
        </Suspense>
      )}

      {showInspector && (
        <ResizeHandle side="right" label={UI.shell.rightWidth} value={RIGHT_W} min={RIGHT_RANGE.min} max={maxOf('right')}
          style={{ top: sideTop, bottom: sideBottom, right: GAP + RIGHT_W - 2, width: HANDLE_W }}
          onChange={resize('right')} onReset={reset('right')} />
      )}

      {/* 1024px 미만: 좌측 패널·인스펙터·타임라인을 하단 시트 탭으로 (P20) */}
      {narrow && (
        <BottomSheet
          style={{ left: 0, right: 0, bottom: 0, height: sheetH }}
          snap={sheet.snap}
          tab={sheet.tab}
          onSnap={(snap) => setSheet((v) => ({ ...v, snap }))}
          onTab={(tab) => setSheet((v) => ({ ...v, tab }))}
        />
      )}

      {/* 하단 타임라인 44px 접힘 / 200px 펼침 (T) */}
      {!narrow && (
      <GlassPanel
        as="section"
        data-testid="timeline"
        data-open={s.timelineOpen}
        aria-label={UI.time.title}
        className="absolute px-4 pb-1 text-body"
        style={{ bottom: GAP, left: GAP, right: GAP, height: tlH }}
      >
        <Suspense
          fallback={
            <button onClick={s.toggleTimeline} aria-expanded={s.timelineOpen} className="flex h-[44px] items-center gap-2 font-semibold">
              {UI.time.title}
            </button>
          }
        >
          <Timeline />
        </Suspense>
      </GlassPanel>
      )}

      {s.evidence && (
        <Suspense fallback={null}>
          <EvidenceModal />
        </Suspense>
      )}

      {s.paletteOpen && (
        <Suspense fallback={null}>
          <CommandPalette />
        </Suspense>
      )}

      {s.shortcutsOpen && (
        <Suspense fallback={null}>
          <ShortcutsModal />
        </Suspense>
      )}
    </div>
  )
}

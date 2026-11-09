import { ChevronDown, ChevronUp, Contrast, Search } from 'lucide-react'
import { BRAND } from '../copy/brand'
import { useMapStore, type Workspace } from '../state/useMapStore'
import { GlassPanel } from '../ui/GlassPanel'
import { LiquidGlassFilter } from '../ui/LiquidGlassFilter'
import { useLiquidGlass } from '../ui/useLiquidGlass'
import { useShellEffects } from './useShellEffects'

const GAP = 12 // 패널과 화면 가장자리 사이
const TOP_H = 56
const LEFT_W = 320
const RIGHT_W = 400
const TL_CLOSED = 44
const TL_OPEN = 200

const TABS: { id: Workspace; label: string }[] = [
  { id: 'gangnam', label: '강남구 전체' },
  { id: 'project', label: '선택한 사업' },
]

export default function App() {
  useLiquidGlass()
  useShellEffects()
  const s = useMapStore()
  const tlH = s.timelineOpen ? TL_OPEN : TL_CLOSED
  const sideTop = GAP + TOP_H + GAP
  const sideBottom = GAP + tlH + GAP

  return (
    <div className="relative h-full w-full overflow-hidden">
      <LiquidGlassFilter />

      {/* 지도 자리: 화면 전체 (P12에서 MapLibre로 교체) */}
      <div
        className="map-placeholder absolute inset-0 grid place-items-center text-sm text-ink-muted"
        data-testid="map"
        aria-label="지도 자리"
      >
        지도 (P12)
      </div>

      {/* 상단 바 56px */}
      <GlassPanel
        as="header"
        data-testid="topbar"
        className="absolute flex items-center gap-4 px-4"
        style={{ top: GAP, left: GAP, right: GAP, height: TOP_H }}
      >
        <img
          src={`${import.meta.env.BASE_URL}brand/logo-wordmark.png`}
          alt={BRAND.logoAlt}
          className="h-6 w-auto select-none"
          draggable={false}
        />
        <nav className="flex gap-1" role="tablist" aria-label="작업 탭">
          {TABS.map((t) => {
            const on = s.workspace === t.id
            return (
              <button
                key={t.id}
                role="tab"
                aria-selected={on}
                onClick={() => s.setWorkspace(t.id)}
                className={`glass glass-liquid rounded-full px-3 py-1 text-sm ${on ? 'font-semibold' : ''}`}
                style={{ borderRadius: 999 }}
              >
                {t.label}
              </button>
            )
          })}
        </nav>
        <label className="ml-2 flex h-9 max-w-md flex-1 items-center gap-2 rounded-full bg-white/60 px-3 text-sm text-ink-muted">
          <Search size={16} aria-hidden="true" />
          <input
            disabled
            placeholder="주소·지번·사업명 검색 (P14)"
            className="w-full bg-transparent outline-none placeholder:text-ink-muted"
            aria-label="검색"
          />
        </label>
        <div className="ml-auto flex items-center gap-3 text-sm">
          <button
            onClick={s.toggleReduceTransparency}
            aria-pressed={s.reduceTransparency}
            title="투명도 줄이기"
            className="flex items-center gap-1 text-ink-muted"
          >
            <Contrast size={16} aria-hidden="true" />
            <span>투명도 줄이기</span>
          </button>
          <span data-testid="as-of" className="text-ink-muted">
            기준일 —
          </span>
        </div>
      </GlassPanel>

      {/* 좌측 패널 320px (L) */}
      {s.leftOpen && (
        <GlassPanel
          as="aside"
          data-testid="left-panel"
          aria-label="레이어 패널"
          className="absolute p-4 text-sm"
          style={{ top: sideTop, bottom: sideBottom, left: GAP, width: LEFT_W }}
        >
          <h2 className="font-semibold">레이어</h2>
          <p className="mt-2 text-ink-muted">레이어 패널 자리 (P14) · L 키로 접기</p>
        </GlassPanel>
      )}

      {/* 우측 인스펙터 400px (I) */}
      {s.rightOpen && (
        <GlassPanel
          as="aside"
          data-testid="right-panel"
          aria-label="인스펙터"
          className="absolute p-4 text-sm"
          style={{ top: sideTop, bottom: sideBottom, right: GAP, width: RIGHT_W }}
        >
          <h2 className="font-semibold">인스펙터</h2>
          <p className="mt-2 text-ink-muted">
            {s.selection ? `선택: ${s.selection}` : '선택한 대상 없음'} · I 키로 접기 · Esc 선택 해제
          </p>
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
    </div>
  )
}

/**
 * 하단 시트 (P20, 1024px 미만 보기 전용): 좌측 패널 탭(레이어·사업 목록·고시 피드·데이터 상태) + 정보(인스펙터) + 타임라인.
 * 높이 3단(접힘·절반·전체) — 손잡이 버튼(누를 때마다 다음 단)과 단 버튼으로 바꾼다. 키보드로도 같은 버튼을 쓴다.
 * 겉모양은 GlassPanel 하나 (안쪽 내용은 글래스를 겹치지 않는다).
 */
import { lazy, Suspense, type CSSProperties, type ReactNode } from 'react'
import { GripHorizontal } from 'lucide-react'
import { UI } from '../copy/ui'
import { LeftPanelBody } from '../panel/LeftPanel'
import { useMapStore } from '../state/useMapStore'
import { LEFT_TABS, type LeftTab } from '../state/url'
import { GlassPanel } from './GlassPanel'

const Inspector = lazy(() => import('../inspector/Inspector'))
const Timeline = lazy(() => import('../timeline/Timeline'))

export type SheetSnap = 'collapsed' | 'half' | 'full'
export type SheetTab = LeftTab | 'info' | 'timeline'
export const SHEET_SNAPS: SheetSnap[] = ['collapsed', 'half', 'full']
export const SHEET_TABS: SheetTab[] = ['info', ...LEFT_TABS, 'timeline']
/** 접힘 높이: 손잡이 + 탭 줄 */
export const SHEET_COLLAPSED = 88

export function nextSnap(s: SheetSnap): SheetSnap {
  return SHEET_SNAPS[(SHEET_SNAPS.indexOf(s) + 1) % SHEET_SNAPS.length]
}

export function sheetHeight(snap: SheetSnap, available: number): number {
  if (snap === 'collapsed') return SHEET_COLLAPSED
  if (snap === 'half') return Math.max(SHEET_COLLAPSED, Math.round(available * 0.5))
  return Math.max(SHEET_COLLAPSED, available)
}

const label = (t: SheetTab) => (t === 'info' ? UI.sheet.info : t === 'timeline' ? UI.sheet.timeline : UI.left.tabs[t])

export function BottomSheet({ style, snap, tab, onSnap, onTab }: {
  style: CSSProperties
  snap: SheetSnap
  tab: SheetTab
  onSnap: (s: SheetSnap) => void
  onTab: (t: SheetTab) => void
}) {
  const setLeftTab = useMapStore((s) => s.setLeftTab)
  const pick = (t: SheetTab) => {
    onTab(t)
    if (t !== 'info' && t !== 'timeline') setLeftTab(t)
    if (t === 'timeline' && !useMapStore.getState().timelineOpen) useMapStore.getState().toggleTimeline()
    if (snap === 'collapsed') onSnap('half')
  }
  let body: ReactNode = null
  if (snap !== 'collapsed') {
    if (tab === 'info')
      body = (
        <Suspense fallback={<p className="p-4 text-ink-muted">{UI.left.loading}</p>}>
          <Inspector bare style={{}} />
        </Suspense>
      )
    else if (tab === 'timeline')
      body = (
        <div className="h-[200px] px-4" data-testid="sheet-timeline">
          <Suspense fallback={null}>
            <Timeline />
          </Suspense>
        </div>
      )
    else body = <div className="p-4"><LeftPanelBody tab={tab} /></div>
  }
  return (
    <GlassPanel as="section" data-testid="bottom-sheet" data-snap={snap} data-tab={tab} aria-label={UI.sheet.label}
      className="absolute flex flex-col overflow-hidden text-body" style={{ ...style, borderRadius: '16px 16px 0 0' }}>
      <button
        type="button"
        data-testid="sheet-handle"
        onClick={() => onSnap(nextSnap(snap))}
        aria-label={UI.sheet.handle(UI.sheet.snaps[snap], UI.sheet.snaps[nextSnap(snap)])}
        className="flex h-6 w-full shrink-0 items-center justify-center text-ink-muted focus-visible:outline-2 focus-visible:outline-brand-indigo"
      >
        <GripHorizontal size={20} aria-hidden="true" />
      </button>
      <div className="flex shrink-0 items-center gap-1 border-b border-ink/10 px-2 pb-2">
        <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto" role="tablist" aria-label={UI.sheet.label}>
        {SHEET_TABS.map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={tab === t}
            data-testid={`sheet-tab-${t}`}
            onClick={() => pick(t)}
            className={`shrink-0 rounded-full px-3 py-1.5 text-meta focus-visible:outline-2 focus-visible:outline-brand-indigo ${tab === t ? 'bg-white/80 font-semibold' : 'text-ink-muted'}`}
          >
            {label(t)}
          </button>
        ))}
        </div>
        <span className="flex shrink-0 gap-0.5 pl-1" role="group" aria-label={UI.sheet.snapGroup}>
          {SHEET_SNAPS.map((s) => (
            <button
              key={s}
              type="button"
              aria-pressed={snap === s}
              data-testid={`sheet-snap-${s}`}
              onClick={() => onSnap(s)}
              title={UI.sheet.snaps[s]}
              aria-label={UI.sheet.snaps[s]}
              className="inline-flex h-6 w-6 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-brand-indigo"
            >
              <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${snap === s ? 'bg-brand-indigo' : 'bg-ink/25'}`} />
            </button>
          ))}
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain" data-testid="sheet-body">{body}</div>
    </GlassPanel>
  )
}

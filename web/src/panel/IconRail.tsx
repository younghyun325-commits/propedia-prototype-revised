/** 접힌 좌측 패널의 아이콘 줄 (P20, 1024~1279px): 탭 아이콘을 누르면 그 탭으로 패널을 연다. */
import type { CSSProperties } from 'react'
import { Database, Layers, List, Newspaper, type LucideIcon } from 'lucide-react'
import { UI } from '../copy/ui'
import { useMapStore } from '../state/useMapStore'
import { LEFT_TABS, type LeftTab } from '../state/url'
import { GlassPanel } from '../ui/GlassPanel'

export const TAB_ICONS: Record<LeftTab, LucideIcon> = { layers: Layers, projects: List, feed: Newspaper, status: Database }

export function IconRail({ style }: { style: CSSProperties }) {
  const tab = useMapStore((s) => s.leftTab)
  const open = (t: LeftTab) => {
    const s = useMapStore.getState()
    s.setLeftTab(t)
    if (!s.leftOpen) s.toggleLeft()
  }
  return (
    <GlassPanel as="nav" data-testid="icon-rail" aria-label={UI.left.panelLabel} className="absolute flex flex-col items-center gap-1 py-2" style={style}>
      {LEFT_TABS.map((t) => {
        const Icon = TAB_ICONS[t]
        return (
          <button
            key={t}
            type="button"
            data-testid={`rail-${t}`}
            aria-label={`${UI.left.tabs[t]} ${UI.left.openPanel}`}
            title={UI.left.tabs[t]}
            aria-current={tab === t ? 'true' : undefined}
            onClick={() => open(t)}
            className={`inline-flex h-9 w-9 items-center justify-center rounded-lg hover:bg-white/80 focus-visible:outline-2 focus-visible:outline-brand-indigo ${tab === t ? 'text-brand-indigo' : 'text-ink-muted'}`}
          >
            <Icon size={18} aria-hidden="true" />
          </button>
        )
      })}
    </GlassPanel>
  )
}

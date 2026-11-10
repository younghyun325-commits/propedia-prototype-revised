/** 좌측 패널 320px (P14): 레이어 · 사업 목록 · 고시 피드 · 데이터 상태. 스크롤은 패널 안에서만. */
import type { CSSProperties } from 'react'
import { useHealth, useManifest, useMapProjects } from '../api/map'
import { UI } from '../copy/ui'
import { useMapStore } from '../state/useMapStore'
import { LEFT_TABS, type LeftTab } from '../state/url'
import { GlassPanel } from '../ui/GlassPanel'
import { FeedTab } from './FeedTab'
import { LayersTab } from './LayersTab'
import { ProjectsTab } from './ProjectsTab'
import { StatusTab } from './StatusTab'

function Pending({ error }: { error?: unknown }) {
  return (
    <p className="text-ink-muted" role={error ? 'alert' : 'status'}>
      {error ? `${UI.left.loadError} (${error instanceof Error ? error.message : ''})` : UI.left.loading}
    </p>
  )
}

export function LeftPanel({ style }: { style: CSSProperties }) {
  const tab = useMapStore((s) => s.leftTab)
  const setTab = useMapStore((s) => s.setLeftTab)
  const manifest = useManifest()
  const projects = useMapProjects()
  const health = useHealth()

  const body = (t: LeftTab) => {
    if (t === 'feed') return <FeedTab />
    if (t === 'projects')
      return projects.data ? <ProjectsTab projects={projects.data.projects} /> : <Pending error={projects.error} />
    if (!manifest.data) return <Pending error={manifest.error} />
    return t === 'layers' ? <LayersTab manifest={manifest.data} /> : <StatusTab manifest={manifest.data} health={health.data} />
  }

  return (
    <GlassPanel
      as="aside"
      data-testid="left-panel"
      aria-label={UI.left.panelLabel}
      className="absolute flex flex-col text-sm"
      style={style}
    >
      <div role="tablist" aria-label={UI.left.panelLabel} className="flex gap-1 border-b border-ink/10 px-3 pt-3">
        {LEFT_TABS.map((t) => (
          <button
            key={t}
            role="tab"
            id={`left-tab-${t}`}
            aria-selected={tab === t}
            aria-controls="left-tabpanel"
            data-testid={`left-tab-${t}`}
            onClick={() => setTab(t)}
            className={`left-tab rounded-t-lg px-2 pb-2 text-[13px] ${tab === t ? 'font-semibold' : 'text-ink-muted'}`}
          >
            {UI.left.tabs[t]}
          </button>
        ))}
      </div>
      <div
        id="left-tabpanel"
        role="tabpanel"
        aria-labelledby={`left-tab-${tab}`}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-4"
      >
        {body(tab)}
      </div>
    </GlassPanel>
  )
}

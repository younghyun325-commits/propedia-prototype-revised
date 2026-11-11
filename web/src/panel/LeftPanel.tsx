/** 좌측 패널 320px (P14): 레이어 · 사업 목록 · 고시 피드 · 데이터 상태. 스크롤은 패널 안에서만. */
import type { CSSProperties } from 'react'
import { PanelLeftClose } from 'lucide-react'
import { useHealth, useManifest, useMapProjects } from '../api/map'
import { UI } from '../copy/ui'
import { useMapStore } from '../state/useMapStore'
import { LEFT_TABS, type LeftTab } from '../state/url'
import { GlassPanel } from '../ui/GlassPanel'
import { FeedTab } from './FeedTab'
import { LayersTab } from './LayersTab'
import { ProjectsTab } from './ProjectsTab'
import { StatusTab } from './StatusTab'
import { TAB_ICONS } from './IconRail'
import { useOverflowCompact } from '../ui/useOverflow'

function Pending({ error }: { error?: unknown }) {
  return (
    <p className="text-ink-muted" role={error ? 'alert' : 'status'}>
      {error ? `${UI.left.loadError} (${error instanceof Error ? error.message : ''})` : UI.left.loading}
    </p>
  )
}

/** 탭 본문 (P20: 하단 시트에서도 쓴다) */
export function LeftPanelBody({ tab: t }: { tab: LeftTab }) {
  const manifest = useManifest()
  const projects = useMapProjects()
  const health = useHealth()
  if (t === 'feed') return <FeedTab />
  if (t === 'projects')
    return projects.data ? <ProjectsTab projects={projects.data.projects} /> : <Pending error={projects.error} />
  if (!manifest.data) return <Pending error={manifest.error} />
  return t === 'layers' ? <LayersTab manifest={manifest.data} /> : <StatusTab manifest={manifest.data} health={health.data} />
}

/** collapsible (P20, 1024~1279px): 탭 줄 끝에 접기 버튼 — 접으면 아이콘 줄(IconRail)로 */
export function LeftPanel({ style, collapsible = false }: { style: CSSProperties; collapsible?: boolean }) {
  const tab = useMapStore((s) => s.leftTab)
  const setTab = useMapStore((s) => s.setLeftTab)
  const [tabsRef, iconTabs] = useOverflowCompact<HTMLDivElement>()

  return (
    <GlassPanel
      as="aside"
      data-testid="left-panel"
      aria-label={UI.left.panelLabel}
      className="@container absolute flex flex-col text-body"
      style={style}
    >
      <div ref={tabsRef} role="tablist" aria-label={UI.left.panelLabel} data-icon-tabs={iconTabs ? '1' : '0'}
        className="flex flex-nowrap gap-1 border-b border-ink/10 px-3 pt-3">
        {LEFT_TABS.map((t) => {
          const Icon = TAB_ICONS[t]
          return (
          <button
            key={t}
            role="tab"
            id={`left-tab-${t}`}
            aria-selected={tab === t}
            aria-controls="left-tabpanel"
            data-testid={`left-tab-${t}`}
            onClick={() => setTab(t)}
            aria-label={iconTabs ? UI.left.tabs[t] : undefined}
            title={iconTabs ? UI.left.tabs[t] : undefined}
            className={`left-tab shrink-0 whitespace-nowrap rounded-t-lg px-2 pb-2 text-meta ${tab === t ? 'font-semibold text-ink' : 'text-ink-muted'}`}
          >
            {iconTabs ? <Icon size={18} aria-hidden="true" className="mx-1" /> : UI.left.tabs[t]}
          </button>
          )
        })}
        {collapsible && (
          <button
            type="button"
            data-testid="left-collapse"
            onClick={() => useMapStore.getState().toggleLeft()}
            aria-label={UI.left.closePanel}
            title={UI.left.closePanel}
            className="ml-auto mb-1.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-ink-muted hover:bg-white/80 focus-visible:outline-2 focus-visible:outline-brand-indigo"
          >
            <PanelLeftClose size={16} aria-hidden="true" />
          </button>
        )}
      </div>
      <div
        id="left-tabpanel"
        role="tabpanel"
        aria-labelledby={`left-tab-${tab}`}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-4"
      >
        <LeftPanelBody tab={tab} />
      </div>
    </GlassPanel>
  )
}

/** 상단 바 56px (P14 4): 로고 · 작업 탭 · 검색(Ctrl+K) · 서울·구 고시 칩 · 기준일. */
import { useState, type CSSProperties } from 'react'
import { Contrast, Search } from 'lucide-react'
import { useHealth, useMapProjects, useNotices, type Notice } from '../api/map'
import { BRAND } from '../copy/brand'
import { UI } from '../copy/ui'
import { todayKst } from '../state/actions'
import { useMapStore } from '../state/useMapStore'
import { GlassPanel } from '../ui/GlassPanel'
import { Popover } from '../ui/Floating'

const MAX_CHIPS = 3

function NoticeBody({ n }: { n: Notice }) {
  const src = n.source
  return (
    <div className="space-y-1" data-testid="notice-popover">
      <p className="font-semibold">{n.short_title}</p>
      <p>
        <span className="text-ink-muted">{UI.topbar.kind}</span> {n.kind_label}
      </p>
      <p>
        <span className="text-ink-muted">{UI.topbar.effective}</span>{' '}
        {n.effective_label ? `${n.effective_label} (${n.effective_status_label})` : UI.topbar.noEffective}
      </p>
      <p>
        <span className="text-ink-muted">{UI.topbar.evidence}</span> {src.doc_id} · p{src.pdf_page}
        {src.page_image && (
          <>
            {' · '}
            <a href={src.page_image} target="_blank" rel="noreferrer" className="underline">
              {UI.topbar.openPage}
            </a>
          </>
        )}
      </p>
    </div>
  )
}

function NoticeChips() {
  const { data } = useNotices()
  const [open, setOpen] = useState<{ key: string; el: HTMLElement } | null>(null)
  const items = data?.items ?? []
  const shown = items.slice(0, MAX_CHIPS)
  const rest = items.slice(MAX_CHIPS)
  const chip = 'glass-liquid max-w-[11rem] truncate rounded-full bg-white/70 px-2.5 py-1 text-xs'
  return (
    <div className="flex min-w-0 items-center gap-1" role="group" aria-label={UI.topbar.noticesLabel} data-testid="notice-chips">
      {shown.map((n) => (
        <button
          key={n.item_key}
          type="button"
          data-testid="notice-chip"
          title={n.short_title}
          aria-expanded={open?.key === n.item_key}
          onClick={(e) => setOpen(open?.key === n.item_key ? null : { key: n.item_key, el: e.currentTarget })}
          className={chip}
        >
          {n.short_title}
        </button>
      ))}
      {rest.length > 0 && (
        <button
          type="button"
          data-testid="notice-more"
          aria-expanded={open?.key === '+'}
          onClick={(e) => setOpen(open?.key === '+' ? null : { key: '+', el: e.currentTarget })}
          className={chip}
        >
          {UI.topbar.moreNotices(rest.length)}
        </button>
      )}
      <Popover anchor={open?.el ?? null} open={!!open} onClose={() => setOpen(null)} label={UI.topbar.noticesLabel}>
        {open?.key === '+'
          ? rest.map((n) => (
              <div key={n.item_key} className="border-t border-ink/10 py-1 first:border-0">
                <NoticeBody n={n} />
              </div>
            ))
          : items.filter((n) => n.item_key === open?.key).map((n) => <NoticeBody key={n.item_key} n={n} />)}
      </Popover>
    </div>
  )
}

export function TopBar({ style }: { style: CSSProperties }) {
  const workspace = useMapStore((s) => s.workspace)
  const selected = useMapStore((s) => s.selected)
  const reduce = useMapStore((s) => s.reduceTransparency)
  const projects = useMapProjects().data?.projects ?? []
  const health = useHealth().data
  const selProject = selected?.kind === 'project' ? projects.find((p) => String(p.id) === selected.id) : undefined

  const goGangnam = () => {
    const s = useMapStore.getState()
    s.setWorkspace('gangnam')
    s.requestView({ type: 'home' })
  }
  const goProject = () => {
    if (!selProject?.bbox) return
    const s = useMapStore.getState()
    s.setWorkspace('project')
    s.requestView({ type: 'bbox', bbox: selProject.bbox })
  }

  return (
    <GlassPanel as="header" data-testid="topbar" className="absolute flex items-center gap-3 px-4" style={style}>
      <img
        src={`${import.meta.env.BASE_URL}brand/logo-wordmark.png`}
        alt={BRAND.logoAlt}
        className="h-6 w-auto shrink-0 select-none"
        draggable={false}
      />
      <nav className="flex shrink-0 gap-1" role="tablist" aria-label={UI.topbar.tabsLabel}>
        {(
          [
            ['gangnam', UI.topbar.gangnam, goGangnam, false],
            ['project', UI.topbar.project, goProject, !selProject],
          ] as const
        ).map(([id, label, onClick, disabled]) => {
          const on = workspace === id && !disabled
          return (
            <button
              key={id}
              role="tab"
              aria-selected={on}
              aria-disabled={disabled || undefined}
              disabled={disabled}
              title={disabled ? UI.topbar.projectDisabled : undefined}
              data-testid={`work-tab-${id}`}
              onClick={onClick}
              className={`work-tab glass glass-liquid rounded-full px-3 py-1 text-sm ${on ? 'font-semibold' : ''} disabled:text-ink-muted`}
              style={{ borderRadius: 999 }}
            >
              {label}
            </button>
          )
        })}
      </nav>
      <button
        type="button"
        data-testid="search-open"
        onClick={() => useMapStore.getState().setPaletteOpen(true)}
        className="flex h-9 w-56 shrink-0 items-center gap-2 rounded-full bg-white/60 px-3 text-sm text-ink-muted"
        aria-keyshortcuts="Control+K Meta+K"
      >
        <Search size={16} aria-hidden="true" />
        <span className="flex-1 truncate text-left">{UI.topbar.search}</span>
        <kbd className="rounded bg-ink/8 px-1.5 text-[11px]">{UI.topbar.searchKey}</kbd>
      </button>
      <NoticeChips />
      <div className="ml-auto flex shrink-0 items-center gap-3 text-xs">
        <button
          onClick={() => useMapStore.getState().toggleReduceTransparency()}
          aria-pressed={reduce}
          title={UI.topbar.reduceTransparency}
          aria-label={UI.topbar.reduceTransparency}
          className="flex items-center gap-1 text-ink-muted"
        >
          <Contrast size={16} aria-hidden="true" />
        </button>
        <span data-testid="as-of" className="text-right leading-tight text-ink-muted">
          {UI.topbar.today} <span className="tabular-nums text-ink">{todayKst()}</span>
          <br />
          {UI.topbar.dbAsOf} <span className="tabular-nums">{health?.as_of ?? '—'}</span>
        </span>
      </div>
    </GlassPanel>
  )
}

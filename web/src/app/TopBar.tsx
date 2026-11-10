/** 상단 바 56px (P14 4): 로고 · 작업 탭 · 검색(Ctrl+K) · 서울·구 고시 칩 · 기준일. */
import { useRef, useState, type CSSProperties } from 'react'
import { ExternalLink, Keyboard, Search, Settings } from 'lucide-react'
import { useHealth, useMapProjects, useNotices, type Notice } from '../api/map'
import { BRAND } from '../copy/brand'
import { UI } from '../copy/ui'
import { todayIso, todayKst } from '../state/dates'
import { useMapStore } from '../state/useMapStore'
import { GlassPanel } from '../ui/GlassPanel'
import { Popover } from '../ui/Floating'

const MAX_CHIPS = 3

/**
 * 설정 메뉴 (P20): P11 임시 토글 '투명도 줄이기'를 옮김(선택은 이 브라우저에 저장), 단축키 보기, 기존 화면 링크.
 */
function SettingsMenu() {
  const reduce = useMapStore((s) => s.reduceTransparency)
  const btn = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  const close = () => {
    setOpen(false)
    btn.current?.focus()
  }
  const row = 'flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs hover:bg-white/80 focus-visible:outline-2 focus-visible:outline-brand-indigo'
  return (
    <>
      <button
        ref={btn}
        type="button"
        data-testid="settings-open"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={UI.topbar.settings}
        title={UI.topbar.settings}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex h-8 w-8 items-center justify-center rounded-full text-ink-muted hover:bg-white/70 focus-visible:outline-2 focus-visible:outline-brand-indigo"
      >
        <Settings size={16} aria-hidden="true" />
      </button>
      <Popover anchor={btn.current} open={open} onClose={close} width={240} testId="settings-menu" label={UI.topbar.settings}>
        <div className="space-y-0.5">
          <button
            type="button"
            role="switch"
            aria-checked={reduce}
            data-testid="reduce-transparency"
            onClick={() => useMapStore.getState().toggleReduceTransparency()}
            className={row}
          >
            <span className="flex-1">{UI.topbar.reduceTransparency}</span>
            <span aria-hidden="true" className={`h-4 w-7 rounded-full p-0.5 ${reduce ? 'bg-brand-indigo' : 'bg-ink/20'}`}>
              <span className={`block h-3 w-3 rounded-full bg-white transition-transform ${reduce ? 'translate-x-3' : ''}`} />
            </span>
          </button>
          <button
            type="button"
            data-testid="shortcuts-open"
            aria-keyshortcuts="Shift+Slash"
            onClick={() => {
              setOpen(false)
              btn.current?.focus() // 도움말을 닫으면 설정 버튼으로 포커스가 돌아온다
              useMapStore.getState().setShortcutsOpen(true)
            }}
            className={row}
          >
            <Keyboard size={14} aria-hidden="true" />
            <span className="flex-1">{UI.topbar.shortcuts}</span>
            <kbd className="rounded bg-ink/8 px-1.5 text-[11px]">?</kbd>
          </button>
          <p className="px-2 pt-1.5 text-[11px] text-ink-muted">{UI.topbar.otherScreens}</p>
          <a href="/index.html" data-testid="legacy-lookup" className={row}>
            <ExternalLink size={14} aria-hidden="true" />
            {UI.topbar.legacyLookup}
          </a>
          <a href="/docs.html" data-testid="legacy-docs" className={row}>
            <ExternalLink size={14} aria-hidden="true" />
            {UI.topbar.legacyDocs}
          </a>
        </div>
      </Popover>
    </>
  )
}

function NoticeBody({ n, onOpen }: { n: Notice; onOpen: () => void }) {
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
      <button
        type="button"
        data-testid="notice-open-inspector"
        onClick={onOpen}
        className="mt-1 rounded-lg bg-white/80 px-2 py-1 font-semibold text-brand-indigo hover:bg-white focus-visible:outline-2 focus-visible:outline-brand-indigo"
      >
        {UI.notices.openInspector}
      </button>
    </div>
  )
}

function NoticeChips() {
  const { data } = useNotices()
  const [open, setOpen] = useState<{ key: string; el: HTMLElement } | null>(null)
  const select = useMapStore((s) => s.select)
  const openInspector = (n: Notice) => {
    setOpen(null)
    select({ kind: 'regulation', id: n.doc_id })
  }
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
                <NoticeBody n={n} onOpen={() => openInspector(n)} />
              </div>
            ))
          : items.filter((n) => n.item_key === open?.key).map((n) => <NoticeBody key={n.item_key} n={n} onOpen={() => openInspector(n)} />)}
      </Popover>
    </div>
  )
}

/** 기준일 (P19): 오늘이면 '오늘 · DB 기준', 다른 날이면 '기준일 2026-05-01 · 지난 시점 보기' + '오늘로' */
function AsOf({ dbAsOf }: { dbAsOf: string | null }) {
  const asOf = useMapStore((s) => s.asOf)
  const setAsOf = useMapStore((s) => s.setAsOf)
  if (!asOf)
    return (
      <span data-testid="as-of" data-as-of="" className="text-right leading-tight text-ink-muted">
        {UI.topbar.today} <span className="tabular-nums text-ink">{todayKst()}</span>
        <br />
        {UI.topbar.dbAsOf} <span className="tabular-nums">{dbAsOf ?? '—'}</span>
      </span>
    )
  const mode = asOf < todayIso() ? UI.time.past : UI.time.other
  return (
    <span className="flex items-center gap-2">
      <span data-testid="as-of" data-as-of={asOf} className="text-right leading-tight">
        <span className="font-semibold text-brand-indigo">
          {UI.time.asOf} <span className="tabular-nums">{asOf}</span>
        </span>
        <br />
        <span className="text-ink-muted" data-testid="as-of-mode">{mode}</span>
      </span>
      <button
        type="button"
        data-testid="as-of-today"
        title={UI.time.toTodayHelp}
        onClick={() => setAsOf(null)}
        className="rounded-full bg-brand-indigo px-2.5 py-1 font-semibold text-white hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-indigo"
      >
        {UI.time.toToday}
      </button>
    </span>
  )
}

/** compact (P20, 1024px 미만): 작업 탭·고시 칩을 빼고 검색은 아이콘만 */
export function TopBar({ style, compact = false }: { style: CSSProperties; compact?: boolean }) {
  const workspace = useMapStore((s) => s.workspace)
  const selected = useMapStore((s) => s.selected)
  const asOf = useMapStore((s) => s.asOf)
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
      {!compact && (
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
      )}
      <button
        type="button"
        data-testid="search-open"
        onClick={() => useMapStore.getState().setPaletteOpen(true)}
        className={`flex h-9 shrink-0 items-center gap-2 rounded-full bg-white/60 text-sm text-ink-muted ${compact ? 'w-9 justify-center' : 'w-56 px-3'}`}
        aria-keyshortcuts="Control+K Meta+K"
        aria-label={compact ? UI.topbar.search : undefined}
      >
        <Search size={16} aria-hidden="true" />
        {!compact && <span className="flex-1 truncate text-left">{UI.topbar.search}</span>}
        {!compact && <kbd className="rounded bg-ink/8 px-1.5 text-[11px]">{UI.topbar.searchKey}</kbd>}
      </button>
      {!compact && <NoticeChips />}
      <div className="ml-auto flex shrink-0 items-center gap-3 text-xs">
        <AsOf dbAsOf={health?.as_of ?? null} />
        <SettingsMenu />
      </div>
      {/* 오늘이 아닌 날짜를 보는 동안: 상단 바 아래 가장자리에 얇은 브랜드 색 띠 (P19) */}
      {asOf && <span aria-hidden="true" data-testid="as-of-band" className="as-of-band" />}
    </GlassPanel>
  )
}

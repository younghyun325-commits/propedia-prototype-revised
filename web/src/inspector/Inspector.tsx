/**
 * 우측 인스펙터 (docs/map/PLAN.md P16). 따로 불러오는 청크 (App.tsx).
 * - 머리(스크롤해도 고정): 종류 배지 · 이름 · 기준일 · '확인 전' · 링크 복사 · 닫기(Esc)
 * - 탭(role=tablist, ←/→/Home/End): 개요 · 근거 · (사업만) 필지 · 이력
 * - 내용은 패널 안에서만 스크롤. 지도 이동 중(.map-moving)에도 그대로 둔다
 * 대상: 사업·규제 = /api/v1/map/feature, 사업 필지 = /api/v1/map/feature/parcel, 빈 곳 클릭 = /map/parcel-at(store.parcel)
 */
import { useEffect, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react'
import { Link2, X } from 'lucide-react'
import { useFeature, type Badge as BadgeT, type EvidenceItem, type Feature, type FeatureKind } from '../api/feature'
import type { ParcelAt } from '../api/parcel'
import { UI } from '../copy/ui'
import { todayKst } from '../state/actions'
import { featureId, isParcelLookup } from '../state/url'
import { useMapStore } from '../state/useMapStore'
import { EvidenceLine } from '../ui/EvidenceLine'
import { GlassPanel } from '../ui/GlassPanel'
import { Badge, Skeleton, dot } from './parts'
import { ParcelView } from './ParcelView'
import { ProjectView } from './ProjectView'
import { RegulationView } from './RegulationView'

const TABS: Record<FeatureKind, string[]> = {
  project: ['overview', 'evidence', 'parcels', 'history'],
  regulation: ['overview', 'evidence', 'history'],
  parcel: ['overview', 'evidence'],
}

type Head = { kind: FeatureKind; title: string; subtitle: string | null; asOf: string; dataAsOf: string | null;
  badges: BadgeT[]; unverified: boolean }

function Header({ h }: { h: Head }) {
  const clear = useMapStore((s) => s.clearSelection)
  const setSearchHit = useMapStore((s) => s.setSearchHit)
  const [copied, setCopied] = useState<string | null>(null)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href)
      setCopied(UI.inspector.copied)
    } catch {
      setCopied(UI.inspector.copyFailed)
    }
    window.setTimeout(() => setCopied(null), 2000)
  }
  const btn = 'inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg hover:bg-white/80 focus-visible:outline-2 focus-visible:outline-brand-indigo'
  return (
    <header className="sticky top-0 z-10 space-y-1.5 border-b border-ink/10 bg-white/80 px-4 pt-3 pb-2" data-testid="inspector-header">
      <div className="flex items-start gap-1">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1">
            <Badge text={UI.inspector.kind[h.kind]} tone="brand" testId="inspector-kind" />
            {h.unverified && <Badge text={UI.inspector.unverified} tone="warn" testId="inspector-unverified" />}
          </div>
          <h2 className="mt-1 text-base leading-snug font-semibold" data-testid="inspector-title">{h.title}</h2>
          {h.subtitle && h.subtitle !== h.title && <p className="text-[11px] text-ink-muted">{h.subtitle}</p>}
        </div>
        <button type="button" className={btn} onClick={copy} aria-label={UI.inspector.copyLink} title={UI.inspector.copyLink} data-testid="inspector-copy">
          <Link2 size={16} aria-hidden="true" />
        </button>
        <button
          type="button"
          className={btn}
          onClick={() => {
            clear()
            setSearchHit(null)
          }}
          aria-label={UI.inspector.close}
          title={UI.inspector.close}
          data-testid="inspector-close"
        >
          <X size={16} aria-hidden="true" />
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-1 text-[11px] text-ink-muted">
        <span className="tabular-nums" data-testid="inspector-as-of">{UI.inspector.asOf} {dot(h.asOf)}</span>
        {h.dataAsOf && <span className="tabular-nums">· {UI.inspector.dataAsOf} {dot(h.dataAsOf)}</span>}
        {h.badges.filter((b) => b.text !== UI.inspector.kind[h.kind]).map((b) => (
          <Badge key={b.text} text={b.text} tone={b.tone} />
        ))}
      </div>
      <p role="status" aria-live="polite" className="text-[11px] text-ink-muted" data-testid="inspector-copied">{copied ?? ''}</p>
    </header>
  )
}

function Tabs({ tabs, active, onChange, idBase }: { tabs: string[]; active: string; onChange: (t: string) => void; idBase: string }) {
  const refs = useRef<(HTMLButtonElement | null)[]>([])
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const i = tabs.indexOf(active)
    let j = -1
    if (e.key === 'ArrowRight') j = (i + 1) % tabs.length
    else if (e.key === 'ArrowLeft') j = (i - 1 + tabs.length) % tabs.length
    else if (e.key === 'Home') j = 0
    else if (e.key === 'End') j = tabs.length - 1
    if (j < 0) return
    e.preventDefault()
    onChange(tabs[j])
    refs.current[j]?.focus()
  }
  return (
    <div role="tablist" aria-label={UI.inspector.tabsLabel} className="flex gap-1 px-4 pt-2" onKeyDown={onKey} data-testid="inspector-tabs">
      {tabs.map((t, i) => (
        <button
          key={t}
          ref={(el) => {
            refs.current[i] = el
          }}
          type="button"
          role="tab"
          id={`${idBase}-tab-${t}`}
          aria-selected={active === t}
          aria-controls={`${idBase}-panel`}
          tabIndex={active === t ? 0 : -1}
          data-testid={`inspector-tab-${t}`}
          onClick={() => onChange(t)}
          className={`relative px-2 pb-2 text-xs focus-visible:outline-2 focus-visible:outline-brand-indigo ${active === t ? 'font-semibold text-ink' : 'text-ink-muted hover:text-ink'}`}
        >
          {UI.inspector.tabs[t]}
          {active === t && <span aria-hidden="true" className="absolute inset-x-1 bottom-0 h-0.5 rounded-full bg-brand-indigo" />}
        </button>
      ))}
    </div>
  )
}

function EvidenceTab({ items }: { items: EvidenceItem[] }) {
  if (!items.length) return <p className="text-xs text-ink-muted">{UI.inspector.evidenceEmpty}</p>
  return (
    <ol className="space-y-2" data-testid="inspector-evidence-list">
      {items.map((e, i) => (
        <li key={i} className="rounded-xl bg-white/65 p-2">
          <p className="text-xs font-semibold">{e.label}</p>
          {e.evidence && <p className="mt-0.5 text-[11px] leading-relaxed text-ink-muted">{e.evidence}</p>}
          <EvidenceLine source={e} evidence={e.evidence} items={items} label={e.label} />
        </li>
      ))}
    </ol>
  )
}

function Body({ kind, tab, feature, parcel, boundaryNote }: {
  kind: FeatureKind; tab: string; feature: Feature | null; parcel: ParcelAt | null; boundaryNote?: string | null
}) {
  const evidence = feature?.evidence ?? parcel?.evidence ?? []
  if (tab === 'evidence') return <EvidenceTab items={evidence} />
  if (kind === 'project' && feature?.kind === 'project') return <ProjectView f={feature} tab={tab} />
  if (kind === 'regulation' && feature?.kind === 'regulation') return <RegulationView f={feature} tab={tab} />
  if (parcel) return <ParcelView d={parcel} boundaryNote={boundaryNote} />
  return null
}

function Shell({ head, kind, children }: { head: Head | null; kind: FeatureKind | null; children: (tab: string) => React.ReactNode }) {
  const tabs = kind ? TABS[kind] : []
  const [tab, setTab] = useState('overview')
  const idBase = 'inspector'
  return (
    <>
      {head && <Header h={head} />}
      {kind && <Tabs tabs={tabs} active={tab} onChange={setTab} idBase={idBase} />}
      <div
        id={`${idBase}-panel`}
        role={kind ? 'tabpanel' : undefined}
        aria-labelledby={kind ? `${idBase}-tab-${tab}` : undefined}
        tabIndex={kind ? 0 : undefined}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-3 text-sm"
        data-testid="inspector-body"
        data-tab={tab}
      >
        {children(tab)}
      </div>
    </>
  )
}

function Message({ text, testId, retry }: { text: string; testId: string; retry?: () => void }) {
  return (
    <div className="space-y-2">
      <p role="alert" className="text-sm" data-testid={testId}>{text}</p>
      {retry && (
        <button type="button" onClick={retry} className="rounded-lg bg-white/70 px-2 py-1 text-xs hover:bg-white">
          {UI.inspector.retry}
        </button>
      )}
    </div>
  )
}

/** 빈 곳 클릭 필지 (store.parcel, /map/parcel-at) */
function ClickParcel() {
  const lookup = useMapStore((s) => s.parcel)
  const today = todayKst().replaceAll('.', '-')
  if (lookup.status === 'loading')
    return (
      <Shell head={null} kind={null}>
        {() => (
          <div data-testid="parcel-card" data-status="loading">
            <p role="status" className="text-ink-muted" data-testid="parcel-loading">{UI.parcel.loading}</p>
            <Skeleton />
          </div>
        )}
      </Shell>
    )
  if (lookup.status === 'error')
    return <Shell head={null} kind={null}>{() => <div data-testid="parcel-card" data-status="error"><Message text={lookup.message} testId="parcel-message" /></div>}</Shell>
  if (lookup.status !== 'done') return <Shell head={null} kind={null}>{() => <Skeleton />}</Shell>
  const d = lookup.data
  if (d.status !== 'ok')
    return (
      <Shell head={null} kind={null}>
        {() => <div data-testid="parcel-card" data-status={d.status}><Message text={UI.parcel.status[d.status] ?? UI.parcel.failed} testId="parcel-message" /></div>}
      </Shell>
    )
  const head: Head = {
    kind: 'parcel', title: d.jibun_address ?? d.pnu ?? '', subtitle: null, asOf: today, dataAsOf: d.as_of,
    badges: d.project_banner.map((b) => ({ text: b.inclusion_label, tone: b.verified ? 'brand' : 'warn' })),
    unverified: d.project_banner.some((b) => !b.verified),
  }
  return (
    <div data-testid="parcel-card" data-status="ok" className="contents">
      <Shell key={d.pnu} head={head} kind="parcel">
        {(tab) => <Body kind="parcel" tab={tab} feature={null} parcel={d} />}
      </Shell>
    </div>
  )
}

function Selected({ kind, id }: { kind: FeatureKind; id: string }) {
  const q = useFeature(kind, id)
  if (q.isPending) return <Shell head={null} kind={null}>{() => <Skeleton />}</Shell>
  if (q.isError) {
    const nf = /찾을 수 없|밖입니다/.test(q.error.message)
    return (
      <Shell head={null} kind={null}>
        {() => <Message text={nf ? `${UI.inspector.notFound}: ${q.error.message}` : UI.inspector.error} testId="inspector-error"
          retry={nf ? undefined : () => void q.refetch()} />}
      </Shell>
    )
  }
  const f = q.data
  const head: Head = { kind, title: f.title, subtitle: f.subtitle, asOf: f.as_of, dataAsOf: f.data_as_of, badges: f.badges,
    unverified: f.unverified }
  const parcel = f.kind === 'parcel' ? f.sections.parcel : null
  return (
    <Shell key={`${kind}:${id}`} head={head} kind={kind}>
      {(tab) => <Body kind={kind} tab={tab} feature={f} parcel={parcel} boundaryNote={parcel?.boundary_note} />}
    </Shell>
  )
}

export default function Inspector({ style }: { style: CSSProperties }) {
  const selected = useMapStore((s) => s.selected)
  const parcelStatus = useMapStore((s) => s.parcel.status)
  // 빈 곳 클릭·URL 복원 필지(sel=parcel:{PNU})는 /map/parcel-at 결과(store.parcel)로 보여 준다
  const clickMode = isParcelLookup(selected) || (parcelStatus !== 'idle' && !selected)
  // 선택이 바뀌면 내용 맨 위로
  const ref = useRef<HTMLElement>(null)
  const key = clickMode ? `click:${parcelStatus}` : selected ? featureId(selected) : 'none'
  useEffect(() => {
    ref.current?.querySelector('[data-testid=inspector-body]')?.scrollTo?.({ top: 0 })
  }, [key])
  return (
    <GlassPanel
      as="aside"
      ref={ref}
      data-testid="right-panel"
      data-selected={selected ? featureId(selected) : ''}
      aria-label={UI.inspector.title}
      className="absolute flex flex-col overflow-hidden text-sm"
      style={style}
    >
      {clickMode ? (
        <ClickParcel />
      ) : selected ? (
        <Selected kind={selected.kind} id={selected.id} />
      ) : (
        <div className="space-y-2 p-4" data-testid="inspector-empty">
          <h2 className="font-semibold">{UI.inspector.title}</h2>
          <p className="text-ink-muted">{UI.inspector.none}</p>
          <p className="text-xs text-ink-muted">{UI.inspector.noneHelp}</p>
          <p className="text-xs text-ink-muted">{UI.parcel.clickHint}</p>
          <p className="text-xs text-ink-muted">{UI.inspector.hint}</p>
        </div>
      )}
    </GlassPanel>
  )
}

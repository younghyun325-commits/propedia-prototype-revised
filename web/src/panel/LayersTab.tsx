/**
 * 레이어 탭 (P14 3-1·3-2). 그룹 접기·펼치기·그룹 전체 토글, 행마다 체크박스·색 칩·이름·건수·'확인 전'·정보 툴팁·투명도.
 * 건수·원천·기준일은 모두 /api/v1/map/manifest에서 읽는다 (숫자를 코드에 적지 않음).
 */
import { useEffect, useRef, useState } from 'react'
import { ChevronDown, ChevronRight, Info, SlidersHorizontal } from 'lucide-react'
import type { Manifest, ManifestLayer } from '../api/map'
import { UI } from '../copy/ui'
import { BASEMAP_ORDER, BASEMAPS } from '../map/basemaps'
import { zoomBlocked } from '../map/reference'
import { useMapStore } from '../state/useMapStore'
import { PANEL_LAYER_IDS, type PanelLayerId } from '../state/url'
import { Tooltip } from '../ui/Floating'
import { LayerSwatch, type SwatchKind } from './LayerSwatch'

const isPanelId = (s: string): s is PanelLayerId => (PANEL_LAYER_IDS as readonly string[]).includes(s)
const TREE_GROUPS = ['basemap', 'propedia', 'reference', 'market', 'infra'] as const

function swatchOf(l: ManifestLayer): SwatchKind {
  if (l.id === 'projects') return 'project'
  if (l.id.startsWith('impact')) return 'impact'
  if (l.id === 'parcels') return 'parcel'
  if (l.id.startsWith('regulation')) return 'regulation'
  if (l.id === 'apartments' && l.status === 'ready') return 'apartment'
  if (l.ref) return l.kind === 'raster' ? 'raster' : 'reference'
  if (l.status !== 'ready') return l.kind === 'symbol' ? 'symbol' : l.kind === 'raster' ? 'raster' : 'pending'
  return 'pending'
}

function Badge({ children, tone = 'muted' }: { children: React.ReactNode; tone?: 'warn' | 'muted' }) {
  return (
    <span
      className={`rounded-full px-1.5 py-px text-[10px] font-semibold whitespace-nowrap ${
        tone === 'warn' ? 'bg-layer-regulation/15 text-warn' : 'bg-ink/8 text-ink-muted'
      }`}
    >
      {children}
    </span>
  )
}

function InfoTip({ l }: { l: ManifestLayer }) {
  const rows: [string, string | null][] = [
    [UI.layers.infoSource, l.source],
    [UI.layers.infoAsOf, l.as_of],
    [UI.layers.infoLicense, l.license],
    [UI.layers.infoPages, l.source_pages.length ? l.source_pages.join(', ') : null],
  ]
  return (
    <Tooltip
      testId={`layer-info-${l.id}`}
      content={
        <dl className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5">
          {rows.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-ink-muted">{k}</dt>
              <dd>{v ?? UI.layers.none}</dd>
            </div>
          ))}
          {l.note && <dd className="col-span-2 mt-1 text-ink-muted">{l.note}</dd>}
        </dl>
      }
    >
      {(p) => (
        <button
          type="button"
          {...p}
          aria-label={`${l.name} ${UI.layers.info}`}
          className="rounded p-0.5 text-ink-muted hover:text-ink"
        >
          <Info size={14} aria-hidden="true" />
        </button>
      )}
    </Tooltip>
  )
}

function LayerRow({ l }: { l: ManifestLayer }) {
  const panelId = isPanelId(l.id) ? l.id : null
  const state = useMapStore((s) => (panelId ? s.layers[panelId] : null))
  const setVisible = useMapStore((s) => s.setLayerVisible)
  const setOpacity = useMapStore((s) => s.setLayerOpacity)
  const zoom = useMapStore((s) => s.zoom)
  const [open, setOpen] = useState(false)
  const enabled = l.status === 'ready' && panelId !== null
  const blockedAt = zoomBlocked(l.id, zoom)
  const inputId = `layer-${l.id}`
  return (
    <li
      role="treeitem"
      aria-level={2}
      aria-selected={false}
      aria-disabled={!enabled || undefined}
      aria-expanded={enabled ? open : undefined}
      data-testid={`layer-row-${l.id}`}
      className={`py-1 ${enabled ? '' : 'opacity-70'}`}
    >
      <div className="flex items-center gap-2">
        <input
          id={inputId}
          type="checkbox"
          data-testid={`layer-toggle-${l.id}`}
          checked={!!state?.visible}
          disabled={!enabled}
          onChange={(e) => panelId && setVisible(panelId, e.target.checked)}
          className="h-4 w-4 shrink-0 accent-brand-indigo"
        />
        <label htmlFor={inputId} className="flex min-w-0 flex-1 items-center gap-2">
          <span className="flex shrink-0"><LayerSwatch kind={swatchOf(l)} opacity={state ? state.opacity / 100 : 1} /></span>
          <span className="leading-tight break-keep">{l.name}</span>
        </label>
        {l.status === 'ready' && l.count !== null && (
          <span className="text-xs text-ink-muted tabular-nums" data-testid={`layer-count-${l.id}`}>
            {UI.layers.count(l.count)}
          </span>
        )}
        {l.status === 'ready' && l.unverified && <Badge tone="warn">{UI.layers.unverified}</Badge>}
        {l.status === 'ready' && l.badge && <Badge>{l.badge}</Badge>}
        {l.status === 'not_adopted' && <Badge tone="warn">{UI.layers.notAdopted}</Badge>}
        {l.status === 'pending' && (
          <span className="flex flex-col items-end gap-0.5">
            <Badge>{UI.layers.pending(l.available_from ?? '')}</Badge>
            {l.badge && <Badge>{l.badge}</Badge>}
          </span>
        )}
        <InfoTip l={l} />
        {enabled && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label={`${l.name} ${UI.layers.opacity} ${open ? UI.layers.collapse : UI.layers.expand}`}
            aria-expanded={open}
            data-testid={`layer-expand-${l.id}`}
            className="rounded p-0.5 text-ink-muted hover:text-ink"
          >
            <SlidersHorizontal size={14} aria-hidden="true" />
          </button>
        )}
      </div>
      {enabled && open && state && panelId && (
        <label className="mt-1 ml-6 flex items-center gap-2 text-xs text-ink-muted">
          {UI.layers.opacity}
          <input
            type="range"
            min={0}
            max={100}
            step={5}
            value={state.opacity}
            data-testid={`layer-opacity-${l.id}`}
            onChange={(e) => setOpacity(panelId, Number(e.target.value))}
            className="flex-1 accent-brand-indigo"
          />
          <span className="w-9 text-right tabular-nums">{state.opacity}%</span>
        </label>
      )}
      {l.id === 'impact500' && <p className="mt-1 ml-6 text-xs text-ink-muted">{UI.layers.impactNote}</p>}
      {l.id === 'apartments' && l.status === 'ready' && (
        <p className="mt-1 ml-6 text-xs text-ink-muted" data-testid="apartment-legend-note">
          {l.note ?? UI.apartment.layerNote}
          {l.boundary_note ? ` · ${l.boundary_note}` : ''}
        </p>
      )}
      {enabled && blockedAt !== null && (
        <p className="mt-1 ml-6 text-xs text-ink-muted" data-testid={`layer-zoomhint-${l.id}`}>
          {UI.reference.zoomHint(blockedAt)}
        </p>
      )}
      {l.id === 'parcels' && l.count_by_judgment && (
        <ul className="mt-1 ml-6 space-y-0.5 text-xs text-ink-muted" data-testid="parcel-legend">
          <li className="flex items-center gap-1.5">
            <LayerSwatch kind="parcel" />
            <span className="flex-1">{UI.layers.legendSolid}</span>
            <span className="tabular-nums">
              {UI.layers.count(l.count_by_judgment.included + l.count_by_judgment.possible)}
            </span>
          </li>
          <li className="flex items-center gap-1.5">
            <LayerSwatch kind="parcel-likely" />
            <span className="flex-1">{UI.layers.legendDashed}</span>
            <span className="tabular-nums">{UI.layers.count(l.count_by_judgment.likely)}</span>
          </li>
        </ul>
      )}
    </li>
  )
}

function GroupCheckbox({ ids, name }: { ids: PanelLayerId[]; name: string }) {
  const layers = useMapStore((s) => s.layers)
  const setMany = useMapStore((s) => s.setLayersVisible)
  const ref = useRef<HTMLInputElement>(null)
  const on = ids.filter((id) => layers[id].visible).length
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = on > 0 && on < ids.length
  }, [on, ids.length])
  return (
    <input
      ref={ref}
      type="checkbox"
      aria-label={UI.layers.groupToggle(name)}
      data-testid="group-toggle"
      disabled={ids.length === 0}
      checked={ids.length > 0 && on === ids.length}
      onChange={() => setMany(ids, on !== ids.length)}
      className="h-4 w-4 accent-brand-indigo"
    />
  )
}

function BasemapRows() {
  const basemap = useMapStore((s) => s.basemap)
  const setBasemap = useMapStore((s) => s.setBasemap)
  return (
    <>
      {BASEMAP_ORDER.map((id) => (
        <li key={id} role="treeitem" aria-level={2} aria-selected={basemap === id} className="py-1">
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="basemap"
              data-basemap-option={id}
              checked={basemap === id}
              onChange={() => setBasemap(id)}
              className="h-4 w-4 accent-brand-indigo"
            />
            {BASEMAPS[id].label}
          </label>
        </li>
      ))}
    </>
  )
}

export function LayersTab({ manifest }: { manifest: Manifest }) {
  const overlap = useMapStore((s) => s.overlap)
  const setOverlap = useMapStore((s) => s.setOverlap)
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})
  const groupName = Object.fromEntries(manifest.groups.map((g) => [g.id, g.name]))

  return (
    <div className="space-y-3">
      <button
        type="button"
        role="switch"
        aria-checked={overlap}
        data-testid="overlap-switch"
        title={UI.layers.overlapHelp}
        onClick={() => setOverlap(!overlap)}
        className="flex w-full items-center justify-between gap-2 rounded-xl bg-white/60 px-3 py-2 text-left"
      >
        <span>{UI.layers.overlap}</span>
        <span
          aria-hidden="true"
          className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${overlap ? 'bg-brand-indigo' : 'bg-ink/25'}`}
        >
          <span
            className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all ${overlap ? 'left-4.5' : 'left-0.5'}`}
          />
        </span>
      </button>

      <ul role="tree" aria-label={UI.layers.treeLabel} data-testid="layer-tree" className="space-y-2">
        {TREE_GROUPS.map((g) => {
          const rows = manifest.layers.filter((l) => l.group === g)
          const toggleable = rows.filter((l) => l.status === 'ready' && isPanelId(l.id)).map((l) => l.id as PanelLayerId)
          const isOpen = !collapsed[g]
          const name = groupName[g] ?? g
          return (
            <li key={g} role="treeitem" aria-level={1} aria-expanded={isOpen} aria-selected={false} aria-label={name}
              data-testid={`layer-group-${g}`}>
              <div className="flex items-center gap-2 font-semibold">
                <button
                  type="button"
                  onClick={() => setCollapsed((c) => ({ ...c, [g]: isOpen }))}
                  aria-label={`${name} ${isOpen ? UI.layers.collapse : UI.layers.expand}`}
                  className="rounded p-0.5 text-ink-muted hover:text-ink"
                >
                  {isOpen ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronRight size={14} aria-hidden="true" />}
                </button>
                {g !== 'basemap' && <GroupCheckbox ids={toggleable} name={name} />}
                <span>{name}</span>
              </div>
              {isOpen && (
                <ul role="group" className="mt-1 ml-5">
                  {g === 'basemap' ? <BasemapRows /> : rows.map((l) => <LayerRow key={l.id} l={l} />)}
                </ul>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

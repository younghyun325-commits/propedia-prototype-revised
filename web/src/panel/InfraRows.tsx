/**
 * 레이어 탭의 생활 인프라 부분 (P18): 칩 모양 색 칩, 편의시설 6분류 하위 행(켜기·끄기·건수),
 * 병원·의원·학원은 펼치면 하위 분류 행. 건수·안내는 manifest(pipeline/fetch_pois.py) 값 그대로.
 */
import { useState } from 'react'
import { ChevronDown, ChevronRight, Info } from 'lucide-react'
import { UI } from '../copy/ui'
import type { InfraLayer, PoiCategory } from '../infra/data'
import { ICON_OF, INK } from '../infra/icons'
import { useMapStore } from '../state/useMapStore'
import { Tooltip } from '../ui/Floating'

const ICON_FOR_LAYER: Record<string, string> = { schools: 'school', stations: 'station', bus_stops: 'bus' }

/** 흰 원형 칩 + 아이콘 (지도와 같은 모양) */
export function ChipSwatch({ icon, small = false }: { icon: string; small?: boolean }) {
  const Icon = ICON_OF[icon]
  const s = small ? 16 : 20
  return (
    <span
      aria-hidden="true"
      className="inline-flex shrink-0 items-center justify-center rounded-full bg-white"
      style={{ width: s, height: s, border: `1.5px solid ${INK}` }}
    >
      {Icon && <Icon size={Math.round(s * 0.6)} color={INK} strokeWidth={2} />}
    </span>
  )
}

export const infraSwatchIcon = (id: string) => ICON_FOR_LAYER[id] ?? (id === 'pois' ? 'convenience' : null)

function CategoryRow({ c, enabled }: { c: PoiCategory; enabled: boolean }) {
  const hidden = useMapStore((s) => s.poiHidden)
  const toggle = useMapStore((s) => s.togglePoiHidden)
  const [open, setOpen] = useState(false)
  const id = `poi-cat-${c.key}`
  const on = !hidden.includes(c.key)
  return (
    <li data-testid={`poi-cat-row-${c.key}`} className="py-0.5">
      <div className="flex items-center gap-1.5">
        <input id={id} type="checkbox" checked={on} disabled={!enabled} onChange={() => toggle(c.key)}
          data-testid={`poi-cat-toggle-${c.key}`} className="h-3.5 w-3.5 accent-brand-indigo" />
        <label htmlFor={id} className="flex min-w-0 flex-1 items-center gap-1.5">
          <ChipSwatch icon={c.key} small />
          <span className="break-keep">{c.label}</span>
        </label>
        <span className="tabular-nums" data-testid={`poi-cat-count-${c.key}`}>{UI.layers.count(c.count)}</span>
        {c.note && (
          <Tooltip testId={`poi-cat-note-${c.key}`} content={<span>{c.note}</span>}>
            {(p) => (
              <button type="button" {...p} aria-label={`${c.label} ${UI.layers.info}`} className="rounded p-0.5 hover:text-ink">
                <Info size={12} aria-hidden="true" />
              </button>
            )}
          </Tooltip>
        )}
        {c.sub_categories.length > 0 && (
          <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
            aria-label={`${c.label} ${open ? UI.infra.collapseSubs : UI.infra.expandSubs}`}
            data-testid={`poi-cat-expand-${c.key}`} className="rounded p-0.5 hover:text-ink">
            {open ? <ChevronDown size={12} aria-hidden="true" /> : <ChevronRight size={12} aria-hidden="true" />}
          </button>
        )}
      </div>
      {open && c.sub_categories.length > 0 && (
        <ul className="mt-0.5 ml-6 space-y-0.5">
          {c.sub_categories.map((sub) => {
            const key = `${c.key}/${sub}`
            const sid = `poi-sub-${c.key}-${sub}`
            return (
              <li key={sub} className="flex items-center gap-1.5" data-testid="poi-sub-row" data-key={key}>
                <input id={sid} type="checkbox" checked={on && !hidden.includes(key)} disabled={!enabled || !on}
                  onChange={() => toggle(key)} data-testid="poi-sub-toggle" className="h-3.5 w-3.5 accent-brand-indigo" />
                <label htmlFor={sid} className="flex-1 break-keep">{sub}</label>
                <span className="tabular-nums">{UI.layers.count(c.sub_counts[sub] ?? 0)}</span>
              </li>
            )
          })}
        </ul>
      )}
    </li>
  )
}

/** 편의시설 분류 행 (레이어를 켜야 바꿀 수 있다) */
export function PoiCategoryRows({ l }: { l: InfraLayer }) {
  const visible = useMapStore((s) => s.layers.pois.visible)
  if (!l.categories?.length) return null
  return (
    <div className="mt-1 ml-6 text-xs text-ink-muted">
      <ul className="space-y-0.5" data-testid="poi-categories">
        {l.categories.map((c) => <CategoryRow key={c.key} c={c} enabled={visible} />)}
      </ul>
      <p className="mt-1">{UI.infra.poiNote}</p>
    </div>
  )
}

/** 줌 조건 안내 (정류장: 줌 15 이상) — P15 지적도 안내와 같은 방식 */
export function InfraZoomHint({ l }: { l: InfraLayer }) {
  const zoom = useMapStore((s) => s.zoom)
  const visible = useMapStore((s) => (l.id === 'bus_stops' ? s.layers.bus_stops.visible : false))
  if (!l.min_zoom || !visible || zoom === null || zoom >= l.min_zoom) return null
  return (
    <p className="mt-1 ml-6 text-xs text-ink-muted" data-testid={`layer-zoomhint-${l.id}`}>
      {UI.infra.zoomHint(l.min_zoom)}
    </p>
  )
}

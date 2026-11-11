/**
 * 필지 보기 (P16, P15 간이 카드의 정식판). 지도 빈 곳 클릭(/map/parcel-at)과 사업 필지 선택(/map/feature/parcel)이
 * 같은 조립(core/map._assemble)을 쓰므로 같은 화면으로 보여 준다. 값은 응답 그대로 (해석·판단 문구 없음).
 */
import { useState } from 'react'
import { ChevronRight } from 'lucide-react'
import type { ParcelAt } from '../api/parcel'
import { useMapProjects } from '../api/map'
import { UI } from '../copy/ui'
import { selectProject } from '../state/actions'
import { useMapStore } from '../state/useMapStore'
import { EvidenceLine } from '../ui/EvidenceLine'
import { Badge, Card, KV, Section, dot } from './parts'

const fmt = (n: number | null | undefined) => (n === null || n === undefined ? '—' : n.toLocaleString('ko-KR'))
const LAYERS = ['city', 'gu', 'dong', 'parcel'] as const

function Banner({ d }: { d: ParcelAt }) {
  if (!d.project_banner?.length) return null
  return (
    <div className="space-y-1" data-testid="parcel-banner">
      {d.project_banner.map((b) => (
        <div key={b.project_id} className={`rounded-xl px-3 py-2 text-xs ${b.verified ? 'bg-brand-indigo/10' : 'bg-layer-regulation/12'}`}>
          <p className="font-semibold" data-testid="parcel-banner-text">
            {UI.parcelView.banner(b.short_name, b.inclusion_label, !b.verified, b.review_id)}
          </p>
          <p className="text-[11px] text-ink-muted">{b.basis_label}</p>
          <EvidenceLine source={b.source} items={d.evidence} label={b.basis_label} />
        </div>
      ))}
    </div>
  )
}

function LayerNotices({ d }: { d: ParcelAt }) {
  const [open, setOpen] = useState<string | null>(null)
  const counts = d.layer_counts
  if (!counts) return null
  return (
    <Section title={UI.parcelView.notices} testId="parcel-notices">
      <ul className="grid grid-cols-4 gap-1 text-center text-xs" data-testid="parcel-counts">
        {LAYERS.map((k) => (
          <li key={k}>
            <button
              type="button"
              aria-expanded={open === k}
              aria-controls={`parcel-layer-${k}`}
              onClick={() => setOpen(open === k ? null : k)}
              data-testid={`parcel-layer-${k}`}
              className={`w-full rounded-lg px-1 py-1 focus-visible:outline-2 focus-visible:outline-brand-indigo ${open === k ? 'bg-brand-indigo/12' : 'bg-white/60 hover:bg-white/80'}`}
            >
              <span className="block text-ink-muted">{UI.parcel.layers[k]}</span>
              <span className="tabular-nums">{UI.parcel.count(counts[k])}</span>
            </button>
          </li>
        ))}
      </ul>
      {open && (
        <div id={`parcel-layer-${open}`} className="space-y-1.5" data-testid="parcel-layer-items">
          {(d.layer_items?.[open as (typeof LAYERS)[number]] ?? []).length === 0 ? (
            <p className="text-xs text-ink-muted">{UI.parcelView.itemsNone}</p>
          ) : (
            d.layer_items![open as (typeof LAYERS)[number]].map((it) => (
              <Card key={it.item_key} className="!p-2">
                <p className="text-xs font-semibold">{it.display_title}</p>
                {it.effective_label && (
                  <p className="text-[11px] text-ink-muted">
                    {it.effective_label}{it.effective_status_label ? ` · ${it.effective_status_label}` : ''}
                  </p>
                )}
                <EvidenceLine source={it.source} evidence={it.evidence} items={d.evidence} label={it.display_title} />
              </Card>
            ))
          )}
        </div>
      )}
    </Section>
  )
}

export function ParcelView({ d, boundaryNote }: { d: ParcelAt; boundaryNote?: string | null }) {
  const { data: projects } = useMapProjects()
  const select = useMapStore((s) => s.select)
  const land = d.land
  const zones = (land?.zones ?? []).map((z) => (z.relation ? `${z.name}(${z.relation})` : z.name))
  const b = d.building
  const goProject = (id: number) => {
    const p = projects?.projects.find((x) => x.id === id)
    if (p) selectProject(p)
    else select({ kind: 'project', id: String(id) })
  }
  return (
    <div className="space-y-4" data-testid="parcel-card-body">
      <Banner d={d} />
      <p className="text-xs text-ink-muted">
        {UI.parcel.pnu} <code className="font-mono" data-testid="parcel-pnu">{d.pnu}</code>
        <span className="sr-only" data-testid="parcel-address">{d.jibun_address}</span>
      </p>
      {boundaryNote && <p className="text-[11px] text-warn">{boundaryNote}</p>}

      <Section title={UI.parcel.land} testId="parcel-land-card">
        <Card>
          {land && land.status !== 'unavailable' ? (
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs" data-testid="parcel-land">
              <KV k={UI.parcel.jimok} testId="parcel-jimok">{land.jimok ?? '—'}</KV>
              <KV k={UI.parcel.area}><span className="tabular-nums">{land.area_m2 !== null ? `${fmt(land.area_m2)}㎡` : '—'}</span></KV>
              <KV k={UI.parcel.zone}>{[land.land_use_zone, land.land_use_zone2].filter(Boolean).join(' · ') || '—'}</KV>
              <KV k={UI.parcel.zones}>{zones.length ? zones.join(', ') : '—'}</KV>
              <KV k={UI.parcel.price}>
                <span className="tabular-nums">
                  {land.official_price?.won_per_m2
                    ? `${fmt(land.official_price.won_per_m2)} ${UI.parcel.perM2} (${land.official_price.year ?? ''})`
                    : '—'}
                </span>
              </KV>
            </dl>
          ) : (
            <p className="text-xs text-ink-muted">{land?.note ?? UI.parcel.landNone}</p>
          )}
          <p className="mt-1 text-[11px] text-ink-muted" data-testid="parcel-land-source">
            {UI.parcel.source}: {UI.parcelView.landSource(land?.source ?? null, dot(land?.fetched_at ?? null) || null)}
          </p>
        </Card>
      </Section>

      <Section title={UI.parcelView.building}>
        {b && b.found !== false ? (
          <Card>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs" data-testid="parcel-building">
              <KV k={UI.parcelView.mainPurpose}>{b.main_purpose ?? '—'}</KV>
              {b.bld_names && b.bld_names.length > 0 && <KV k={UI.parcelView.names}>{b.bld_names.join(', ')}</KV>}
            </dl>
            {b.source && <p className="mt-1 text-[11px] text-ink-muted">{UI.parcel.source}: {b.source}{b.fetched_label ? ` · ${b.fetched_label}` : ''}</p>}
          </Card>
        ) : (
          <p className="text-xs text-ink-muted">{d.building_note ?? UI.parcelView.buildingNone}</p>
        )}
      </Section>

      <LayerNotices d={d} />

      <Section title={UI.parcel.nearby}>
        {d.nearby_projects.length ? (
          <ul className="space-y-1 text-xs" data-testid="parcel-nearby">
            {d.nearby_projects.map((p) => (
              <li key={p.project_id}>
                <button
                  type="button"
                  onClick={() => goProject(p.project_id)}
                  data-testid="parcel-nearby-item"
                  className="flex w-full items-center gap-1 rounded-lg bg-white/60 px-2 py-1.5 text-left hover:bg-white/80 focus-visible:outline-2 focus-visible:outline-brand-indigo"
                >
                  <span className="min-w-0 flex-1 truncate">{p.name}</span>
                  <span className="tabular-nums text-ink-muted">{UI.parcel.distance(p.distance_m ?? 0)}</span>
                  <ChevronRight size={14} aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-ink-muted">{d.nearby_note ?? UI.parcel.nearbyNone}</p>
        )}
      </Section>

      <Section title={UI.parcel.refZones}>
        {d.ref_zones.length ? (
          <ul className="space-y-1 text-xs" data-testid="parcel-ref-zones">
            {d.ref_zones.map((z, i) => (
              <li key={`${z.layer}-${i}`} data-testid="parcel-ref-zone" className="rounded-lg bg-white/60 px-2 py-1.5">
                <Badge text={z.badge || UI.parcelView.refBadge} tone="muted" /> <span>{z.name}</span>
                <span className="block text-[11px] text-ink-muted">{z.layer_title} · {z.source} · {z.license}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-ink-muted">{UI.parcel.refNone}</p>
        )}
        <p className="text-[11px] text-ink-muted">{UI.parcel.refNote}</p>
      </Section>
    </div>
  )
}

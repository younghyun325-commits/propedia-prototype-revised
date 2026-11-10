/**
 * 지도 클릭 필지 조회 카드 (P15-3-3). 내용이 맞게 나오는 것이 목표이고 디자인 완성은 P16.
 * 값은 API 응답 그대로 보여 준다 (해석·판단 문구 없음).
 */
import { UI } from '../copy/ui'
import type { ParcelAt } from '../api/parcel'
import type { ParcelLookup } from '../state/useMapStore'

const fmt = (n: number | null | undefined) => (n === null || n === undefined ? '—' : n.toLocaleString('ko-KR'))

function Row({ k, v, testId }: { k: string; v: React.ReactNode; testId?: string }) {
  return (
    <div className="contents">
      <dt className="text-ink-muted">{k}</dt>
      <dd data-testid={testId}>{v}</dd>
    </div>
  )
}

function Body({ d }: { d: ParcelAt }) {
  const land = d.land
  const zones = (land?.zones ?? []).map((z) => (z.relation ? `${z.name}(${z.relation})` : z.name))
  const counts = d.layer_counts
  return (
    <div className="space-y-3" data-testid="parcel-card-body">
      <div>
        <p className="font-semibold" data-testid="parcel-address">{d.jibun_address}</p>
        <p className="text-xs text-ink-muted">
          {UI.parcel.pnu} <code className="font-mono" data-testid="parcel-pnu">{d.pnu}</code>
        </p>
      </div>

      <section>
        <h3 className="text-xs font-semibold text-ink-muted">{UI.parcel.land}</h3>
        {land && land.status !== 'unavailable' ? (
          <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs" data-testid="parcel-land">
            <Row k={UI.parcel.jimok} v={land.jimok ?? '—'} testId="parcel-jimok" />
            <Row k={UI.parcel.area} v={land.area_m2 !== null ? `${fmt(land.area_m2)}㎡` : '—'} />
            <Row k={UI.parcel.zone} v={[land.land_use_zone, land.land_use_zone2].filter(Boolean).join(' · ') || '—'} />
            <Row k={UI.parcel.zones} v={zones.length ? zones.join(', ') : '—'} />
            <Row
              k={UI.parcel.price}
              v={land.official_price?.won_per_m2
                ? `${fmt(land.official_price.won_per_m2)} ${UI.parcel.perM2} (${land.official_price.year ?? ''})`
                : '—'}
            />
          </dl>
        ) : (
          <p className="mt-1 text-xs text-ink-muted">{land?.note ?? UI.parcel.landNone}</p>
        )}
        {land?.source && <p className="mt-0.5 text-[11px] text-ink-muted">{UI.parcel.source}: {land.source}</p>}
      </section>

      {counts && (
        <section>
          <h3 className="text-xs font-semibold text-ink-muted">{UI.parcel.notices}</h3>
          <ul className="mt-1 grid grid-cols-4 gap-1 text-center text-xs" data-testid="parcel-counts">
            {(['city', 'gu', 'dong', 'parcel'] as const).map((k) => (
              <li key={k} className="rounded-lg bg-white/60 px-1 py-1">
                <span className="block text-ink-muted">{UI.parcel.layers[k]}</span>
                <span className="tabular-nums">{UI.parcel.count(counts[k])}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {d.included_projects.length > 0 && (
        <section>
          <h3 className="text-xs font-semibold text-ink-muted">{UI.parcel.projects}</h3>
          <ul className="mt-1 space-y-0.5 text-xs">
            {d.included_projects.map((p) => (
              <li key={p.project_id}>{p.message ?? `${p.name} · ${p.inclusion_label}`}</li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h3 className="text-xs font-semibold text-ink-muted">{UI.parcel.nearby}</h3>
        {d.nearby_projects.length ? (
          <ul className="mt-1 space-y-0.5 text-xs" data-testid="parcel-nearby">
            {d.nearby_projects.map((p) => (
              <li key={p.project_id}>
                {p.name} · <span className="tabular-nums">{UI.parcel.distance(p.distance_m ?? 0)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-xs text-ink-muted">{d.nearby_note ?? UI.parcel.nearbyNone}</p>
        )}
      </section>

      <section>
        <h3 className="text-xs font-semibold text-ink-muted">{UI.parcel.refZones}</h3>
        {d.ref_zones.length ? (
          <ul className="mt-1 space-y-1 text-xs" data-testid="parcel-ref-zones">
            {d.ref_zones.map((z, i) => (
              <li key={`${z.layer}-${i}`} data-testid="parcel-ref-zone">
                <span className="mr-1 rounded-full bg-ink/8 px-1.5 py-px text-[10px] font-semibold text-ink-muted">
                  {z.badge}
                </span>
                <span>{z.name}</span>
                <span className="block text-[11px] text-ink-muted">
                  {z.layer_title} · {z.source} · {z.license}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1 text-xs text-ink-muted">{UI.parcel.refNone}</p>
        )}
        <p className="mt-1 text-[11px] text-ink-muted">{UI.parcel.refNote}</p>
      </section>

      <p className="text-[11px] text-ink-muted">{d.disclaimer}</p>
    </div>
  )
}

export function ParcelLookupCard({ lookup }: { lookup: ParcelLookup }) {
  return (
    <div className="mt-2" data-testid="parcel-card" data-status={lookup.status === 'done' ? lookup.data.status : lookup.status}>
      <h3 className="sr-only">{UI.parcel.title}</h3>
      {lookup.status === 'loading' && (
        <p role="status" className="text-ink-muted" data-testid="parcel-loading">{UI.parcel.loading}</p>
      )}
      {lookup.status === 'error' && <p role="alert" data-testid="parcel-message">{lookup.message}</p>}
      {lookup.status === 'done' &&
        (lookup.data.status === 'ok' ? (
          <Body d={lookup.data} />
        ) : (
          <p role="alert" data-testid="parcel-message">
            {UI.parcel.status[lookup.data.status] ?? UI.parcel.failed}
          </p>
        ))}
    </div>
  )
}

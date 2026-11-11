/**
 * 생활 인프라 인스펙터 (P18 4단계): 학교·지하철역·버스정류장·편의시설.
 * 값은 불러온 레이어(public/data/layers)의 원자료 값 그대로. 원자료에 없는 정보(배차·첫차·막차·도착·영업 여부)는 넣지 않는다.
 */
import { useMapProjects } from '../api/map'
import { UI } from '../copy/ui'
import type { BusRoute, BusStopProps, InfraLayer, InfraProps, PoiCategory } from '../infra/data'
import { useMapStore } from '../state/useMapStore'

export const infraAsOf = (s: string) => (/^\d{6}$/.test(s) ? `${s.slice(0, 4)}.${s.slice(4)}` : s.replaceAll('-', '.'))

function Row({ k, children, testId }: { k: string; children: React.ReactNode; testId?: string }) {
  return (
    <div className="grid grid-cols-[96px_1fr] gap-2 py-1">
      <dt className="text-meta text-ink-muted">{k}</dt>
      <dd className="text-body" data-testid={testId}>{children}</dd>
    </div>
  )
}

function SourceLine({ l }: { l: InfraLayer | undefined }) {
  if (!l) return null
  return (
    <p className="text-caption leading-relaxed text-ink-muted" data-testid="poi-source">
      {UI.poi.source}: {UI.poi.sourceLine(l.source ?? '', infraAsOf(l.as_of ?? ''))}
      {l.license ? ` · ${l.license}` : ''}
      {l.as_of_note ? ` · ${l.as_of_note}` : ''}
    </p>
  )
}

function Impact({ p }: { p: InfraProps }) {
  const projects = useMapProjects().data?.projects ?? []
  const wi = p.within_impact
  const name = projects.find((x) => x.id === wi.project_id)?.short_name
  return (
    <Row k={UI.poi.impacts} testId="poi-impact">
      {wi.project_id !== null && wi.buffer_m !== null ? UI.poi.impact(name ?? String(wi.project_id), wi.buffer_m) : UI.poi.impactsNone}
    </Row>
  )
}

function BusRoutes({ p, routes }: { p: BusStopProps; routes: Map<string, BusRoute> }) {
  const setRoute = useMapStore((s) => s.setRoute)
  const current = useMapStore((s) => s.route)
  if (!p.route_ids.length) return <p className="text-body" data-testid="poi-no-routes">{UI.poi.noRoutes}</p>
  const groups = new Map<string, BusRoute[]>()
  for (const id of p.route_ids) {
    const r = routes.get(id)
    if (!r) continue
    const list = groups.get(r.route_type) ?? []
    list.push(r)
    groups.set(r.route_type, list)
  }
  const ordered = [...groups.entries()].sort((a, b) => (a[0] || '힣').localeCompare(b[0] || '힣', 'ko'))
  return (
    <section className="space-y-1.5" data-testid="poi-routes">
      <h3 className="text-meta font-semibold">{UI.poi.routes(p.route_ids.length)}</h3>
      {ordered.map(([type, list]) => (
        <div key={type} className="flex flex-wrap items-center gap-1" data-route-type={type}>
          <span className="mr-1 rounded-full bg-ink/8 px-1.5 py-px text-caption font-semibold text-ink-muted">{UI.poi.routeType(type)}</span>
          {list
            .sort((a, b) => a.route_no.localeCompare(b.route_no, 'ko', { numeric: true }))
            .map((r) => (
              <button
                key={r.route_id}
                type="button"
                data-testid="route-chip-button"
                data-route={r.route_id}
                aria-pressed={current === r.route_id}
                onClick={() => setRoute(current === r.route_id ? null : r.route_id)}
                className={`rounded-md border border-ink/20 px-1.5 py-0.5 text-meta tabular-nums hover:bg-white ${current === r.route_id ? 'bg-white font-semibold ring-2 ring-brand-indigo' : 'bg-white/60'}`}
              >
                {r.route_no}
              </button>
            ))}
        </div>
      ))}
      <p className="text-caption text-ink-muted">{UI.poi.routeHelp}</p>
    </section>
  )
}

export function PoiBody({ p, layer, routesLayer, routes, cats, byId }: {
  p: InfraProps
  layer: InfraLayer | undefined
  routesLayer: InfraLayer['routes']
  routes: Map<string, BusRoute>
  cats: PoiCategory[]
  byId: (id: string) => InfraProps | undefined
}) {
  const select = useMapStore((s) => s.select)
  const requestView = useMapStore((s) => s.requestView)
  const goStop = (id: string) => {
    const q = byId(id)
    select({ kind: 'bus', id: id.replace(/^bus:/, '') })
    if (q) requestView({ type: 'bbox', bbox: [q.lon - 0.0008, q.lat - 0.0006, q.lon + 0.0008, q.lat + 0.0006] })
  }
  const cat = p.kind === 'poi' ? cats.find((c) => c.key === p.category) : undefined
  return (
    <div className="space-y-3" data-testid="poi-view" data-kind={p.kind}>
      <dl>
        {p.kind === 'school' && <Row k={UI.poi.level} testId="poi-level">{p.level}</Row>}
        {p.kind === 'station' && (
          <>
            <Row k={UI.poi.lines} testId="poi-lines">{p.lines.join(', ')}</Row>
            <Row k={UI.poi.aliases} testId="poi-aliases">{p.aliases.join(', ')}</Row>
          </>
        )}
        {p.kind === 'bus_stop' && (
          <>
            <Row k={UI.poi.ars} testId="poi-ars"><span className="font-mono">{p.ars_no}</span></Row>
            {p.stop_type && <Row k={UI.poi.stopType} testId="poi-stop-type">{p.stop_type}</Row>}
          </>
        )}
        {p.kind === 'poi' && (
          <>
            <Row k={UI.poi.category} testId="poi-category">{cat?.label ?? p.category}</Row>
            {p.sub_category && <Row k={UI.poi.subCategory}>{p.sub_category}</Row>}
            <Row k={UI.poi.industry} testId="poi-industry">{cat?.codes[p.category_code] ?? p.category_code}</Row>
          </>
        )}
        {(p.kind === 'school' || p.kind === 'poi') && p.address && <Row k={UI.poi.address}>{p.address}</Row>}
        {(p.kind === 'station' || p.kind === 'bus_stop') && (
          <Row k={UI.poi.coord}>
            <span className="tabular-nums">{p.lat.toFixed(6)}, {p.lon.toFixed(6)}</span>
            <span className="block text-caption text-ink-muted">{UI.poi.coordSource}</span>
          </Row>
        )}
        <Impact p={p} />
      </dl>
      {p.kind === 'bus_stop' && (
        <>
          <section data-testid="poi-same-name">
            {p.same_name_nearby.length ? (
              <>
                <h3 className="text-meta font-semibold">{UI.poi.sameName(p.same_name_nearby.length)}</h3>
                <ul className="mt-1 flex flex-wrap gap-1">
                  {p.same_name_nearby.map((id) => (
                    <li key={id}>
                      <button type="button" onClick={() => goStop(id)} data-testid="same-name-stop"
                        className="rounded-md bg-white/60 px-1.5 py-0.5 font-mono text-meta hover:bg-white">
                        {id.replace(/^bus:/, '')}
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="text-meta text-ink-muted">{UI.poi.sameNameNone}</p>
            )}
          </section>
          <BusRoutes p={p} routes={routes} />
        </>
      )}
      <div className="space-y-0.5 border-t border-ink/10 pt-2">
        <SourceLine l={layer} />
        {p.kind === 'bus_stop' && routesLayer && p.route_ids.length > 0 && (
          <p className="text-caption text-ink-muted" data-testid="poi-route-source">{UI.poi.routeSource(infraAsOf(routesLayer.as_of))}</p>
        )}
      </div>
    </div>
  )
}

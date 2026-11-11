/**
 * 반경 보기 결과 (P18 5단계): 원 안 개수를 분류별 표로. 숫자만 (점수·순위·많음/적음 표현 없음).
 * 계산은 브라우저에 불러온 GeoJSON으로 (infra/radius.ts). 꺼져 있던 정류장·편의시설은 원을 그릴 때 불러온다.
 * P19-1: 편의시설은 모든 분류 개수를 보여 주되 지도에서 꺼진 분류·하위 분류 줄은 흐리게 + '지도에서 꺼짐'.
 *   분류·하위 분류 이름을 누르면 '이것만 보기'와 같다.
 */
import { useMemo } from 'react'
import { X } from 'lucide-react'
import type { FeatureCollection, Geometry } from 'geojson'
import { UI } from '../copy/ui'
import type { Insets } from '../map/insets'
import type { ApartmentFC } from '../market/apartments'
import type { PropediaProps } from '../map/layers'
import { useMapStore } from '../state/useMapStore'
import { GlassPanel } from '../ui/GlassPanel'
import { RADII, summarize, type PoiRow } from './radius'
import { poiNode, solo, type PoiSel } from './poiSelect'
import type { useInfra } from './useInfra'

type Infra = ReturnType<typeof useInfra>

const joinParts = (xs: [string, number][]) => xs.map(([k, n]) => `${k || UI.poi.routeType('')} ${n}`).join(' · ')

function PoiLine({ r, sel }: { r: PoiRow; sel: PoiSel }) {
  const setPoi = useMapStore((s) => s.setPoi)
  const catOn = r.key in sel
  const slugOf = (label: string) => poiNode(r.key)?.subs.find((s) => s.label === label)?.slug
  const off = <span className="ml-1 text-caption" data-testid="radius-poi-off">{UI.infra.offOnMap}</span>
  return (
    <li data-cat={r.key} data-on={catOn ? '1' : '0'} className={catOn ? '' : 'opacity-50'}>
      <button type="button" className="underline-offset-2 hover:underline" data-testid="radius-poi-cat"
        aria-label={UI.infra.onlyLabel(r.label)} onClick={() => setPoi(solo(r.key))}>
        {r.label}
      </button>{' '}
      {r.count.toLocaleString('ko-KR')}
      {!catOn && off}
      {r.subs.length > 0 && (
        <ul className="ml-3">
          {r.subs.map(([label, n]) => {
            const slug = slugOf(label)
            const on = catOn && !!slug && sel[r.key].includes(slug)
            return (
              <li key={label} data-sub={slug} data-on={on ? '1' : '0'} className={on || !catOn ? '' : 'opacity-50'}>
                <button type="button" className="underline-offset-2 hover:underline" data-testid="radius-poi-sub"
                  aria-label={UI.infra.onlyLabel(label)} onClick={() => slug && setPoi(solo(r.key, slug))}>
                  {label}
                </button>{' '}
                {n.toLocaleString('ko-KR')}
                {catOn && !on && off}
              </li>
            )
          })}
        </ul>
      )}
    </li>
  )
}

export function RadiusPanel({ insets, infra, apartments, projects }: {
  insets: Insets
  infra: Infra
  apartments: ApartmentFC | null
  projects: FeatureCollection<Geometry, PropediaProps> | null
}) {
  const radius = useMapStore((s) => s.radius)
  const setRadius = useMapStore((s) => s.setRadius)
  const poiSel = useMapStore((s) => s.poi)
  const res = useMemo(() => {
    if (!radius) return null
    const polys = (projects?.features ?? []).flatMap((f) =>
      f.geometry.type === 'Polygon' || f.geometry.type === 'MultiPolygon'
        ? [{ name: f.properties.short_name ?? f.properties.name, geometry: f.geometry }]
        : [],
    )
    return summarize(radius, {
      schools: (infra.schools?.features ?? []).map((f) => f.properties),
      stations: (infra.stations?.features ?? []).map((f) => f.properties),
      stops: infra.bus ? infra.bus.features.map((f) => f.properties) : null,
      routes: infra.routes,
      pois: infra.poiLoading || !infra.cats.length ? null : infra.poiFeatures.map((f) => f.properties),
      cats: infra.cats,
      apartments: apartments ? apartments.features.map((f) => f.properties) : null,
      projects: polys,
    })
  }, [radius, infra.schools, infra.stations, infra.bus, infra.routes, infra.poiFeatures, infra.poiLoading, infra.cats, apartments, projects])
  if (!radius || !res) return null
  const rows: [string, string, string][] = [
    ['schools', UI.radius.schools, UI.radius.schoolLine(res.schools.total, joinParts(res.schools.byLevel))],
    ['stations', UI.radius.stations, res.stations.length ? `${UI.radius.count(res.stations.length)} (${res.stations.join(', ')})` : UI.radius.none],
    ['bus', UI.radius.bus, res.bus ? UI.radius.busLine(res.bus.stops, res.bus.names, res.bus.routes, joinParts(res.bus.routeTypes)) : UI.radius.loading],
    ['apartments', UI.radius.apartments, res.apartments === null ? UI.radius.loading : UI.radius.count(res.apartments)],
    ['projects', UI.radius.projects, res.projects.length ? res.projects.join(', ') : UI.radius.none],
  ]
  return (
    <GlassPanel
      role="region"
      aria-label={UI.radius.title(radius.m)}
      data-testid="radius-panel"
      data-m={radius.m}
      className="absolute overflow-y-auto p-3 text-meta"
      style={{ left: insets.left, bottom: insets.bottom + 40, width: 340, maxHeight: `calc(100% - ${insets.top + insets.bottom + 60}px)`, borderRadius: 14 }}
    >
      <div className="mb-2 flex items-center gap-2">
        <h3 className="flex-1 text-body font-semibold">{UI.radius.title(radius.m)}</h3>
        <div className="flex rounded-full bg-white/60 p-0.5" role="radiogroup" aria-label={UI.radius.tool}>
          {RADII.map((m) => (
            <button
              key={m}
              type="button"
              role="radio"
              aria-checked={radius.m === m}
              data-testid={`radius-${m}`}
              onClick={() => setRadius({ ...radius, m })}
              className={`rounded-full px-2 py-0.5 tabular-nums ${radius.m === m ? 'glass-liquid map-chip-on font-semibold' : ''}`}
            >
              {UI.radius.switchTo(m)}
            </button>
          ))}
        </div>
        <button type="button" onClick={() => setRadius(null)} aria-label={UI.radius.close} data-testid="radius-close"
          className="rounded p-0.5 text-ink-muted hover:text-ink">
          <X size={14} aria-hidden="true" />
        </button>
      </div>
      <table className="w-full border-separate border-spacing-y-1" data-testid="radius-table">
        <tbody>
          {rows.map(([k, label, text]) => (
            <tr key={k} data-row={k}>
              <th scope="row" className="w-20 pr-2 text-left align-top font-normal text-ink-muted">{label}</th>
              <td className="tabular-nums" data-testid={`radius-row-${k}`}>{text}</td>
            </tr>
          ))}
          <tr data-row="pois">
            <th scope="row" className="w-20 pr-2 text-left align-top font-normal text-ink-muted">{UI.radius.pois}</th>
            <td className="tabular-nums" data-testid="radius-row-pois">
              {res.pois ? (
                <ul className="space-y-0.5">
                  {res.pois.map((r) => <PoiLine key={r.key} r={r} sel={poiSel} />)}
                </ul>
              ) : (
                UI.radius.loading
              )}
            </td>
          </tr>
        </tbody>
      </table>
      <p className="mt-2 text-caption text-ink-muted">{UI.radius.center(radius.lon, radius.lat)}</p>
      <p className="text-caption text-ink-muted">{UI.radius.rule}</p>
    </GlassPanel>
  )
}

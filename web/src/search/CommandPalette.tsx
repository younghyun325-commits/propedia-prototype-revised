/**
 * 명령 팔레트 (P14 5). App에서 lazy()로 불러온다 (초기 JS 예산).
 * - 사업: /api/v1/map/projects 결과에서 이름·대표 지번 부분 일치 (searchProjects)
 * - 단지 (P17): 아파트 단지 레이어(실거래 신고 단지)의 단지명·다른 이름·신고 지번 부분 일치. 창을 열 때 불러온다.
 *   그룹 순서는 사업 → 주소 → 단지 (지번을 넣으면 Enter가 주소를 고른다)
 * - 주소: 기존 /api/v1/lookup 그대로. ambiguous면 후보 목록, 실패하면 응답의 안내 문구 그대로
 * - 고르면: 사업 → 그 구역으로 이동 + 선택 / 주소 → 필지 경계가 있으면 강조, 없으면 임시 핀 (좌표는 화면 메모리에만)
 * - P18: '역·학교'(역 원자료 이름 포함), 5자리 숫자면 '정류장'(ARS) 먼저 + 같은 번호 노선, '노선'(노선 번호 일치).
 *   편의시설은 검색하지 않는다. 노선 목록은 창을 열 때, 정류장은 5자리 숫자를 넣었을 때 불러온다
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Building2, Bus, Clock, MapPin, Route, School, Search, Shapes, TrainFront } from 'lucide-react'
import { getJson, useMapProjects, type MapProject } from '../api/map'
import { UI } from '../copy/ui'
import { selectProject } from '../state/actions'
import { searchApartments, useApartmentLayer, type ApartmentProps } from '../market/apartments'
import { bboxOf } from '../map/geo'
import { useMapStore } from '../state/useMapStore'
import { GlassPanel } from '../ui/GlassPanel'
import { addressQuery, loadRecent, pushRecent, saveRecent, searchProjects } from './search'
import { useBusRoutes, useBusStops, useSchools, useStations, type BusRoute, type BusStopProps, type SchoolProps, type StationProps } from '../infra/data'
import { isArsQuery } from '../infra/pick'
import { searchPlaces, searchRoutes, searchStops } from '../infra/search'

const DEBOUNCE_MS = 300

type Lookup = {
  status: 'ok' | 'ambiguous' | 'not_found' | 'out_of_scope'
  message: string | null
  normalized?: { jibun_address?: string | null; road_address?: string | null; pnu?: string | null; lat?: number | null; lon?: number | null }
  candidates?: { road_address: string | null; jibun_address: string | null; pnu: string | null; bld_name?: string | null }[]
  layers?: { parcel?: { land?: { location?: { lat?: number; lon?: number } | null } | null } } | null
}

type Item =
  | { kind: 'project'; key: string; label: string; sub: string; project: MapProject }
  | { kind: 'apartment'; key: string; label: string; sub: string; apt: ApartmentProps }
  | { kind: 'address'; key: string; label: string; sub: string; lookup: Lookup }
  | { kind: 'candidate'; key: string; label: string; sub: string; query: string }
  | { kind: 'recent'; key: string; label: string; sub: string; query: string }
  | { kind: 'place'; key: string; label: string; sub: string; place: StationProps | SchoolProps }
  | { kind: 'stop'; key: string; label: string; sub: string; stop: BusStopProps }
  | { kind: 'route'; key: string; label: string; sub: string; route: BusRoute }

/** 점 둘레 작은 상자 (이동 요청용, 줌 17 정도) */
const around = (lon: number, lat: number): [number, number, number, number] => [lon - 0.0008, lat - 0.0006, lon + 0.0008, lat + 0.0006]

function pointOf(r: Lookup): [number, number] | null {
  const n = r.normalized
  if (n?.lat != null && n?.lon != null) return [n.lon, n.lat]
  const loc = r.layers?.parcel?.land?.location
  if (loc?.lat != null && loc?.lon != null) return [loc.lon, loc.lat]
  return null
}

export default function CommandPalette() {
  const close = () => useMapStore.getState().setPaletteOpen(false)
  const projectsData = useMapProjects().data
  const projects = useMemo(() => projectsData?.projects ?? [], [projectsData])
  const aptData = useApartmentLayer(true).data
  const aptProps = useMemo(() => (aptData?.features ?? []).map((f) => f.properties), [aptData])
  const stationsData = useStations().data
  const schoolsData = useSchools().data
  const routesData = useBusRoutes(true).data
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  const [lookup, setLookup] = useState<Lookup | null>(null)
  const [loading, setLoading] = useState(false)
  const [active, setActive] = useState(0)
  const [recent, setRecent] = useState<string[]>(() => loadRecent())
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => inputRef.current?.focus(), [])
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), DEBOUNCE_MS)
    return () => clearTimeout(t)
  }, [q])
  useEffect(() => {
    setLookup(null)
    if (debounced.length < 2) return
    const ac = new AbortController()
    setLoading(true)
    getJson<Lookup>(`/api/v1/lookup?address=${encodeURIComponent(addressQuery(debounced))}`, ac.signal)
      .then(setLookup)
      .catch((e: Error) => {
        if (e.name !== 'AbortError') setLookup({ status: 'not_found', message: e.message })
      })
      .finally(() => setLoading(false))
    return () => ac.abort()
  }, [debounced])

  const projectHits = useMemo(() => searchProjects(projects, debounced), [projects, debounced])
  const aptHits = useMemo(() => searchApartments(aptProps, debounced), [aptProps, debounced])
  const ars = isArsQuery(debounced)
  const stopsData = useBusStops(ars).data
  const placeHits = useMemo(
    () => searchPlaces((stationsData?.features ?? []).map((f) => f.properties), (schoolsData?.features ?? []).map((f) => f.properties), debounced),
    [stationsData, schoolsData, debounced],
  )
  const stopHits = useMemo(() => searchStops((stopsData?.features ?? []).map((f) => f.properties), debounced), [stopsData, debounced])
  const routeHits = useMemo(() => searchRoutes(routesData?.routes ?? [], debounced), [routesData, debounced])
  const items: Item[] = useMemo(() => {
    if (!debounced) return recent.map((r) => ({ kind: 'recent', key: `r:${r}`, label: r, sub: UI.palette.recent, query: r }))
    const out: Item[] = projectHits.map((h) => ({
      kind: 'project',
      key: `p:${h.project.id}`,
      label: h.project.short_name,
      sub: `${h.project.project_type_label} · ${h.project.representative_jibun ?? ''}`,
      project: h.project,
    }))
    if (lookup?.status === 'ok')
      out.push({
        kind: 'address',
        key: `a:${lookup.normalized?.pnu ?? debounced}`,
        label: lookup.normalized?.jibun_address ?? debounced,
        sub: lookup.normalized?.road_address ?? '',
        lookup,
      })
    if (lookup?.status === 'ambiguous')
      // 같은 필지에 도로명이 여럿인 후보가 있어 순번을 키에 넣는다
      for (const [i, c] of (lookup.candidates ?? []).entries())
        out.push({
          kind: 'candidate',
          key: `c:${i}:${c.pnu ?? c.road_address}`,
          label: c.road_address ?? c.jibun_address ?? '',
          sub: [c.jibun_address, c.bld_name].filter(Boolean).join(' · '),
          query: c.jibun_address ?? c.road_address ?? '',
        })
    // 단지는 주소 다음 (지번 입력이면 주소 결과가 먼저, Enter = 주소)
    for (const h of aptHits)
      out.push({
        kind: 'apartment',
        key: `apt:${h.props.id}`,
        label: h.props.name,
        sub: [h.props.jibuns.slice(0, 2).join(', '), h.props.aliases.length ? h.props.aliases.join(', ') : null].filter(Boolean).join(' · '),
        apt: h.props,
      })
    for (const h of placeHits)
      out.push({
        kind: 'place', key: h.props.id, label: h.props.name, place: h.props,
        sub: h.props.kind === 'station' ? `${UI.inspector.kind.station} · ${h.props.lines.join(', ')}` : `${h.props.level} · ${h.props.address ?? ''}`,
      })
    for (const s of stopHits)
      out.push({ kind: 'stop', key: s.id, label: s.name, sub: UI.palette.stopSub(s.ars_no, s.stop_type), stop: s })
    for (const r of routeHits)
      out.push({ kind: 'route', key: `route:${r.route_id}`, label: r.route_no, sub: UI.palette.routeSub(r.route_type, new Set(r.gangnam_stop_ids).size), route: r })
    // 5자리 숫자 = 정류장 번호(ARS)가 먼저
    if (ars) out.sort((a, b) => Number(b.kind === 'stop') - Number(a.kind === 'stop'))
    return out
  }, [debounced, projectHits, aptHits, lookup, recent, placeHits, stopHits, routeHits, ars])

  useEffect(() => setActive(0), [items.length, debounced])

  const remember = (s: string) => {
    const next = pushRecent(recent, s)
    setRecent(next)
    saveRecent(next)
  }

  const choose = async (it: Item) => {
    const s = useMapStore.getState()
    if (it.kind === 'recent' || it.kind === 'candidate') {
      setQ(it.query)
      return
    }
    remember(debounced || it.label)
    if (it.kind === 'project') {
      s.setSearchHit(null)
      selectProject(it.project)
    } else if (it.kind === 'apartment') {
      s.setSearchHit(null)
      s.setLayerVisible('apartments', true)
      s.select({ kind: 'apt', id: it.apt.id.replace(/^apt:/, '') })
      const f = aptData?.features.find((x) => x.properties.id === it.apt.id)
      if (f) {
        const [[w, so], [e, n]] = bboxOf([f])
        s.requestView({ type: 'bbox', bbox: [w, so, e, n] })
      }
    } else if (it.kind === 'place') {
      const p = it.place
      s.setSearchHit(null)
      s.setLayerVisible(p.kind === 'station' ? 'stations' : 'schools', true)
      s.select({ kind: p.kind, id: p.id.replace(/^[a-z]+:/, '') })
      s.requestView({ type: 'bbox', bbox: around(p.lon, p.lat) })
    } else if (it.kind === 'stop') {
      s.setSearchHit(null)
      s.setLayerVisible('bus_stops', true)
      s.select({ kind: 'bus', id: it.stop.ars_no })
      s.requestView({ type: 'bbox', bbox: around(it.stop.lon, it.stop.lat) })
    } else if (it.kind === 'route') {
      s.setSearchHit(null)
      s.setRoute(it.route.route_id)
      const pts = (stopsData?.features ?? []).filter((f) => it.route.gangnam_stop_ids.includes(f.properties.ars_no))
      if (pts.length) {
        const xs = pts.map((f) => f.properties.lon), ys = pts.map((f) => f.properties.lat)
        s.requestView({ type: 'bbox', bbox: [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)] })
      }
    } else {
      const pnu = it.lookup.normalized?.pnu ?? null
      s.setSearchHit({ label: it.label, pnu, point: pointOf(it.lookup) })
    }
    close()
  }

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      e.stopPropagation()
      close()
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((a) => Math.min(ordered.length - 1, a + 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => Math.max(0, a - 1))
    } else if (e.key === 'Enter' && ordered[active]) {
      e.preventDefault()
      void choose(ordered[active])
    }
  }

  const base: [string, Item[]][] = [
    [UI.palette.projects, items.filter((i) => i.kind === 'project')],
    [UI.palette.addresses, items.filter((i) => i.kind === 'address' || i.kind === 'candidate')],
    [UI.palette.apartments, items.filter((i) => i.kind === 'apartment')],
    [UI.palette.places, items.filter((i) => i.kind === 'place')],
  ]
  const stopsG: [string, Item[]] = [UI.palette.stops, items.filter((i) => i.kind === 'stop')]
  const routesG: [string, Item[]] = [UI.palette.routes, items.filter((i) => i.kind === 'route')]
  const groups: [string, Item[]][] = debounced
    ? ars ? [stopsG, routesG, ...base] : [...base, stopsG, routesG]
    : [[UI.palette.recent, items]]
  // 화면 순서(그룹 순서)와 ↑↓ 순서를 맞춘다
  const ordered = groups.flatMap(([, list]) => list)
  const message =
    lookup && (lookup.status === 'not_found' || lookup.status === 'out_of_scope') ? lookup.message : null

  return createPortal(
    <div
      className="palette-backdrop fixed inset-0 flex items-start justify-center pt-[12vh]"
      style={{ zIndex: 70 }}
      onMouseDown={(e) => e.target === e.currentTarget && close()}
    >
      <GlassPanel
        role="dialog"
        aria-modal="true"
        aria-label={UI.palette.label}
        data-testid="palette"
        className="w-[560px] max-w-[calc(100vw-32px)] overflow-hidden text-body"
        onKeyDown={onKey}
      >
        <div className="flex items-center gap-2 border-b border-ink/10 px-4 py-3">
          <Search size={18} aria-hidden="true" className="text-ink-muted" />
          <input
            ref={inputRef}
            data-testid="palette-input"
            role="combobox"
            aria-expanded="true"
            aria-controls="palette-list"
            aria-activedescendant={ordered[active] ? `pi-${active}` : undefined}
            aria-label={UI.palette.label}
            placeholder={UI.palette.placeholder}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="flex-1 bg-transparent text-title outline-none placeholder:text-ink-muted"
          />
          {loading && <span className="text-meta text-ink-muted">{UI.palette.searching}</span>}
        </div>
        <ul id="palette-list" role="listbox" aria-label={UI.palette.label} className="max-h-[50vh] overflow-y-auto overscroll-contain py-2">
          {groups.map(([title, list]) =>
            list.length === 0 ? null : (
              <li key={title} role="presentation">
                <div className="px-4 pt-2 pb-1 text-meta font-semibold text-ink-muted" data-testid="palette-group">
                  {title}
                </div>
                <ul role="group" aria-label={title}>
                  {list.map((it) => {
                    const idx = ordered.indexOf(it)
                    const Icon = it.kind === 'project' ? Shapes : it.kind === 'apartment' ? Building2 : it.kind === 'recent' ? Clock
                      : it.kind === 'place' ? (it.place.kind === 'station' ? TrainFront : School) : it.kind === 'stop' ? Bus
                      : it.kind === 'route' ? Route : MapPin
                    return (
                      <li
                        key={it.key}
                        id={`pi-${idx}`}
                        role="option"
                        aria-selected={idx === active}
                        data-testid={`palette-item-${it.kind}`}
                        onMouseEnter={() => setActive(idx)}
                        onMouseDown={(e) => {
                          e.preventDefault()
                          void choose(it)
                        }}
                        className={`mx-2 flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 ${idx === active ? 'bg-brand-indigo/10' : ''}`}
                      >
                        <Icon size={16} aria-hidden="true" className="shrink-0 text-ink-muted" />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate">{it.label}</span>
                          {it.sub && <span className="block truncate text-meta text-ink-muted">{it.sub}</span>}
                        </span>
                      </li>
                    )
                  })}
                </ul>
              </li>
            ),
          )}
          {debounced && !loading && items.length === 0 && (
            <li role="presentation" className="px-4 py-3 text-ink-muted" data-testid="palette-message">
              {message ?? UI.palette.empty}
            </li>
          )}
          {debounced && message && items.length > 0 && (
            <li role="presentation" className="px-4 py-2 text-meta text-ink-muted" data-testid="palette-message">
              {message}
            </li>
          )}
        </ul>
        <div className="border-t border-ink/10 px-4 py-2 text-meta text-ink-muted">{UI.palette.hint}</div>
      </GlassPanel>
    </div>,
    document.getElementById('portal-root') ?? document.body,
  )
}

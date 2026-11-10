/**
 * 반경 보기 (docs/map/PLAN.md P18 5단계). 순수 함수 — Vitest.
 * - 거리 = 하버사인(지구 반지름 6,371,008.8m). 경계 포함: 거리 ≤ 반경이면 안 (정확히 500m는 포함).
 * - 개수만 센다. 점수·순위·'많음/적음' 같은 판단을 만들지 않는다.
 */
import type { Feature, MultiPolygon, Polygon, Position } from 'geojson'
import type { BusRoute, BusStopProps, PoiCategory, PoiProps, SchoolProps, StationProps } from './data'

export const RADII = [250, 500] as const
export type Radius = { lon: number; lat: number; m: number }
const R = 6371008.8
const rad = (d: number) => (d * Math.PI) / 180

export function haversine(lon1: number, lat1: number, lon2: number, lat2: number): number {
  const p1 = rad(lat1), p2 = rad(lat2)
  const a = Math.sin((p2 - p1) / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(rad(lon2 - lon1) / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(a))
}

/** 경계 포함 규칙: 거리 ≤ m (부동소수 오차 1mm 허용) */
export const within = (r: Radius, lon: number, lat: number) => haversine(r.lon, r.lat, lon, lat) <= r.m + 1e-3

/** URL r=lon,lat,m (m은 250 또는 500). 잘못되면 null */
export function parseRadius(v: string | null | undefined): Radius | null {
  if (!v) return null
  const [lon, lat, m] = v.split(',').map(Number)
  if (![lon, lat, m].every(Number.isFinite)) return null
  if (lon < 126.9 || lon > 127.25 || lat < 37.4 || lat > 37.6) return null
  if (!(RADII as readonly number[]).includes(m)) return null
  return { lon, lat, m }
}
export const formatRadius = (r: Radius) => `${r.lon.toFixed(5)},${r.lat.toFixed(5)},${r.m}`

/** 원 둘레 (지도에 그리는 면, 64각형) */
export function circlePolygon(r: Radius, steps = 64): Feature<Polygon> {
  const ring: Position[] = []
  const dLat = r.m / 111_320
  const dLon = r.m / (111_320 * Math.cos(rad(r.lat)))
  for (let i = 0; i <= steps; i++) {
    const t = (i / steps) * 2 * Math.PI
    ring.push([r.lon + dLon * Math.cos(t), r.lat + dLat * Math.sin(t)])
  }
  return { type: 'Feature', properties: { m: r.m }, geometry: { type: 'Polygon', coordinates: [ring] } }
}

/** 점에서 선분까지 거리(m) — 반경 크기에서는 평면 근사(경도 cos 보정)로 충분 */
function segDist(r: Radius, a: Position, b: Position): number {
  const kx = 111_320 * Math.cos(rad(r.lat)), ky = 111_320
  const ax = (a[0] - r.lon) * kx, ay = (a[1] - r.lat) * ky
  const bx = (b[0] - r.lon) * kx, by = (b[1] - r.lat) * ky
  const dx = bx - ax, dy = by - ay
  const L = dx * dx + dy * dy
  const t = L ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / L)) : 0
  return Math.hypot(ax + t * dx, ay + t * dy)
}
function inRing(lon: number, lat: number, ring: Position[]): boolean {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j]
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}
/** 원이 면에 걸치는지: 중심이 면 안이거나, 면 경계까지 거리 ≤ 반경 */
export function circleTouches(r: Radius, g: Polygon | MultiPolygon): boolean {
  const polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates
  for (const poly of polys) {
    if (inRing(r.lon, r.lat, poly[0]) && !poly.slice(1).some((h) => inRing(r.lon, r.lat, h))) return true
    for (const ring of poly) for (let i = 1; i < ring.length; i++) if (segDist(r, ring[i - 1], ring[i]) <= r.m) return true
  }
  return false
}

type Pt = { lon: number; lat: number }
const inside = <T extends Pt>(r: Radius, xs: T[]) => xs.filter((p) => within(r, p.lon, p.lat))

/** 값별 개수 (원자료 순서가 아니라 이름 순) */
function tally(values: string[]): [string, number][] {
  const m = new Map<string, number>()
  for (const v of values) m.set(v, (m.get(v) ?? 0) + 1)
  return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0], 'ko'))
}

export type BusSummary = { stops: number; names: number; routes: number; routeTypes: [string, number][] }
/** 정류장 수 · 정류장 이름 수 · 지나는 서로 다른 노선 수(유형별) */
export function busSummary(r: Radius, stops: BusStopProps[], routes: Map<string, BusRoute>): BusSummary {
  const s = inside(r, stops)
  const ids = new Set(s.flatMap((x) => x.route_ids))
  return {
    stops: s.length,
    names: new Set(s.map((x) => x.name)).size,
    routes: ids.size,
    routeTypes: tally([...ids].map((id) => routes.get(id)?.route_type ?? '')),
  }
}

export type PoiRow = { key: string; label: string; count: number; subs: [string, number][] }
/** 편의시설 분류별 개수 (하위 분류가 있으면 하위 분류별 개수, 분류표 순서) */
export function poiSummary(r: Radius, pois: PoiProps[], cats: PoiCategory[]): PoiRow[] {
  const s = inside(r, pois)
  return cats.map((c) => {
    const mine = s.filter((p) => p.category === c.key)
    return {
      key: c.key, label: c.label, count: mine.length,
      subs: c.sub_categories.map((sub) => [sub, mine.filter((p) => p.sub_category === sub).length] as [string, number]),
    }
  })
}

export type RadiusResult = {
  schools: { total: number; byLevel: [string, number][] }
  stations: string[]
  bus: BusSummary | null
  pois: PoiRow[] | null
  apartments: number | null
  projects: string[]
}

export function summarize(
  r: Radius,
  d: {
    schools: SchoolProps[]
    stations: StationProps[]
    stops: BusStopProps[] | null
    routes: Map<string, BusRoute>
    pois: PoiProps[] | null
    cats: PoiCategory[]
    apartments: Pt[] | null
    projects: { name: string; geometry: Polygon | MultiPolygon }[]
  },
): RadiusResult {
  const sc = inside(r, d.schools)
  const order = ['초등학교', '중학교', '고등학교']
  const byLevel = tally(sc.map((s) => s.level)).sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0]))
  return {
    schools: { total: sc.length, byLevel },
    stations: inside(r, d.stations).map((s) => s.name).sort((a, b) => a.localeCompare(b, 'ko')),
    bus: d.stops ? busSummary(r, d.stops, d.routes) : null,
    pois: d.pois ? poiSummary(r, d.pois, d.cats) : null,
    apartments: d.apartments ? inside(r, d.apartments).length : null,
    projects: d.projects.filter((p) => circleTouches(r, p.geometry)).map((p) => p.name),
  }
}

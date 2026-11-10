/**
 * 검색(Ctrl+K)의 생활 인프라 그룹 (P18). 순수 함수 — Vitest.
 * - '역·학교': 역 이름·원자료 이름(aliases, 예: '무역센터' → 삼성)·학교 이름. 2글자 이상
 * - '정류장': 5자리 숫자를 넣었을 때만 정류장 번호(ARS) 일치
 * - '노선': 노선 번호 일치(146, 3412, 강남01). 같은 5자리 번호의 노선이 있으면 정류장과 함께 보여 준다
 * 편의시설은 검색하지 않는다.
 */
import { normQuery } from '../search/search'
import type { BusRoute, BusStopProps, SchoolProps, StationProps } from './data'
import { isArsQuery, routeRank } from './pick'

export type PlaceHit = { props: StationProps | SchoolProps; rank: number }

export function searchPlaces(stations: StationProps[], schools: SchoolProps[], q: string, limit = 8): PlaceHit[] {
  const n = normQuery(q).replace(/역$/, '')
  if (n.length < 2 || /^\d+$/.test(n)) return []
  const hits: PlaceHit[] = []
  for (const s of stations) {
    const name = normQuery(s.name)
    if (name.startsWith(n)) hits.push({ props: s, rank: 0 })
    else if (name.includes(n) || s.aliases.some((a) => normQuery(a).includes(n))) hits.push({ props: s, rank: 1 })
  }
  for (const s of schools) {
    const name = normQuery(s.name)
    if (name.startsWith(n)) hits.push({ props: s, rank: 2 })
    else if (name.includes(n)) hits.push({ props: s, rank: 3 })
  }
  return hits.sort((a, b) => a.rank - b.rank || a.props.name.localeCompare(b.props.name, 'ko')).slice(0, limit)
}

export function searchStops(stops: BusStopProps[], q: string): BusStopProps[] {
  if (!isArsQuery(q)) return []
  const n = q.replace(/\s+/g, '')
  return stops.filter((s) => s.ars_no === n)
}

export function searchRoutes(routes: BusRoute[], q: string, limit = 8): BusRoute[] {
  return routes
    .map((r) => ({ r, k: routeRank(r.route_no, q) }))
    .filter((x): x is { r: BusRoute; k: number } => x.k !== null)
    .sort((a, b) => a.k - b.k || a.r.route_no.localeCompare(b.r.route_no, 'ko'))
    .slice(0, limit)
    .map((x) => x.r)
}

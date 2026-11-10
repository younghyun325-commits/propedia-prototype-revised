import { describe, expect, it } from 'vitest'
import manifestRaw from '../../../public/data/layers/manifest.json?raw'
import type { BusRoute, BusStopProps, PoiCategory, PoiProps, SchoolProps, StationProps } from './data'
import { poiVisible, routeIndex } from './data'
import { HIT_PX, iconHit, isArsQuery, routeRank } from './pick'
import { busSummary, circleTouches, formatRadius, haversine, parseRadius, poiSummary, summarize, within } from './radius'
import { searchPlaces, searchRoutes, searchStops } from './search'
import { infraLayers, routeFilter } from './layers'
import { mergeSearch, parseUrl, toSearch } from '../state/url'
import { OVERLAP_TARGETS, paintPlan } from '../map/layers'

const C = { lon: 127.0276, lat: 37.4979 }
/** 북쪽으로 m미터 떨어진 점 (하버사인 기준 위도 차) */
const north = (m: number) => ({ lon: C.lon, lat: C.lat + (m / 6371008.8) * (180 / Math.PI) })
const impact = { within_impact: { project_id: null, buffer_m: null }, impact_buffer_m: null }
const stop = (ars: string, name: string, at: { lon: number; lat: number }, routes: string[]): BusStopProps => ({
  id: `bus:${ars}`, kind: 'bus_stop', ars_no: ars, stop_id: `1${ars}`, name, stop_type: '일반차로', central_lane: false,
  route_ids: routes, route_count: routes.length, route_types: {}, same_name_nearby: [], as_of: '2026-11-11', ...at, ...impact,
})
const route = (id: string, no: string, type: string, ars: string[]): BusRoute => ({ route_id: id, route_no: no, route_type: type, gangnam_stop_ids: ars, as_of: '2026-11-11' })
const poi = (id: string, category: string, sub: string | undefined, at: { lon: number; lat: number }): PoiProps => ({
  id: `poi:${id}`, kind: 'poi', name: id, category, ...(sub ? { sub_category: sub } : {}), category_code: 'X', address: null,
  as_of: '202609', ...at, ...impact,
})
const CATS: PoiCategory[] = [
  { key: 'academy', label: '학원', icon: 'academy', note: null, sub_categories: ['교과', '외국어', '예체능·기타'], codes: {}, count: 0, sub_counts: {} },
  { key: 'cafe', label: '카페', icon: 'cafe', note: null, sub_categories: [], codes: {}, count: 0, sub_counts: {} },
]

describe('반경 보기 (P18 5단계)', () => {
  it('하버사인: 북쪽 500m 점은 500m', () => {
    const p = north(500)
    expect(haversine(C.lon, C.lat, p.lon, p.lat)).toBeCloseTo(500, 3)
  })
  it('경계 포함: 정확히 반경 거리면 안, 1m 넘으면 밖', () => {
    const r = { ...C, m: 500 }
    const at = north(500), out = north(501)
    expect(within(r, at.lon, at.lat)).toBe(true)
    expect(within(r, out.lon, out.lat)).toBe(false)
    expect(within({ ...C, m: 250 }, at.lon, at.lat)).toBe(false)
  })
  it('정류장 수·이름 수·서로 다른 노선 수(유형별)', () => {
    const stops = [
      stop('22001', '강남역', north(10), ['1', '2']),
      stop('22002', '강남역', north(20), ['2', '3']), // 같은 이름 다른 정류장 (길 건너편)
      stop('22003', '역삼역', north(300), ['3']),
      stop('22004', '먼곳', north(900), ['4']),
    ]
    const routes = routeIndex({ routes: [route('1', '146', '간선', []), route('2', '341', '간선', []), route('3', '3412', '지선', []), route('4', '9', '광역', [])] })
    const s = busSummary({ ...C, m: 500 }, stops, routes)
    expect(s).toEqual({ stops: 3, names: 2, routes: 3, routeTypes: [['간선', 2], ['지선', 1]] })
  })
  it('편의시설 분류별·하위 분류별 개수 (분류표 순서)', () => {
    const pois = [poi('a', 'academy', '교과', north(10)), poi('b', 'academy', '외국어', north(20)), poi('c', 'academy', '교과', north(30)),
      poi('d', 'cafe', undefined, north(40)), poi('e', 'cafe', undefined, north(800))]
    expect(poiSummary({ ...C, m: 500 }, pois, CATS)).toEqual([
      { key: 'academy', label: '학원', count: 3, subs: [['교과', 2], ['외국어', 1], ['예체능·기타', 0]] },
      { key: 'cafe', label: '카페', count: 1, subs: [] },
    ])
  })
  it('학교(학교급별)·역 이름·단지 수·걸친 사업 구역', () => {
    const school = (id: string, level: string, at: { lon: number; lat: number }): SchoolProps =>
      ({ id, kind: 'school', name: id, level, address: null, as_of: '2026-10-01', ...at, ...impact })
    const st: StationProps = { id: 'station:1', kind: 'station', name: '강남', aliases: ['강남'], lines: ['2호선'], station_ids: ['1'], as_of: '', ...C, ...impact }
    const sq = (dx: number) => ({
      type: 'Polygon' as const,
      coordinates: [[[C.lon + dx, C.lat], [C.lon + dx + 0.001, C.lat], [C.lon + dx + 0.001, C.lat + 0.001], [C.lon + dx, C.lat + 0.001], [C.lon + dx, C.lat]]],
    })
    const res = summarize({ ...C, m: 500 }, {
      schools: [school('s1', '중학교', north(100)), school('s2', '초등학교', north(200)), school('s3', '고등학교', north(700))],
      stations: [st], stops: null, routes: new Map(), pois: null, cats: CATS,
      apartments: [north(100), north(499), north(600)],
      projects: [{ name: '가까운 구역', geometry: sq(0.004) }, { name: '먼 구역', geometry: sq(0.02) }],
    })
    expect(res.schools).toEqual({ total: 2, byLevel: [['초등학교', 1], ['중학교', 1]] })
    expect(res.stations).toEqual(['강남'])
    expect(res.apartments).toBe(2)
    expect(res.projects).toEqual(['가까운 구역'])
    expect(res.bus).toBeNull()
    expect(circleTouches({ ...C, m: 50 }, sq(-0.0001))).toBe(true) // 중심이 면 안
  })
  it('URL r 파라미터: 왕복, 잘못된 값은 무시 (반경은 250·500만)', () => {
    const r = parseRadius('127.02760,37.49790,500')
    expect(r).toEqual({ lon: 127.0276, lat: 37.4979, m: 500 })
    expect(formatRadius(r!)).toBe('127.02760,37.49790,500')
    expect(parseRadius('127.0276,37.4979,300')).toBeNull()
    expect(parseRadius('120,37.4979,500')).toBeNull()
    expect(parseRadius('a,b,c')).toBeNull()
  })
})

describe('URL 상태 (P18): r · route · ph', () => {
  it('왕복', () => {
    const q = '?r=127.02760,37.49790,250&route=100100025&ph=cafe,clinic/치과'
    const s = parseUrl(q)
    expect(s.radius).toEqual({ lon: 127.0276, lat: 37.4979, m: 250 })
    expect(s.route).toBe('100100025')
    expect(s.poiHidden).toEqual(['cafe', 'clinic/치과'])
    expect(parseUrl(`?${toSearch(s)}`)).toEqual(s)
    expect(mergeSearch('?debug=1', toSearch(s))).toContain('route=100100025')
  })
  it('잘못된 route·ph는 무시', () => {
    const s = parseUrl('?route=abc&ph=Cafe,,clinic/a/b')
    expect([s.route, s.poiHidden]).toEqual([null, []])
  })
  it('sel: 생활 인프라 종류', () => {
    for (const v of ['school:B000011449', 'station:0222', 'bus:22012', 'poi:MA010120220800065946'])
      expect(parseUrl(`?sel=${v}`).selected).not.toBeNull()
  })
})

describe('아이콘 클릭 히트 반경 (P18)', () => {
  const icons = [
    { id: 'school:1', kind: 'school', x: 100, y: 100 },
    { id: 'bus:22012', kind: 'bus_stop', x: 130, y: 100 },
  ]
  it('학교·역·편의시설 12px, 버스정류장 8px', () => {
    expect(HIT_PX).toEqual({ default: 12, bus_stop: 8 })
    expect(iconHit({ x: 112, y: 100 }, icons)?.id).toBe('school:1')
    expect(iconHit({ x: 100, y: 113 }, icons)).toBeNull()
    expect(iconHit({ x: 138, y: 100 }, icons)?.id).toBe('bus:22012')
    expect(iconHit({ x: 139, y: 100 }, icons)).toBeNull()
  })
  it('둘 다 안이면 가까운 쪽', () => {
    const near = [{ id: 'school:1', kind: 'school', x: 100, y: 100 }, { id: 'bus:22012', kind: 'bus_stop', x: 115, y: 100 }]
    expect(iconHit({ x: 108, y: 100 }, near)?.id).toBe('bus:22012') // 학교 8px · 정류장 7px
    expect(iconHit({ x: 106, y: 100 }, near)?.id).toBe('school:1') // 학교 6px · 정류장 9px(8px 밖)
  })
})

describe('검색 판별 (P18)', () => {
  const stations: StationProps[] = [
    { id: 'station:9006', kind: 'station', name: '삼성', aliases: ['삼성', '삼성(무역센터)'], lines: ['2호선'], station_ids: [], as_of: '', ...C, ...impact },
    { id: 'station:0220', kind: 'station', name: '선릉', aliases: ['선릉'], lines: ['2호선', '분당선'], station_ids: [], as_of: '', ...C, ...impact },
  ]
  it('ARS: 5자리 숫자만', () => {
    expect(['22012', ' 22012 ', '2201', '220123', '22a12'].map(isArsQuery)).toEqual([true, true, false, false, false])
  })
  it('노선 번호: 같으면 0, 앞부분이면 1 (2글자 이상)', () => {
    expect([routeRank('146', '146'), routeRank('1461', '146'), routeRank('146', '1'), routeRank('강남01', '강남01'), routeRank('3412', '41')])
      .toEqual([0, 1, null, 0, null])
    const rs = [route('a', '146', '간선', []), route('b', '1461', '경기', []), route('c', '3412', '지선', [])]
    expect(searchRoutes(rs, '146').map((r) => r.route_no)).toEqual(['146', '1461'])
  })
  it("역 원자료 이름으로도 찾음 ('무역센터' → 삼성), '역' 꼬리 무시", () => {
    expect(searchPlaces(stations, [], '무역센터').map((h) => h.props.name)).toEqual(['삼성'])
    expect(searchPlaces(stations, [], '선릉역').map((h) => h.props.name)).toEqual(['선릉'])
    expect(searchPlaces(stations, [], '22012')).toEqual([])
  })
  it('정류장: 5자리 번호가 같은 정류장만', () => {
    const ss = [stop('22012', '지하철2호선강남역', C, []), stop('22013', '논현역', C, [])]
    expect(searchStops(ss, '22012').map((s) => s.ars_no)).toEqual(['22012'])
    expect(searchStops(ss, '2201')).toEqual([])
  })
})

describe('지도 레이어 (P18)', () => {
  const E = { type: 'FeatureCollection', features: [] } as never
  const ids = infraLayers({ schools: E, stations: E, bus: E, pois: E }, '#5d34a9').map((l) => l.id)
  it('불러온 것만 레이어로, 클러스터는 학교·편의시설', () => {
    expect(ids).toEqual(['pois-cluster', 'pois-icon', 'pois-selected', 'schools-cluster', 'schools-icon', 'schools-selected',
      'bus-icon', 'bus-route', 'bus-selected', 'stations-icon', 'stations-selected'])
    expect(infraLayers({ schools: null, stations: E, bus: null, pois: null }, '#000').map((l) => l.id)).toEqual(['stations-icon', 'stations-selected'])
  })
  it('정류장은 줌 15 이상, 노선 정류장 필터', () => {
    const bus = infraLayers({ schools: null, stations: null, bus: E, pois: null }, '#000')
    expect(bus.find((l) => l.id === 'bus-icon')!.minzoom).toBe(15)
    expect(routeFilter(['22012'])).toEqual(['all', ['!', ['has', 'point_count']], ['in', ['get', 'ars_no'], ['literal', ['22012']]]])
  })
  it('겹침 보기 대상 4종: 칩은 영향권 밖 25%, 클러스터 원은 그대로', () => {
    for (const id of ['schools', 'stations', 'bus_stops', 'pois'] as const) expect(OVERLAP_TARGETS).toContain(id)
    const plan = Object.fromEntries(paintPlan('schools', 100, true).map(([l, p, v]) => [`${l}.${p}`, v]))
    expect(plan['schools-icon.icon-opacity']).toEqual(['case', ['==', ['get', 'impact_buffer_m'], null], 0.25, 1])
    expect(plan['schools-cluster.circle-opacity']).toBe(0.95)
  })
  it('편의시설 숨김: 분류 · 하위 분류', () => {
    expect(poiVisible({ category: 'clinic', sub_category: '치과' }, ['clinic/치과'])).toBe(false)
    expect(poiVisible({ category: 'clinic', sub_category: '의원' }, ['clinic/치과'])).toBe(true)
    expect(poiVisible({ category: 'cafe' }, ['cafe'])).toBe(false)
  })
  it('manifest: 생활 인프라 4종 + 노선, 편의시설 6분류와 하위 분류', () => {
    const m = JSON.parse(manifestRaw).layers
    for (const k of ['schools', 'stations', 'bus_stops', 'bus_routes', 'pois']) expect(m[k]?.count).toBeGreaterThan(0)
    expect(m.pois.categories.map((c: PoiCategory) => c.key)).toEqual(['supermarket', 'convenience', 'clinic', 'pharmacy', 'cafe', 'academy'])
    expect(m.pois.categories.find((c: PoiCategory) => c.key === 'clinic').sub_categories).toEqual(['병원', '의원', '치과', '한방'])
    expect(m.pois.categories.reduce((a: number, c: PoiCategory) => a + c.count, 0)).toBe(m.pois.count)
  })
})

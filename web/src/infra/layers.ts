/**
 * 생활 인프라 지도 레이어 (P18). 순수 함수 — Vitest.
 * - 학교·편의시설: 줌 15 미만은 클러스터(흰 원 + 개수, 개수는 HTML 마커), 그 이상은 칩. 이름은 줌 16 이상 HTML 마커
 * - 지하철역: 칩 + 역 이름(호선 색 없음, 호선은 툴팁·인스펙터에서)
 * - 버스정류장: 작은 칩, 줌 15 이상. 이름은 줌 17 이상. 중앙차로만 테두리가 굵은 칩
 * - 노선 선택 모드: 그 노선의 강남구 정류장만 크게 + 굵은 테두리(줌 제한 없음), 나머지 정류장은 흐리게. 선은 그리지 않는다
 * - 선택: 브랜드 색 고리
 * - 편의시설(P19-1): 분류마다 소스·레이어 따로 (poi-{key}, poi-{key}-cluster, poi-{key}-selected).
 *   하위 분류는 setFilter로만 거른다 (infra/poiSelect.ts). 클러스터 숫자는 켠 하위 분류 건수만
 */
import type { FeatureCollection, Point } from 'geojson'
import type { LayerSpecification } from 'maplibre-gl'
import type { BusStopProps, PoiProps, SchoolProps, StationProps } from './data'
import {
  POI_KEYS, clusterFilter, clusterRadiusExpr, iconFilter, poiClusterLayer, poiIconLayer, poiSelectedLayer, poiSourceId,
} from './poiSelect'

export const INFRA_SOURCES = {
  schools: 'infra-schools', stations: 'infra-stations', bus_stops: 'infra-bus',
} as const
export const RADIUS_SOURCE = 'infra-radius'
export const CLUSTER_MAX_ZOOM = 14
export const NAME_MIN_ZOOM = 16
export const STATION_NAME_MIN_ZOOM = 13
export const BUS_MIN_ZOOM = 15
export const BUS_NAME_MIN_ZOOM = 17
/** 노선 선택 모드에서 다른 정류장의 투명도 배율 */
export const ROUTE_DIM = 0.3
export const CLUSTER_LAYERS = ['schools-cluster', ...POI_KEYS.map(poiClusterLayer)]
/** 클릭 판정 대상 아이콘 레이어 → 종류 */
export const ICON_LAYERS: Record<string, string> = {
  'schools-icon': 'school', 'stations-icon': 'station', 'bus-icon': 'bus_stop', 'bus-route': 'bus_stop',
  ...Object.fromEntries(POI_KEYS.map((k) => [poiIconLayer(k), 'poi'])),
}
/** 선택 강조 레이어 → 선택 종류 */
export const INFRA_SELECTED: Record<string, string> = {
  'schools-selected': 'school', 'stations-selected': 'station', 'bus-selected': 'bus',
  ...Object.fromEntries(POI_KEYS.map((k) => [poiSelectedLayer(k), 'poi'])),
}

export type InfraData = {
  schools: FeatureCollection<Point, SchoolProps> | null
  stations: FeatureCollection<Point, StationProps> | null
  bus: FeatureCollection<Point, BusStopProps> | null
  /** 불러온 편의시설 분류만 (분류 key → 점) */
  pois: Partial<Record<string, FeatureCollection<Point, PoiProps>>>
}

const HAS_COUNT = ['has', 'point_count']
const cluster = (id: string, source: string): LayerSpecification => ({
  id, type: 'circle', source, filter: HAS_COUNT as never, maxzoom: CLUSTER_MAX_ZOOM + 1,
  paint: {
    'circle-color': '#ffffff', 'circle-stroke-color': '#1f2328', 'circle-stroke-width': 1.5,
    'circle-radius': ['step', ['get', 'point_count'], 13, 10, 15, 50, 18, 200, 21] as never,
    'circle-opacity': 0.95, 'circle-stroke-opacity': 1,
  },
})
const icon = (id: string, source: string, image: unknown, extra: Partial<LayerSpecification> = {}): LayerSpecification =>
  ({
    id, type: 'symbol', source, filter: ['!', HAS_COUNT] as never,
    layout: { 'icon-image': image as never, 'icon-allow-overlap': true, 'icon-ignore-placement': true },
    paint: { 'icon-opacity': 1 },
    ...extra,
  }) as LayerSpecification
const ring = (id: string, source: string, hl: string, r: number, minzoom = 0): LayerSpecification => ({
  id, type: 'circle', source, minzoom, filter: ['==', ['get', 'id'], '__none__'] as never,
  paint: { 'circle-color': 'rgba(0,0,0,0)', 'circle-radius': r, 'circle-stroke-color': hl, 'circle-stroke-width': 3 },
})

/** 노선 정류장 필터 (ARS 목록) */
export function routeFilter(ars: string[]): unknown[] {
  return ['all', ['!', HAS_COUNT], ['in', ['get', 'ars_no'], ['literal', ars]]]
}

/** 편의시설 분류 하나의 레이어 (처음 만들 때 켠 하위 분류 필터를 넣는다. 이후는 setFilter) */
export function poiLayers(key: string, on: string[], hl: string): LayerSpecification[] {
  const src = poiSourceId(key)
  const c = cluster(poiClusterLayer(key), src)
  return [
    { ...c, filter: clusterFilter(key, on) as never,
      paint: { ...(c as { paint: object }).paint, 'circle-radius': clusterRadiusExpr(key, on) as never } } as LayerSpecification,
    icon(poiIconLayer(key), src, `chip-${key}`, { filter: iconFilter(key, on) } as never),
    ring(poiSelectedLayer(key), src, hl, 15),
  ]
}

/** 불러온 데이터만 레이어로 (아래에서 위: 편의시설 → 학교 → 정류장 → 역 → 반경 원은 따로) */
export function infraLayers(d: InfraData, hl: string, poiOn: Record<string, string[]> = {}): LayerSpecification[] {
  const S = INFRA_SOURCES
  const out: LayerSpecification[] = []
  for (const k of POI_KEYS) if (d.pois[k]) out.push(...poiLayers(k, poiOn[k] ?? [], hl))
  if (d.schools)
    out.push(cluster('schools-cluster', S.schools), icon('schools-icon', S.schools, 'chip-school'), ring('schools-selected', S.schools, hl, 15))
  if (d.bus)
    out.push(
      icon('bus-icon', S.bus_stops, ['case', ['get', 'central_lane'], 'chip-bus-central', 'chip-bus'], { minzoom: BUS_MIN_ZOOM } as never),
      icon('bus-route', S.bus_stops, 'chip-bus-route', { filter: routeFilter([]) } as never),
      ring('bus-selected', S.bus_stops, hl, 12),
    )
  if (d.stations) out.push(icon('stations-icon', S.stations, 'chip-station'), ring('stations-selected', S.stations, hl, 15))
  return out
}

/** 반경 원 (면 6% + 잉크 점선) */
export function radiusLayers(): LayerSpecification[] {
  return [
    { id: 'radius-fill', type: 'fill', source: RADIUS_SOURCE, paint: { 'fill-color': '#1f2328', 'fill-opacity': 0.06 } },
    { id: 'radius-line', type: 'line', source: RADIUS_SOURCE,
      paint: { 'line-color': '#1f2328', 'line-width': 1.5, 'line-dasharray': [3, 2] } },
  ]
}


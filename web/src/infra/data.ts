/**
 * 생활 인프라 레이어 데이터 (docs/map/PLAN.md P18, public/data/layers — pipeline/fetch_pois.py).
 * 학교·지하철역은 처음부터, 버스정류장·노선·편의시설은 켜거나 반경 보기·검색·선택할 때만 불러온다.
 * 편의시설이 분류별 파일로 나뉘어 있으면(manifest categories[].file) 켠 분류만 불러온다.
 * 값은 원자료 그대로이며 화면은 다시 계산하지 않는다 (개수 세기만).
 */
import { useMemo } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import type { FeatureCollection, Point } from 'geojson'
import { getJson, type ManifestLayer } from '../api/map'

const DIR = '/data/layers/'

type Impact = { within_impact: { project_id: number | null; buffer_m: number | null }; impact_buffer_m: number | null }
type Base = Impact & { id: string; name: string; lon: number; lat: number; as_of: string }

export type SchoolProps = Base & { kind: 'school'; level: string; address: string | null }
export type StationProps = Base & { kind: 'station'; aliases: string[]; lines: string[]; station_ids: string[] }
export type BusStopProps = Base & {
  kind: 'bus_stop'
  ars_no: string
  stop_id: string
  stop_type: string | null
  central_lane: boolean
  route_ids: string[]
  route_count: number
  route_types: Record<string, number>
  same_name_nearby: string[]
}
export type PoiProps = Base & {
  kind: 'poi'
  category: string
  sub_category?: string
  category_code: string
  address: string | null
}
export type InfraProps = SchoolProps | StationProps | BusStopProps | PoiProps
export type InfraFC<P> = FeatureCollection<Point, P>

export type BusRoute = { route_id: string; route_no: string; route_type: string; gangnam_stop_ids: string[]; as_of: string }
export type BusRoutes = { routes: BusRoute[]; note?: string }

/** manifest 편의시설 분류 (pipeline/fetch_pois.py → core/map.py) */
export type PoiCategory = {
  key: string
  label: string
  icon: string
  note: string | null
  sub_categories: string[]
  codes: Record<string, string>
  count: number
  sub_counts: Record<string, number>
  file?: string
}
export type InfraLayer = ManifestLayer & {
  default_on?: boolean
  label_min_zoom?: number | null
  excluded?: Record<string, number>
  as_of_note?: string | null
  dataset_id?: string | null
  url?: string | null
  categories?: PoiCategory[]
  routes?: { file: string; count: number; source: string; license: string; as_of: string; dataset_id: string; url: string; as_of_note: string }
}

const opts = { staleTime: Infinity, gcTime: Infinity } as const

export const useSchools = (enabled = true) =>
  useQuery({ queryKey: ['layer', 'schools'], queryFn: ({ signal }) => getJson<InfraFC<SchoolProps>>(`${DIR}schools.geojson`, signal), enabled, ...opts })
export const useStations = (enabled = true) =>
  useQuery({ queryKey: ['layer', 'stations'], queryFn: ({ signal }) => getJson<InfraFC<StationProps>>(`${DIR}stations.geojson`, signal), enabled, ...opts })
export const useBusStops = (enabled: boolean) =>
  useQuery({ queryKey: ['layer', 'bus_stops'], queryFn: ({ signal }) => getJson<InfraFC<BusStopProps>>(`${DIR}bus_stops.geojson`, signal), enabled, ...opts })
export const useBusRoutes = (enabled: boolean) =>
  useQuery({ queryKey: ['layer', 'bus_routes'], queryFn: ({ signal }) => getJson<BusRoutes>(`${DIR}bus_routes.json`, signal), enabled, ...opts })

/** 편의시설: 분류별 파일이면 wanted 분류만, 한 파일이면 하나를 불러와 분류별로 나눈다 */
export function usePois(categories: PoiCategory[] | undefined, wanted: string[]) {
  const split = !!categories?.length && categories.every((c) => c.file)
  const files = split ? categories!.filter((c) => wanted.includes(c.key)).map((c) => c.file!) : wanted.length ? ['pois.geojson'] : []
  const qs = useQueries({
    queries: files.map((f) => ({
      queryKey: ['layer', 'pois', f],
      queryFn: ({ signal }: { signal: AbortSignal }) => getJson<InfraFC<PoiProps>>(`${DIR}${f}`, signal),
      ...opts,
    })),
  })
  const stamp = qs.map((q) => q.dataUpdatedAt).join(',')
  const key = wanted.join(',')
  const features = useMemo(
    () => qs.flatMap((q) => q.data?.features ?? []).filter((f) => key.split(',').includes(f.properties.category)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [stamp, key],
  )
  return { features, loading: qs.some((q) => q.isPending), error: qs.find((q) => q.error)?.error ?? null }
}

/** 편의시설 숨김 키: 'cafe'(분류) 또는 'clinic/치과'(하위 분류) */
export function poiVisible(p: Pick<PoiProps, 'category' | 'sub_category'>, hidden: string[]): boolean {
  if (hidden.includes(p.category)) return false
  return !(p.sub_category && hidden.includes(`${p.category}/${p.sub_category}`))
}

/** 노선 id → 노선 */
export function routeIndex(r: BusRoutes | undefined): Map<string, BusRoute> {
  return new Map((r?.routes ?? []).map((x) => [x.route_id, x]))
}

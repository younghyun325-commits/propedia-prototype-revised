/**
 * 생활 인프라 데이터 묶음 (P18): 지도·인스펙터·반경 보기·노선 칩이 같은 캐시를 쓴다.
 * 불러오는 조건 — 학교·역: 늘 (작음) / 버스정류장·노선: 레이어를 켜거나, 정류장을 고르거나, 노선 선택·반경 보기 중
 * 편의시설: 레이어가 켜져 있으면 숨기지 않은 분류만, 반경 보기·편의시설 선택 중이면 모든 분류
 */
import { useMemo } from 'react'
import { useManifest } from '../api/map'
import { useMapStore } from '../state/useMapStore'
import {
  poiVisible, routeIndex, useBusRoutes, useBusStops, usePois, useSchools, useStations, type InfraLayer, type PoiCategory,
} from './data'

export function useInfraLayers(): Partial<Record<'schools' | 'stations' | 'bus_stops' | 'pois', InfraLayer>> {
  const m = useManifest().data
  return useMemo(() => {
    const out: Partial<Record<string, InfraLayer>> = {}
    for (const l of m?.layers ?? []) if (l.group === 'infra' && l.status === 'ready') out[l.id] = l as InfraLayer
    return out
  }, [m])
}

export function useInfra() {
  const layers = useMapStore((s) => s.layers)
  const selected = useMapStore((s) => s.selected)
  const route = useMapStore((s) => s.route)
  const radius = useMapStore((s) => s.radius)
  const hidden = useMapStore((s) => s.poiHidden)
  const man = useInfraLayers()
  const cats: PoiCategory[] = useMemo(() => man.pois?.categories ?? [], [man.pois])

  const schoolsQ = useSchools(!!man.schools)
  const stationsQ = useStations(!!man.stations)
  const busWanted = !!man.bus_stops && (layers.bus_stops.visible || selected?.kind === 'bus' || route !== null || radius !== null)
  const busQ = useBusStops(busWanted)
  const routesQ = useBusRoutes(busWanted)
  const allPois = radius !== null || selected?.kind === 'poi'
  const wanted = useMemo(
    () => cats.filter((c) => allPois || (layers.pois.visible && !hidden.includes(c.key))).map((c) => c.key),
    [cats, allPois, layers.pois.visible, hidden],
  )
  const pois = usePois(cats, wanted)
  const routes = useMemo(() => routeIndex(routesQ.data), [routesQ.data])
  const mapPois = useMemo(
    () => (layers.pois.visible ? pois.features.filter((f) => poiVisible(f.properties, hidden)) : []),
    [pois.features, hidden, layers.pois.visible],
  )
  const error = schoolsQ.error ?? stationsQ.error ?? busQ.error ?? routesQ.error ?? pois.error
  return {
    man, cats, routes,
    schools: schoolsQ.data ?? null,
    stations: stationsQ.data ?? null,
    bus: busQ.data ?? null,
    busLoading: busWanted && busQ.isPending,
    routesData: routesQ.data ?? null,
    poiFeatures: pois.features,
    poiLoading: pois.loading,
    mapPois,
    error: error ? (error as Error).message : null,
  }
}

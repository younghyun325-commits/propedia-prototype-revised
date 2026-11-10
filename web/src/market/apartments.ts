/**
 * 아파트 단지 레이어 데이터 (P17, public/data/layers/apartments.geojson). 지도와 검색이 같은 캐시를 쓴다.
 * 레이어를 켜거나, 단지를 고르거나, 검색 창을 열 때만 불러온다.
 */
import { useQuery } from '@tanstack/react-query'
import type { FeatureCollection, MultiPolygon, Polygon } from 'geojson'
import { getJson } from '../api/map'
import { normQuery } from '../search/search'

export const APARTMENT_FILE = '/data/layers/apartments.geojson'

export type ApartmentProps = {
  id: string
  kind: 'apartment'
  name: string
  aliases: string[]
  apt_seq: string | null
  pnus: string[]
  jibuns: string[]
  build_year: number | null
  last_trade_date: string | null
  trade_count: number
  lon: number
  lat: number
  impact_buffer_m: number | null
  impacts: { project_id: number; buffer_m: number }[]
  basis_info: string
  verified?: number
}
export type ApartmentFC = FeatureCollection<Polygon | MultiPolygon, ApartmentProps>

export const useApartmentLayer = (enabled: boolean) =>
  useQuery({
    queryKey: ['layer', 'apartments'],
    queryFn: ({ signal }) => getJson<ApartmentFC>(APARTMENT_FILE, signal),
    enabled,
    staleTime: Infinity,
    gcTime: Infinity,
  })

export type ApartmentHit = { props: ApartmentProps; field: 'name' | 'alias' | 'jibun'; rank: number }

/**
 * 단지 검색: 이름 앞부분(0) → 이름 포함(1) → 다른 이름 포함(2) → 신고 지번 포함(3), 같으면 이름 순. 2글자 미만이면 없음.
 * 지번은 '대치동 316'처럼 동+번지 또는 번지만으로도 찾는다.
 */
export function searchApartments(fs: ApartmentProps[], q: string, limit = 8): ApartmentHit[] {
  const n = normQuery(q).replace(/아파트$/, '')
  if (n.length < 2) return []
  const hits: ApartmentHit[] = []
  for (const p of fs) {
    const name = normQuery(p.name)
    let hit: ApartmentHit | null = null
    if (name.startsWith(n)) hit = { props: p, field: 'name', rank: 0 }
    else if (name.includes(n)) hit = { props: p, field: 'name', rank: 1 }
    else if (p.aliases.some((a) => normQuery(a).includes(n))) hit = { props: p, field: 'alias', rank: 2 }
    else if (p.jibuns.some((j) => normQuery(j).includes(n))) hit = { props: p, field: 'jibun', rank: 3 }
    if (hit) hits.push(hit)
  }
  return hits.sort((a, b) => a.rank - b.rank || a.props.name.localeCompare(b.props.name, 'ko')).slice(0, limit)
}

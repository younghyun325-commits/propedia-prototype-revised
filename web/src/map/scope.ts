/**
 * 지도 도형이 없는 규제 고르기 (P20): 원문에 경계가 없거나(서울 전역·구 단위) 경계 확인 전(D5 법정동 단위)인 규제는
 * 적용 범위(scope_type·scope_ref, /map/notices)로 법정동 경계나 강남구 경계를 대신 강조한다.
 * 도형이 있는 규제(D10)는 이 함수가 null을 돌려주고 기존 선택 강조를 쓴다.
 */
import type { Feature, FeatureCollection, MultiPolygon, Polygon } from 'geojson'
import type { RegulationState } from '../api/map'
import { UI } from '../copy/ui'
import { bboxOf, type Bounds } from './geo'

type AreaProps = { name: string; bjd_code?: string; sgg_code: string }
type Area = FeatureCollection<Polygon | MultiPolygon, AreaProps>

export type ScopeArea = {
  key: string
  level: 'bjd' | 'city'
  label: string
  fc: FeatureCollection<Polygon | MultiPolygon, AreaProps>
  bounds: Bounds
}

const GANGNAM = '11680'

export function scopeArea(
  sel: { kind: string; id: string } | null,
  regulations: RegulationState[] | undefined,
  regulationFeatureIds: ReadonlySet<string>,
  dongs: Area | null,
  gu: Area | null,
): ScopeArea | null {
  if (!sel || sel.kind !== 'regulation') return null
  const fid = `regulation:${sel.id}`
  if (regulationFeatureIds.has(fid)) return null
  const r = regulations?.find((x) => x.feature_id === fid)
  if (!r || r.has_geometry) return null
  let features: Feature<Polygon | MultiPolygon, AreaProps>[] = []
  let level: ScopeArea['level']
  if (r.scope_type === 'BJD' || r.scope_type === 'PARCEL') {
    const codes = new Set(r.scope_type === 'BJD' ? r.scope_ref : r.scope_ref.map((p) => p.slice(0, 10)))
    features = (dongs?.features ?? []).filter((f) => f.properties.bjd_code && codes.has(f.properties.bjd_code))
    level = 'bjd'
  } else if (r.scope_type === 'SIDO' || (r.scope_type === 'SGG' && r.scope_ref.includes(GANGNAM))) {
    features = gu?.features ?? []
    level = 'city'
  } else {
    return null
  }
  if (!features.length) return null
  return {
    key: `${fid}:${level}`,
    level,
    label: level === 'bjd' ? UI.regulation.scopeBjd : r.scope_type === 'SIDO' ? UI.regulation.scopeCity : UI.regulation.scopeGu,
    fc: { type: 'FeatureCollection', features },
    bounds: bboxOf(features),
  }
}

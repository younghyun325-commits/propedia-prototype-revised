import { describe, expect, it } from 'vitest'
import type { FeatureCollection, MultiPolygon, Polygon } from 'geojson'
import type { RegulationState } from '../api/map'
import { UI } from '../copy/ui'
import { scopeArea } from './scope'

type P = { name: string; bjd_code?: string; sgg_code: string }
const sq = (x: number, y: number): Polygon => ({
  type: 'Polygon', coordinates: [[[x, y], [x + 1, y], [x + 1, y + 1], [x, y + 1], [x, y]]],
})
const dongs: FeatureCollection<Polygon | MultiPolygon, P> = {
  type: 'FeatureCollection',
  features: [
    { type: 'Feature', properties: { name: '압구정동', bjd_code: '1168011000', sgg_code: '11680' }, geometry: sq(0, 0) },
    { type: 'Feature', properties: { name: '대치동', bjd_code: '1168010600', sgg_code: '11680' }, geometry: sq(5, 5) },
  ],
}
const gu: FeatureCollection<Polygon | MultiPolygon, P> = {
  type: 'FeatureCollection', features: [{ type: 'Feature', properties: { name: '강남구', sgg_code: '11680' }, geometry: sq(0, 0) }],
}
const reg = (doc: string, scope_type: RegulationState['scope_type'], scope_ref: string[], has_geometry = false): RegulationState => ({
  feature_id: `regulation:${doc}`, doc_id: doc, item_key: `${doc}-01`, status: 'in_force', status_label: null,
  effective_from: null, effective_to: null, scope_type, scope_ref, has_geometry,
})
const regs = [reg('D5', 'BJD', ['1168011000']), reg('D6', 'SIDO', ['11']), reg('D10', 'BJD', ['1168010600'], true)]
const withGeom = new Set(['regulation:D10'])

describe('scopeArea (P20 도형 없는 규제)', () => {
  it('D5: 법정동 경계, 경계 확인 전 문구', () => {
    const a = scopeArea({ kind: 'regulation', id: 'D5' }, regs, withGeom, dongs, gu)!
    expect(a.level).toBe('bjd')
    expect(a.label).toBe(UI.regulation.scopeBjd)
    expect(a.fc.features.map((f) => f.properties.name)).toEqual(['압구정동'])
    expect(a.bounds).toEqual([[0, 0], [1, 1]])
  })
  it('D6: 서울 전역 → 강남구 경계', () => {
    const a = scopeArea({ kind: 'regulation', id: 'D6' }, regs, withGeom, dongs, gu)!
    expect(a.level).toBe('city')
    expect(a.label).toBe(UI.regulation.scopeCity)
    expect(a.fc.features[0].properties.name).toBe('강남구')
  })
  it('도형이 있는 규제(D10)·다른 선택·선택 없음은 null', () => {
    expect(scopeArea({ kind: 'regulation', id: 'D10' }, regs, withGeom, dongs, gu)).toBeNull()
    expect(scopeArea({ kind: 'project', id: '1' }, regs, withGeom, dongs, gu)).toBeNull()
    expect(scopeArea(null, regs, withGeom, dongs, gu)).toBeNull()
  })
  it('경계를 아직 못 불러왔으면 null', () => {
    expect(scopeArea({ kind: 'regulation', id: 'D5' }, regs, withGeom, null, null)).toBeNull()
  })
})

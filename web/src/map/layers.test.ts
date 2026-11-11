import { describe, expect, it } from 'vitest'
import projectsRaw from '../../../public/data/layers/propedia_projects.geojson?raw'
import impactRaw from '../../../public/data/layers/propedia_impact.geojson?raw'
import parcelsRaw from '../../../public/data/layers/propedia_parcels.geojson?raw'
import regsRaw from '../../../public/data/layers/propedia_regulations.geojson?raw'
import manifestRaw from '../../../public/data/layers/manifest.json?raw'
import {
  apartmentLayers,
  DEFAULT_COLORS, HATCH_ID, OPACITY, OVERLAP_DIM, OVERLAP_TARGETS, PANEL_LAYERS, UNVERIFIED, WIDTH, hatchImage, idFilter,
  labelText, confirmedFilter, opacityExpr, paintPlan, propediaLayers, readLayerColors, SHAPE, svgDash,
  type PropediaFC,
} from './layers'
import { REF_GEO_IDS, REF_WMS_IDS, refGeoLayers, refWmsLayer } from './reference'
import { infraLayers } from '../infra/layers'
import { POI_KEYS } from '../infra/poiSelect'

const EMPTY = { type: 'FeatureCollection', features: [] }

describe('Propedia 레이어 모양 (PLAN.md 지도 레이어 모양)', () => {
  const layers = propediaLayers(DEFAULT_COLORS)
  const byId = Object.fromEntries(layers.map((l) => [l.id, l]))
  const paint = (id: string) => (byId[id] as { paint: Record<string, unknown> }).paint

  it('사업 구역: 면 32% + 외곽선 2px', () => {
    expect(OPACITY.projectFill).toBe(0.32)
    expect(paint('propedia-project-fill')['fill-opacity']).toBe(0.32)
    expect(paint('propedia-project-line')['line-width']).toBe(2)
  })
  it('영향권: 옅은 면 + 가는 점선 (SHAPE.impact)', () => {
    for (const m of [250, 500]) {
      expect(paint(`propedia-impact${m}-fill`)['fill-opacity']).toBe(SHAPE.impact.fillOpacity)
      expect(SHAPE.impact.fillOpacity).toBeLessThan(0.08)
      expect(SHAPE.impact.width).toBeLessThan(SHAPE.parcelUncertain.width)
      expect(paint(`propedia-impact${m}-line`)['line-dasharray']).toEqual([...SHAPE.impact.dash])
      expect(paint(`propedia-impact${m}-line`)['line-width']).toBe(WIDTH.impact)
      expect(paint(`propedia-impact${m}-line`)['line-dasharray']).toBeTruthy()
      expect((byId[`propedia-impact${m}-fill`] as { filter: unknown }).filter).toEqual(['==', ['get', 'buffer_m'], m])
    }
    expect(WIDTH.impact).toBe(SHAPE.impact.width)
  })
  it('규제: 빗금 + 외곽선 #B07A00', () => {
    expect(paint('propedia-regulation-fill')['fill-pattern']).toBe(HATCH_ID)
    expect(String(paint('propedia-regulation-line')['line-color']).toLowerCase()).toBe('#b07a00')
  })
  it('필지 (P22-1): 포함(확정)은 실선 + 채움, 확인 전은 점선 + 채움 없음', () => {
    expect(paint('propedia-parcel-hit')['fill-opacity']).toBe(0)
    expect(paint('propedia-parcel-fill')['fill-opacity']).toBe(SHAPE.parcelConfirmed.fillOpacity)
    expect(SHAPE.parcelConfirmed.fillOpacity).toBeGreaterThan(0)
    expect(SHAPE.parcelUncertain.fillOpacity).toBe(0)
    expect((byId['propedia-parcel-fill'] as { filter: unknown }).filter).toEqual(confirmedFilter(true))
    expect(paint('propedia-parcel-line')['line-dasharray']).toBeUndefined()
    expect(paint('propedia-parcel-line-uncertain')['line-dasharray']).toEqual([...SHAPE.parcelUncertain.dash])
    expect(layers.filter((l) => l.id.startsWith('propedia-parcel-fill')).length).toBe(1)
  })
  it('범례 칩과 지도는 같은 SHAPE 값 (SVG 점선 = 굵기 × 배수)', () => {
    expect(svgDash(SHAPE.parcelConfirmed)).toBeUndefined()
    expect(svgDash(SHAPE.parcelUncertain)).toBe('3 2.25')
    expect(svgDash(SHAPE.impact)).toBe('3 2')
    expect(WIDTH.parcel).toBe(SHAPE.parcelConfirmed.width)
    expect(WIDTH.impact).toBe(SHAPE.impact.width)
  })
  it('CSS 변수 색을 읽고, 없으면 기본값', () => {
    const fake = { getPropertyValue: (n: string) => (n === '--color-layer-project' ? ' #123456 ' : '') }
    expect(readLayerColors(fake)).toEqual({ ...DEFAULT_COLORS, project: '#123456' })
  })
  it('빗금 패턴: 45° 선, 일부만 칠함', () => {
    const img = hatchImage('#eda100', 12, 2)
    const at = (x: number, y: number) => img.data[(y * 12 + x) * 4 + 3]
    expect(at(0, 0)).toBeGreaterThan(0)
    expect(at(11, 1)).toBeGreaterThan(0)
    expect(at(6, 0)).toBe(0)
    expect(img.data[0]).toBe(0xed)
  })
})

describe('레이어 데이터 (public/data/layers)', () => {
  const all = [projectsRaw, impactRaw, parcelsRaw, regsRaw].map((r) => JSON.parse(r) as PropediaFC)
  const [projects, impact, parcels, regs] = all

  // 건수는 숫자로 적지 않고 manifest.json과 비교한다 (528 반영처럼 바뀔 수 있음)
  it('건수 = manifest.json', () => {
    const m = JSON.parse(manifestRaw).layers as Record<string, { count: number }>
    expect(projects.features).toHaveLength(m.propedia_projects.count)
    expect(impact.features).toHaveLength(m.propedia_impact.count)
    expect(parcels.features).toHaveLength(m.propedia_parcels.count)
    expect(regs.features).toHaveLength(m.propedia_regulations.count)
  })
  it('겹침 보기 속성: 필지·규제 도형마다 impact_buffer_m (null = 영향권 밖)', () => {
    for (const f of [...parcels.features, ...regs.features]) expect(f.properties).toHaveProperty('impact_buffer_m')
    const p528 = parcels.features.find((f) => f.properties.pnu === '1168011000105280000')
    expect(p528?.properties.impact_buffer_m).toBe(250)
    expect(p528?.properties.inclusion).toBe('likely')
  })
  it('확인 전 도형 라벨에는 "확인 전"', () => {
    for (const fc of all)
      for (const f of fc.features) {
        expect(f.properties.verified).toBe(0)
        expect(labelText(f.properties)).toContain(UNVERIFIED)
      }
    expect(labelText({ ...projects.features[0].properties, verified: 1 })).not.toContain(UNVERIFIED)
  })
  it('사업 라벨에 단계, 규제 라벨에 효력 기간', () => {
    expect(labelText(projects.features[0].properties)).toContain('13단계 중 2번째')
    expect(labelText(regs.features[0].properties)).toMatch(/\d{4}\.\d{2}\.\d{2}~\d{4}\.\d{2}\.\d{2}/)
  })
  it('영향권 note: 표시 기준', () => {
    for (const f of impact.features)
      expect((f.properties as unknown as { note: string }).note).toBe('표시 기준이며 영향의 크기를 뜻하지 않음')
  })
})

describe('P14 겹침 보기·점선·강조 식', () => {
  it('겹침 끔: 숫자 그대로 / 켬: 영향권 밖(impact_buffer_m == null)만 25%', () => {
    expect(opacityExpr(0.32, false)).toBe(0.32)
    expect(opacityExpr(1, true)).toEqual(['case', ['==', ['get', 'impact_buffer_m'], null], OVERLAP_DIM, 1])
    expect(OVERLAP_DIM).toBe(0.25)
  })
  it('paintPlan: 투명도 % 곱하기, 겹침 대상만 식', () => {
    expect(paintPlan('projects', 50, true)).toEqual([
      ['propedia-project-fill', 'fill-opacity', 0.16],
      ['propedia-project-line', 'line-opacity', 0.5],
    ])
    expect(OVERLAP_TARGETS).toContain('parcels')
    expect(OVERLAP_TARGETS).toContain('regulations')
    const line = (on: boolean) => paintPlan('parcels', 100, on).find(([l]) => l === 'propedia-parcel-line')!
    expect(Array.isArray(line(true)[2])).toBe(true)
    expect(line(false)[2]).toBe(1)
  })
  it('확정·확인 전 식: 같은 소스를 판정으로 나눔 (included 또는 verified 1 = 확정)', () => {
    const conf = confirmedFilter(true)
    expect(conf).toEqual(['any', ['==', ['get', 'inclusion'], 'included'], ['==', ['get', 'verified'], 1]])
    expect(confirmedFilter(false)).toEqual(['!', conf])
    const layers = propediaLayers(DEFAULT_COLORS)
    const dashed = layers.find((l) => l.id === 'propedia-parcel-line-uncertain') as { filter: unknown; paint: Record<string, unknown> }
    expect(dashed.filter).toEqual(confirmedFilter(false))
    expect(dashed.paint['line-dasharray']).toBeTruthy()
  })
  it('선택·검색 강조: 값이 없으면 맞는 도형 없음', () => {
    expect(idFilter('id', 'project:1')).toEqual(['==', ['get', 'id'], 'project:1'])
    expect(idFilter('pnu', null)[2]).not.toBe('')
  })
  it('패널 레이어마다 지도 레이어가 스타일에 있음', () => {
    const ids = new Set([
      ...propediaLayers(DEFAULT_COLORS),
      ...REF_GEO_IDS.flatMap((id) => refGeoLayers(id, DEFAULT_COLORS.ref)),
      ...REF_WMS_IDS.map(refWmsLayer),
      ...apartmentLayers(DEFAULT_COLORS),
      ...infraLayers({ schools: EMPTY as never, stations: EMPTY as never, bus: EMPTY as never, pois: Object.fromEntries(POI_KEYS.map((k) => [k, EMPTY])) as never }, '#5d34a9'),
    ].map((l) => l.id))
    for (const p of Object.values(PANEL_LAYERS)) for (const l of p.layers) expect(ids.has(l)).toBe(true)
  })
})

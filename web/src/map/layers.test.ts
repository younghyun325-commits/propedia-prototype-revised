import { describe, expect, it } from 'vitest'
import projectsRaw from '../../../public/data/layers/propedia_projects.geojson?raw'
import impactRaw from '../../../public/data/layers/propedia_impact.geojson?raw'
import parcelsRaw from '../../../public/data/layers/propedia_parcels.geojson?raw'
import regsRaw from '../../../public/data/layers/propedia_regulations.geojson?raw'
import {
  DEFAULT_COLORS, HATCH_ID, OPACITY, UNVERIFIED, WIDTH, hatchImage, labelText, propediaLayers, readLayerColors,
  type PropediaFC,
} from './layers'

describe('Propedia 레이어 모양 (PLAN.md 지도 레이어 모양)', () => {
  const layers = propediaLayers(DEFAULT_COLORS)
  const byId = Object.fromEntries(layers.map((l) => [l.id, l]))
  const paint = (id: string) => (byId[id] as { paint: Record<string, unknown> }).paint

  it('사업 구역: 면 32% + 외곽선 2px', () => {
    expect(OPACITY.projectFill).toBe(0.32)
    expect(paint('propedia-project-fill')['fill-opacity']).toBe(0.32)
    expect(paint('propedia-project-line')['line-width']).toBe(2)
  })
  it('영향권: 면 8% + 점선 1.5px', () => {
    expect(paint('propedia-impact-fill')['fill-opacity']).toBe(0.08)
    expect(paint('propedia-impact-line')['line-width']).toBe(WIDTH.impact)
    expect(WIDTH.impact).toBe(1.5)
    expect(paint('propedia-impact-line')['line-dasharray']).toBeTruthy()
  })
  it('규제: 빗금 + 외곽선 #B07A00', () => {
    expect(paint('propedia-regulation-fill')['fill-pattern']).toBe(HATCH_ID)
    expect(String(paint('propedia-regulation-line')['line-color']).toLowerCase()).toBe('#b07a00')
  })
  it('필지: 외곽선만 (면 레이어 없음), likely는 점선', () => {
    expect(layers.filter((l) => l.id.startsWith('propedia-parcel')).every((l) => l.type === 'line')).toBe(true)
    expect(paint('propedia-parcel-line-likely')['line-dasharray']).toBeTruthy()
    expect(paint('propedia-parcel-line')['line-dasharray']).toBeUndefined()
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

  // 필지 19 = 18 + 압구정동 528 (2026-11-10 영현 결정: D1 p018 결정도 대조, likely, 사람 확인 전, HUMAN_TODO 35)
  it('건수: 사업 2, 영향권 4, 필지 19, 규제 1 이상', () => {
    expect(projects.features).toHaveLength(2)
    expect(impact.features).toHaveLength(4)
    expect(parcels.features).toHaveLength(19)
    expect(regs.features.length).toBeGreaterThanOrEqual(1)
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

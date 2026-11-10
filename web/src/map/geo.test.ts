import { describe, expect, it } from 'vitest'
import type { FeatureCollection, MultiPolygon, Polygon, Position } from 'geojson'
import { bboxOf, initialFitTarget, labelPoint, outsideMask, padBounds } from './geo'
import guRaw from '../../../public/data/base/gangnam.geojson?raw'
import bjdRaw from '../../../public/data/base/bjd.geojson?raw'
import { BASEMAP_ORDER, BASEMAPS, DEFAULT_BASEMAP, tileUrl } from './basemaps'

type FC = FeatureCollection<Polygon | MultiPolygon, { name: string; bjd_code?: string }>

function inRing([x, y]: number[], ring: Position[]): boolean {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]
    const [xj, yj] = ring[j]
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}
function inArea(p: number[], g: Polygon | MultiPolygon): boolean {
  const polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates
  return polys.some((poly) => inRing(p, poly[0]) && !poly.slice(1).some((h) => inRing(p, h)))
}

describe('경계 데이터 (public/data/base)', () => {
  const gu: FC = JSON.parse(guRaw)
  const bjd: FC = JSON.parse(bjdRaw)

  it('강남구 1개, 법정동 14개', () => {
    expect(gu.features).toHaveLength(1)
    expect(bjd.features).toHaveLength(14)
  })

  it('법정동 라벨 위치가 모두 그 동 안에 있다', () => {
    for (const f of bjd.features) expect(inArea(labelPoint(f.geometry), f.geometry), f.properties.name).toBe(true)
  })

  it('경계 상자는 강남구 근처, maxBounds는 약 2km 넓다', () => {
    const [[w, s], [e, n]] = bboxOf(gu.features)
    expect(w).toBeGreaterThan(126.9)
    expect(e).toBeLessThan(127.2)
    expect(s).toBeGreaterThan(37.4)
    expect(n).toBeLessThan(37.6)
    const [[w2, s2], [e2, n2]] = padBounds([[w, s], [e, n]], 2000)
    expect((s - s2) * 111_320).toBeCloseTo(2000, 0)
    expect((n2 - n) * 111_320).toBeCloseTo(2000, 0)
    expect(w2).toBeLessThan(w)
    expect(e2).toBeGreaterThan(e)
  })

  it('스포트라이트 마스크: 구 안은 구멍, 구 밖은 덮임', () => {
    const mask = outsideMask(gu).geometry
    const center = labelPoint(gu.features[0].geometry)
    expect(inArea(center, mask)).toBe(false)
    expect(inArea([126.98, 37.57], mask)).toBe(true) // 종로 쪽
  })
})

describe('배경지도 상수', () => {
  it('4종, 기본값 회색, 회색은 Capabilities의 white 레이어', () => {
    expect(BASEMAP_ORDER).toEqual(['base', 'gray', 'satellite', 'hybrid'])
    expect(DEFAULT_BASEMAP).toBe('gray')
    expect(BASEMAPS.gray.layers[0].name).toBe('white')
    expect(BASEMAPS.hybrid.layers.map((l) => l.name)).toEqual(['Satellite', 'Hybrid'])
  })

  it('타일 주소는 https, {z}/{y}/{x} 순서', () => {
    expect(tileUrl('K', BASEMAPS.satellite.layers[0])).toBe(
      'https://api.vworld.kr/req/wmts/1.0.0/K/Satellite/{z}/{y}/{x}.jpeg',
    )
  })
})

describe('initialFitTarget (P17 0단계: 카메라 없는 sel)', () => {
  const sq = (x: number, y: number) => ({ type: 'Polygon' as const, coordinates: [[[x, y], [x + 1, y], [x + 1, y + 1], [x, y + 1], [x, y]]] })
  const fc = (id: string, x: number): FeatureCollection => ({
    type: 'FeatureCollection',
    features: [{ type: 'Feature', properties: { id }, geometry: sq(x, 0) }],
  })
  const fcs = { project: fc('project:1', 10), parcel: fc('parcel:1:1168011000105280000', 20) }

  it('선택 없음 → null', () => expect(initialFitTarget(null, fcs, true)).toBeNull())
  it('사업 → 그 도형 bbox', () =>
    expect(initialFitTarget({ kind: 'project', id: '1' }, fcs, true)).toEqual([[10, 0], [11, 1]]))
  it('사업 필지(parcel:사업:PNU) → 그 필지 bbox', () =>
    expect(initialFitTarget({ kind: 'parcel', id: '1:1168011000105280000' }, fcs, true)).toEqual([[20, 0], [21, 1]]))
  it('레이어를 아직 불러오는 중 → wait, 다 불렀는데 없음 → null', () => {
    expect(initialFitTarget({ kind: 'regulation', id: 'D10' }, fcs, false)).toBe('wait')
    expect(initialFitTarget({ kind: 'regulation', id: 'D10' }, fcs, true)).toBeNull()
  })
  it('없는 id → null', () => expect(initialFitTarget({ kind: 'project', id: '9' }, fcs, true)).toBeNull())
})

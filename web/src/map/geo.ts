/** 지도 도형 계산 (순수 함수, Vitest). */
import type { Feature, FeatureCollection, MultiPolygon, Polygon, Position } from 'geojson'

export type Bounds = [[number, number], [number, number]] // [[서, 남], [동, 북]]

type Area = Polygon | MultiPolygon

function rings(g: Area): Position[][][] {
  return g.type === 'Polygon' ? [g.coordinates] : g.coordinates
}

/** 도형들의 경계 상자 */
export function bboxOf(features: Feature<Area>[]): Bounds {
  let w = Infinity, s = Infinity, e = -Infinity, n = -Infinity
  for (const f of features)
    for (const poly of rings(f.geometry))
      for (const ring of poly)
        for (const [x, y] of ring) {
          if (x < w) w = x
          if (x > e) e = x
          if (y < s) s = y
          if (y > n) n = y
        }
  return [[w, s], [e, n]]
}

/** 경계 상자를 미터만큼 넓힌다 (위도 1° ≈ 111,320m, 경도는 cos(위도) 보정) */
export function padBounds([[w, s], [e, n]]: Bounds, meters: number): Bounds {
  const dLat = meters / 111_320
  const midLat = ((s + n) / 2) * (Math.PI / 180)
  const dLon = meters / (111_320 * Math.cos(midLat))
  return [[w - dLon, s - dLat], [e + dLon, n + dLat]]
}

/**
 * 스포트라이트 마스크: 세계를 덮는 사각형에 구 경계의 바깥 고리를 구멍으로 뚫은 폴리곤.
 * 구멍 고리는 바깥 고리와 감는 방향이 반대여야 하므로 뒤집는다.
 */
export function outsideMask(fc: FeatureCollection<Area>): Feature<Polygon> {
  const world: Position[] = [[-180, -85], [180, -85], [180, 85], [-180, 85], [-180, -85]]
  const holes: Position[][] = []
  for (const f of fc.features) for (const poly of rings(f.geometry)) holes.push([...poly[0]].reverse())
  return { type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [world, ...holes] } }
}

/** 라벨 위치: 가장 큰 고리의 면적 중심 (경계가 오목해도 대부분 안쪽에 떨어진다) */
export function labelPoint(g: Area): [number, number] {
  let best: Position[] = []
  let bestA = -1
  for (const poly of rings(g)) {
    const a = Math.abs(ringArea(poly[0]))
    if (a > bestA) {
      bestA = a
      best = poly[0]
    }
  }
  let cx = 0, cy = 0, a2 = 0
  for (let i = 0; i < best.length - 1; i++) {
    const [x0, y0] = best[i]
    const [x1, y1] = best[i + 1]
    const c = x0 * y1 - x1 * y0
    a2 += c
    cx += (x0 + x1) * c
    cy += (y0 + y1) * c
  }
  return [cx / (3 * a2), cy / (3 * a2)]
}

function ringArea(r: Position[]): number {
  let a = 0
  for (let i = 0; i < r.length - 1; i++) a += r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1]
  return a / 2
}

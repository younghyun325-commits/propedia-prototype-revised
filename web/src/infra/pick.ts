/**
 * 생활 인프라 아이콘 클릭·검색 판별 (P18). 순수 함수 — Vitest.
 * 아이콘은 면 위에 있으므로 아이콘을 정확히 누른 경우에만 고른다:
 * 화면 좌표 거리 ≤ 히트 반경(학교·역·편의시설 12px, 버스정류장 8px)인 것 중 가장 가까운 것.
 */
export const HIT_PX = { default: 12, bus_stop: 8 } as const

export type IconAt = { id: string; kind: string; x: number; y: number }

export function hitRadius(kind: string): number {
  return kind === 'bus_stop' ? HIT_PX.bus_stop : HIT_PX.default
}

/** 클릭 지점(px)에서 히트 반경 안의 아이콘 중 가장 가까운 하나 */
export function iconHit(click: { x: number; y: number }, icons: IconAt[]): IconAt | null {
  let best: IconAt | null = null
  let bestD = Infinity
  for (const ic of icons) {
    const d = Math.hypot(ic.x - click.x, ic.y - click.y)
    if (d <= hitRadius(ic.kind) && d < bestD) {
      best = ic
      bestD = d
    }
  }
  return best
}

/** 정류장 번호(ARS) 입력: 공백을 뺀 5자리 숫자 */
export const isArsQuery = (q: string) => /^\d{5}$/.test(q.replace(/\s+/g, ''))

/** 노선 번호 검색: 공백을 뺀 입력과 노선 번호가 같으면 0, 앞부분이 같으면 1 (2글자 이상일 때만 앞부분) */
export function routeRank(routeNo: string, q: string): number | null {
  const n = q.replace(/\s+/g, '').toLowerCase()
  const r = routeNo.replace(/\s+/g, '').toLowerCase()
  if (!n) return null
  if (r === n) return 0
  if (n.length >= 2 && r.startsWith(n)) return 1
  return null
}

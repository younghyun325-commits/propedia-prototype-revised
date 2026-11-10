/** 원문 쪽 이미지 확대·이동 (P16 EvidenceModal). 순수 함수 — Vitest. */
export type View = { scale: number; x: number; y: number }

export const MIN_SCALE = 1
export const MAX_SCALE = 6
export const STEP = 1.4
export const PAN_STEP = 80
export const IDENTITY: View = { scale: 1, x: 0, y: 0 }

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))

/**
 * 한 점(cx, cy — 그림 상자 가운데 기준 좌표)을 고정한 채 배율을 factor배로.
 * 이동량은 그림이 상자 밖으로 다 나가지 않게 묶는다 (상자 크기 w·h).
 */
export function zoomAt(v: View, factor: number, cx: number, cy: number, w: number, h: number): View {
  const scale = clamp(v.scale * factor, MIN_SCALE, MAX_SCALE)
  const k = scale / v.scale
  return clampPan({ scale, x: cx - (cx - v.x) * k, y: cy - (cy - v.y) * k }, w, h)
}

export function panBy(v: View, dx: number, dy: number, w: number, h: number): View {
  return clampPan({ ...v, x: v.x + dx, y: v.y + dy }, w, h)
}

/** 배율 1이면 이동 없음. 그 위에서는 가장자리가 상자 가운데를 넘지 않게 */
export function clampPan(v: View, w: number, h: number): View {
  if (v.scale <= 1) return IDENTITY
  const mx = (w * (v.scale - 1)) / 2
  const my = (h * (v.scale - 1)) / 2
  return { scale: v.scale, x: clamp(v.x, -mx, mx), y: clamp(v.y, -my, my) }
}

/** 휠 한 번 → 배율 (위로 굴리면 확대) */
export const wheelFactor = (deltaY: number) => (deltaY < 0 ? 1.15 : 1 / 1.15)

/** 두 손가락 거리 변화 → 배율 */
export function pinchFactor(prevDist: number, dist: number): number {
  return prevDist > 0 ? dist / prevDist : 1
}

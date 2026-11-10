/**
 * 사업·규제 라벨 배치 (P14, P13 잔여: 강남구 전체 줌에서 대청마을·D10 라벨이 겹침). 순수 함수 — Vitest.
 *
 * 라벨은 HTML 마커라(스타일에 글꼴(glyphs) 없음, 외부 CDN 금지) MapLibre의 text-variable-anchor를 쓸 수 없다.
 * 같은 규칙을 여기서 흉내 낸다:
 *  - 줌별 표시: 라벨마다 minZoom (규제 라벨은 14 이상)
 *  - variable anchor + radial offset: 가운데 → 위 → 아래 → 오른쪽 → 왼쪽 순서로, 기준점에서 radial px 떨어뜨려 놓아 보고
 *    이미 놓은 라벨·장애물(법정동 이름)과 겹치지 않는 첫 자리를 고른다
 *  - 모두 겹치면: 늘 보여야 하는 라벨(keep)은 가장 덜 겹치는 자리, 나머지는 숨김
 */
export type Box = { x: number; y: number; w: number; h: number } // 가운데 기준
export type LabelInput = {
  id: string
  x: number // 화면 좌표 (기준점)
  y: number
  w: number
  h: number
  minZoom?: number
  keep?: boolean
}
export type Anchor = 'center' | 'top' | 'bottom' | 'right' | 'left'
export type Placement = { visible: boolean; anchor: Anchor; dx: number; dy: number }

export const ANCHORS: Anchor[] = ['center', 'top', 'bottom', 'right', 'left']
export const REGULATION_LABEL_MIN_ZOOM = 14
const GAP = 2

export function offsetFor(a: Anchor, w: number, h: number, radial: number): [number, number] {
  switch (a) {
    case 'top':
      return [0, -(h / 2 + radial)]
    case 'bottom':
      return [0, h / 2 + radial]
    case 'right':
      return [w / 2 + radial, 0]
    case 'left':
      return [-(w / 2 + radial), 0]
    default:
      return [0, 0]
  }
}

export function overlapArea(a: Box, b: Box): number {
  const dx = Math.min(a.x + a.w / 2, b.x + b.w / 2) - Math.max(a.x - a.w / 2, b.x - b.w / 2) + GAP
  const dy = Math.min(a.y + a.h / 2, b.y + b.h / 2) - Math.max(a.y - a.h / 2, b.y - b.h / 2) + GAP
  return dx > 0 && dy > 0 ? dx * dy : 0
}

export function placeLabels(
  labels: LabelInput[],
  zoom: number,
  obstacles: Box[] = [],
  radial = 14,
): Record<string, Placement> {
  const out: Record<string, Placement> = {}
  const placed: Box[] = []
  // keep(사업) 먼저, 같은 순서면 입력 순서
  const order = [...labels].sort((a, b) => Number(!!b.keep) - Number(!!a.keep))
  for (const l of order) {
    if (l.minZoom !== undefined && zoom < l.minZoom) {
      out[l.id] = { visible: false, anchor: 'center', dx: 0, dy: 0 }
      continue
    }
    let best: { a: Anchor; dx: number; dy: number; cost: number } | null = null
    for (const a of ANCHORS) {
      const [dx, dy] = offsetFor(a, l.w, l.h, radial)
      const box = { x: l.x + dx, y: l.y + dy, w: l.w, h: l.h }
      // 다른 라벨과 겹치면 크게, 법정동 이름과 겹치면 작게 친다
      const cost =
        placed.reduce((s, p) => s + overlapArea(box, p) * 10, 0) + obstacles.reduce((s, o) => s + overlapArea(box, o), 0)
      if (!best || cost < best.cost) best = { a, dx, dy, cost }
      if (cost === 0) break
    }
    const b = best!
    const clashesLabel = placed.some((p) => overlapArea({ x: l.x + b.dx, y: l.y + b.dy, w: l.w, h: l.h }, p) > 0)
    const visible = !clashesLabel || !!l.keep
    out[l.id] = { visible, anchor: b.a, dx: Math.round(b.dx), dy: Math.round(b.dy) }
    if (visible) placed.push({ x: l.x + b.dx, y: l.y + b.dy, w: l.w, h: l.h })
  }
  return out
}

/** 11px Pretendard 라벨 너비 어림값 (한글 11px, 그 밖 6.2px, 좌우 여백·띠 17px) */
export function estimateLabelWidth(text: string, hangul = 11, other = 6.2, pad = 17): number {
  let w = pad
  for (const ch of text) w += /[ᄀ-ᇿ㄰-㆏가-힯]/.test(ch) ? hangul : other
  return Math.round(w)
}

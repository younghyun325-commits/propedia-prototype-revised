/**
 * 지도 콜아웃 배치 (P16): 선택한 사업·규제 옆 미니 카드와 연결선. 순수 함수 — Vitest.
 * - 기준점이 보이는 영역(패널을 뺀 곳) 밖이면 숨긴다.
 * - 기본은 오른쪽. 오른쪽에 두면 우측 패널(보이는 영역 오른쪽 끝)과 겹칠 때 왼쪽에 둔다.
 * - 세로는 기준점 위쪽에 두되 보이는 영역 안으로 묶는다.
 */
import type { Insets } from './insets'

export type Pt = { x: number; y: number }
export type CalloutPlacement =
  | { visible: false }
  | { visible: true; side: 'left' | 'right'; left: number; top: number; line: [Pt, Pt] }

export const CALLOUT_GAP = 48

export function placeCallout(anchor: Pt, card: { w: number; h: number }, viewport: { width: number; height: number },
  insets: Insets): CalloutPlacement {
  const minX = insets.left
  const maxX = viewport.width - insets.right
  const minY = insets.top
  const maxY = viewport.height - insets.bottom
  if (!(anchor.x >= minX && anchor.x <= maxX && anchor.y >= minY && anchor.y <= maxY)) return { visible: false }
  let side: 'left' | 'right' = 'right'
  let left = anchor.x + CALLOUT_GAP
  if (left + card.w > maxX) {
    side = 'left'
    left = anchor.x - CALLOUT_GAP - card.w
  }
  if (left < minX) return { visible: false } // 양쪽 모두 자리가 없음 (아주 좁은 화면)
  const top = Math.min(Math.max(minY + 4, anchor.y - card.h - 12), maxY - card.h - 4)
  const edgeX = side === 'right' ? left : left + card.w
  const edgeY = Math.min(Math.max(anchor.y, top + 12), top + card.h - 12)
  return { visible: true, side, left, top, line: [anchor, { x: edgeX, y: edgeY }] }
}

export function bboxCenter(b: [number, number, number, number]): [number, number] {
  return [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2]
}

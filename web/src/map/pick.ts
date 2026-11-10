/**
 * 지도 클릭 우선순위 (docs/map/PLAN.md P15-3-3). 순수 함수 — Vitest.
 *
 * 사업 구역 → 규제 구역 → 사업 필지 → (P17 아파트, P18 생활 인프라 자리) → 빈 곳 = 필지 조회.
 * 공식 참고 레이어(서울플랜+·의제처리구역·WMS)는 클릭 대상이 아니다.
 * Propedia 도형이 하나면 바로 선택, 둘 이상 겹치면 우선순위 순서의 선택 목록(P14 방식 유지, 영현 결정 2026-11-10).
 */
export const PICK_ORDER: Record<string, number> = {
  project: 0,
  regulation: 1,
  parcel: 2,
  apartment: 3, // P17 자리
  poi: 4, // P18 자리
}

export type PickTarget = { id: string; kind: string }
export type ClickDecision =
  | { type: 'select'; id: string }
  | { type: 'choose'; items: PickTarget[] }
  | { type: 'parcel-lookup' }

/** 클릭 지점의 대상(중복 제거 전이어도 됨) → 할 일 */
export function decideClick(targets: PickTarget[]): ClickDecision {
  const seen = new Set<string>()
  const ts = targets
    .filter((t) => t.kind in PICK_ORDER)
    .filter((t) => (seen.has(t.id) ? false : (seen.add(t.id), true)))
    .sort((a, b) => PICK_ORDER[a.kind] - PICK_ORDER[b.kind])
  if (ts.length === 0) return { type: 'parcel-lookup' }
  if (ts.length === 1) return { type: 'select', id: ts[0].id }
  return { type: 'choose', items: ts }
}

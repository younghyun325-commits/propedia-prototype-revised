/**
 * 움직임 줄이기 (P20): 사용자가 OS에서 prefers-reduced-motion을 켜면 지도 이동 애니메이션을 0ms로(flyTo → jumpTo와 같음).
 * MapLibre도 기본으로 이 설정을 따르지만, 여기서 한 번 더 명시해 화면 코드에서 같은 규칙을 쓴다.
 */
export function prefersReducedMotion(): boolean {
  try {
    return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  } catch {
    return false
  }
}

/** 지도 이동 시간: 움직임 줄이기면 0 */
export function motionMs(ms: number): number {
  return prefersReducedMotion() ? 0 : ms
}

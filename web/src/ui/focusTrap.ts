/** 모달 키보드·포커스 (P16 EvidenceModal). 순수 함수 — Vitest. */

/** Tab·Shift+Tab으로 다음 포커스 칸 (끝에서 처음으로 돈다). 지금 칸이 목록 밖(-1)이면 처음·끝 */
export function nextFocusIndex(current: number, count: number, shift: boolean): number {
  if (count <= 0) return -1
  if (current < 0 || current >= count) return shift ? count - 1 : 0
  return shift ? (current - 1 + count) % count : (current + 1) % count
}

export type ModalKey = 'close' | 'prev' | 'next' | 'zoomIn' | 'zoomOut' | 'reset' | 'panLeft' | 'panRight' | 'panUp' |
  'panDown' | null

/**
 * 모달 안 키 → 할 일. Esc 닫기, [ ] 이전·다음 근거, +/− 확대·축소, 0 원래 크기.
 * 방향키: 확대한 상태면 그림 이동, 아니면 ←/→ 이전·다음 근거. 입력칸·버튼 위의 Enter·Space는 건드리지 않는다.
 */
export function modalKey(key: string, zoomed: boolean): ModalKey {
  switch (key) {
    case 'Escape':
      return 'close'
    case '[':
      return 'prev'
    case ']':
      return 'next'
    case '+':
    case '=':
      return 'zoomIn'
    case '-':
    case '_':
      return 'zoomOut'
    case '0':
      return 'reset'
    case 'ArrowLeft':
      return zoomed ? 'panLeft' : 'prev'
    case 'ArrowRight':
      return zoomed ? 'panRight' : 'next'
    case 'ArrowUp':
      return zoomed ? 'panUp' : null
    case 'ArrowDown':
      return zoomed ? 'panDown' : null
    default:
      return null
  }
}

/** 포커스할 수 있는 요소 고르기 (모달 안) */
export const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"]), input, select, textarea'

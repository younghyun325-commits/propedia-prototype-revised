export type KeyAction = 'left' | 'right' | 'timeline' | 'clear' | 'palette' | 'help'

type KeyLike = {
  key: string
  ctrlKey?: boolean
  metaKey?: boolean
  altKey?: boolean
  shiftKey?: boolean
  target?: { tagName?: string; isContentEditable?: boolean } | null
}

const TYPING = new Set(['INPUT', 'TEXTAREA', 'SELECT'])

/**
 * L 좌측 · I 우측 · T 타임라인 · Esc 선택 해제 · Ctrl+K(맥 Cmd+K) 검색 · ? 단축키 도움말 (P20).
 * 입력 중이거나 수정 키가 눌렸으면 무시한다. Esc와 Ctrl/Cmd+K는 입력 중에도 동작한다
 * (Ctrl+K는 브라우저 기본 동작(주소창 검색)을 막는다 — useShellEffects).
 */
export function keyAction(e: KeyLike): KeyAction | null {
  if (e.key === 'Escape') return 'clear'
  if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === 'k') return 'palette'
  if (e.ctrlKey || e.metaKey || e.altKey) return null
  const t = e.target
  if (t && (t.isContentEditable || (t.tagName && TYPING.has(t.tagName)))) return null
  switch (e.key.toLowerCase()) {
    case 'l':
      return 'left'
    case 'i':
      return 'right'
    case 't':
      return 'timeline'
    case '?':
      return 'help'
    default:
      return null
  }
}

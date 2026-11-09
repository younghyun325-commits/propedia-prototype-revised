export type KeyAction = 'left' | 'right' | 'timeline' | 'clear'

type KeyLike = {
  key: string
  ctrlKey?: boolean
  metaKey?: boolean
  altKey?: boolean
  target?: { tagName?: string; isContentEditable?: boolean } | null
}

const TYPING = new Set(['INPUT', 'TEXTAREA', 'SELECT'])

/** L 좌측 · I 우측 · T 타임라인 · Esc 선택 해제. 입력 중이거나 수정 키가 눌렸으면 무시 (Esc는 입력 중에도 동작). */
export function keyAction(e: KeyLike): KeyAction | null {
  if (e.key === 'Escape') return 'clear'
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
    default:
      return null
  }
}

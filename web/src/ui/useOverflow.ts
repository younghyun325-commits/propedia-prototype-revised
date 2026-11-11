import { useLayoutEffect, useRef, useState, type RefObject } from 'react'

export function nextCompact(compact: boolean, scrollW: number, clientW: number, need: number): { compact: boolean; need: number } {
  if (!compact) return scrollW > clientW + 1 ? { compact: true, need: scrollW } : { compact: false, need }
  return clientW >= need ? { compact: false, need } : { compact: true, need }
}

export function useOverflowCompact<T extends HTMLElement>(): [RefObject<T | null>, boolean] {
  const ref = useRef<T>(null)
  const [compact, setCompact] = useState(false)
  const need = useRef(0)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const check = () => {
      const r = nextCompact(compact, el.scrollWidth, el.clientWidth, need.current)
      need.current = r.need
      if (r.compact !== compact) setCompact(r.compact)
    }
    check()
    const ro = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(check)
    ro?.observe(el)
    document.fonts?.ready.then(check).catch(() => {})
    return () => ro?.disconnect()
  }, [compact])
  return [ref, compact]
}

export function chipsThatFit(widths: number[], avail: number, moreW: number, gap: number, max: number): number {
  const total = (k: number) => widths.slice(0, k).reduce((s, w) => s + w + gap, 0) + (k < widths.length ? moreW : 0)
  for (let k = Math.min(max, widths.length); k > 0; k--) if (total(k) <= avail) return k
  return 0
}

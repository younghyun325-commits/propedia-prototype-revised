import { useRef, type CSSProperties, type KeyboardEvent, type PointerEvent } from 'react'
import { keyDelta, type Side } from './panelSize'

type Props = {
  side: Side
  label: string
  value: number
  min: number
  max: number
  style: CSSProperties
  onChange: (w: number) => void
  onReset: () => void
}

export function ResizeHandle({ side, label, value, min, max, style, onChange, onReset }: Props) {
  const drag = useRef<{ x: number; w: number } | null>(null)
  const frame = useRef(0)
  const pending = useRef<number | null>(null)

  const flush = () => {
    frame.current = 0
    if (pending.current !== null) onChange(pending.current)
    pending.current = null
  }
  const schedule = (w: number) => {
    pending.current = w
    if (!frame.current) frame.current = requestAnimationFrame(flush)
  }

  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return
    e.preventDefault()
    e.currentTarget.setPointerCapture(e.pointerId)
    e.currentTarget.focus()
    drag.current = { x: e.clientX, w: value }
    document.documentElement.classList.add('panel-resizing')
  }
  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current
    if (!d) return
    const dx = e.clientX - d.x
    schedule(d.w + (side === 'left' ? dx : -dx))
  }
  const end = (e: PointerEvent<HTMLDivElement>) => {
    if (!drag.current) return
    drag.current = null
    if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId)
    if (frame.current) cancelAnimationFrame(frame.current)
    flush()
    document.documentElement.classList.remove('panel-resizing')
  }
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      onReset()
      return
    }
    const d = keyDelta(side, e.key, e.shiftKey)
    if (d === null) return
    e.preventDefault()
    onChange(value + d)
  }

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-valuenow={Math.round(value)}
      aria-valuemin={min}
      aria-valuemax={max}
      tabIndex={0}
      data-testid={`resize-${side}`}
      className="panel-resize group absolute z-20 flex w-3 cursor-col-resize touch-none items-center justify-center focus-visible:outline-none"
      style={style}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={end}
      onPointerCancel={end}
      onDoubleClick={onReset}
      onKeyDown={onKeyDown}
    >
      <span
        aria-hidden="true"
        className="h-12 w-1 rounded-full bg-ink/20 transition-colors group-hover:bg-brand-indigo/70 group-focus-visible:bg-brand-indigo group-focus-visible:ring-2 group-focus-visible:ring-brand-indigo/40"
      />
    </div>
  )
}

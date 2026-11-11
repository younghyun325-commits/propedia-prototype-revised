/**
 * 툴팁·팝오버 (P14). backdrop-filter 안의 position: fixed가 어긋나므로(glass.css 6) body 직속 #portal-root로 띄운다.
 * 겉모양은 GlassPanel만 쓴다.
 */
import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { GlassPanel } from './GlassPanel'

function portalRoot(): HTMLElement {
  return document.getElementById('portal-root') ?? document.body
}

type Pos = { left: number; top: number }
const MARGIN = 8

/** 기준 요소 아래(공간이 없으면 위)에, 화면 안으로 */
function place(anchor: DOMRect, w: number, h: number): Pos {
  const vw = window.innerWidth
  const vh = window.innerHeight
  let left = Math.min(Math.max(MARGIN, anchor.left), vw - w - MARGIN)
  let top = anchor.bottom + 6
  if (top + h > vh - MARGIN) top = Math.max(MARGIN, anchor.top - h - 6)
  if (left < MARGIN) left = MARGIN
  return { left, top }
}

function Floating({ anchor, children, id, role, testId, width }: {
  anchor: HTMLElement
  children: ReactNode
  id: string
  role: string
  testId?: string
  width?: number
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState<Pos | null>(null)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const r = el.getBoundingClientRect()
    setPos(place(anchor.getBoundingClientRect(), r.width, r.height))
  }, [anchor])
  return createPortal(
    <div
      ref={ref}
      id={id}
      role={role}
      data-testid={testId}
      className="pointer-events-auto fixed"
      style={{ left: pos?.left ?? -9999, top: pos?.top ?? -9999, width, zIndex: 60 }}
    >
      <GlassPanel className="px-3 py-2 text-meta leading-relaxed" style={{ borderRadius: 12 }}>
        {children}
      </GlassPanel>
    </div>,
    portalRoot(),
  )
}

/** 마우스를 올리거나 포커스하면 뜨는 설명 (role=tooltip) */
export function Tooltip({ content, children, width = 260, testId }: {
  content: ReactNode
  children: (props: { ref: (el: HTMLElement | null) => void; 'aria-describedby'?: string; onMouseEnter: () => void; onMouseLeave: () => void; onFocus: () => void; onBlur: () => void }) => ReactNode
  width?: number
  testId?: string
}) {
  const id = useId()
  const [el, setEl] = useState<HTMLElement | null>(null)
  const [open, setOpen] = useState(false)
  return (
    <>
      {children({
        ref: setEl,
        'aria-describedby': open ? id : undefined,
        onMouseEnter: () => setOpen(true),
        onMouseLeave: () => setOpen(false),
        onFocus: () => setOpen(true),
        onBlur: () => setOpen(false),
      })}
      {open && el && (
        <Floating anchor={el} id={id} role="tooltip" width={width} testId={testId}>
          {content}
        </Floating>
      )}
    </>
  )
}

/** 누르면 열리는 작은 창. 바깥을 누르거나 Esc면 닫힌다 */
export function Popover({ anchor, open, onClose, children, width = 280, testId, label }: {
  anchor: HTMLElement | null
  open: boolean
  onClose: () => void
  children: ReactNode
  width?: number
  testId?: string
  label: string
}) {
  const id = useId()
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onClose()
      }
    }
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node
      if (anchor?.contains(t) || document.getElementById(id)?.contains(t)) return
      onClose()
    }
    window.addEventListener('keydown', onKey, true)
    window.addEventListener('mousedown', onDown)
    return () => {
      window.removeEventListener('keydown', onKey, true)
      window.removeEventListener('mousedown', onDown)
    }
  }, [open, anchor, id, onClose])
  if (!open || !anchor) return null
  return (
    <Floating anchor={anchor} id={id} role="dialog" width={width} testId={testId}>
      <div aria-label={label}>{children}</div>
    </Floating>
  )
}

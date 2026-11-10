/**
 * 원문 보기 모달 (P16). 기존 public/pages/Dn/pNNN.jpg 쪽 이미지 + 근거 문장 + 문서 정보 + '문서 DB에서 보기'(docs.html).
 * - body 직속 #portal-root로 띄운다 (글래스 안 position: fixed 함정, glass.css 6)
 * - role=dialog aria-modal, 포커스 가두기, Esc 닫기(지도 선택 해제와 겹치지 않게 캡처 단계에서 멈춤), 닫으면 연 버튼으로 포커스 복귀
 * - 확대·이동: 휠, 두 손가락 핀치, 끌기, +/−/원래 크기 버튼, 키보드 (ui/zoom.ts, ui/focusTrap.ts)
 * 따로 불러오는 청크 (App.tsx).
 */
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type PointerEvent as RPointerEvent } from 'react'
import { createPortal } from 'react-dom'
import { ChevronLeft, ChevronRight, ExternalLink, Minus, Plus, RotateCcw, X } from 'lucide-react'
import { UI } from '../copy/ui'
import { useMapStore } from '../state/useMapStore'
import { FOCUSABLE, modalKey, nextFocusIndex } from './focusTrap'
import { GlassPanel } from './GlassPanel'
import { IDENTITY, PAN_STEP, STEP, clampPan, panBy, pinchFactor, wheelFactor, zoomAt, type View } from './zoom'

function portalRoot(): HTMLElement {
  return document.getElementById('portal-root') ?? document.body
}

const iconBtn =
  'inline-flex h-8 w-8 items-center justify-center rounded-lg bg-white/70 text-ink hover:bg-white disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-brand-indigo'

export default function EvidenceModal() {
  const ev = useMapStore((s) => s.evidence)
  const close = useMapStore((s) => s.closeEvidence)
  const setIndex = useMapStore((s) => s.setEvidenceIndex)
  const dialogRef = useRef<HTMLDivElement>(null)
  const boxRef = useRef<HTMLDivElement>(null)
  const returnTo = useRef<HTMLElement | null>(null)
  const [view, setView] = useState<View>(IDENTITY)
  const [imgState, setImgState] = useState<'loading' | 'ok' | 'error'>('loading')
  const pointers = useRef(new Map<number, { x: number; y: number }>())
  const pinchDist = useRef(0)

  const item = ev ? ev.items[ev.index] : null
  const n = ev?.items.length ?? 0
  const i = ev?.index ?? 0

  // 열 때 포커스 기억, 닫을 때 돌려주기
  useLayoutEffect(() => {
    returnTo.current = document.activeElement as HTMLElement | null
    dialogRef.current?.querySelector<HTMLElement>('[data-autofocus]')?.focus()
    return () => {
      const el = returnTo.current
      if (el && document.contains(el)) el.focus()
    }
  }, [])

  // 칸이 바뀌면 배율·로딩 초기화
  useEffect(() => {
    setView(IDENTITY)
    setImgState('loading')
  }, [item?.page_image, i])

  const size = () => {
    const r = boxRef.current?.getBoundingClientRect()
    return { w: r?.width ?? 600, h: r?.height ?? 600 }
  }
  const zoomBy = useCallback((f: number) => {
    const { w, h } = size()
    setView((v) => zoomAt(v, f, 0, 0, w, h))
  }, [])
  const pan = useCallback((dx: number, dy: number) => {
    const { w, h } = size()
    setView((v) => panBy(v, dx, dy, w, h))
  }, [])
  const go = useCallback((d: number) => {
    if (!ev) return
    const j = ev.index + d
    if (j >= 0 && j < ev.items.length) setIndex(j)
  }, [ev, setIndex])

  // 키보드: 캡처 단계에서 받아 지도 단축키(Esc 선택 해제·L·I·T)로 새지 않게 한다
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const dlg = dialogRef.current
      if (!dlg) return
      if (e.key === 'Tab') {
        const els = Array.from(dlg.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((x) => x.offsetParent !== null)
        const j = nextFocusIndex(els.indexOf(document.activeElement as HTMLElement), els.length, e.shiftKey)
        if (j >= 0) {
          e.preventDefault()
          els[j].focus()
        }
        e.stopPropagation()
        return
      }
      const t = e.target as HTMLElement | null
      if ((e.key === 'Enter' || e.key === ' ') && t?.closest('button,a')) return
      const a = e.ctrlKey || e.metaKey || e.altKey ? (e.key === 'Escape' ? 'close' : null) : modalKey(e.key, view.scale > 1)
      e.stopPropagation()
      if (!a) return
      e.preventDefault()
      if (a === 'close') close()
      else if (a === 'prev') go(-1)
      else if (a === 'next') go(1)
      else if (a === 'zoomIn') zoomBy(STEP)
      else if (a === 'zoomOut') zoomBy(1 / STEP)
      else if (a === 'reset') setView(IDENTITY)
      else if (a === 'panLeft') pan(PAN_STEP, 0)
      else if (a === 'panRight') pan(-PAN_STEP, 0)
      else if (a === 'panUp') pan(0, PAN_STEP)
      else if (a === 'panDown') pan(0, -PAN_STEP)
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [close, go, zoomBy, pan, view.scale])

  // 휠 확대 (passive 해제가 필요해 직접 단다)
  useEffect(() => {
    const el = boxRef.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const r = el.getBoundingClientRect()
      const cx = e.clientX - r.left - r.width / 2
      const cy = e.clientY - r.top - r.height / 2
      setView((v) => zoomAt(v, wheelFactor(e.deltaY), cx, cy, r.width, r.height))
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [item?.page_image])

  // 끌기·두 손가락 핀치 (pointer events)
  const onPointerDown = (e: RPointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId)
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()]
      pinchDist.current = Math.hypot(a.x - b.x, a.y - b.y)
    }
  }
  const onPointerMove = (e: RPointerEvent<HTMLDivElement>) => {
    const prev = pointers.current.get(e.pointerId)
    if (!prev) return
    const cur = { x: e.clientX, y: e.clientY }
    pointers.current.set(e.pointerId, cur)
    const { w, h } = size()
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()]
      const d = Math.hypot(a.x - b.x, a.y - b.y)
      const f = pinchFactor(pinchDist.current, d)
      pinchDist.current = d
      setView((v) => zoomAt(v, f, 0, 0, w, h))
    } else {
      setView((v) => (v.scale > 1 ? clampPan({ ...v, x: v.x + cur.x - prev.x, y: v.y + cur.y - prev.y }, w, h) : v))
    }
  }
  const onPointerUp = (e: RPointerEvent<HTMLDivElement>) => {
    pointers.current.delete(e.pointerId)
    if (pointers.current.size < 2) pinchDist.current = 0
  }

  if (!ev || !item) return null
  const titleId = 'evidence-modal-title'
  return createPortal(
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-ink/40 p-4"
      data-testid="evidence-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) close()
      }}
    >
      <GlassPanel
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        data-testid="evidence-modal"
        className="flex max-h-[92vh] w-[min(1080px,96vw)] flex-col gap-3 p-4 text-sm md:flex-row"
      >
        {/* 왼쪽: 쪽 이미지 (확대·이동) */}
        <div className="flex min-h-0 flex-1 flex-col gap-2">
          <div
            ref={boxRef}
            data-testid="evidence-image-box"
            className="relative min-h-[50vh] flex-1 touch-none overflow-hidden rounded-xl bg-white"
            style={{ cursor: view.scale > 1 ? 'grab' : 'default' }}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
          >
            {item.page_image ? (
              <img
                key={item.page_image}
                src={item.page_image}
                alt={UI.evidenceModal.imageAlt(item.doc_id, item.pdf_page ?? 0)}
                data-testid="evidence-image"
                data-state={imgState}
                draggable={false}
                onLoad={() => setImgState('ok')}
                onError={() => setImgState('error')}
                className="absolute inset-0 h-full w-full select-none object-contain"
                style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`, transformOrigin: 'center' }}
              />
            ) : null}
            {(!item.page_image || imgState === 'error') && (
              <p className="absolute inset-0 flex items-center justify-center text-ink-muted">{UI.evidenceModal.noImage}</p>
            )}
          </div>
          <div className="flex items-center gap-1.5" role="toolbar" aria-label={UI.evidenceModal.label}>
            <button type="button" className={iconBtn} onClick={() => zoomBy(1 / STEP)} aria-label={UI.evidenceModal.zoomOut} data-testid="evidence-zoom-out">
              <Minus size={16} aria-hidden="true" />
            </button>
            <span className="w-12 text-center text-xs tabular-nums" aria-live="polite" data-testid="evidence-zoom">
              {Math.round(view.scale * 100)}%
            </span>
            <button type="button" className={iconBtn} onClick={() => zoomBy(STEP)} aria-label={UI.evidenceModal.zoomIn} data-testid="evidence-zoom-in">
              <Plus size={16} aria-hidden="true" />
            </button>
            <button type="button" className={iconBtn} onClick={() => setView(IDENTITY)} aria-label={UI.evidenceModal.zoomReset}>
              <RotateCcw size={15} aria-hidden="true" />
            </button>
            <span className="ml-auto hidden text-[11px] text-ink-muted lg:inline">{UI.evidenceModal.keys}</span>
          </div>
        </div>

        {/* 오른쪽: 근거 문장·문서 정보 */}
        <div className="flex w-full shrink-0 flex-col gap-3 overflow-y-auto md:w-[320px]">
          <div className="flex items-start gap-2">
            <div className="min-w-0 flex-1">
              <p className="text-xs text-ink-muted">{item.label}</p>
              <h2 id={titleId} className="font-semibold leading-snug" data-testid="evidence-title">
                {item.short_title}
              </h2>
            </div>
            <button type="button" className={iconBtn} onClick={close} aria-label={UI.evidenceModal.close} data-autofocus data-testid="evidence-close">
              <X size={16} aria-hidden="true" />
            </button>
          </div>

          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
            {item.title && item.title !== item.short_title && (
              <>
                <dt className="text-ink-muted">{UI.evidenceModal.document}</dt>
                <dd>{item.title}</dd>
              </>
            )}
            {item.gosi_no && (
              <>
                <dt className="text-ink-muted">{UI.evidenceModal.gosiNo}</dt>
                <dd>{item.gosi_no}</dd>
              </>
            )}
            {item.published_at && (
              <>
                <dt className="text-ink-muted">{UI.evidenceModal.published}</dt>
                <dd className="tabular-nums">{item.published_at}</dd>
              </>
            )}
            {item.pdf_page !== null && (
              <>
                <dt className="text-ink-muted">{item.doc_id}</dt>
                <dd className="tabular-nums" data-testid="evidence-page">{UI.evidenceModal.pdfPage(item.pdf_page, item.page_label)}</dd>
              </>
            )}
          </dl>

          <section>
            <h3 className="text-xs font-semibold text-ink-muted">{UI.evidenceModal.evidence}</h3>
            <blockquote className="mt-1 rounded-lg bg-white/70 p-2 text-[13px] leading-relaxed" data-testid="evidence-text">
              {item.evidence ?? UI.evidenceModal.noEvidence}
            </blockquote>
          </section>

          <a
            href={item.docs_url}
            target="_blank"
            rel="noreferrer"
            data-testid="evidence-docs-link"
            className="inline-flex items-center gap-1 self-start rounded-lg px-1 text-xs text-brand-indigo underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-brand-indigo"
          >
            {UI.evidenceModal.docsLink}
            <ExternalLink size={12} aria-hidden="true" />
          </a>

          {n > 1 && (
            <div className="mt-auto flex items-center gap-2">
              <button type="button" className={iconBtn} onClick={() => go(-1)} disabled={i === 0} aria-label={UI.evidenceModal.prev} data-testid="evidence-prev">
                <ChevronLeft size={16} aria-hidden="true" />
              </button>
              <span className="text-xs tabular-nums text-ink-muted" data-testid="evidence-position">
                {UI.evidenceModal.position(i + 1, n)}
              </span>
              <button type="button" className={iconBtn} onClick={() => go(1)} disabled={i === n - 1} aria-label={UI.evidenceModal.next} data-testid="evidence-next">
                <ChevronRight size={16} aria-hidden="true" />
              </button>
            </div>
          )}
        </div>
      </GlassPanel>
    </div>,
    portalRoot(),
  )
}

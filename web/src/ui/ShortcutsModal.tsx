/**
 * 단축키 도움말 (P20). ? 키 또는 설정 메뉴 '단축키 보기'로 연다.
 * role=dialog aria-modal, 포커스 가두기(Tab 순환), Esc 닫기(캡처 단계에서 멈춰 지도 선택 해제와 겹치지 않게),
 * 닫으면 연 요소로 포커스 복귀 — EvidenceModal과 같은 규칙 (ui/focusTrap.ts). 따로 불러오는 청크 (App.tsx).
 */
import { useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { UI } from '../copy/ui'
import { useMapStore } from '../state/useMapStore'
import { FOCUSABLE, nextFocusIndex } from './focusTrap'
import { GlassPanel } from './GlassPanel'

function portalRoot(): HTMLElement {
  return document.getElementById('portal-root') ?? document.body
}

export default function ShortcutsModal() {
  const setOpen = useMapStore((s) => s.setShortcutsOpen)
  const dialogRef = useRef<HTMLDivElement>(null)
  const returnTo = useRef<HTMLElement | null>(null)
  const titleId = useId()

  useEffect(() => {
    returnTo.current = document.activeElement as HTMLElement | null
    dialogRef.current?.querySelector<HTMLElement>('[data-autofocus]')?.focus()
    const onKey = (e: KeyboardEvent) => {
      const dlg = dialogRef.current
      if (!dlg) return
      if (e.key === 'Escape') {
        e.preventDefault()
        e.stopPropagation()
        setOpen(false)
      } else if (e.key === 'Tab') {
        const els = Array.from(dlg.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((x) => x.offsetParent !== null)
        const j = nextFocusIndex(els.indexOf(document.activeElement as HTMLElement), els.length, e.shiftKey)
        if (j >= 0) {
          e.preventDefault()
          els[j].focus()
        }
      }
    }
    window.addEventListener('keydown', onKey, true)
    return () => {
      window.removeEventListener('keydown', onKey, true)
      const back = returnTo.current
      if (back && document.contains(back)) back.focus()
    }
  }, [setOpen])

  return createPortal(
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-ink/30 p-4"
      onMouseDown={(e) => e.target === e.currentTarget && setOpen(false)}
    >
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby={titleId} data-testid="shortcuts-modal" className="w-full max-w-md">
        <GlassPanel className="p-4" style={{ borderRadius: 16 }}>
          <div className="mb-3 flex items-center">
            <h2 id={titleId} className="text-sm font-semibold">{UI.shortcuts.title}</h2>
            <button
              type="button"
              data-autofocus
              data-testid="shortcuts-close"
              onClick={() => setOpen(false)}
              aria-label={UI.shortcuts.close}
              className="ml-auto inline-flex h-8 w-8 items-center justify-center rounded-lg bg-white/70 hover:bg-white focus-visible:outline-2 focus-visible:outline-brand-indigo"
            >
              <X size={16} aria-hidden="true" />
            </button>
          </div>
          {UI.shortcuts.groups.map((g) => (
            <section key={g.title} className="mb-3 last:mb-0">
              <h3 className="mb-1 text-xs text-ink-muted">{g.title}</h3>
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                {g.rows.map(([keys, label]) => (
                  <div key={label} className="contents" data-testid="shortcut-row">
                    <dt className="whitespace-nowrap">
                      {keys.map((k, i) => (
                        <span key={k}>
                          {i > 0 && <span className="px-0.5 text-ink-muted">/</span>}
                          <kbd className="rounded bg-ink/8 px-1.5 py-0.5 font-mono text-[11px]">{k}</kbd>
                        </span>
                      ))}
                    </dt>
                    <dd>{label}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}
        </GlassPanel>
      </div>
    </div>,
    portalRoot(),
  )
}

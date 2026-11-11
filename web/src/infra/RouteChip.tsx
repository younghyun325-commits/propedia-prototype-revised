/** 노선 선택 모드 칩 (P18): '노선 146 · 강남구 정류장 n곳 · 해제'. 노선 유형은 색이 아니라 글자 배지(원자료 값). */
import { X } from 'lucide-react'
import { UI } from '../copy/ui'
import type { Insets } from '../map/insets'
import { useMapStore } from '../state/useMapStore'
import type { BusRoute } from './data'

export function RouteChip({ insets, routes }: { insets: Insets; routes: Map<string, BusRoute> }) {
  const route = useMapStore((s) => s.route)
  const setRoute = useMapStore((s) => s.setRoute)
  const r = route ? routes.get(route) : undefined
  if (!route || !r) return null
  const n = new Set(r.gangnam_stop_ids).size
  return (
    <div
      className="absolute flex justify-center"
      style={{ top: insets.top, left: insets.left, right: insets.right + 120, pointerEvents: 'none' }}
    >
      <div
        role="status"
        aria-label={UI.route.label}
        data-testid="route-chip"
        data-route={r.route_id}
        title={UI.route.note}
        className="glass flex items-center gap-2 px-3 py-1 text-body"
        style={{ borderRadius: 999, pointerEvents: 'auto' }}
      >
        <span className="rounded-full bg-ink/8 px-1.5 py-px text-caption font-semibold text-ink-muted">{UI.poi.routeType(r.route_type)}</span>
        <span className="tabular-nums">{UI.route.chip(r.route_no, n)}</span>
        <button
          type="button"
          onClick={() => setRoute(null)}
          data-testid="route-clear"
          className="flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-meta hover:bg-white/80"
        >
          <X size={12} aria-hidden="true" />
          {UI.route.clear}
        </button>
      </div>
    </div>
  )
}

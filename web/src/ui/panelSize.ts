export type Side = 'left' | 'right'
export type Widths = { left: number; right: number }
export type Range = { min: number; max: number; def: number }

export const LEFT_RANGE: Range = { min: 260, max: 560, def: 340 }
export const RIGHT_RANGE: Range = { min: 320, max: 720, def: 400 }
export const MAP_MIN_RATIO = 0.4
export const PANEL_GAP = 12
export const KEY_STEP = 16
export const KEY_STEP_BIG = 64
export const WIDTHS_KEY = 'propedia.map.panelWidths.v1'
export const DEFAULT_WIDTHS: Widths = { left: LEFT_RANGE.def, right: RIGHT_RANGE.def }

const RANGES: Record<Side, Range> = { left: LEFT_RANGE, right: RIGHT_RANGE }
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))

export type Shown = { left: boolean; right: boolean }

function budget(vw: number, shown: Shown): number {
  const edge = (on: boolean) => (on ? 2 * PANEL_GAP : PANEL_GAP)
  return Math.floor(vw * (1 - MAP_MIN_RATIO)) - edge(shown.left) - edge(shown.right)
}

export function maxWidth(side: Side, w: Widths, vw: number, shown: Shown): number {
  const other: Side = side === 'left' ? 'right' : 'left'
  const used = shown[other] ? w[other] : 0
  const r = RANGES[side]
  return Math.max(r.min, Math.min(r.max, budget(vw, shown) - used))
}

export function fitWidths(want: Widths, vw: number, shown: Shown, active?: Side): Widths {
  let left = Math.round(clamp(want.left, LEFT_RANGE.min, LEFT_RANGE.max))
  let right = Math.round(clamp(want.right, RIGHT_RANGE.min, RIGHT_RANGE.max))
  let over = (shown.left ? left : 0) + (shown.right ? right : 0) - budget(vw, shown)
  const order: Side[] = active === 'left' ? ['right', 'left'] : ['left', 'right']
  for (const s of order) {
    if (over <= 0 || !shown[s]) continue
    const cur = s === 'left' ? left : right
    const cut = Math.min(over, cur - RANGES[s].min)
    if (s === 'left') left -= cut
    else right -= cut
    over -= cut
  }
  return { left, right }
}

export function parseWidths(raw: string | null): Widths {
  if (!raw) return { ...DEFAULT_WIDTHS }
  try {
    const v = JSON.parse(raw) as Partial<Widths>
    const ok = (n: unknown): n is number => typeof n === 'number' && Number.isFinite(n)
    return {
      left: ok(v.left) ? clamp(v.left, LEFT_RANGE.min, LEFT_RANGE.max) : LEFT_RANGE.def,
      right: ok(v.right) ? clamp(v.right, RIGHT_RANGE.min, RIGHT_RANGE.max) : RIGHT_RANGE.def,
    }
  } catch {
    return { ...DEFAULT_WIDTHS }
  }
}

type Store = Pick<Storage, 'getItem' | 'setItem'>

function localStore(): Store | null {
  return typeof window === 'undefined' ? null : window.localStorage
}

export function readWidths(storage?: Pick<Storage, 'getItem'> | null): Widths {
  try {
    const s = storage === undefined ? localStore() : storage
    return parseWidths(s ? s.getItem(WIDTHS_KEY) : null)
  } catch {
    return { ...DEFAULT_WIDTHS }
  }
}

export function writeWidths(w: Widths, storage?: Pick<Storage, 'setItem'> | null): boolean {
  try {
    const s = storage === undefined ? localStore() : storage
    if (!s) return false
    s.setItem(WIDTHS_KEY, JSON.stringify({ left: Math.round(w.left), right: Math.round(w.right) }))
    return true
  } catch {
    return false
  }
}

export function keyDelta(side: Side, key: string, shift: boolean): number | null {
  const step = shift ? KEY_STEP_BIG : KEY_STEP
  const sign = key === 'ArrowRight' ? 1 : key === 'ArrowLeft' ? -1 : 0
  if (!sign) return null
  return side === 'left' ? sign * step : -sign * step
}

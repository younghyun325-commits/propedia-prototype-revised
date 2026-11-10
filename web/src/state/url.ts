/**
 * 지도 상태 ↔ URL (docs/map/PLAN.md P14). 순수 함수 — Vitest로 검사한다.
 * 예: ?layers=projects,impact250,impact500,parcels&op=projects:80&base=gray&ov=1&sel=project:1&tab=layers&c=127.05,37.50&z=13
 * P18: route=100100025 (노선 선택), r=127.02760,37.49794,500 (반경 보기)
 * P19-1: poi=supermarket,medical:dental+oriental,academy:language (켠 편의시설 분류·하위 분류, infra/poiSelect.ts).
 *   편의시설은 layers 파라미터에 쓰지 않는다 (layers의 'pois'는 무시하고, 켜짐 여부는 poi에서 정한다)
 * - 잘못된 값은 무시하고 기본값을 쓴다.
 * - 기본값과 같은 항목은 URL에 쓰지 않는다 (layers는 기본과 다를 때만, 카메라는 이동한 뒤에만).
 */
import { BASEMAP_ORDER, DEFAULT_BASEMAP, type BasemapId } from '../map/basemaps'
import { formatRadius, parseRadius, type Radius } from '../infra/radius'
import { formatPoi, parsePoi, poiAny, type PoiSel } from '../infra/poiSelect'

export const PANEL_LAYER_IDS = [
  'projects', 'impact250', 'impact500', 'parcels', 'regulations',
  // P15 공식 참고 (기본 꺼짐): 빌드 GeoJSON 2종 + 브이월드 WMS 3종
  'ref-seoulplan', 'ref-uije', 'ref-zoning', 'ref-district', 'ref-cadastral',
  // P17 시장 (기본 꺼짐, 켤 때 불러오기)
  'apartments',
  // P18 생활 인프라: 학교·지하철역 기본 켜짐, 버스정류장·편의시설 기본 꺼짐 (수가 많아서, 켤 때 불러오기)
  'schools', 'stations', 'bus_stops', 'pois',
] as const
export type PanelLayerId = (typeof PANEL_LAYER_IDS)[number]
export const DEFAULT_VISIBLE: PanelLayerId[] = ['projects', 'impact250', 'impact500', 'parcels', 'schools', 'stations']

export type LayerState = { visible: boolean; opacity: number } // opacity 0~100 (%)
export type LayerStates = Record<PanelLayerId, LayerState>

export const LEFT_TABS = ['layers', 'projects', 'feed', 'status'] as const
export type LeftTab = (typeof LEFT_TABS)[number]

// apt = 아파트 단지 (P17): sel=apt:11680-218 → 도형 id apt:11680-218, 인스펙터 /map/feature/apartment/apt:11680-218
// P18: school:{학교ID} · station:{역사_ID} · bus:{정류장 번호(ARS)} · poi:{상가업소번호} (도형 id와 같다)
export const SELECT_KINDS = ['project', 'parcel', 'regulation', 'apt', 'school', 'station', 'bus', 'poi'] as const
export const INFRA_SELECT_KINDS = ['school', 'station', 'bus', 'poi'] as const
export type SelectKind = (typeof SELECT_KINDS)[number]
/** id는 도형 id에서 kind를 뺀 나머지 (예: project:1 → '1', parcel:1:1168011000105280000 → '1:1168011000105280000') */
export type Selected = { kind: SelectKind; id: string } | null
export type Camera = { lon: number; lat: number; zoom: number } | null

export type UrlState = {
  layers: LayerStates
  basemap: BasemapId
  overlap: boolean
  selected: Selected
  leftTab: LeftTab
  camera: Camera
  /** 켠 편의시설 분류 → 켠 하위 분류 (P19-1). layers.pois.visible은 이 값에서 정한다 */
  poi: PoiSel
  /** 노선 선택 모드: 노선 id */
  route: string | null
  /** 반경 보기 */
  radius: Radius | null
}

/** 강남구 주변만 받는다 (지도 이동 범위보다 넓게) */
const LON = [126.9, 127.25] as const
const LAT = [37.4, 37.6] as const
const ZOOM = [11, 19] as const

export function defaultLayers(): LayerStates {
  return Object.fromEntries(
    PANEL_LAYER_IDS.map((id) => [id, { visible: DEFAULT_VISIBLE.includes(id), opacity: 100 }]),
  ) as LayerStates
}

export function defaultUrlState(): UrlState {
  return { layers: defaultLayers(), basemap: DEFAULT_BASEMAP, overlap: false, selected: null, leftTab: 'layers', camera: null,
    poi: {}, route: null, radius: null }
}

/** sel=parcel:{19자리 PNU} = 지도 클릭 필지 조회 (P15). parcel:{사업}:{PNU}는 Propedia 사업 필지 */
export function isParcelLookup(s: Selected): s is { kind: 'parcel'; id: string } {
  return !!s && s.kind === 'parcel' && /^\d{19}$/.test(s.id)
}

export function featureId(s: NonNullable<Selected>): string {
  return `${s.kind}:${s.id}`
}

export function parseSelected(v: string | null | undefined): Selected {
  if (!v) return null
  const i = v.indexOf(':')
  if (i < 1) return null
  const kind = v.slice(0, i) as SelectKind
  const id = v.slice(i + 1)
  if (!SELECT_KINDS.includes(kind) || !/^[A-Za-z0-9:._-]{1,64}$/.test(id)) return null
  return { kind, id }
}

const isPanelId = (s: string): s is PanelLayerId => (PANEL_LAYER_IDS as readonly string[]).includes(s)
const inRange = (v: number, [lo, hi]: readonly [number, number]) => Number.isFinite(v) && v >= lo && v <= hi

export function parseUrl(search: string): UrlState {
  const q = new URLSearchParams(search)
  const s = defaultUrlState()

  const lv = q.get('layers')
  if (lv !== null) {
    const ids = lv.split(',').map((x) => x.trim()).filter(Boolean)
    const valid = ids.filter(isPanelId).filter((id) => id !== 'pois')
    // 비어 있으면 '모두 끔', 모르는 이름만 있으면 기본값
    if (ids.length === 0 || valid.length > 0)
      for (const id of PANEL_LAYER_IDS) if (id !== 'pois') s.layers[id].visible = valid.includes(id)
  }
  for (const part of (q.get('op') ?? '').split(',')) {
    const [id, v] = part.split(':')
    const n = Number(v)
    if (id && isPanelId(id) && v !== undefined && v !== '' && Number.isInteger(n) && n >= 0 && n <= 100)
      s.layers[id].opacity = n
  }
  const base = q.get('base')
  if (base && (BASEMAP_ORDER as string[]).includes(base)) s.basemap = base as BasemapId
  const ov = q.get('ov')
  if (ov === '1') s.overlap = true
  s.selected = parseSelected(q.get('sel'))
  const tab = q.get('tab')
  if (tab && (LEFT_TABS as readonly string[]).includes(tab)) s.leftTab = tab as LeftTab
  const c = (q.get('c') ?? '').split(',').map(Number)
  const z = Number(q.get('z'))
  if (c.length === 2 && inRange(c[0], LON) && inRange(c[1], LAT) && q.get('z') !== null && inRange(z, ZOOM))
    s.camera = { lon: c[0], lat: c[1], zoom: z }
  s.poi = parsePoi(q.get('poi'))
  s.layers.pois.visible = poiAny(s.poi)
  const route = q.get('route')
  if (route && /^\d{1,12}$/.test(route)) s.route = route
  s.radius = parseRadius(q.get('r'))
  return s
}

/** 우리 키만 쓴 쿼리 문자열 (앞의 ? 없음). 기본값과 같은 항목은 뺀다. */
export function toSearch(s: UrlState): string {
  const d = defaultUrlState()
  const q = new URLSearchParams()
  const visible = PANEL_LAYER_IDS.filter((id) => id !== 'pois' && s.layers[id]?.visible)
  if (visible.join(',') !== DEFAULT_VISIBLE.join(',')) q.set('layers', visible.join(','))
  const op = PANEL_LAYER_IDS.filter((id) => s.layers[id] && s.layers[id].opacity !== 100).map(
    (id) => `${id}:${Math.round(s.layers[id].opacity)}`,
  )
  if (op.length) q.set('op', op.join(','))
  if (s.basemap !== d.basemap) q.set('base', s.basemap)
  if (s.overlap) q.set('ov', '1')
  if (s.selected) q.set('sel', featureId(s.selected))
  if (s.leftTab !== d.leftTab) q.set('tab', s.leftTab)
  if (s.camera) {
    q.set('c', `${s.camera.lon.toFixed(5)},${s.camera.lat.toFixed(5)}`)
    q.set('z', s.camera.zoom.toFixed(2))
  }
  const poi = formatPoi(s.poi)
  if (poi) q.set('poi', poi)
  if (s.route) q.set('route', s.route)
  if (s.radius) q.set('r', formatRadius(s.radius))
  return q.toString()
}

export const URL_KEYS = ['layers', 'op', 'base', 'ov', 'sel', 'tab', 'c', 'z', 'poi', 'route', 'r'] as const

/** 지금 주소의 다른 파라미터(debug 등)는 두고 우리 키만 바꾼 search 문자열 */
export function mergeSearch(current: string, ours: string): string {
  const q = new URLSearchParams(current)
  for (const k of URL_KEYS) q.delete(k)
  for (const [k, v] of new URLSearchParams(ours)) q.set(k, v)
  const s = q.toString().replaceAll('%2C', ',').replaceAll('%3A', ':').replaceAll('%2F', '/').replaceAll('%2B', '+')
  return s ? `?${s}` : ''
}

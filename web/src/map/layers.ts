/**
 * Propedia 검증 레이어 (docs/map/PLAN.md P13, '지도 레이어 모양'). 순수 함수 — Vitest로 검사한다.
 *
 * - 사업 구역: 면 32% + 외곽선 2px (--color-layer-project)
 * - 영향권 250m·500m: 옅은 면 + 가는 점선 (같은 색, '표시 기준' — 영향의 크기가 아님). P14: 250·500을 따로 켜고 끈다
 * - 규제 구역: 45° 빗금 + 외곽선 #B07A00 (--color-layer-regulation-line). 앰버는 흰 바탕 대비가 낮아 빗금·진한 외곽선을 같이 쓴다
 * - 포함 판정 필지 (P22-1): 포함(확정) = 실선 + 채움, 확인 전(포함될 수 있음·포함된 것으로 보임) = 점선 + 채움 없음
 * - 모양 값은 SHAPE 하나에서 지도 스타일과 범례(panel/LayerSwatch)가 같이 읽는다
 * 라벨은 HTML 마커로 그린다 (스타일에 글꼴(glyphs)이 없고 외부 CDN을 쓰지 않는다). 사람 확인 전(verified=0)이면 '확인 전'을 붙인다.
 * P14: 패널 토글은 setLayoutProperty('visibility'), 투명도·겹침 보기는 setPaintProperty(opacity 식)로 — 다시 그리지 않는다.
 */
import type { FeatureCollection, Geometry } from 'geojson'
import type { LayerSpecification } from 'maplibre-gl'
import type { PanelLayerId } from '../state/url'
import { REF_OPACITY } from './reference'
import { POI_KEYS, poiClusterLayer, poiIconLayer, poiSelectedLayer } from '../infra/poiSelect'

export type LayerKind = 'project' | 'impact' | 'parcel' | 'regulation'
export type PropediaProps = {
  id: string
  kind: LayerKind
  name: string
  short_name?: string
  verified: number
  stage_label?: string
  effective_from?: string | null
  effective_to?: string | null
  buffer_m?: number
  inclusion?: string
  pnu?: string
  project_id?: number
  impact_buffer_m?: number | null
}
export type PropediaFC = FeatureCollection<Geometry, PropediaProps>

export const LAYER_FILES: Record<LayerKind, string> = {
  project: '/data/layers/propedia_projects.geojson',
  impact: '/data/layers/propedia_impact.geojson',
  parcel: '/data/layers/propedia_parcels.geojson',
  regulation: '/data/layers/propedia_regulations.geojson',
}

export type LayerColors = { project: string; regulation: string; regulationLine: string; ref: string; apartment: string }

/** tokens.css 값과 같게 둔 기본값 (CSS 변수를 못 읽을 때) */
export const DEFAULT_COLORS: LayerColors = {
  project: '#5d34a9', regulation: '#eda100', regulationLine: '#b07a00', ref: '#5b6270', apartment: '#e0567a',
}

export const OPACITY = { projectFill: 0.32, impactFill: 0.05 } as const
export type Shape = { width: number; dash: readonly number[] | null; fillOpacity: number; lineOpacity: number }
export const SHAPE = {
  parcelConfirmed: { width: 1.5, dash: null, fillOpacity: 0.2, lineOpacity: 1 },
  parcelUncertain: { width: 1.5, dash: [2, 1.5], fillOpacity: 0, lineOpacity: 1 },
  impact: { width: 1, dash: [3, 2], fillOpacity: OPACITY.impactFill, lineOpacity: 0.7 },
} as const satisfies Record<string, Shape>
/** MapLibre line-dasharray는 선 굵기의 배수, SVG stroke-dasharray는 px */
export function svgDash(s: Shape): string | undefined {
  return s.dash ? s.dash.map((d) => d * s.width).join(' ') : undefined
}
/** 아파트 단지 (P17): 면 28% + 외곽선 */
export const APARTMENT_OPACITY = { fill: 0.28, line: 0.9 } as const
export const WIDTH = { project: 2, impact: SHAPE.impact.width, regulation: 2, parcel: SHAPE.parcelConfirmed.width } as const
export const HATCH_ID = 'propedia-hatch'
export const UNVERIFIED = '확인 전'

type CssReader = { getPropertyValue(name: string): string }
function cssReader(root?: CssReader): CssReader | undefined {
  return root ?? (typeof document !== 'undefined' ? getComputedStyle(document.documentElement) : undefined)
}

/** MapLibre 페인트는 CSS 변수를 못 읽으므로 tokens.css의 --color-layer-* 값을 읽어 넘긴다 */
export function readLayerColors(root?: CssReader): LayerColors {
  const css = cssReader(root)
  const get = (name: string, fallback: string) => css?.getPropertyValue(name).trim() || fallback
  return {
    project: get('--color-layer-project', DEFAULT_COLORS.project),
    regulation: get('--color-layer-regulation', DEFAULT_COLORS.regulation),
    regulationLine: get('--color-layer-regulation-line', DEFAULT_COLORS.regulationLine),
    ref: get('--color-layer-ref', DEFAULT_COLORS.ref),
    apartment: get('--color-layer-apartment', DEFAULT_COLORS.apartment),
  }
}

/** 라벨 글자 (짧은 이름 우선): 사람 확인 전이면 '(확인 전)'을 붙인다 */
export function labelText(p: PropediaProps): string {
  const name = p.short_name ?? p.name
  const base =
    p.kind === 'regulation' && p.effective_from && p.effective_to
      ? `${name} · ${dot(p.effective_from)}~${dot(p.effective_to)}`
      : p.kind === 'project' && p.stage_label
        ? `${name} · ${p.stage_label}`
        : name
  return p.verified ? base : `${base} (${UNVERIFIED})`
}

export function dot(iso: string): string {
  return iso.replaceAll('-', '.')
}

/** 45° 빗금 패턴 (RGBA). 줄 사이는 투명이라 아래 지도가 보인다 */
export function hatchImage(hex: string, size = 12, lineWidth = 2, alpha = 0.85): { width: number; height: number; data: Uint8Array } {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))
  const data = new Uint8Array(size * size * 4)
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      // x + y ≡ 0 (mod size) 줄 = 오른쪽 위로 올라가는 45° 선 (타일을 이어 붙여도 끊기지 않음)
      const on = (x + y) % size < lineWidth
      const i = (y * size + x) * 4
      if (on) {
        data[i] = r
        data[i + 1] = g
        data[i + 2] = b
        data[i + 3] = Math.round(alpha * 255)
      }
    }
  return { width: size, height: size, data }
}

/** 영향권 밖 도형의 투명도 배율 (겹침 보기) */
export const OVERLAP_DIM = 0.25
export const PARCEL_MIN_ZOOM = 14

/** 포함 확정 = 판정 included 또는 사람 확인(verified 1). 나머지(possible·likely)는 확인 전 */
const CONFIRMED: unknown[] = ['any', ['==', ['get', 'inclusion'], 'included'], ['==', ['get', 'verified'], 1]]
export function confirmedFilter(confirmed: boolean): unknown[] {
  return confirmed ? CONFIRMED : ['!', CONFIRMED]
}
const linePaint = (color: string, s: Shape) => ({
  'line-color': color, 'line-width': s.width, 'line-opacity': s.lineOpacity, ...(s.dash ? { 'line-dasharray': [...s.dash] } : {}),
})

const NONE = '__none__'
/** 선택·검색 강조 필터: 값이 없으면 아무것도 맞지 않는 값 */
export function idFilter(prop: 'id' | 'pnu', value: string | null): unknown[] {
  return ['==', ['get', prop], value ?? NONE]
}

export type HighlightColors = { selected: string; search: string }
export const DEFAULT_HIGHLIGHT: HighlightColors = { selected: '#5d34a9', search: '#4ab2e6' }

/** tokens.css의 브랜드 색 (선택 = indigo, 검색 = sky) */
export function readHighlightColors(root?: CssReader): HighlightColors {
  const css = cssReader(root)
  const get = (name: string, fallback: string) => css?.getPropertyValue(name).trim() || fallback
  return {
    selected: get('--color-brand-indigo', DEFAULT_HIGHLIGHT.selected),
    search: get('--color-brand-sky', DEFAULT_HIGHLIGHT.search),
  }
}

/** 스타일에 넣을 레이어 (아래에서 위 순서: 영향권 500 → 250 → 규제 → 사업 → 필지 → 강조) */
export function propediaLayers(c: LayerColors, h: HighlightColors = DEFAULT_HIGHLIGHT): LayerSpecification[] {
  const impact = (m: 250 | 500): LayerSpecification[] => [
    { id: `propedia-impact${m}-fill`, type: 'fill', source: 'propedia-impact', filter: ['==', ['get', 'buffer_m'], m],
      paint: { 'fill-color': c.project, 'fill-opacity': OPACITY.impactFill } },
    { id: `propedia-impact${m}-line`, type: 'line', source: 'propedia-impact', filter: ['==', ['get', 'buffer_m'], m],
      paint: linePaint(c.project, SHAPE.impact) },
  ]
  return [
    ...impact(500),
    ...impact(250),
    { id: 'propedia-regulation-fill', type: 'fill', source: 'propedia-regulation',
      paint: { 'fill-pattern': HATCH_ID, 'fill-opacity': 1 } },
    { id: 'propedia-regulation-line', type: 'line', source: 'propedia-regulation',
      paint: { 'line-color': c.regulationLine, 'line-width': WIDTH.regulation, 'line-opacity': 1 } },
    { id: 'propedia-project-fill', type: 'fill', source: 'propedia-project',
      paint: { 'fill-color': c.project, 'fill-opacity': OPACITY.projectFill } },
    { id: 'propedia-project-line', type: 'line', source: 'propedia-project',
      paint: { 'line-color': c.project, 'line-width': WIDTH.project, 'line-opacity': 1 } },
    // 필지는 외곽선만 보인다. 호버·클릭을 잡기 위한 투명 면을 따로 둔다
    { id: 'propedia-parcel-hit', type: 'fill', source: 'propedia-parcel', minzoom: PARCEL_MIN_ZOOM,
      paint: { 'fill-color': c.project, 'fill-opacity': 0 } },
    { id: 'propedia-parcel-fill', type: 'fill', source: 'propedia-parcel', minzoom: PARCEL_MIN_ZOOM,
      filter: confirmedFilter(true) as never,
      paint: { 'fill-color': c.project, 'fill-opacity': SHAPE.parcelConfirmed.fillOpacity } },
    { id: 'propedia-parcel-line', type: 'line', source: 'propedia-parcel', minzoom: PARCEL_MIN_ZOOM,
      filter: confirmedFilter(true) as never, paint: linePaint(c.project, SHAPE.parcelConfirmed) },
    { id: 'propedia-parcel-line-uncertain', type: 'line', source: 'propedia-parcel', minzoom: PARCEL_MIN_ZOOM,
      filter: confirmedFilter(false) as never, paint: linePaint(c.project, SHAPE.parcelUncertain) },
    // 검색으로 찾은 필지 (pnu)
    { id: 'propedia-parcel-search', type: 'line', source: 'propedia-parcel', filter: idFilter('pnu', null) as never,
      paint: { 'line-color': h.search, 'line-width': 4 } },
    // 선택 강조 (브랜드 색 외곽선)
    ...(['project', 'regulation', 'parcel'] as const).map(
      (k): LayerSpecification => ({
        id: `propedia-${k}-selected`, type: 'line', source: `propedia-${k}`, filter: idFilter('id', null) as never,
        paint: { 'line-color': h.selected, 'line-width': 4, 'line-blur': 0.5 },
      }),
    ),
  ]
}

/** 레이어 id → 소스 (점검·조회용) */
export const PROPEDIA_SOURCES: Record<LayerKind, string> = {
  project: 'propedia-project',
  impact: 'propedia-impact',
  parcel: 'propedia-parcel',
  regulation: 'propedia-regulation',
}

/** 좌측 패널 레이어 id → 지도 레이어와 투명도 페인트 (기준 값) */
type PaintSlot = {
  layer: string
  prop: 'fill-opacity' | 'line-opacity' | 'raster-opacity' | 'icon-opacity' | 'circle-opacity' | 'circle-stroke-opacity'
  base: number
  /** 겹침 보기에서 흐리지 않음 (클러스터 원: 개수 묶음에는 영향권 속성이 없다) */
  noOverlap?: boolean
}
export const PANEL_LAYERS: Record<PanelLayerId, { layers: string[]; paint: PaintSlot[] }> = {
  projects: {
    layers: ['propedia-project-fill', 'propedia-project-line', 'propedia-project-selected'],
    paint: [
      { layer: 'propedia-project-fill', prop: 'fill-opacity', base: OPACITY.projectFill },
      { layer: 'propedia-project-line', prop: 'line-opacity', base: 1 },
    ],
  },
  impact250: {
    layers: ['propedia-impact250-fill', 'propedia-impact250-line'],
    paint: [
      { layer: 'propedia-impact250-fill', prop: 'fill-opacity', base: OPACITY.impactFill },
      { layer: 'propedia-impact250-line', prop: 'line-opacity', base: SHAPE.impact.lineOpacity },
    ],
  },
  impact500: {
    layers: ['propedia-impact500-fill', 'propedia-impact500-line'],
    paint: [
      { layer: 'propedia-impact500-fill', prop: 'fill-opacity', base: OPACITY.impactFill },
      { layer: 'propedia-impact500-line', prop: 'line-opacity', base: SHAPE.impact.lineOpacity },
    ],
  },
  parcels: {
    layers: ['propedia-parcel-hit', 'propedia-parcel-fill', 'propedia-parcel-line', 'propedia-parcel-line-uncertain', 'propedia-parcel-selected'],
    paint: [
      { layer: 'propedia-parcel-fill', prop: 'fill-opacity', base: SHAPE.parcelConfirmed.fillOpacity },
      { layer: 'propedia-parcel-line', prop: 'line-opacity', base: 1 },
      { layer: 'propedia-parcel-line-uncertain', prop: 'line-opacity', base: 1 },
    ],
  },
  regulations: {
    layers: ['propedia-regulation-fill', 'propedia-regulation-line', 'propedia-regulation-selected'],
    paint: [
      { layer: 'propedia-regulation-fill', prop: 'fill-opacity', base: 1 },
      { layer: 'propedia-regulation-line', prop: 'line-opacity', base: 1 },
    ],
  },
  // P15 공식 참고 (map/reference.ts의 스타일과 같은 기준 값)
  'ref-seoulplan': refGeoPanel('ref-seoulplan'),
  'ref-uije': refGeoPanel('ref-uije'),
  'ref-zoning': refWmsPanel('ref-zoning'),
  'ref-district': refWmsPanel('ref-district'),
  'ref-cadastral': refWmsPanel('ref-cadastral'),
  // P17 아파트 단지 (map/layers.ts apartmentLayers)
  apartments: {
    layers: ['apartments-fill', 'apartments-line', 'apartments-selected'],
    paint: [
      { layer: 'apartments-fill', prop: 'fill-opacity', base: APARTMENT_OPACITY.fill },
      { layer: 'apartments-line', prop: 'line-opacity', base: APARTMENT_OPACITY.line },
    ],
  },
  // P18 생활 인프라 (infra/layers.ts). 칩 투명도 = icon-opacity, 클러스터 원은 겹침 보기에서 흐리지 않음
  schools: {
    layers: ['schools-cluster', 'schools-icon', 'schools-selected'],
    paint: [
      { layer: 'schools-icon', prop: 'icon-opacity', base: 1 },
      { layer: 'schools-cluster', prop: 'circle-opacity', base: 0.95, noOverlap: true },
      { layer: 'schools-cluster', prop: 'circle-stroke-opacity', base: 1, noOverlap: true },
    ],
  },
  stations: { layers: ['stations-icon', 'stations-selected'], paint: [{ layer: 'stations-icon', prop: 'icon-opacity', base: 1 }] },
  bus_stops: {
    layers: ['bus-icon', 'bus-route', 'bus-selected'],
    paint: [
      { layer: 'bus-icon', prop: 'icon-opacity', base: 1 },
      { layer: 'bus-route', prop: 'icon-opacity', base: 1, noOverlap: true },
    ],
  },
  // P19-1 편의시설: 분류마다 레이어 3개. 켜고 끄기는 분류별(MapView applyState), 투명도·겹침 보기는 여기서 한꺼번에
  pois: {
    layers: POI_KEYS.flatMap((k) => [poiClusterLayer(k), poiIconLayer(k), poiSelectedLayer(k)]),
    paint: POI_KEYS.flatMap((k) => [
      { layer: poiIconLayer(k), prop: 'icon-opacity', base: 1 },
      { layer: poiClusterLayer(k), prop: 'circle-opacity', base: 0.95, noOverlap: true },
      { layer: poiClusterLayer(k), prop: 'circle-stroke-opacity', base: 1, noOverlap: true },
    ]),
  },
}

/**
 * 아파트 단지 (P17): 면 28% + 외곽선 1px (--color-layer-apartment). 라벨은 줌 15 이상 HTML 마커.
 * 소스 id = 'apartments' (켤 때·고를 때·검색할 때만 불러온다). 사업·규제·필지 레이어 아래에 둔다.
 */
export const APARTMENT_LABEL_MIN_ZOOM = 15
export const APARTMENT_SOURCE = 'apartments'
export function apartmentLayers(c: LayerColors, h: HighlightColors = DEFAULT_HIGHLIGHT): LayerSpecification[] {
  return [
    { id: 'apartments-fill', type: 'fill', source: APARTMENT_SOURCE,
      paint: { 'fill-color': c.apartment, 'fill-opacity': APARTMENT_OPACITY.fill } },
    { id: 'apartments-line', type: 'line', source: APARTMENT_SOURCE,
      paint: { 'line-color': c.apartment, 'line-width': 1, 'line-opacity': APARTMENT_OPACITY.line } },
    { id: 'apartments-selected', type: 'line', source: APARTMENT_SOURCE, filter: idFilter('id', null) as never,
      paint: { 'line-color': h.selected, 'line-width': 3.5, 'line-blur': 0.5 } },
  ]
}

function refGeoPanel(id: 'ref-seoulplan' | 'ref-uije'): { layers: string[]; paint: PaintSlot[] } {
  return { layers: [`${id}-fill`, `${id}-line`], paint: [
    { layer: `${id}-fill`, prop: 'fill-opacity', base: REF_OPACITY.fill },
    { layer: `${id}-line`, prop: 'line-opacity', base: REF_OPACITY.line },
  ] }
}
function refWmsPanel(id: 'ref-zoning' | 'ref-district' | 'ref-cadastral'): { layers: string[]; paint: PaintSlot[] } {
  return { layers: [`${id}-raster`], paint: [{ layer: `${id}-raster`, prop: 'raster-opacity', base: REF_OPACITY.raster }] }
}

/**
 * 겹침 보기 대상 (설정 하나). 도형 속성 impact_buffer_m(빌드 때 계산한 within_impact)이 null이면 흐리게.
 * P17 아파트·P18 생활 인프라도 같은 속성을 빌드에 넣고 여기에 id만 더한다.
 */
export const OVERLAP_TARGETS: PanelLayerId[] = ['parcels', 'regulations', 'apartments', 'schools', 'stations', 'bus_stops', 'pois']

const r3 = (v: number) => Math.round(v * 1000) / 1000

// ---- P19 '그날 기준' (core/map.state_at 결과를 식으로만 건다 — 소스·레이어를 다시 만들지 않는다)
/** 효력 중이 아닌(효력 전·종료) 규제 구역 투명도 배율 */
export const REG_DIM = 0.25

/** 그날 숨기는 사업에 딸린 레이어와 그 사업을 가리키는 속성 (사업 도형은 id 'project:1', 나머지는 project_id 1) */
export const DATE_FILTER_LAYERS: Record<string, 'id' | 'project_id'> = {
  'propedia-project-fill': 'id', 'propedia-project-line': 'id', 'propedia-project-selected': 'id',
  'propedia-impact250-fill': 'project_id', 'propedia-impact250-line': 'project_id',
  'propedia-impact500-fill': 'project_id', 'propedia-impact500-line': 'project_id',
  'propedia-parcel-hit': 'project_id', 'propedia-parcel-fill': 'project_id', 'propedia-parcel-line': 'project_id',
  'propedia-parcel-line-uncertain': 'project_id',
  'propedia-parcel-search': 'project_id', 'propedia-parcel-selected': 'project_id',
}

/** 숨긴 사업 번호 → 그 레이어에 걸 '숨긴 사업이 아님' 식 (없으면 null) */
export function hiddenProjectFilter(prop: 'id' | 'project_id', hidden: number[]): unknown[] | null {
  if (!hidden.length) return null
  const values = prop === 'id' ? hidden.map((n) => `project:${n}`) : hidden
  return ['!', ['in', ['get', prop], ['literal', values]]]
}

/** 기존 필터(버퍼·판정·선택)와 날짜 필터를 함께 건다 */
export function combineFilter(base: unknown[] | undefined | null, extra: unknown[] | null): unknown[] | undefined {
  if (!extra) return base ?? undefined
  return base ? ['all', base, extra] : extra
}

/** 투명도 페인트 값: 겹침 보기면 영향권 밖(impact_buffer_m == null)만 OVERLAP_DIM 배 */
export function opacityExpr(base: number, overlap: boolean): number | unknown[] {
  const v = r3(base)
  if (!overlap) return v
  return ['case', ['==', ['get', 'impact_buffer_m'], null], r3(v * OVERLAP_DIM), v]
}

/** 패널 상태 → 지도에 걸 페인트 목록 (순수 함수) */
/** 패널 상태 → 지도에 걸 페인트 목록 (순수 함수).
 *  P19: regDim = 그날 효력 중이 아닌 규제 도형 id — 규제 레이어에서 그 도형만 REG_DIM 배 */
export function paintPlan(
  id: PanelLayerId, opacityPct: number, overlap: boolean, regDim: string[] = [],
): [string, string, number | unknown[]][] {
  const k = Math.max(0, Math.min(100, opacityPct)) / 100
  const on = overlap && OVERLAP_TARGETS.includes(id)
  return PANEL_LAYERS[id].paint.map((p) => {
    const v = opacityExpr(p.base * k, on && !p.noOverlap)
    if (id !== 'regulations' || !regDim.length) return [p.layer, p.prop, v]
    return [p.layer, p.prop, ['case', ['in', ['get', 'id'], ['literal', regDim]], opacityExpr(p.base * k * REG_DIM, on && !p.noOverlap), v]]
  })
}

/** 규제 라벨 (P19): 효력 중이 아니면 '· 효력 전'·'· 종료'를 붙인다 */
export function regulationLabel(text: string, statusLabel: string | null | undefined, inForce: boolean): string {
  return inForce || !statusLabel ? text : `${text} · ${statusLabel}`
}

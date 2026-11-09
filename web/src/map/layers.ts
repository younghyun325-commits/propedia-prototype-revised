/**
 * Propedia 검증 레이어 (docs/map/PLAN.md P13, '지도 레이어 모양'). 순수 함수 — Vitest로 검사한다.
 *
 * - 사업 구역: 면 32% + 외곽선 2px (--color-layer-project)
 * - 영향권 250m·500m: 면 8% + 점선 1.5px (같은 색, '표시 기준' — 영향의 크기가 아님)
 * - 규제 구역: 45° 빗금 + 외곽선 #B07A00 (--color-layer-regulation). 앰버는 흰 바탕 대비가 낮아 빗금·진한 외곽선을 같이 쓴다
 * - 포함 판정 필지: 외곽선만. 포함·포함될 수 있음은 실선, 포함된 것으로 보임(likely)은 점선
 * 라벨은 HTML 마커로 그린다 (스타일에 글꼴(glyphs)이 없고 외부 CDN을 쓰지 않는다). 사람 확인 전(verified=0)이면 '확인 전'을 붙인다.
 */
import type { FeatureCollection, Geometry } from 'geojson'
import type { LayerSpecification } from 'maplibre-gl'

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
}
export type PropediaFC = FeatureCollection<Geometry, PropediaProps>

export const LAYER_FILES: Record<LayerKind, string> = {
  project: '/data/layers/propedia_projects.geojson',
  impact: '/data/layers/propedia_impact.geojson',
  parcel: '/data/layers/propedia_parcels.geojson',
  regulation: '/data/layers/propedia_regulations.geojson',
}

export type LayerColors = { project: string; regulation: string; regulationLine: string }

/** tokens.css 값과 같게 둔 기본값 (CSS 변수를 못 읽을 때) */
export const DEFAULT_COLORS: LayerColors = { project: '#5d34a9', regulation: '#eda100', regulationLine: '#b07a00' }

export const OPACITY = { projectFill: 0.32, impactFill: 0.08 } as const
export const WIDTH = { project: 2, impact: 1.5, regulation: 2, parcel: 1.25 } as const
export const HATCH_ID = 'propedia-hatch'
export const UNVERIFIED = '확인 전'

/** MapLibre 페인트는 CSS 변수를 못 읽으므로 tokens.css의 --color-layer-* 값을 읽어 넘긴다 */
export function readLayerColors(root?: { getPropertyValue(name: string): string }): LayerColors {
  const css = root ?? (typeof document !== 'undefined' ? getComputedStyle(document.documentElement) : undefined)
  const get = (name: string, fallback: string) => css?.getPropertyValue(name).trim() || fallback
  return {
    project: get('--color-layer-project', DEFAULT_COLORS.project),
    regulation: get('--color-layer-regulation', DEFAULT_COLORS.regulation),
    regulationLine: DEFAULT_COLORS.regulationLine,
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

function dot(iso: string): string {
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

/** 스타일에 넣을 레이어 (아래에서 위 순서: 영향권 → 규제 → 사업 → 필지) */
export function propediaLayers(c: LayerColors): LayerSpecification[] {
  return [
    { id: 'propedia-impact-fill', type: 'fill', source: 'propedia-impact',
      paint: { 'fill-color': c.project, 'fill-opacity': OPACITY.impactFill } },
    { id: 'propedia-impact-line', type: 'line', source: 'propedia-impact',
      paint: { 'line-color': c.project, 'line-width': WIDTH.impact, 'line-dasharray': [3, 2], 'line-opacity': 0.8 } },
    { id: 'propedia-regulation-fill', type: 'fill', source: 'propedia-regulation',
      paint: { 'fill-pattern': HATCH_ID } },
    { id: 'propedia-regulation-line', type: 'line', source: 'propedia-regulation',
      paint: { 'line-color': c.regulationLine, 'line-width': WIDTH.regulation } },
    { id: 'propedia-project-fill', type: 'fill', source: 'propedia-project',
      paint: { 'fill-color': c.project, 'fill-opacity': OPACITY.projectFill } },
    { id: 'propedia-project-line', type: 'line', source: 'propedia-project',
      paint: { 'line-color': c.project, 'line-width': WIDTH.project } },
    { id: 'propedia-parcel-line', type: 'line', source: 'propedia-parcel', minzoom: 14,
      filter: ['!=', ['get', 'inclusion'], 'likely'],
      paint: { 'line-color': c.project, 'line-width': WIDTH.parcel } },
    { id: 'propedia-parcel-line-likely', type: 'line', source: 'propedia-parcel', minzoom: 14,
      filter: ['==', ['get', 'inclusion'], 'likely'],
      paint: { 'line-color': c.project, 'line-width': WIDTH.parcel, 'line-dasharray': [2, 1.5] } },
  ]
}

/** 레이어 id → 소스 (점검·조회용) */
export const PROPEDIA_SOURCES: Record<LayerKind, string> = {
  project: 'propedia-project',
  impact: 'propedia-impact',
  parcel: 'propedia-parcel',
  regulation: 'propedia-regulation',
}

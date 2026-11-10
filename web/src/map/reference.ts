/**
 * 공식 참고 레이어 (docs/map/PLAN.md P15). 참고 레이어는 클릭 대상이 아니다.
 *
 * 1) 빌드 GeoJSON 2종 (pipeline/import_reference.py, 공공누리 4유형 — 도형 가공 없음):
 *    서울시 도시계획사업 현황(서울플랜+) · 의제처리구역. 행을 처음 켤 때만 불러온다(켤 때 불러오기).
 *    모양: 회색 점선 외곽선 + 면 8%. 종류별 색은 쓰지 않는다 (Propedia 레이어와 헷갈리지 않게).
 *    라벨: 줌 15 이상에서 DGM_NM + '참고'.
 * 2) 브이월드 WMS 3종 — 이름은 GetCapabilities로 확인 (pipeline/check_wms.py, 2026-11-10).
 *    GetLegendGraphic·LegendURL이 없어 범례는 표시하지 않는다.
 *    브이월드 WMS는 CORS 헤더를 보내지 않아(WMTS는 보냄) 브라우저가 타일을 직접 받을 수 없다 →
 *    우리 API 프록시 /api/v1/map/wms/{layer}/{z}/{x}/{y}.png (서버 키, 저장 없음)로 받는다. 브라우저에 키가 드러나지 않는다.
 *    연속지적도는 0.6m/px보다 거친 요청에 빈 그림을 줘서 줌 17부터 표시한다 (서버가 512px로 받아 줌 17 타일에 씀).
 */
import type { LayerSpecification } from 'maplibre-gl'
import type { PanelLayerId } from '../state/url'

export type RefGeoId = 'ref-seoulplan' | 'ref-uije'
export type RefWmsId = 'ref-zoning' | 'ref-district' | 'ref-cadastral'

export const REF_GEOJSON: Record<RefGeoId, { file: string; attribution: string }> = {
  'ref-seoulplan': {
    file: '/data/layers/ref_seoulplan.geojson',
    attribution: '서울시 도시계획사업 현황: 서울 열린데이터광장 (공공누리 4유형)',
  },
  'ref-uije': {
    file: '/data/layers/ref_uije.geojson',
    attribution: '의제처리구역: 서울특별시·공공데이터포털 (공공누리 4유형)',
  },
}
export const REF_GEO_IDS = Object.keys(REF_GEOJSON) as RefGeoId[]

/** Capabilities 확인 결과: 이름 | 제목 | 스타일 (2026-11-10) */
export const WMS: Record<RefWmsId, { layer: string; title: string; minZoom: number }> = {
  'ref-zoning': { layer: 'lt_c_uq111', title: '도시지역', minZoom: 14 }, // 강남구는 모두 도시지역
  'ref-district': { layer: 'lt_c_upisuq161', title: '지구단위계획', minZoom: 14 },
  'ref-cadastral': { layer: 'lp_pa_cbnd_bubun', title: '연속지적도', minZoom: 17 },
}
export const REF_WMS_IDS = Object.keys(WMS) as RefWmsId[]
export const WMS_ATTRIBUTION = '참고 WMS: 국토교통부 브이월드'
export const REF_LABEL_MIN_ZOOM = 15

export const isRefGeo = (id: string): id is RefGeoId => id in REF_GEOJSON
export const isRefWms = (id: string): id is RefWmsId => id in WMS

/** 타일 주소 (MapLibre가 {z}/{x}/{y}를 채움). 화면과 같은 출처의 API 프록시 — 절대 주소로 만든다 */
export function wmsTileUrl(layer: string, origin: string = typeof window !== 'undefined' ? window.location.origin : ''): string {
  return `${origin}/api/v1/map/wms/${layer}/{z}/{x}/{y}.png`
}

export const REF_OPACITY = { fill: 0.08, line: 0.9, raster: 0.75 } as const

/** GeoJSON 참고 레이어 스타일 (소스 id = 패널 id) */
export function refGeoLayers(id: RefGeoId, color: string): LayerSpecification[] {
  return [
    { id: `${id}-fill`, type: 'fill', source: id, paint: { 'fill-color': color, 'fill-opacity': REF_OPACITY.fill } },
    { id: `${id}-line`, type: 'line', source: id,
      paint: { 'line-color': color, 'line-width': 1.25, 'line-dasharray': [2, 2], 'line-opacity': REF_OPACITY.line } },
  ]
}

export function refWmsLayer(id: RefWmsId): LayerSpecification {
  return { id: `${id}-raster`, type: 'raster', source: id, minzoom: WMS[id].minZoom,
    paint: { 'raster-opacity': REF_OPACITY.raster } }
}

/** 켜진 참고 레이어의 출처 (우하단 출처 줄에 이어 붙임) */
export function refAttributions(visible: (id: PanelLayerId) => boolean): string[] {
  const out: string[] = REF_GEO_IDS.filter(visible).map((id) => REF_GEOJSON[id].attribution)
  if (REF_WMS_IDS.some(visible)) out.push(WMS_ATTRIBUTION)
  return out
}

/** 줌 조건 때문에 안 보이면 안내 (null이면 보임) */
export function zoomBlocked(id: string, zoom: number | null): number | null {
  if (!isRefWms(id) || zoom === null) return null
  return zoom < WMS[id].minZoom ? WMS[id].minZoom : null
}

/**
 * 브이월드 WMTS 배경지도. 레이어 이름·형식은 WMTSCapabilities.xml 응답으로 확인했다 (2026-11-09, P12).
 * Capabilities의 레이어: Base(png) · midnight(png) · Hybrid(png, 투명 겹침) · Satellite(jpeg) · white(png) 외 해외 도시.
 * 'gray'라는 레이어는 없다(요청 시 오류 XML). 회색 배경은 무채색 지도인 'white'를 쓴다 (평균 RGB 226·227·225).
 * TileMatrixSet GoogleMapsCompatible, TileMatrix 6~18 → 소스 maxzoom 18, 그 위는 확대 표시.
 * 키는 실행 중에 /api/v1/map/config에서 받는다 (P20, 빌드·소스·로그에 값을 남기지 않음).
 */
export type BasemapId = 'base' | 'gray' | 'satellite' | 'hybrid'

type Layer = { name: string; ext: 'png' | 'jpeg' }

/** 래스터 페인트 (MapLibre raster 레이어 paint). 회색 배경에만 쓴다. */
export type RasterPaint = {
  'raster-saturation'?: number
  'raster-brightness-min'?: number
  'raster-brightness-max'?: number
}

/**
 * 'white' 레이어는 무채색에 가깝지만 녹지·물에 옅은 색이 남는다 → 채도를 -1로 빼서 완전한 회색으로 만든다 (P13).
 * 채도를 빼면 살짝 어두워 보여 밝기 하한을 조금 올린다.
 */
export const GRAY_PAINT: RasterPaint = {
  'raster-saturation': -1,
  'raster-brightness-min': 0.2, // P13: 0.08 → 0.2 — 진한 도로·녹지가 보라색 사업 구역·점선과 겹쳐 보여 어두운 쪽을 올림
  'raster-brightness-max': 1,
}

export const BASEMAPS: Record<BasemapId, { label: string; layers: Layer[]; paint?: RasterPaint }> = {
  base: { label: '기본', layers: [{ name: 'Base', ext: 'png' }] },
  gray: { label: '회색', layers: [{ name: 'white', ext: 'png' }], paint: GRAY_PAINT },
  satellite: { label: '위성', layers: [{ name: 'Satellite', ext: 'jpeg' }] },
  hybrid: {
    label: '하이브리드',
    layers: [
      { name: 'Satellite', ext: 'jpeg' },
      { name: 'Hybrid', ext: 'png' },
    ],
  },
}

export const BASEMAP_ORDER: BasemapId[] = ['base', 'gray', 'satellite', 'hybrid']
export const DEFAULT_BASEMAP: BasemapId = 'gray'
export const TILE_MIN_ZOOM = 6
export const TILE_MAX_ZOOM = 18
export const ATTRIBUTION = '배경지도: 국토교통부 브이월드'

export function tileUrl(key: string, layer: Layer): string {
  return `https://api.vworld.kr/req/wmts/1.0.0/${key}/${layer.name}/{z}/{y}/{x}.${layer.ext}`
}

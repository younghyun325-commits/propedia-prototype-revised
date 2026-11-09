/**
 * 브이월드 WMTS 배경지도. 레이어 이름·형식은 WMTSCapabilities.xml 응답으로 확인했다 (2026-11-09, P12).
 * Capabilities의 레이어: Base(png) · midnight(png) · Hybrid(png, 투명 겹침) · Satellite(jpeg) · white(png) 외 해외 도시.
 * 'gray'라는 레이어는 없다(요청 시 오류 XML). 회색 배경은 무채색 지도인 'white'를 쓴다 (평균 RGB 226·227·225).
 * TileMatrixSet GoogleMapsCompatible, TileMatrix 6~18 → 소스 maxzoom 18, 그 위는 확대 표시.
 * 키는 import.meta.env.VITE_VWORLD_KEY로만 읽는다 (소스·로그에 값을 남기지 않음).
 */
export type BasemapId = 'base' | 'gray' | 'satellite' | 'hybrid'

type Layer = { name: string; ext: 'png' | 'jpeg' }

export const BASEMAPS: Record<BasemapId, { label: string; layers: Layer[] }> = {
  base: { label: '기본', layers: [{ name: 'Base', ext: 'png' }] },
  gray: { label: '회색', layers: [{ name: 'white', ext: 'png' }] },
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

/**
 * 지도 클릭 필지 조회 (docs/map/PLAN.md P15). 응답은 화면 메모리에만 두고 저장하지 않는다.
 * 빠르게 여러 번 누르면 이전 요청을 취소한다 (LatestRequest, AbortController).
 */
import type { Geometry } from 'geojson'
import { getJson } from './map'

export type ParcelStatus = 'ok' | 'outside' | 'not_found' | 'unavailable' | 'timeout'
export type RefZone = {
  layer: string
  layer_title: string | null
  name: string | null
  kind_code: string | null
  source: string | null
  license: string | null
  as_of: string | null
  badge: string
}
export type ParcelProject = { project_id: number; name: string; inclusion: string; inclusion_label: string;
  distance_m?: number; message?: string }
export type ParcelAt = {
  status: ParcelStatus
  message: string | null
  pnu: string | null
  jibun_address: string | null
  boundary: Geometry | null
  centroid: { lat: number; lon: number; source: string } | null
  as_of: string | null
  land: {
    status: string
    jimok: string | null
    area_m2: number | null
    land_use_zone: string | null
    land_use_zone2: string | null
    zones: { name: string; relation: string | null }[] | null
    official_price: { won_per_m2: number | null; year: number | null; announced_on: string | null } | null
    source: string | null
    note: string | null
  } | null
  building: { main_purpose?: string; bld_names?: string[] } | null
  building_note: string | null
  layer_counts: { city: number; gu: number; dong: number; parcel: number } | null
  dong_projects: { project_id: number; name: string }[]
  included_projects: ParcelProject[]
  nearby_projects: ParcelProject[]
  nearby_note: string | null
  ref_zones: RefZone[]
  disclaimer: string
}

export const parcelAtUrl = (lat: number, lon: number) =>
  `/api/v1/map/parcel-at?lat=${lat.toFixed(6)}&lon=${lon.toFixed(6)}`
export const parcelByPnuUrl = (pnu: string) => `/api/v1/map/parcel?pnu=${encodeURIComponent(pnu)}`

export const getParcelAt = (lat: number, lon: number, signal?: AbortSignal) =>
  getJson<ParcelAt>(parcelAtUrl(lat, lon), signal)
export const getParcelByPnu = (pnu: string, signal?: AbortSignal) => getJson<ParcelAt>(parcelByPnuUrl(pnu), signal)

/** 마지막 요청만 살린다: run()을 새로 부르면 이전 요청은 abort, 이전 결과는 버린다(undefined). */
export class LatestRequest {
  private ctrl: AbortController | null = null
  private seq = 0

  async run<T>(fn: (signal: AbortSignal) => Promise<T>): Promise<{ ok: true; value: T } | { ok: false; error: Error } | undefined> {
    this.ctrl?.abort()
    const ctrl = new AbortController()
    this.ctrl = ctrl
    const my = ++this.seq
    try {
      const value = await fn(ctrl.signal)
      return my === this.seq ? { ok: true, value } : undefined
    } catch (e) {
      if (ctrl.signal.aborted || my !== this.seq) return undefined
      return { ok: false, error: e as Error }
    }
  }

  cancel(): void {
    this.ctrl?.abort()
    this.ctrl = null
    this.seq++
  }
}

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
  distance_m?: number; message?: string; review_id?: number | null; basis_label?: string; distance_basis?: string;
  stage?: { code: string; title: string | null; seq: number | null } }
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
    fetched_at?: string | null
  } | null
  building: {
    found?: boolean
    main_purpose?: string | null
    bld_names?: string[]
    main_count?: number | null
    structure?: string | null
    use_apr_day?: string | null
    max_grnd_flr?: number | null
    total_hhld?: number | null
    total_area?: number | null
    source?: string | null
    fetched_label?: string | null
  } | null
  building_note: string | null
  layer_counts: { city: number; gu: number; dong: number; parcel: number } | null
  dong_projects: { project_id: number; name: string }[]
  included_projects: ParcelProject[]
  nearby_projects: ParcelProject[]
  nearby_note: string | null
  ref_zones: RefZone[]
  /** P16: 이 필지가 사업 필지면 맨 위 한 줄 (포함 판정·검수 번호) */
  project_banner: {
    project_id: number
    short_name: string
    inclusion: string
    inclusion_label: string
    verified: boolean
    review_id: number | null
    basis_label: string
    source: LayerItemSource | null
  }[]
  /** P16: 층별 항목 (펼치기) */
  layer_items: Record<'city' | 'gu' | 'dong' | 'parcel', LayerItem[]> | null
  /** P16: 원문 모달용 근거 목록 */
  evidence: import('./feature').EvidenceItem[]
  disclaimer: string
}
export type LayerItemSource = {
  doc_id: string
  short_title: string
  published_at: string | null
  pdf_page: number | null
  page_label: string | null
  page_image: string | null
}
export type LayerItem = {
  item_key: string
  title: string
  summary: string | null
  scope_label: string | null
  effective_label: string | null
  effective_status_label: string | null
  evidence: string | null
  source: LayerItemSource | null
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

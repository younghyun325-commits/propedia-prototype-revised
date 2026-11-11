/** 지도용 API (P14). 화면은 값을 새로 계산하지 않고 받은 문구·건수를 그대로 쓴다. */
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useMapStore } from '../state/useMapStore'

export type LayerStatus = 'ready' | 'pending' | 'not_adopted'
export type ManifestLayer = {
  id: string
  group: string
  name: string
  kind: 'fill' | 'line' | 'symbol' | 'raster'
  source: string | null
  license: string | null
  as_of: string | null
  count: number | null
  status: LayerStatus
  note: string | null
  available_from: string | null
  unverified: boolean
  doc_ids: string[]
  source_pages: string[]
  badge?: string
  count_by_judgment?: { included: number; possible: number; likely: number }
  unverified_count?: number
  // P15 공식 참고
  lazy?: boolean
  min_zoom?: number
  wms_layer?: string
  file?: string | null
  size_bytes?: number | null
  disclaimer?: string | null
  ref?: boolean
  // P17 아파트 단지
  points_file?: string | null
  fill_min_zoom?: number | null
  boundary_note?: string | null
}
export type Ratio = { num: number; den: number }
export type MarketStatus =
  | { available: false; layer_count: number | null }
  | {
      available: true
      trade_from: string | null
      trade_to: string | null
      trade_count: number
      cancelled_count: number
      fetched_on: string | null
      m22: Ratio | null
      m23: Ratio | null
      basis_linked: number
      list_total: number | null
      basis_check: string | null
      layer_count: number | null
    }
export type Manifest = {
  generated_as_of: string | null
  db_as_of: string | null
  build_at: string | null
  /** patch_* 스크립트가 DB를 마지막으로 고친 시각 (P20). run_all로 새로 만든 DB면 null */
  patched_at?: string | null
  groups: { id: string; name: string }[]
  layers: ManifestLayer[]
  notes: string[]
  market?: MarketStatus
}

export type Source = { doc_id: string; short_title: string; pdf_page: number | null; page_image: string | null }
export type Notice = {
  doc_id: string
  item_key: string
  short_title: string
  title: string
  doc_kind: string
  kind_label: string
  effective_label: string | null
  effective_status_label: string | null
  source: Source
}
export type MapProject = {
  id: number
  feature_id: string
  /** P19: 기준일에 첫 근거 문서가 발행돼 있으면 true (false인 사업은 hidden 목록으로 따로 뺀다) */
  shown?: boolean
  shown_from?: string | null
  name: string
  short_name: string
  aliases: string[]
  project_type_label: string
  position_label: string
  stage_seq: number
  stage_total: number
  stage_title: string
  status_badge: string
  /** P16: 공람 중 / 공람 마감 / 승인 고시 미확인 (progress 값을 문구로) */
  status_badges: string[]
  stage_note: string | null
  deadline: { title: string; d_day_label: string; status: 'open' | 'closed'; due_on: string } | null
  representative_jibun: string | null
  representative_pnu: string | null
  bbox: [number, number, number, number] | null
  parcels: { included: number; possible: number; likely: number }
  parcels_unverified: number
  unverified: boolean
  hover_line: string
}
export type Health = {
  status: string
  as_of: string | null
  build_at: string | null
  patched_at?: string | null
  keys?: { vworld: string; juso: string }
  key_notes?: string[]
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const r = await fetch(path, { signal })
  if (!r.ok) {
    let detail = `HTTP ${r.status}`
    try {
      detail = (await r.json()).detail ?? detail
    } catch {
      /* 본문 없음 */
    }
    throw new Error(detail)
  }
  return r.json() as Promise<T>
}

/** 지도 설정 (P20): 배경지도(브이월드 WMTS) 키는 빌드에 넣지 않고 실행 중에 서버에서 받는다. 값을 로그에 남기지 않는다 */
export type MapConfig = { basemap: { key: string | null; configured: boolean } }

export const useMapConfig = () =>
  useQuery({
    queryKey: ['map', 'config'],
    queryFn: ({ signal }) => getJson<MapConfig>('/api/v1/map/config', signal),
    staleTime: Infinity,
    retry: 1,
  })

export const useManifest = () =>
  useQuery({ queryKey: ['map', 'manifest'], queryFn: ({ signal }) => getJson<Manifest>('/api/v1/map/manifest', signal) })
/** 그날 규제 효력 상태 (P19, core/map.state_at). 지도에서 효력 중이 아니면 흐리게 */
export type RegulationState = {
  feature_id: string
  doc_id: string
  item_key: string
  status: 'in_force' | 'not_started' | 'ended' | null
  status_label: string | null
  effective_from: string | null
  effective_to: string | null
  /** P20: 적용 범위 (SIDO·SGG·BJD·PARCEL)와 지도 도형 유무 — 도형이 없으면 법정동·구 경계로 대신 강조 */
  scope_type: 'SIDO' | 'SGG' | 'SAENGHWAL' | 'BJD' | 'PARCEL'
  scope_ref: string[]
  has_geometry: boolean
}
export type Notices = { as_of: string; items: Notice[]; regulations: RegulationState[] }
/** 숨긴 사업 (그날 첫 근거 문서가 아직 없음) */
export type HiddenProject = { id: number; feature_id: string; shown: false; shown_from: string | null }
export type MapProjects = { as_of: string; projects: MapProject[]; hidden: HiddenProject[] }

/** 기준일(store.asOf, null = 오늘) → 쿼리 문자열 */
export const asOfQuery = (asOf: string | null, sep: '?' | '&' = '?') => (asOf ? `${sep}as_of=${asOf}` : '')
export const useAsOf = () => useMapStore((s) => s.asOf)

/** 상단 칩 + 규제 효력 상태 (P19: 기준일마다 다시 받는다, 받는 동안 이전 값 유지) */
export const useNotices = () => {
  const asOf = useAsOf()
  return useQuery({
    queryKey: ['map', 'notices', asOf],
    queryFn: ({ signal }) => getJson<Notices>(`/api/v1/map/notices${asOfQuery(asOf)}`, signal),
    placeholderData: keepPreviousData,
  })
}
/** 사업 목록. 그날 보이지 않는 사업은 projects에서 빼고 hidden에 둔다 (P19) */
export const useMapProjects = () => {
  const asOf = useAsOf()
  return useQuery({
    queryKey: ['map', 'projects', asOf],
    queryFn: ({ signal }) =>
      getJson<{ as_of: string; projects: (MapProject | HiddenProject)[] }>(`/api/v1/map/projects${asOfQuery(asOf)}`, signal),
    select: (d): MapProjects => ({
      as_of: d.as_of,
      projects: d.projects.filter((p): p is MapProject => p.shown !== false),
      hidden: d.projects.filter((p): p is HiddenProject => p.shown === false),
    }),
    placeholderData: keepPreviousData,
  })
}

// ---- 타임라인·고시 피드 (P19) ----
export type TlSource = { doc_id: string; short_title: string; pdf_page: number | null; page_label?: string | null;
  page_image: string | null; published_at?: string | null }
export type TlPoint = { id: string; date: string; title: string; sel?: string | null; doc_id?: string; doc_kind?: string;
  kind_label?: string; code?: string; project_id?: number; as_of_label?: string; source?: TlSource | null }
export type TlBar = { id: string; start: string; end: string | null; title: string; sel?: string | null; doc_id?: string | null;
  item_key?: string; project_id?: number; source?: TlSource | null }
export type LaneId = 'publish' | 'review' | 'effective' | 'stage' | 'data_as_of'
export type TimelineData = {
  from: string
  to: string
  lane_labels: Record<LaneId, string>
  lanes: { publish: TlPoint[]; review: TlBar[]; effective: TlBar[]; stage: TlPoint[]; data_as_of: TlPoint[] }
}
export const useTimeline = () =>
  useQuery({
    queryKey: ['timeline'],
    queryFn: ({ signal }) => getJson<TimelineData>('/api/v1/timeline', signal),
    staleTime: 10 * 60_000,
  })

export type FeedItem = {
  doc_id: string
  title: string
  short_title: string
  doc_kind: string
  kind_label: string
  gosi_no: string | null
  issuer: string | null
  published_at: string
  related: { kind: 'project' | 'regulation'; id: string; label: string | null; effective_label?: string | null; status?: string | null }[]
  deadline: { title: string; starts_on: string | null; due_on: string; d_day: number; d_day_label: string; status: 'open' | 'closed' } | null
  sel: string | null
  recent_30d: boolean
  source: TlSource | null
}
export const useFeed = () => {
  const asOf = useAsOf()
  return useQuery({
    queryKey: ['feed', asOf],
    queryFn: ({ signal }) =>
      getJson<{ as_of: string; total: number; items: FeedItem[] }>(`/api/v1/feed?limit=50${asOfQuery(asOf, '&')}`, signal),
    placeholderData: keepPreviousData,
  })
}
export const useHealth = () =>
  useQuery({ queryKey: ['health'], queryFn: ({ signal }) => getJson<Health>('/api/v1/health', signal) })

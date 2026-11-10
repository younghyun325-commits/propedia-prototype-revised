/** 지도용 API (P14). 화면은 값을 새로 계산하지 않고 받은 문구·건수를 그대로 쓴다. */
import { useQuery } from '@tanstack/react-query'

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
}
export type Manifest = {
  generated_as_of: string | null
  db_as_of: string | null
  build_at: string | null
  groups: { id: string; name: string }[]
  layers: ManifestLayer[]
  notes: string[]
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
  name: string
  short_name: string
  aliases: string[]
  project_type_label: string
  position_label: string
  stage_seq: number
  stage_total: number
  stage_title: string
  status_badge: string
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

export const useManifest = () =>
  useQuery({ queryKey: ['map', 'manifest'], queryFn: ({ signal }) => getJson<Manifest>('/api/v1/map/manifest', signal) })
export const useNotices = () =>
  useQuery({
    queryKey: ['map', 'notices'],
    queryFn: ({ signal }) => getJson<{ as_of: string; items: Notice[] }>('/api/v1/map/notices', signal),
  })
export const useMapProjects = () =>
  useQuery({
    queryKey: ['map', 'projects'],
    queryFn: ({ signal }) => getJson<{ as_of: string; projects: MapProject[] }>('/api/v1/map/projects', signal),
  })
export const useHealth = () =>
  useQuery({ queryKey: ['health'], queryFn: ({ signal }) => getJson<Health>('/api/v1/health', signal) })

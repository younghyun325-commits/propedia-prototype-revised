/**
 * 인스펙터 API (docs/map/PLAN.md P16): GET /api/v1/map/feature/{kind}/{id}?as_of=
 * 화면은 값을 새로 계산하지 않고 받은 문구·숫자를 그대로 보여 준다.
 */
import { useQuery } from '@tanstack/react-query'
import type { ParcelAt } from './parcel'
import { getJson, useAsOf } from './map'
import type { Apartment } from './market'

export type FeatureKind = 'project' | 'regulation' | 'parcel' | 'apartment'

export type SourceRef = {
  doc_id: string
  short_title: string
  published_at: string | null
  pdf_page: number | null
  page_label: string | null
  page_image: string | null
  source_url?: string | null
  source_note?: string | null
}

/** 원문 모달 한 장 (문서·쪽·근거 문장) */
export type EvidenceItem = {
  doc_id: string
  short_title: string
  title: string | null
  gosi_no: string | null
  published_at: string | null
  pdf_page: number | null
  page_label: string | null
  evidence: string | null
  page_image: string | null
  docs_url: string
  label: string
}

export type Badge = { text: string; tone: 'brand' | 'info' | 'warn' | 'muted' }

export type Stage = {
  seq: number
  code: string
  title: string
  status: 'done' | 'current' | 'upcoming'
  verified?: boolean
  note?: string | null
  entered_at?: string | null
  source?: SourceRef | null
  what_happens: string | null
  what_happens_note: string | null
  owner_actions: string | null
  template_status: string
}

export type Deadline = {
  kind: string
  title: string
  starts_on: string | null
  due_on: string
  d_day: number
  d_day_label: string
  status: 'open' | 'closed'
  how_to_submit: string | null
  places: string[]
  source: SourceRef | null
}

export type Fact = { label: string; value: unknown; unit: string | null; evidence: string | null; evidence_ok: boolean; source: SourceRef | null }

export type HistoryRow = { date: string | null; kind: string; label: string; gosi_no: string | null; evidence: string | null; source: SourceRef | null }

export type Boundary = { bbox: [number, number, number, number] | null; verified: boolean; label: string; source: SourceRef | null }

export type ProjectParcel = {
  pnu: string
  feature_id: string
  name: string
  inclusion: 'included' | 'possible' | 'likely'
  inclusion_label: string
  basis: string
  basis_label: string
  verified: boolean
  review_id: number | null
  source: SourceRef | null
  bbox: [number, number, number, number] | null
}

export type NearbyApartment = { id: string; name: string; build_year: number | null; last_trade_date: string | null }

export type ProjectSections = {
  /** P17: 영향권 안 단지 (250·500, 이름·준공연도·최근 거래일만) */
  nearby_apartments?: { '250': NearbyApartment[]; '500': NearbyApartment[] }
  progress: {
    project_id: number
    name: string
    project_type_label: string
    track_label: string
    position_label: string
    sub_status: string | null
    stage_note: string | null
    stages: Stage[]
    current: { code: string; title: string; what_happens: string | null; what_happens_note: string | null;
      owner_actions: string | null; owner_actions_note: string | null; issuer: string | null; template_status: string }
    next: { code: string; title: string; owner_actions: string | null; owner_actions_note: string | null } | null
    deadlines: Deadline[]
    remaining: { note: string; method_note: string }
    facts: Fact[]
    facts_note: string
    stage_basis: { rule_id: string | null; evidence: string | null; source: SourceRef | null }
  }
  stepper: { total: number; current_seq: number; remaining_stages: number; position_label: string; next_title: string | null }
  status_badges: string[]
  boundary: Boundary | null
  parcels: ProjectParcel[]
  history: HistoryRow[]
}

export type RegulationSections = {
  regulation: {
    doc_id: string
    item_key: string
    doc_kind_label: string
    gosi_no: string | null
    issuer: string | null
    published_at: string | null
    title: string
    summary: string
    scope_label: string
    target_note: string | null
    effective_from: string | null
    effective_to: string | null
    effective_label: string | null
    effective_status: 'in_force' | 'ended' | 'not_started' | null
    effective_status_label: string | null
    evidence: string
    source: SourceRef | null
  }
  boundary: Boundary | null
  boundary_note: string | null
  history: HistoryRow[]
}

export type ParcelSections = { parcel: ParcelAt & { boundary_note: string | null }; project_banner: ParcelAt['project_banner'] }

type Base<K extends FeatureKind, S> = {
  kind: K
  id: string
  kind_label: string
  title: string
  subtitle: string | null
  badges: Badge[]
  unverified: boolean
  as_of: string
  data_as_of: string | null
  bbox: [number, number, number, number] | null
  sections: S
  evidence: EvidenceItem[]
  disclaimer: string
  /** P19: 그날 첫 근거 문서가 아직 없는 사업이면 false (sections는 비어 있고 note에 안내) */
  shown?: boolean
  shown_from?: string | null
  note?: string | null
  /** 규제: 그날 고시가 발행돼 있는지·효력 상태 */
  published?: boolean
  status?: 'in_force' | 'not_started' | 'ended' | null
  status_label?: string | null
}
export type ProjectFeature = Base<'project', ProjectSections>
export type RegulationFeature = Base<'regulation', RegulationSections>
export type ParcelFeature = Base<'parcel', ParcelSections>
export type ApartmentFeature = Base<'apartment', { apartment: Apartment }>
export type Feature = ProjectFeature | RegulationFeature | ParcelFeature | ApartmentFeature

export const featureUrl = (kind: FeatureKind, id: string, asOf?: string) =>
  `/api/v1/map/feature/${kind}/${encodeURIComponent(id)}${asOf ? `?as_of=${asOf}` : ''}`

/** 인스펙터 (P19: 기준일을 쿼리 키·as_of에 넣는다. 같은 대상이면 받는 동안 이전 값 유지) */
export const useFeature = (kind: FeatureKind | null, id: string | null) => {
  const asOf = useAsOf()
  return useQuery({
    queryKey: ['map', 'feature', kind, id, asOf],
    queryFn: ({ signal }) => getJson<Feature>(featureUrl(kind!, id!, asOf ?? undefined), signal),
    enabled: !!kind && !!id,
    retry: 1,
    staleTime: 60_000,
    placeholderData: (prev, q) => (q && q.queryKey[2] === kind && q.queryKey[3] === id ? prev : undefined),
  })
}

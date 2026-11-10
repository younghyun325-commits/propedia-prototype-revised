/** 아파트 단지·실거래 API (P17). 값은 db/market.db 그대로 — 화면은 표기만 바꾼다. */
import { useQuery } from '@tanstack/react-query'
import { getJson, useAsOf } from './map'
import type { BandSummary, BasisStatus } from '../market/format'
import type { Monthly, Point } from '../market/chartScales'

export type Impact = { project_id: number; project_name: string; buffer_m: number; label: string }
export type Apartment = {
  id: string
  name: string
  aliases: string[]
  apt_seq: string | null
  pnus: string[]
  jibuns: string[]
  bjd_code: string | null
  lat: number | null
  lon: number | null
  build_year: number | null
  build_year_note: string
  basis: {
    status: BasisStatus
    label: string | null
    kapt_code: string | null
    households: number | null
    buildings: number | null
    approval_date: string | null
    road_addr: string | null
    jibun_addr: string | null
    source: string | null
  }
  trade_summary: {
    bands: BandSummary[]
    default_band: string | null
    count: number
    cancelled_count: number
    last_trade_date: string | null
    since_12m: string
    since_3y: string
    from: string | null
    to: string | null
  }
  impacts: Impact[]
  sources: { kind: 'trade' | 'basis'; label: string; date: string | null; date_label: string }[]
  as_of: string | null
  disclaimer: string
}
export type Trade = {
  contract_date: string
  exclusive_area_m2: number | null
  area_band: string | null
  floor: number | null
  amount_10k_won: number
  deal_type: string | null
  is_cancelled: number
  cancelled_date: string | null
  apt_dong: string | null
}
export type Trades = {
  id: string
  band: string | null
  from: string | null
  /** P19: 계약일 ≤ 기준일 거래만 (null = 전체) */
  as_of: string | null
  monthly: (Monthly & { partial_to?: string })[]
  points: (Point & { exclusive_area_m2: number | null; floor: number | null })[]
  recent: Trade[]
  source: string
  fetched_on: string | null
}

export function tradesUrl(id: string, band: string | null, asOf: string | null): string {
  const q = new URLSearchParams()
  if (band) q.set('band', band)
  if (asOf) q.set('as_of', asOf)
  const qs = q.toString()
  return `/api/v1/apartments/${encodeURIComponent(id)}/trades${qs ? `?${qs}` : ''}`
}

/** 인스펙터 차트 (P19: 계약일 ≤ 기준일) */
export const useApartmentTrades = (id: string, band: string | null) => {
  const asOf = useAsOf()
  return useQuery({
    queryKey: ['apartment', id, 'trades', band, asOf],
    queryFn: ({ signal }) => getJson<Trades>(tradesUrl(id, band, asOf), signal),
    enabled: !!band,
    staleTime: 5 * 60_000,
    placeholderData: (prev, q) => (q && q.queryKey[1] === id && q.queryKey[3] === band ? prev : undefined),
  })
}

/** 타임라인 거래량 줄 (P19): 면적대를 합친 월별 건수, 전체 기간 (해제 제외) */
export const useApartmentMonthly = (id: string | null) =>
  useQuery({
    queryKey: ['apartment', id, 'monthly'],
    queryFn: ({ signal }) => getJson<Trades>(tradesUrl(id!, null, null), signal),
    enabled: !!id,
    staleTime: 5 * 60_000,
  })

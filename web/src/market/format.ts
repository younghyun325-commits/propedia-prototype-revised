/**
 * 아파트 실거래 표기 (P17). 순수 함수 — Vitest (market/market.test.ts).
 * 금액은 만원 정수(국토교통부 신고 자료 dealAmount). 반올림·환산하지 않고 억·만 단위로만 끊는다.
 */
import { UI } from '../copy/ui'

/** 319000 → '31억 9,000만', 50000 → '5억', 9500 → '9,500만' */
export function formatManwon(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  const n = Math.round(v)
  const sign = n < 0 ? '-' : ''
  const a = Math.abs(n)
  const eok = Math.floor(a / 10000)
  const man = a % 10000
  const parts: string[] = []
  if (eok) parts.push(`${eok.toLocaleString('ko-KR')}억`)
  if (man || !eok) parts.push(`${man.toLocaleString('ko-KR')}만`)
  return sign + parts.join(' ')
}

/** 축 눈금용 짧은 표기: 억 단위 (예: 31.9억), 1억 미만은 만 */
export function formatAxisManwon(v: number): string {
  if (Math.abs(v) >= 10000) return `${(Math.round(v / 1000) / 10).toLocaleString('ko-KR')}억`
  return `${Math.round(v).toLocaleString('ko-KR')}만`
}

export type BandSummary = { band: string; count_12m: number; count_3y: number; count: number; last_trade_date: string | null }

/** 기본 면적대: 서버가 정한 default_band가 있으면 그대로, 없으면 최근 3년 거래가 가장 많은 면적대 (같으면 앞쪽) */
export function pickDefaultBand(bands: BandSummary[], serverDefault: string | null | undefined): string | null {
  if (serverDefault && bands.some((b) => b.band === serverDefault)) return serverDefault
  let best: BandSummary | null = null
  for (const b of bands) if (!best || b.count_3y > best.count_3y) best = b
  return best?.band ?? null
}

export type BasisStatus = 'pending' | 'linked' | 'not_in_list'

/** 기본 정보가 없을 때 문구 (이유를 단정하지 않는다) */
export function basisMissingText(status: BasisStatus): string | null {
  if (status === 'linked') return null
  return status === 'not_in_list' ? UI.apartment.basisNotInList : UI.apartment.basisPending
}

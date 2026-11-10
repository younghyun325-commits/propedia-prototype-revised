/**
 * 실거래 차트 스케일 (P17). 위 = 월별 중위 거래가 선 + 개별 거래 점, 아래 = 월별 거래 건수 막대.
 * 같은 x축(계약월), 위아래 분리 — 한 그림에 두 y축을 겹치지 않는다. 순수 함수 — Vitest.
 */
import { scaleBand, scaleLinear } from 'd3-scale'

export type Monthly = { ym: string; median_amount: number | null; count: number }
export type Point = { contract_date: string; amount_10k_won: number; is_cancelled: number }

/** 'YYYY-MM' 목록 (from ~ to, 빈 달 포함) */
export function monthRange(from: string, to: string): string[] {
  const out: string[] = []
  let [y, m] = from.split('-').map(Number)
  const [ty, tm] = to.split('-').map(Number)
  while (y < ty || (y === ty && m <= tm)) {
    out.push(`${y}-${String(m).padStart(2, '0')}`)
    m += 1
    if (m > 12) {
      m = 1
      y += 1
    }
  }
  return out
}

export type ChartScales = {
  months: string[]
  x: ReturnType<typeof scaleBand<string>>
  /** 계약일 → x 위치 (그 달 칸 안에서 날짜 비율만큼) */
  xDate: (iso: string) => number
  yPrice: ReturnType<typeof scaleLinear<number, number>>
  yCount: ReturnType<typeof scaleLinear<number, number>>
}

export function makeScales(
  monthly: Monthly[],
  points: Point[],
  opt: { width: number; priceHeight: number; countHeight: number; left: number; right: number },
): ChartScales | null {
  const yms = [...monthly.map((d) => d.ym), ...points.map((p) => p.contract_date.slice(0, 7))].sort()
  if (!yms.length) return null
  const months = monthRange(yms[0], yms[yms.length - 1])
  const x = scaleBand<string>().domain(months).range([opt.left, opt.width - opt.right]).paddingInner(0.15).paddingOuter(0.05)
  const xDate = (iso: string) => {
    const ym = iso.slice(0, 7)
    const day = Number(iso.slice(8, 10)) || 15
    return (x(ym) ?? opt.left) + (x.bandwidth() * Math.min(day, 31)) / 31
  }
  const prices = [...monthly.map((d) => d.median_amount).filter((v): v is number => v != null), ...points.map((p) => p.amount_10k_won)]
  const lo = Math.min(...prices)
  const hi = Math.max(...prices)
  const pad = Math.max((hi - lo) * 0.08, hi * 0.02, 1)
  const yPrice = scaleLinear<number, number>().domain([Math.max(0, lo - pad), hi + pad]).range([opt.priceHeight, 8]).nice(4)
  const maxCount = Math.max(1, ...monthly.map((d) => d.count))
  const yCount = scaleLinear<number, number>().domain([0, maxCount]).range([opt.countHeight, 4]).nice(3)
  return { months, x, xDate, yPrice, yCount }
}

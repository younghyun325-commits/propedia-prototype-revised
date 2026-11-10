/**
 * 실거래 차트 (P17). 따로 불러오는 청크 (ApartmentView에서 lazy) — d3-scale·d3-shape는 여기서만 쓴다.
 * 위: 월별 중위 거래가 선(해제 제외) + 개별 거래 점(해제는 빈 원) / 아래: 월별 거래 건수 막대.
 * 같은 x축(계약월), 위아래로 나눈 두 그림 — 한 그림에 두 y축을 겹치지 않는다. 값은 API 그대로.
 */
import { line } from 'd3-shape'
import type { Trades } from '../api/market'
import { UI } from '../copy/ui'
import { makeScales } from '../market/chartScales'
import { formatAxisManwon, formatManwon } from '../market/format'

const W = 340
const LEFT = 44
const RIGHT = 8
const PRICE_H = 150
const COUNT_H = 64
const AXIS_H = 16
const INK = 'var(--color-ink)'
const MUTED = 'var(--color-ink-muted)'
const COLOR = 'var(--color-layer-apartment)'

export default function AptChart({ data }: { data: Trades }) {
  const s = makeScales(data.monthly, data.points, { width: W, priceHeight: PRICE_H, countHeight: COUNT_H, left: LEFT, right: RIGHT })
  if (!s) return <p className="text-xs text-ink-muted" data-testid="apt-chart-empty">{UI.apartment.noTrades}</p>
  const bw = s.x.bandwidth()
  const cx = (ym: string) => (s.x(ym) ?? LEFT) + bw / 2
  const path = line<{ ym: string; median_amount: number | null }>()
    .defined((d) => d.median_amount != null)
    .x((d) => cx(d.ym))
    .y((d) => s.yPrice(d.median_amount as number))(data.monthly)
  // x 눈금: 1월만 (연도), 기간이 짧으면 첫 달도
  const years = s.months.filter((m, i) => m.endsWith('-01') || i === 0)
  const step = Math.ceil(years.length / 6)
  const xTicks = years.filter((_, i) => i % step === 0)
  const priceTicks = s.yPrice.ticks(4)
  const countTicks = s.yCount.ticks(2).filter(Number.isInteger)
  const xAxis = (y: number) => (
    <g aria-hidden="true">
      <line x1={LEFT} x2={W - RIGHT} y1={y} y2={y} stroke={MUTED} strokeOpacity={0.4} />
      {xTicks.map((m) => (
        <text key={m} x={s.x(m) ?? LEFT} y={y + 12} fontSize={9} fill={MUTED}>{m.endsWith('-01') ? m.slice(0, 4) : m.replace('-', '.')}</text>
      ))}
    </g>
  )
  return (
    <div className="space-y-1" data-testid="apt-chart">
      <figure className="space-y-0.5">
        <figcaption className="text-[11px] font-semibold text-ink-muted">{UI.apartment.priceChart}</figcaption>
        <svg viewBox={`0 0 ${W} ${PRICE_H + AXIS_H}`} width="100%" role="img" aria-label={UI.apartment.priceChart} data-testid="price-chart">
          <g aria-hidden="true">
            {priceTicks.map((t) => (
              <g key={t}>
                <line x1={LEFT} x2={W - RIGHT} y1={s.yPrice(t)} y2={s.yPrice(t)} stroke={MUTED} strokeOpacity={0.15} />
                <text x={LEFT - 4} y={s.yPrice(t) + 3} fontSize={9} textAnchor="end" fill={MUTED}>{formatAxisManwon(t)}</text>
              </g>
            ))}
          </g>
          {data.points.map((p, i) => (
            <circle
              key={i}
              cx={s.xDate(p.contract_date)}
              cy={s.yPrice(p.amount_10k_won)}
              r={2.2}
              fill={p.is_cancelled ? 'white' : COLOR}
              fillOpacity={p.is_cancelled ? 1 : 0.45}
              stroke={p.is_cancelled ? INK : 'none'}
              strokeWidth={p.is_cancelled ? 1 : 0}
              data-testid="trade-point"
              data-cancelled={p.is_cancelled ? '1' : '0'}
            >
              <title>{`${p.contract_date} · ${formatManwon(p.amount_10k_won)}${p.is_cancelled ? ` · ${UI.apartment.cancelled(null)}` : ''}`}</title>
            </circle>
          ))}
          {path && <path d={path} fill="none" stroke={INK} strokeWidth={1.6} data-testid="median-line" />}
          {xAxis(PRICE_H)}
        </svg>
      </figure>
      <figure className="space-y-0.5">
        <figcaption className="text-[11px] font-semibold text-ink-muted">{UI.apartment.countChart}</figcaption>
        <svg viewBox={`0 0 ${W} ${COUNT_H + AXIS_H}`} width="100%" role="img" aria-label={UI.apartment.countChart} data-testid="count-chart">
          <g aria-hidden="true">
            {countTicks.map((t) => (
              <text key={t} x={LEFT - 4} y={s.yCount(t) + 3} fontSize={9} textAnchor="end" fill={MUTED}>{t}</text>
            ))}
          </g>
          {data.monthly.map((d) => (
            <rect key={d.ym} x={s.x(d.ym)} y={s.yCount(d.count)} width={bw} height={Math.max(0, COUNT_H - s.yCount(d.count))}
              fill={COLOR} fillOpacity={0.7} data-testid="count-bar">
              <title>{`${d.ym} · ${d.count}건`}</title>
            </rect>
          ))}
          {xAxis(COUNT_H)}
        </svg>
      </figure>
      <p className="text-[10px] text-ink-muted">{UI.apartment.chartNote}</p>
    </div>
  )
}

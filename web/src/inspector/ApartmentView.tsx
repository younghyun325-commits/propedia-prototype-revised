/**
 * 아파트 단지 보기 (P17). 값은 /api/v1/map/feature/apartment/{id} · /api/v1/apartments/{id}/trades 그대로.
 * 단지의 기준은 실거래 신고 단지(aptSeq·PNU). 기본 정보(세대수·동수·사용승인일)는 연결됐을 때만, 없으면 상태 문구.
 * 사실만 보여 준다 — 평가·비교·예측 문구를 만들지 않는다.
 */
import { lazy, Suspense, useState } from 'react'
import type { ApartmentFeature } from '../api/feature'
import { useMapProjects } from '../api/map'
import { useApartmentTrades } from '../api/market'
import { useMapStore } from '../state/useMapStore'
import { UI } from '../copy/ui'
import { basisMissingText, formatManwon, pickDefaultBand } from '../market/format'
import { selectProject } from '../state/actions'
import { Card, KV, Section, Skeleton, dot } from './parts'

const AptChart = lazy(() => import('./AptChart'))

function Basis({ a }: { a: ApartmentFeature['sections']['apartment'] }) {
  const missing = basisMissingText(a.basis.status)
  const b = a.basis
  return (
    <Card testId="apt-basis">
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-meta">
        {missing ? (
          <KV k={UI.apartment.households} testId="apt-basis-missing">{missing}</KV>
        ) : (
          <>
            <KV k={UI.apartment.households}>{b.households != null ? UI.apartment.unit(b.households, '세대') : '—'}</KV>
            <KV k={UI.apartment.buildings}>{b.buildings != null ? UI.apartment.unit(b.buildings, '개 동') : '—'}</KV>
            <KV k={UI.apartment.approval}>{b.approval_date ? dot(b.approval_date) : '—'}</KV>
          </>
        )}
        <KV k={UI.apartment.buildYear} testId="apt-build-year">
          {a.build_year ? `${UI.apartment.year(a.build_year)} (${UI.apartment.buildYearNote})` : '—'}
        </KV>
        <KV k={UI.apartment.jibun}>{a.jibuns.join(', ') || '—'}</KV>
      </dl>
    </Card>
  )
}

function Sources({ a }: { a: ApartmentFeature['sections']['apartment'] }) {
  return (
    <ul className="space-y-0.5 text-caption text-ink-muted" data-testid="apt-sources">
      {a.sources.map((s) => (
        <li key={s.kind}>
          {s.label}
          {s.date ? ` · ${s.date_label} ${dot(s.date)}` : ''}
        </li>
      ))}
    </ul>
  )
}

function Trades({ id, band, until }: { id: string; band: string; until: string | null }) {
  const q = useApartmentTrades(id, band)
  const asOf = useMapStore((st) => st.asOf)
  if (q.isPending) return <Skeleton />
  if (q.isError) return <p role="alert" className="text-meta">{UI.apartment.unavailable}</p>
  const t = q.data
  return (
    <div className="space-y-3">
      <Suspense fallback={<p className="text-meta text-ink-muted" role="status">{UI.apartment.chartLoading}</p>}>
        <AptChart data={t} until={until} asOf={asOf} />
      </Suspense>
      <Section title={UI.apartment.recent(t.recent.length)} testId="apt-recent">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-caption" data-testid="apt-recent-table">
            <thead className="text-left whitespace-nowrap text-ink-muted">
              <tr>
                {Object.values(UI.apartment.cols).map((c) => (
                  <th key={c} scope="col" className="py-1 pr-2 font-medium">{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {t.recent.map((r, i) => (
                <tr key={i} className="border-t border-ink/10 whitespace-nowrap" data-testid="apt-recent-row" data-cancelled={r.is_cancelled ? '1' : '0'}>
                  <td className="py-1 pr-2 tabular-nums">{dot(r.contract_date)}</td>
                  <td className="py-1 pr-2 tabular-nums">{r.exclusive_area_m2 != null ? UI.apartment.area(r.exclusive_area_m2) : '—'}</td>
                  <td className="py-1 pr-2 tabular-nums">{r.floor != null ? UI.apartment.floor(r.floor) : '—'}</td>
                  <td className={`py-1 pr-2 tabular-nums ${r.is_cancelled ? 'text-ink-muted line-through' : ''}`}>{formatManwon(r.amount_10k_won)}</td>
                  <td className="py-1 pr-2">{r.deal_type ?? '—'}</td>
                  <td className="py-1 pr-2" data-testid={r.is_cancelled ? 'apt-cancelled' : undefined}>
                    {r.is_cancelled ? UI.apartment.cancelled(r.cancelled_date ? dot(r.cancelled_date) : null) : UI.apartment.notCancelled}
                  </td>
                  <td className="py-1 pr-2">{r.apt_dong ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  )
}

function Impacts({ a }: { a: ApartmentFeature['sections']['apartment'] }) {
  const projects = useMapProjects().data?.projects ?? []
  return (
    <Section title={UI.apartment.impacts} testId="apt-impacts">
      {a.impacts.length ? (
        <ul className="space-y-1 text-meta">
          {a.impacts.map((i) => {
            const p = projects.find((x) => x.id === i.project_id)
            return (
              <li key={i.project_id} className="flex items-center gap-2">
                <span className="flex-1" data-testid="apt-impact">{i.label}</span>
                {p && (
                  <button type="button" onClick={() => selectProject(p)} className="rounded-lg bg-white/70 px-2 py-0.5 hover:bg-white"
                    data-testid="apt-impact-go">
                    {UI.apartment.goProject}
                  </button>
                )}
              </li>
            )
          })}
        </ul>
      ) : (
        <p className="text-meta text-ink-muted">{UI.apartment.impactsNone}</p>
      )}
    </Section>
  )
}

export function ApartmentView({ f }: { f: ApartmentFeature }) {
  const a = f.sections.apartment
  const s = a.trade_summary
  const [band, setBand] = useState<string | null>(() => pickDefaultBand(s.bands, s.default_band))
  return (
    <div className="space-y-4" data-testid="apartment-view">
      <Basis a={a} />
      <Sources a={a} />
      <Section title={UI.apartment.bands} aside={<span className="text-caption text-ink-muted">{UI.apartment.summary(s.count, s.last_trade_date ? dot(s.last_trade_date) : null)}</span>}>
        <div className="flex flex-wrap gap-1" role="group" aria-label={UI.apartment.bands}>
          {s.bands.map((b) => (
            <button
              key={b.band}
              type="button"
              aria-pressed={band === b.band}
              data-testid={`apt-band-${b.band}`}
              onClick={() => setBand(b.band)}
              title={UI.apartment.bandCount(b.count_3y)}
              className={`rounded-full px-2 py-0.5 text-caption ${band === b.band ? 'bg-brand-indigo text-white' : 'bg-white/70 hover:bg-white'}`}
            >
              {UI.apartment.bandLabel(b.band)}
            </button>
          ))}
        </div>
      </Section>
      {band ? <Trades id={a.id} band={band} until={s.to} /> : <p className="text-meta text-ink-muted">{UI.apartment.noTrades}</p>}
      <Impacts a={a} />
      <p className="text-caption text-ink-muted">{a.disclaimer}</p>
    </div>
  )
}

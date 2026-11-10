/**
 * 규제 보기 (P16). 값은 /api/v1/map/feature/regulation/{doc} = applicability_rules 항목 그대로.
 * 효력 기간 막대(원문 기간 + 오늘 선, KST)·상태 배지(API 문구)·대상 기준·근거 문장·원문 쪽·'지도에서 보기'.
 */
import { MapPin } from 'lucide-react'
import type { RegulationFeature } from '../api/feature'
import { UI } from '../copy/ui'
import { useMapStore } from '../state/useMapStore'
import { EvidenceLine } from '../ui/EvidenceLine'
import { HistoryList } from './HistoryList'
import { Badge, Card, KV, Section, dot } from './parts'
import { periodBar } from './period'

function PeriodBar({ from, to, today, status, statusLabel }: {
  from: string | null; to: string | null; today: string; status: string | null; statusLabel: string | null
}) {
  const bar = periodBar(from, to, today)
  if (!bar) return <p className="text-xs text-ink-muted">{UI.regulation.noPeriod}</p>
  const fill = status === 'in_force' ? 'bg-layer-regulation/70' : 'bg-ink/25'
  return (
    <div data-testid="period-bar" data-status={status ?? ''}>
      <div className="relative h-8" role="img"
        aria-label={`${UI.regulation.period} ${dot(from)} ~ ${to ? dot(to) : UI.regulation.openEnd}, ${UI.regulation.today} ${dot(today)}`}>
        <div className="absolute inset-x-0 top-3 h-2 rounded-full bg-ink/8" />
        <div
          data-testid="period-fill"
          className={`absolute top-3 h-2 rounded-full ${fill} ${bar.openEnd ? 'rounded-r-none' : ''}`}
          style={{ left: `${bar.from}%`, width: `${Math.max(1, bar.to - bar.from)}%`,
            ...(bar.openEnd ? { maskImage: 'linear-gradient(90deg, black 80%, transparent)' } : {}) }}
        />
        <div data-testid="period-today" className="absolute top-0 h-8 w-0.5 bg-brand-indigo" style={{ left: `${bar.today}%` }}>
          <span className="absolute -top-0.5 left-1 whitespace-nowrap text-[10px] font-semibold text-brand-indigo">{UI.regulation.today}</span>
        </div>
      </div>
      <div className="flex justify-between text-[11px] tabular-nums text-ink-muted">
        <span>{UI.regulation.start} {dot(from) || '—'}</span>
        <span>{UI.regulation.today} {dot(today)}</span>
        <span>{UI.regulation.end} {to ? dot(to) : UI.regulation.openEnd}</span>
      </div>
      {statusLabel && <p className="mt-1"><Badge text={statusLabel} tone={status === 'in_force' ? 'info' : 'muted'} testId="period-status" /></p>}
    </div>
  )
}

function Overview({ f }: { f: RegulationFeature }) {
  const { regulation: r, boundary, boundary_note } = f.sections
  const requestView = useMapStore((s) => s.requestView)
  const ev = f.evidence
  return (
    <div className="space-y-4">
      <Section title={UI.regulation.period}>
        <Card>
          <PeriodBar from={r.effective_from} to={r.effective_to} today={f.as_of} status={r.effective_status}
            statusLabel={r.effective_status_label} />
          {r.effective_label && <p className="mt-1 text-xs" data-testid="period-label">{r.effective_label}</p>}
          <EvidenceLine source={r.source} evidence={r.evidence} items={ev} label={UI.regulation.evidence} className="mt-1" />
        </Card>
      </Section>

      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
        <KV k={UI.regulation.kind}>{r.doc_kind_label}</KV>
        {r.gosi_no && <KV k={UI.regulation.gosiNo}>{r.gosi_no}</KV>}
        {r.issuer && <KV k={UI.regulation.issuer}>{r.issuer} · <span className="tabular-nums">{dot(r.published_at)}</span></KV>}
        <KV k={UI.regulation.scope}>{r.scope_label}</KV>
        {r.target_note && <KV k={UI.regulation.target} testId="regulation-target">{r.target_note}</KV>}
      </dl>

      <Section title={UI.regulation.summary}>
        <p className="text-xs leading-relaxed">{r.summary}</p>
      </Section>

      <Section title={UI.regulation.evidence}>
        <blockquote className="rounded-lg bg-white/65 p-2 text-xs leading-relaxed" data-testid="regulation-evidence">{r.evidence}</blockquote>
        <EvidenceLine source={r.source} evidence={r.evidence} items={ev} label={UI.regulation.evidence} />
      </Section>

      {boundary ? (
        <Section title={UI.project.boundary}>
          <p className="text-xs">{boundary.label}</p>
          <div className="flex items-center gap-2">
            <EvidenceLine source={boundary.source} items={ev} label={boundary.label} testId="boundary-evidence" />
            {boundary.bbox && (
              <button
                type="button"
                data-testid="regulation-show-on-map"
                onClick={() => requestView({ type: 'bbox', bbox: boundary.bbox! })}
                className="ml-auto inline-flex items-center gap-1 rounded-lg bg-white/70 px-2 py-1 text-xs hover:bg-white focus-visible:outline-2 focus-visible:outline-brand-indigo"
              >
                <MapPin size={13} aria-hidden="true" />
                {UI.regulation.showOnMap}
              </button>
            )}
          </div>
        </Section>
      ) : boundary_note ? (
        <p className="text-xs text-warn" data-testid="regulation-boundary-note">{boundary_note}</p>
      ) : null}
    </div>
  )
}

export function RegulationView({ f, tab }: { f: RegulationFeature; tab: string }) {
  if (tab === 'history') return <HistoryList rows={f.sections.history} items={f.evidence} />
  return <Overview f={f} />
}

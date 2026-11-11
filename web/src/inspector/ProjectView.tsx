/**
 * 사업 보기 (P16). 값은 /api/v1/map/feature/project/{id} = progress() 결과 그대로.
 * 개요: 단계 스테퍼 · 상태 · 지금/다음 단계 · 기한 · 남은 기간 문구 · 고시 수치 / 필지: 사업 필지 / 이력: 관련 고시
 */
import { useState } from 'react'
import type { ProjectFeature } from '../api/feature'
import { UI } from '../copy/ui'
import { LayerSwatch } from '../panel/LayerSwatch'
import { useMapStore } from '../state/useMapStore'
import { EvidenceLine } from '../ui/EvidenceLine'
import { Stepper } from '../ui/Stepper'
import { Badge, Card, KV, Section, dot, fmtValue } from './parts'
import { HistoryList } from './HistoryList'

function Overview({ f }: { f: ProjectFeature }) {
  const { progress: p, stepper, status_badges, boundary } = f.sections
  const ev = f.evidence
  const [methodOpen, setMethodOpen] = useState(false)
  return (
    <div className="space-y-4">
      <Card testId="project-stepper">
        <Stepper stages={p.stages} currentSeq={stepper.current_seq} positionLabel={stepper.position_label}
          remaining={stepper.remaining_stages} nextTitle={stepper.next_title} />
        <EvidenceLine source={p.stage_basis.source} evidence={p.stage_basis.evidence} items={ev} label={UI.project.stageBasis} className="mt-1" />
      </Card>

      {(status_badges.length > 0 || p.sub_status || p.stage_note) && (
        <Section title={UI.project.status}>
          <div className="flex flex-wrap gap-1" data-testid="project-status-badges">
            {status_badges.map((b) => (
              <Badge key={b} text={b} tone={b === UI.project.statusOpen ? 'info' : 'warn'} />
            ))}
          </div>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
            {p.sub_status && <KV k={UI.project.subStatus} testId="project-sub-status">{p.sub_status}</KV>}
            {p.stage_note && <KV k={UI.project.stageNote} testId="project-stage-note">{p.stage_note}</KV>}
          </dl>
        </Section>
      )}

      <div className="grid grid-cols-2 gap-2">
        <Card>
          <p className="text-[11px] text-ink-muted">{UI.project.current}</p>
          <p className="font-semibold" data-testid="project-current">{p.current.title}</p>
          {p.current.issuer && <p className="text-[11px] text-ink-muted">{UI.project.issuer} {p.current.issuer}</p>}
          <p className="mt-1 text-xs">{p.current.owner_actions ?? p.current.owner_actions_note}</p>
          <p className="mt-1"><Badge text={p.current.template_status} tone="warn" /></p>
        </Card>
        <Card>
          <p className="text-[11px] text-ink-muted">{UI.project.next}</p>
          <p className="font-semibold" data-testid="project-next">{p.next?.title ?? '—'}</p>
          {p.next && <p className="mt-1 text-xs">{p.next.owner_actions ?? p.next.owner_actions_note}</p>}
        </Card>
      </div>

      <Section title={UI.project.deadline}>
        {p.deadlines.length ? (
          p.deadlines.map((d) => (
            <Card key={`${d.kind}-${d.due_on}`} testId="project-deadline">
              <div className="flex items-start gap-2">
                <p className="flex-1 font-semibold">{d.title}</p>
                <span data-testid="deadline-dday" className="tabular-nums">
                  <Badge text={d.d_day_label} tone={d.status === 'open' ? 'info' : 'muted'} />
                </span>
              </div>
              <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
                <KV k={UI.project.period}><span className="tabular-nums">{dot(d.starts_on)} ~ {dot(d.due_on)}</span></KV>
                {d.how_to_submit && <KV k={UI.project.howToSubmit}>{d.how_to_submit}</KV>}
                {d.places.length > 0 && <KV k={UI.project.places}>{d.places.join(', ')}</KV>}
              </dl>
              <EvidenceLine source={d.source} items={ev} label={d.title} className="mt-1" />
            </Card>
          ))
        ) : (
          <p className="text-xs text-ink-muted">{UI.project.deadlineNone}</p>
        )}
      </Section>

      <Section title={UI.project.remaining}>
        <p className="text-sm" data-testid="project-remaining">{p.remaining.note}</p>
        <button type="button" className="text-[11px] text-ink-muted underline underline-offset-2" aria-expanded={methodOpen}
          onClick={() => setMethodOpen(!methodOpen)}>
          {UI.project.method}
        </button>
        {methodOpen && <p className="text-[11px] text-ink-muted">{p.remaining.method_note}</p>}
      </Section>

      <Section title={UI.project.facts}>
        {p.facts.length ? (
          <table className="w-full text-xs" data-testid="project-facts">
            <thead className="sr-only">
              <tr><th>{UI.project.factLabel}</th><th>{UI.project.factValue}</th><th>{UI.project.factSource}</th></tr>
            </thead>
            <tbody>
              {p.facts.map((x, i) => (
                <tr key={i} className="border-t border-ink/8 align-top">
                  <td className="py-1 pr-2 text-ink-muted">{x.label}</td>
                  <td className="py-1 pr-1 text-right font-semibold tabular-nums whitespace-nowrap">{fmtValue(x.value, x.unit)}</td>
                  <td className="py-1 text-right"><EvidenceLine source={x.source} evidence={x.evidence} items={ev} label={x.label} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-xs text-ink-muted">{UI.project.factsEmpty}</p>
        )}
        <p className="text-[11px] text-ink-muted">{p.facts_note}</p>
      </Section>

      {boundary && (
        <Section title={UI.project.boundary}>
          <p className="text-xs">{boundary.label}</p>
          <EvidenceLine source={boundary.source} items={ev} label={boundary.label} testId="boundary-evidence" />
        </Section>
      )}
    </div>
  )
}

function Parcels({ f }: { f: ProjectFeature }) {
  const setSearchHit = useMapStore((s) => s.setSearchHit)
  const focused = useMapStore((s) => s.searchHit?.pnu ?? null)
  const rows = f.sections.parcels
  if (!rows.length) return <p className="text-xs text-ink-muted">{UI.project.parcelsEmpty}</p>
  return (
    <div className="space-y-2">
      <p className="text-[11px] text-ink-muted">{UI.project.parcelsHint}</p>
      <p className="flex gap-3 text-[11px] text-ink-muted">
        <span className="flex items-center gap-1"><LayerSwatch kind="parcel" />{UI.project.legendSolid}</span>
        <span className="flex items-center gap-1"><LayerSwatch kind="parcel-uncertain" />{UI.project.legendDashed}</span>
      </p>
      <ul className="space-y-1" data-testid="project-parcels">
        {rows.map((r) => (
          <li key={r.pnu}>
            <div className={`flex items-start gap-2 rounded-lg px-2 py-1.5 ${focused === r.pnu ? 'bg-brand-indigo/10 ring-1 ring-brand-indigo' : 'bg-white/60'}`}>
              <span
                aria-hidden="true"
                className={`mt-2 inline-block w-4 shrink-0 border-t-2 border-brand-indigo ${r.inclusion === 'likely' ? 'border-dashed' : ''}`}
              />
              <button
                type="button"
                data-testid="project-parcel-row"
                data-pnu={r.pnu}
                aria-pressed={focused === r.pnu}
                onClick={() => setSearchHit({ label: r.name, pnu: r.pnu, point: null })}
                className="min-w-0 flex-1 text-left text-xs focus-visible:outline-2 focus-visible:outline-brand-indigo"
              >
                <span className="font-semibold">{r.name}</span> · {r.inclusion_label}
                {!r.verified && (
                  <span className="ml-1 text-warn">
                    {UI.project.humanUnchecked}{r.review_id ? ` (${UI.project.review(r.review_id)})` : ''}
                  </span>
                )}
                <span className="block text-[11px] text-ink-muted">{r.basis_label}</span>
              </button>
              <EvidenceLine source={r.source} items={f.evidence} label={r.basis_label} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** 영향권 안 단지 (P17): 250m·500m 구분, 이름·준공연도·최근 거래일만 (집계 없음). 행 → 그 단지 선택 */
function Nearby({ f }: { f: ProjectFeature }) {
  const n = f.sections.nearby_apartments ?? { '250': [], '500': [] }
  const layerOn = useMapStore((s) => s.layers.apartments.visible)
  const pick = (id: string) => {
    const s = useMapStore.getState()
    s.setLayerVisible('apartments', true)
    s.select({ kind: 'apt', id: id.replace(/^apt:/, '') })
  }
  return (
    <div className="space-y-4" data-testid="project-nearby">
      <p className="text-[11px] text-ink-muted">{UI.nearbyApartments.note}</p>
      {!layerOn && <p className="text-[11px] text-ink-muted">{UI.nearbyApartments.layerOff}</p>}
      {(['250', '500'] as const).map((m) => (
        <Section key={m} title={UI.nearbyApartments.title(Number(m))} testId={`project-nearby-${m}`}
          aside={<span className="text-[11px] text-ink-muted tabular-nums">{n[m].length}</span>}>
          {n[m].length ? (
            <table className="w-full border-collapse text-xs">
              <thead className="text-left text-ink-muted">
                <tr>
                  <th scope="col" className="py-1 font-medium">{UI.nearbyApartments.cols.name}</th>
                  <th scope="col" className="py-1 font-medium">{UI.nearbyApartments.cols.year}</th>
                  <th scope="col" className="py-1 font-medium">{UI.nearbyApartments.cols.last}</th>
                </tr>
              </thead>
              <tbody>
                {n[m].map((a) => (
                  <tr key={a.id} className="cursor-pointer border-t border-ink/10 hover:bg-white/70" onClick={() => pick(a.id)}
                    data-testid="project-nearby-row">
                    <td className="py-1">
                      <button type="button" className="text-left hover:underline" onClick={(e) => { e.stopPropagation(); pick(a.id) }}>
                        {a.name}
                      </button>
                    </td>
                    <td className="py-1 tabular-nums">{a.build_year ?? '—'}</td>
                    <td className="py-1 tabular-nums">{a.last_trade_date ? dot(a.last_trade_date) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-xs text-ink-muted">{UI.nearbyApartments.none}</p>
          )}
        </Section>
      ))}
    </div>
  )
}

export function ProjectView({ f, tab }: { f: ProjectFeature; tab: string }) {
  if (tab === 'parcels') return <Parcels f={f} />
  if (tab === 'nearby') return <Nearby f={f} />
  if (tab === 'history') return <HistoryList rows={f.sections.history} items={f.evidence} />
  return <Overview f={f} />
}


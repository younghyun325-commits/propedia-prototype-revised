/** 사업 목록 탭 (P14 3-3). 문구·단계·기한은 /api/v1/map/projects(= progress 결과) 그대로. */
import type { MapProject } from '../api/map'
import { UI } from '../copy/ui'
import { selectProject } from '../state/actions'
import { useMapStore } from '../state/useMapStore'

function Stepper({ seq, total }: { seq: number; total: number }) {
  return (
    <div className="flex items-center gap-0.5" role="img" aria-label={UI.projects.stage(seq, total)}>
      {Array.from({ length: total }, (_, i) => (
        <span
          key={i}
          className={`h-1.5 flex-1 rounded-full ${i + 1 < seq ? 'bg-brand-indigo/45' : i + 1 === seq ? 'bg-brand-indigo' : 'bg-ink/12'}`}
        />
      ))}
    </div>
  )
}

export function ProjectsTab({ projects }: { projects: MapProject[] }) {
  const selected = useMapStore((s) => s.selected)
  return (
    <ul className="space-y-2" aria-label={UI.projects.listLabel} data-testid="project-list">
      {projects.map((p) => {
        const on = selected?.kind === 'project' && selected.id === String(p.id)
        const counts = [
          [UI.projects.included, p.parcels.included],
          [UI.projects.possible, p.parcels.possible],
          [UI.projects.likely, p.parcels.likely],
        ].filter(([, n]) => (n as number) > 0)
        return (
          <li key={p.id}>
            <button
              type="button"
              data-testid={`project-card-${p.id}`}
              aria-pressed={on}
              onClick={() => selectProject(p)}
              className={`w-full space-y-1.5 rounded-xl bg-white/60 p-3 text-left hover:bg-white/80 ${on ? 'ring-2 ring-brand-indigo' : ''}`}
            >
              <div className="flex items-start gap-2">
                <span className="flex-1 font-semibold leading-snug">{p.short_name}</span>
                {p.unverified && (
                  <span className="rounded-full bg-layer-regulation/15 px-1.5 py-px text-[10px] font-semibold text-warn">
                    {UI.projects.unverified}
                  </span>
                )}
              </div>
              <div className="text-xs text-ink-muted">
                {p.project_type_label} · {p.position_label}
              </div>
              <Stepper seq={p.stage_seq} total={p.stage_total} />
              <div className="flex flex-wrap items-center gap-1.5 text-xs">
                <span className="rounded-full bg-brand-indigo/10 px-2 py-0.5 text-ink">{p.status_badge}</span>
                {p.deadline && (
                  <span className="text-ink-muted">
                    {UI.projects.deadline} {p.deadline.title} · <span className="tabular-nums">{p.deadline.d_day_label}</span>
                  </span>
                )}
              </div>
              <div className="text-xs text-ink-muted">
                {UI.projects.parcels}: {counts.map(([k, n]) => `${k} ${n}`).join(' · ')}
              </div>
            </button>
          </li>
        )
      })}
    </ul>
  )
}

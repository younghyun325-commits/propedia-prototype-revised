/** 사업 목록 탭 (P14 3-3). 문구·단계·기한은 /api/v1/map/projects(= progress 결과) 그대로. */
import type { MapProject } from '../api/map'
import { UI } from '../copy/ui'
import { selectProject } from '../state/actions'
import { useMapStore } from '../state/useMapStore'
import { MiniStepper } from '../ui/Stepper'

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
                  <span className="rounded-full bg-layer-regulation/15 px-1.5 py-px text-caption font-semibold text-warn">
                    {UI.projects.unverified}
                  </span>
                )}
              </div>
              <div className="text-meta text-ink-muted">
                {p.project_type_label} · {p.position_label}
              </div>
              <MiniStepper seq={p.stage_seq} total={p.stage_total} />
              <div className="flex flex-wrap items-center gap-1.5 text-meta">
                {p.status_badges.map((b) => (
                  <span
                    key={b}
                    data-testid="project-status-badge"
                    className={`rounded-full px-2 py-0.5 font-semibold ${b === UI.project.statusOpen ? 'bg-brand-blue/12 text-ink' : 'bg-layer-regulation/15 text-warn'}`}
                  >
                    {b}
                  </span>
                ))}
                {p.deadline && (
                  <span className="text-ink-muted">
                    {UI.projects.deadline} {p.deadline.title} · <span className="tabular-nums">{p.deadline.d_day_label}</span>
                  </span>
                )}
              </div>
              <div className="text-meta text-ink-muted">
                {UI.projects.parcels}: {counts.map(([k, n]) => `${k} ${n}`).join(' · ')}
              </div>
            </button>
          </li>
        )
      })}
    </ul>
  )
}

/** 이력 탭 (P16): 관련 고시·단계 근거·효력 날짜를 시간순(최신 먼저)으로. 각 줄에 출처 줄. */
import type { EvidenceItem, HistoryRow } from '../api/feature'
import { UI } from '../copy/ui'
import { EvidenceLine } from '../ui/EvidenceLine'
import { dot } from './parts'

export function HistoryList({ rows, items }: { rows: HistoryRow[]; items: EvidenceItem[] }) {
  if (!rows.length) return <p className="text-xs text-ink-muted">{UI.inspector.historyEmpty}</p>
  return (
    <ol className="relative space-y-3 border-l border-ink/15 pl-4" data-testid="history-list">
      {rows.map((h, i) => (
        <li key={i} className="relative">
          <span aria-hidden="true" className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-brand-indigo" />
          <p className="text-[11px] tabular-nums text-ink-muted">{dot(h.date) || '—'}</p>
          <p className="text-xs font-semibold">{h.label}</p>
          {h.gosi_no && <p className="text-[11px] text-ink-muted">{h.gosi_no}</p>}
          <EvidenceLine source={h.source} evidence={h.evidence} items={items} label={h.label} />
        </li>
      ))}
    </ol>
  )
}

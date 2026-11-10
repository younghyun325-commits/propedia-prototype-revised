/** 데이터 상태 탭 (P14 3-4): 레이어별 원천·기준일·건수·라이선스·상태 + DB 빌드 기준일 + 운영 메모. 키는 '있음/없음'만. */
import type { Health, Manifest, ManifestLayer } from '../api/map'
import { UI } from '../copy/ui'

function stateLabel(l: ManifestLayer): string {
  if (l.status === 'ready') return UI.status.ready
  if (l.status === 'not_adopted') return UI.status.notAdopted
  return UI.status.pending(l.available_from)
}

export function StatusTab({ manifest, health }: { manifest: Manifest; health: Health | undefined }) {
  const rows = manifest.layers.filter((l) => l.group !== 'basemap' || l.id === 'basemap-gray')
  const memo = [...manifest.notes, ...(health?.key_notes ?? [])]
  return (
    <div className="space-y-4 text-xs">
      <table className="w-full border-collapse" aria-label={UI.status.tableLabel} data-testid="status-table">
        <thead className="text-left whitespace-nowrap text-ink-muted">
          <tr>
            <th scope="col" className="py-1 pr-1 font-medium">{UI.status.layer}</th>
            <th scope="col" className="py-1 pr-1 font-medium">{UI.status.asOf}</th>
            <th scope="col" className="py-1 pr-1 text-right font-medium">{UI.status.count}</th>
            <th scope="col" className="py-1 font-medium">{UI.status.state}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((l) => (
            <tr key={l.id} className="border-t border-ink/10 align-top" data-testid={`status-row-${l.id}`} data-status={l.status}>
              <td className="py-1.5 pr-1">
                <div className="font-medium">{l.id === 'basemap-gray' ? UI.status.basemap : l.name}</div>
                <div className="text-ink-muted">{l.source ?? '—'}</div>
                <div className="text-ink-muted">{l.license ?? '—'}</div>
              </td>
              <td className="py-1.5 pr-1 whitespace-nowrap tabular-nums">{l.as_of ?? '—'}</td>
              <td className="py-1.5 pr-1 text-right tabular-nums">{l.count ?? '—'}</td>
              <td className="py-1.5 whitespace-nowrap">{stateLabel(l)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <section aria-label={UI.status.dbTitle} className="space-y-1">
        <h3 className="font-semibold">{UI.status.dbTitle}</h3>
        <p data-testid="status-db-as-of">
          {UI.status.dbAsOf} <span className="tabular-nums">{manifest.db_as_of ?? '—'}</span> · {UI.status.buildAt}{' '}
          <span className="tabular-nums">{manifest.build_at ?? '—'}</span>
        </p>
        {health?.keys && (
          <p data-testid="status-keys">
            {UI.status.keys}: {UI.status.vworld} {health.keys.vworld} · {UI.status.juso} {health.keys.juso}
          </p>
        )}
      </section>

      {memo.length > 0 && (
        <section aria-label={UI.status.memo} className="space-y-1">
          <h3 className="font-semibold">{UI.status.memo}</h3>
          <ul className="list-disc space-y-0.5 pl-4 text-ink-muted" data-testid="status-memo">
            {memo.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

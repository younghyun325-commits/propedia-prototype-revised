/**
 * 고시 피드 (P19, 좌측 패널 '고시 피드' 탭): GET /api/v1/feed?as_of= — 발행일 ≤ 기준일 문서, 최신순.
 * 카드: 종류 배지 · 제목 · 발행일 · 관련 사업·규제 · 기한 · 출처 줄. 누르면 지도 이동 + 인스펙터.
 * 값(기한 라벨·효력 상태·'최근 30일')은 API 그대로 — 화면은 날짜를 계산하지 않는다.
 */
import { useFeed, type FeedItem } from '../api/map'
import { UI } from '../copy/ui'
import { focusSel } from '../state/actions'
import { useMapStore } from '../state/useMapStore'

const dot = (iso: string | null | undefined) => (iso ? iso.replaceAll('-', '.') : '—')

function Card({ it, selected }: { it: FeedItem; selected: boolean }) {
  const src = it.source
  const body = (
    <>
      <div className="flex flex-wrap items-center gap-1">
        <span className="rounded-full bg-brand-indigo/10 px-2 py-0.5 text-[11px] font-semibold text-brand-indigo" data-testid="feed-kind">
          {it.kind_label}
        </span>
        {it.recent_30d && (
          <span className="rounded-full bg-brand-sky/20 px-2 py-0.5 text-[11px] font-semibold text-ink" data-testid="feed-recent">
            {UI.feed.recent}
          </span>
        )}
        <span className="ml-auto text-[11px] tabular-nums text-ink-muted">
          {UI.feed.published} {dot(it.published_at)}
        </span>
      </div>
      <p className="mt-1 text-[13px] leading-snug font-semibold" data-testid="feed-title">{it.short_title}</p>
      {it.gosi_no && <p className="text-[11px] text-ink-muted">{it.gosi_no}</p>}
      {it.related.length > 0 && (
        <p className="mt-1 text-[11px]">
          <span className="text-ink-muted">{UI.feed.related}</span>{' '}
          {it.related
            .map((r) => (r.kind === 'regulation' ? [r.label, r.effective_label].filter(Boolean).join(' · ') : r.label))
            .filter(Boolean)
            .join(' / ')}
        </p>
      )}
      {it.deadline && (
        <p className="text-[11px]" data-testid="feed-deadline" data-status={it.deadline.status}>
          <span className="text-ink-muted">{UI.feed.deadline}</span>{' '}
          {UI.feed.deadlineLine(it.deadline.title, dot(it.deadline.due_on), it.deadline.d_day_label)}
        </p>
      )}
      <p className="mt-1 text-[10px] text-ink-muted">
        {src ? [src.doc_id, src.pdf_page ? UI.source.page(src.pdf_page) : null, dot(it.published_at)].filter(Boolean).join(' · ') : it.doc_id}
        {!it.sel && ` · ${UI.feed.noTarget}`}
      </p>
    </>
  )
  const cls = `block w-full rounded-xl p-2.5 text-left ${selected ? 'bg-white ring-2 ring-brand-indigo' : 'bg-white/65'}`
  return (
    <li data-testid="feed-card" data-doc={it.doc_id} data-sel={it.sel ?? ''}>
      {it.sel ? (
        <button type="button" onClick={() => focusSel(it.sel)} className={`${cls} hover:bg-white focus-visible:outline-2 focus-visible:outline-brand-indigo`}
          aria-label={`${it.short_title} · ${UI.feed.openTarget}`}>
          {body}
        </button>
      ) : (
        <div className={cls}>{body}</div>
      )}
    </li>
  )
}

export function FeedTab() {
  const q = useFeed()
  const selected = useMapStore((s) => (s.selected ? `${s.selected.kind}:${s.selected.id}` : null))
  if (q.isPending) return <p role="status" className="text-ink-muted">{UI.feed.loading}</p>
  if (q.isError) return <p role="alert">{UI.feed.error} ({q.error.message})</p>
  const d = q.data
  return (
    <div className="space-y-2" data-testid="feed" data-as-of={d.as_of} aria-busy={q.isFetching}>
      <p className="text-[11px] text-ink-muted" data-testid="feed-count">{UI.feed.count(d.total, dot(d.as_of))}</p>
      {d.items.length ? (
        <ol className="space-y-2">
          {d.items.map((it) => (
            <Card key={it.doc_id} it={it} selected={!!it.sel && it.sel === selected} />
          ))}
        </ol>
      ) : (
        <p className="text-ink-muted" data-testid="feed-empty">{UI.feed.empty}</p>
      )}
    </div>
  )
}

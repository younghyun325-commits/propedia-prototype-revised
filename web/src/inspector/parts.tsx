/** 인스펙터 공용 조각 (P16): 배지·섹션·키값 줄·스켈레톤·값 표기. 색은 토큰만. */
import type { ReactNode } from 'react'
import type { Badge as BadgeT } from '../api/feature'

const TONE: Record<BadgeT['tone'], string> = {
  brand: 'bg-brand-indigo/12 text-brand-indigo',
  info: 'bg-brand-blue/12 text-ink',
  warn: 'bg-layer-regulation/15 text-warn',
  muted: 'bg-ink/8 text-ink-muted',
}

export function Badge({ text, tone = 'muted', testId }: { text: string; tone?: BadgeT['tone']; testId?: string }) {
  return (
    <span data-testid={testId} className={`inline-flex items-center rounded-full px-2 py-0.5 text-caption font-semibold ${TONE[tone]}`}>
      {text}
    </span>
  )
}

export function Section({ title, children, testId, aside }: { title: string; children: ReactNode; testId?: string; aside?: ReactNode }) {
  return (
    <section className="space-y-1.5" data-testid={testId}>
      <div className="flex items-center gap-2">
        <h3 className="text-meta font-semibold text-ink-muted">{title}</h3>
        {aside && <div className="ml-auto">{aside}</div>}
      </div>
      {children}
    </section>
  )
}

export function Card({ children, className = '', testId }: { children: ReactNode; className?: string; testId?: string }) {
  return (
    <div data-testid={testId} className={`rounded-xl bg-white/65 p-3 ${className}`}>
      {children}
    </div>
  )
}

export function KV({ k, children, testId }: { k: string; children: ReactNode; testId?: string }) {
  return (
    <div className="contents">
      <dt className="text-ink-muted">{k}</dt>
      <dd data-testid={testId} className="min-w-0 @max-panel-md:mb-1">{children}</dd>
    </div>
  )
}

export function Skeleton() {
  return (
    <div className="space-y-3 p-4" data-testid="inspector-loading" role="status" aria-busy="true">
      {[70, 45, 90, 60, 80].map((w, i) => (
        <div key={i} className="h-3 animate-pulse rounded-full bg-ink/10" style={{ width: `${w}%` }} />
      ))}
    </div>
  )
}

/** 'YYYY-MM-DD' → 'YYYY.MM.DD' */
export const dot = (s: string | null | undefined) => (s ? s.slice(0, 10).replaceAll('-', '.') : '')

/** 고시 수치 값 (원문 숫자를 그대로 — 천 단위 쉼표만) */
export function fmtValue(v: unknown, unit: string | null): string {
  const one = (x: unknown) => (typeof x === 'number' ? x.toLocaleString('ko-KR', { maximumFractionDigits: 6 }) : String(x ?? '—'))
  const s = Array.isArray(v) ? v.map(one).join(', ') : one(v)
  return unit ? `${s}${unit === '%' || unit === '㎡' ? '' : ' '}${unit}` : s
}

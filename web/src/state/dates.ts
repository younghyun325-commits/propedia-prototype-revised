/**
 * 화면 날짜 도우미 (P19). 판정(효력·D-day·공람 상태)은 서버(core/timeutil, KST 고정)가 하고,
 * 화면은 '오늘(KST)'과 기준일 문자열 다루기만 한다. 순수 함수 — Vitest.
 */

/** 오늘 (KST) 'YYYY.MM.DD' */
export function todayKst(now = new Date()): string {
  const s = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now)
  return s.replaceAll('-', '.')
}

/** 오늘 (KST) 'YYYY-MM-DD' — 기준일(asOf) 비교·API as_of에 쓴다 */
export function todayIso(now = new Date()): string {
  return todayKst(now).replaceAll('.', '-')
}

/** 'YYYY-MM-DD' → UTC 자정 Date (달력 날짜 계산용, 시간대 영향 없음) */
export function isoToDate(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d))
}

export function dateToIso(d: Date): string {
  return d.toISOString().slice(0, 10)
}

/** 날짜 더하기: 일·달 (달 끝은 그 달 마지막 날로 맞춘다: 01-31 + 1달 = 02-28) */
export function addDays(iso: string, n: number): string {
  const d = isoToDate(iso)
  d.setUTCDate(d.getUTCDate() + n)
  return dateToIso(d)
}
export function addMonths(iso: string, n: number): string {
  const d = isoToDate(iso)
  const day = d.getUTCDate()
  d.setUTCDate(1)
  d.setUTCMonth(d.getUTCMonth() + n)
  const last = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate()
  d.setUTCDate(Math.min(day, last))
  return dateToIso(d)
}

/** 레이어 자료 기준일 → 'YYYY-MM' ('202609' · '2026-11-11' · '2025-01' 모두) */
export function ymLabel(asOf: string | null | undefined): string | null {
  if (!asOf) return null
  const v = String(asOf)
  if (/^\d{6}$/.test(v)) return `${v.slice(0, 4)}-${v.slice(4)}`
  if (/^\d{4}-\d{2}/.test(v)) return v.slice(0, 7)
  return null
}

/** 날짜와 함께 바뀌지 않는 레이어 그룹 (P19): 공식 참고·아파트 위치·생활 인프라 */
export const STATIC_GROUPS = ['reference', 'market', 'infra'] as const

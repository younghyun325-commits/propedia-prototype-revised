/** 규제 효력 기간 막대 (P16). 원문 기간과 기준일(오늘)의 위치만 — 효력 상태 문구는 API 값을 쓴다. 순수 함수 — Vitest. */
const DAY = 86_400_000
const t = (s: string) => Date.parse(`${s.slice(0, 10)}T00:00:00Z`)

export type PeriodBar = {
  /** 막대 시작·끝 (0~100, 표시 범위 안 %) */
  from: number
  to: number
  /** 오늘 선 위치 (0~100) */
  today: number
  openEnd: boolean
}

/**
 * 표시 범위 = 시작 − 여백 ~ 끝 + 여백 (오늘이 밖이면 오늘까지 넓힌다). 끝 날짜가 없으면 오늘 뒤로 1년을 이어 그린다.
 * 시작도 끝도 없으면 null (막대를 그리지 않음).
 */
export function periodBar(from: string | null, to: string | null, today: string): PeriodBar | null {
  if (!from && !to) return null
  const now = t(today)
  const s = from ? t(from) : Math.min(now, to ? t(to) : now) - 365 * DAY
  const openEnd = !to
  const e = to ? t(to) : Math.max(now, s) + 365 * DAY
  const pad = Math.max((e - s) * 0.08, 15 * DAY)
  const lo = Math.min(s, now) - pad
  const hi = Math.max(e, now) + pad
  const pct = (x: number) => Math.round(((x - lo) / (hi - lo)) * 1000) / 10
  return { from: pct(s), to: pct(e), today: pct(now), openEnd }
}

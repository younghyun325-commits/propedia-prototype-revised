/**
 * 하단 타임라인 계산 (docs/map/PLAN.md P19). 순수 함수 — Vitest.
 * 날짜는 모두 'YYYY-MM-DD' 달력 날짜(KST 기준 서버 값 그대로)이고, 위치 계산만 UTC 자정으로 한다 (시간대 영향 없음).
 * 판정(효력·D-day)은 하지 않는다 — 서버(core/map.state_at) 몫이다.
 */
import { scaleUtc, type ScaleTime } from 'd3-scale'
import type { TimelineData, TlBar, TlPoint } from '../api/map'
import { addDays, addMonths, dateToIso, isoToDate } from '../state/dates'

export type Domain = [string, string]
/** 기본 범위 2025-10 ~ 2027-06 */
export const DEFAULT_DOMAIN: Domain = ['2025-10-01', '2027-06-30']
/** 확대 한계: 최소 14일, 최대 60년 */
const MIN_SPAN_DAYS = 14
const MAX_SPAN_DAYS = 60 * 366

export type XScale = ScaleTime<number, number>

export function makeX(domain: Domain, left: number, right: number): XScale {
  return scaleUtc().domain([isoToDate(domain[0]), isoToDate(domain[1])]).range([left, right])
}

/** 화면 x → 그 날짜 (가장 가까운 날로 반올림) */
export function dateAtX(x: XScale, px: number): string {
  const d = x.invert(px)
  return dateToIso(new Date(Math.round(d.getTime() / 86_400_000) * 86_400_000))
}

export const xOf = (x: XScale, iso: string) => x(isoToDate(iso))

export function spanDays(d: Domain): number {
  return Math.round((isoToDate(d[1]).getTime() - isoToDate(d[0]).getTime()) / 86_400_000)
}

/** 휠 확대·축소: 가리킨 날짜를 고정점으로 factor배 (factor < 1 = 확대) */
export function zoomDomain(d: Domain, anchor: string, factor: number): Domain {
  const a = isoToDate(anchor).getTime()
  const s = isoToDate(d[0]).getTime()
  const e = isoToDate(d[1]).getTime()
  const span = Math.max(MIN_SPAN_DAYS, Math.min(MAX_SPAN_DAYS, ((e - s) / 86_400_000) * factor))
  const ratio = e === s ? 0.5 : (a - s) / (e - s)
  const ns = a - ratio * span * 86_400_000
  const day = (t: number) => dateToIso(new Date(Math.round(t / 86_400_000) * 86_400_000))
  return [day(ns), day(ns + span * 86_400_000)]
}

/** 끌어서 이동: days만큼 (양수 = 뒤 날짜 쪽으로) */
export function panDomain(d: Domain, days: number): Domain {
  const n = Math.round(days)
  return [addDays(d[0], n), addDays(d[1], n)]
}

/** 모든 이벤트 날짜 (점 날짜·막대 시작·막대 끝) — 이전·다음 이벤트 버튼, 전체 보기 */
export function eventDates(data: TimelineData | undefined): string[] {
  if (!data) return []
  const out = new Set<string>()
  for (const lane of Object.values(data.lanes) as (TlPoint | TlBar)[][])
    for (const e of lane) {
      if ('date' in e) out.add(e.date)
      else {
        out.add(e.start)
        if (e.end) out.add(e.end)
      }
    }
  return [...out].sort()
}

export function prevEvent(dates: string[], cur: string): string | null {
  for (let i = dates.length - 1; i >= 0; i--) if (dates[i] < cur) return dates[i]
  return null
}
export function nextEvent(dates: string[], cur: string): string | null {
  for (const d of dates) if (d > cur) return d
  return null
}

/** 전체 보기: 모든 이벤트 + 오늘이 들어가는 범위 (앞뒤로 한 달 여유) */
export function fullDomain(dates: string[], today: string): Domain {
  const all = [...dates, today].sort()
  return [addMonths(all[0].slice(0, 8) + '01', -1), addMonths(all[all.length - 1], 1)]
}

/** 키보드 (타임라인에 포커스): ←/→ 하루, Shift+←/→ 한 달, Home 오늘. 해당 없으면 null */
export function keyStep(key: string, shift: boolean, cur: string, today: string): string | null {
  if (key === 'Home') return today
  if (key === 'ArrowRight') return shift ? addMonths(cur, 1) : addDays(cur, 1)
  if (key === 'ArrowLeft') return shift ? addMonths(cur, -1) : addDays(cur, -1)
  return null
}

/** 재생: 한 번에 한 주 앞으로. 배속은 넘기는 간격만 바꾼다 (1배 = 0.8초) */
export const PLAY_SPEEDS = [1, 2, 4] as const
export type PlaySpeed = (typeof PLAY_SPEEDS)[number]
export const PLAY_BASE_MS = 800
export function playInterval(speed: PlaySpeed): number {
  return PLAY_BASE_MS / speed
}
/** 다음 재생 날짜. end를 넘으면 null (재생 멈춤) */
export function playStep(cur: string, end: string): string | null {
  const n = addDays(cur, 7)
  return n > end ? null : n
}

/**
 * 같은 줄에서 겹치는 이벤트를 위아래로 비켜 놓는다 (구간 묶기, 왼쪽부터 들어갈 수 있는 가장 위 줄).
 * 점은 [x − r, x + r], 막대는 [x1, x2] 칸을 차지한다. gap만큼 떨어져야 같은 줄에 놓는다.
 * 반환: id → 줄 번호 (0 = 맨 위)
 */
export function stackRows(spans: { id: string; x1: number; x2: number }[], gap = 2): Record<string, number> {
  const sorted = [...spans].sort((a, b) => a.x1 - b.x1 || a.x2 - b.x2 || a.id.localeCompare(b.id))
  const ends: number[] = []
  const out: Record<string, number> = {}
  for (const s of sorted) {
    let row = ends.findIndex((e) => s.x1 >= e + gap)
    if (row < 0) {
      row = ends.length
      ends.push(s.x2)
    } else ends[row] = s.x2
    out[s.id] = row
  }
  return out
}

/** 눈금: 범위가 넓으면 연도, 좁으면 달 */
export function ticks(x: XScale, width: number): { iso: string; label: string; major: boolean }[] {
  const n = Math.max(2, Math.floor(width / 70))
  return x.ticks(n).map((d) => {
    const iso = dateToIso(d)
    const major = iso.endsWith('-01-01')
    const days = (x.domain()[1].getTime() - x.domain()[0].getTime()) / 86_400_000
    const label = days > 3 * 366 ? iso.slice(0, 4) : major ? iso.slice(0, 4) : days > 120 ? iso.slice(5, 7) + '월' : `${Number(iso.slice(5, 7))}.${Number(iso.slice(8, 10))}`
    return { iso, label, major }
  })
}

/** 거래량 줄: 'YYYY-MM' → 그 달 1일 ~ 다음 달 1일 */
export function monthSpan(ym: string): [string, string] {
  const s = `${ym}-01`
  return [s, addMonths(s, 1)]
}

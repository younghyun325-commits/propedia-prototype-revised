import { describe, expect, it } from 'vitest'
import { mergeSearch, parseIsoDate, parseUrl, toSearch } from '../state/url'
import { addDays, addMonths, todayIso, ymLabel } from '../state/dates'
import {
  DEFAULT_DOMAIN, dateAtX, eventDates, fullDomain, keyStep, makeX, monthSpan, nextEvent, panDomain, playInterval, playStep,
  prevEvent, spanDays, stackRows, xOf, zoomDomain,
} from './scale'
import { combineFilter, hiddenProjectFilter, paintPlan, REG_DIM, regulationLabel } from '../map/layers'
import type { TimelineData } from '../api/map'

describe('기준일 URL t (P19)', () => {
  it('t 왕복, 없으면 오늘(null)', () => {
    const s = parseUrl('?t=2026-05-01&sel=project:2')
    expect(s.asOf).toBe('2026-05-01')
    expect(toSearch(s)).toContain('t=2026-05-01')
    expect(parseUrl(toSearch(s))).toEqual(s)
    expect(parseUrl('').asOf).toBeNull()
    expect(toSearch(parseUrl(''))).toBe('')
  })
  it('잘못된 날짜는 무시', () => {
    for (const v of ['2026-13-01', '2026-02-30', '20260501', '2026-5-1', 'today', '1800-01-01', ''])
      expect(parseUrl(`?t=${v}`).asOf).toBeNull()
    expect(parseIsoDate('2028-02-29')).toBe('2028-02-29')
    expect(parseIsoDate('2027-02-29')).toBeNull()
  })
  it("'오늘로' = t 제거, 다른 파라미터는 그대로", () => {
    const s = parseUrl('?t=2026-05-01&debug=1')
    expect(mergeSearch('?t=2026-05-01&debug=1', toSearch({ ...s, asOf: null }))).toBe('?debug=1')
  })
})

describe('날짜 더하기 (달력 날짜, KST 오늘)', () => {
  it('하루·한 달·달 끝', () => {
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01')
    expect(addDays('2026-03-01', -1)).toBe('2026-02-28')
    expect(addMonths('2026-01-31', 1)).toBe('2026-02-28')
    expect(addMonths('2026-05-01', -1)).toBe('2026-04-01')
  })
  it('오늘(KST): UTC 15시 = 다음 날', () => {
    expect(todayIso(new Date('2026-11-10T15:00:00Z'))).toBe('2026-11-11')
    expect(todayIso(new Date('2026-11-10T14:59:00Z'))).toBe('2026-11-10')
  })
  it('레이어 자료 기준 YYYY-MM', () => {
    expect([ymLabel('202609'), ymLabel('2026-11-11'), ymLabel('2025-01'), ymLabel(null)]).toEqual(['2026-09', '2026-11', '2025-01', null])
  })
})

describe('스크러버 위치 ↔ 날짜', () => {
  const x = makeX(DEFAULT_DOMAIN, 100, 1100)
  it('양 끝과 왕복', () => {
    expect(xOf(x, DEFAULT_DOMAIN[0])).toBe(100)
    expect(xOf(x, DEFAULT_DOMAIN[1])).toBe(1100)
    for (const d of ['2025-10-01', '2026-05-01', '2026-11-06', '2027-06-30']) expect(dateAtX(x, xOf(x, d))).toBe(d)
  })
  it('가운데 근처는 가장 가까운 날로 반올림', () => {
    const a = xOf(x, '2026-05-01')
    const b = xOf(x, '2026-05-02')
    expect(dateAtX(x, a + (b - a) * 0.4)).toBe('2026-05-01')
    expect(dateAtX(x, a + (b - a) * 0.6)).toBe('2026-05-02')
  })
})

describe('확대·이동', () => {
  it('가리킨 날짜 고정 확대, 한계', () => {
    const z = zoomDomain(DEFAULT_DOMAIN, '2026-05-01', 0.5)
    expect(spanDays(z)).toBe(Math.round(spanDays(DEFAULT_DOMAIN) * 0.5))
    expect(z[0] < '2026-05-01' && z[1] > '2026-05-01').toBe(true)
    expect(spanDays(zoomDomain(['2026-05-01', '2026-05-10'], '2026-05-05', 0.1))).toBe(14)
  })
  it('이동', () => {
    expect(panDomain(['2026-01-01', '2026-12-31'], 31)).toEqual(['2026-02-01', '2027-01-31'])
  })
})

const DATA: TimelineData = {
  from: '1900-01-01', to: '2100-12-31',
  lane_labels: { publish: '고시 발행', review: '공람', effective: '효력', stage: '사업 단계', data_as_of: '자료 기준일' },
  lanes: {
    publish: [{ id: 'publish:D9', date: '2026-04-17', title: 'D9' }, { id: 'publish:D1', date: '2026-10-06', title: 'D1' }],
    review: [{ id: 'review:2', start: '2026-04-17', end: '2026-05-01', title: '공람' }],
    effective: [{ id: 'effective:D6-01', start: '2025-10-20', end: '2026-12-31', title: 'D6' },
      { id: 'effective:D7-01', start: '2025-10-16', end: null, title: 'D7' }],
    stage: [], data_as_of: [],
  },
}

describe('이벤트 날짜·이전·다음·전체 보기', () => {
  const dates = eventDates(DATA)
  it('점 날짜 + 막대 시작·끝, 중복 없이 정렬', () => {
    expect(dates).toEqual(['2025-10-16', '2025-10-20', '2026-04-17', '2026-05-01', '2026-10-06', '2026-12-31'])
  })
  it('이전·다음', () => {
    expect(prevEvent(dates, '2026-05-01')).toBe('2026-04-17')
    expect(nextEvent(dates, '2026-05-01')).toBe('2026-10-06')
    expect(prevEvent(dates, '2025-01-01')).toBeNull()
    expect(nextEvent(dates, '2027-01-01')).toBeNull()
  })
  it('전체 보기 = 모든 이벤트 + 오늘, 앞뒤 한 달', () => {
    expect(fullDomain(dates, '2026-11-11')).toEqual(['2025-09-01', '2027-01-31'])
  })
})

describe('겹침 배치', () => {
  it('겹치면 아래 줄로, 떨어져 있으면 같은 줄', () => {
    const r = stackRows([
      { id: 'a', x1: 0, x2: 10 }, { id: 'b', x1: 5, x2: 15 }, { id: 'c', x1: 13, x2: 20 }, { id: 'd', x1: 30, x2: 40 },
    ], 2)
    expect(r).toEqual({ a: 0, b: 1, c: 0, d: 0 })
  })
  it('같은 날 점 3개 → 3줄', () => {
    const r = stackRows([1, 2, 3].map((i) => ({ id: `p${i}`, x1: 95, x2: 105 })))
    expect(Object.values(r).sort()).toEqual([0, 1, 2])
  })
})

describe('재생·키보드', () => {
  it('한 주씩, 끝을 넘으면 멈춤', () => {
    expect(playStep('2026-05-01', '2027-06-30')).toBe('2026-05-08')
    expect(playStep('2027-06-28', '2027-06-30')).toBeNull()
    expect([1, 2, 4].map((s) => playInterval(s as 1 | 2 | 4))).toEqual([800, 400, 200])
  })
  it('←/→ 하루, Shift 한 달, Home 오늘, 다른 키 없음', () => {
    expect(keyStep('ArrowRight', false, '2026-05-01', '2026-11-11')).toBe('2026-05-02')
    expect(keyStep('ArrowLeft', false, '2026-05-01', '2026-11-11')).toBe('2026-04-30')
    expect(keyStep('ArrowRight', true, '2026-05-01', '2026-11-11')).toBe('2026-06-01')
    expect(keyStep('ArrowLeft', true, '2026-05-31', '2026-11-11')).toBe('2026-04-30')
    expect(keyStep('Home', false, '2026-05-01', '2026-11-11')).toBe('2026-11-11')
    expect(keyStep('a', false, '2026-05-01', '2026-11-11')).toBeNull()
  })
  it('거래량 달 칸', () => {
    expect(monthSpan('2026-12')).toEqual(['2026-12-01', '2027-01-01'])
  })
})

describe("지도 '그날 기준' 식 (setFilter·setPaintProperty만)", () => {
  it('숨긴 사업 필터: 사업 도형은 id, 나머지는 project_id', () => {
    expect(hiddenProjectFilter('id', [])).toBeNull()
    expect(hiddenProjectFilter('id', [1])).toEqual(['!', ['in', ['get', 'id'], ['literal', ['project:1']]]])
    expect(hiddenProjectFilter('project_id', [1, 2])).toEqual(['!', ['in', ['get', 'project_id'], ['literal', [1, 2]]]])
  })
  it('기존 필터와 함께', () => {
    const base = ['==', ['get', 'buffer_m'], 250]
    expect(combineFilter(base, null)).toBe(base)
    expect(combineFilter(base, ['x'])).toEqual(['all', base, ['x']])
    expect(combineFilter(undefined, ['x'])).toEqual(['x'])
  })
  it('효력 중이 아닌 규제만 25%', () => {
    expect(paintPlan('regulations', 100, false)).toEqual([
      ['propedia-regulation-fill', 'fill-opacity', 1], ['propedia-regulation-line', 'line-opacity', 1]])
    const [fill] = paintPlan('regulations', 100, false, ['regulation:D10'])
    expect(fill[2]).toEqual(['case', ['in', ['get', 'id'], ['literal', ['regulation:D10']]], REG_DIM, 1])
    // 다른 레이어에는 걸지 않는다
    expect(paintPlan('projects', 100, false, ['regulation:D10'])[0][2]).toBe(0.32)
  })
  it('규제 라벨에 상태', () => {
    expect(regulationLabel('대치동 506', '효력 전', false)).toBe('대치동 506 · 효력 전')
    expect(regulationLabel('대치동 506', '효력 중', true)).toBe('대치동 506')
  })
})

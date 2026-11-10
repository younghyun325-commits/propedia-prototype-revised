import { describe, expect, it } from 'vitest'
import { UI } from '../copy/ui'
import { searchApartments, type ApartmentProps } from './apartments'
import { makeScales, monthRange } from './chartScales'
import { basisMissingText, formatAxisManwon, formatManwon, pickDefaultBand } from './format'

describe('금액 표기 (만원)', () => {
  it.each([
    [319000, '31억 9,000만'],
    [50000, '5억'],
    [9500, '9,500만'],
    [100500, '10억 500만'],
    [1230000, '123억'],
    [0, '0만'],
  ])('%d → %s', (v, s) => expect(formatManwon(v)).toBe(s))
  it('없는 값', () => {
    expect(formatManwon(null)).toBe('—')
    expect(formatManwon(Number.NaN)).toBe('—')
  })
  it('축 눈금', () => {
    expect(formatAxisManwon(319000)).toBe('31.9억')
    expect(formatAxisManwon(9500)).toBe('9,500만')
  })
})

describe('면적대 기본 선택', () => {
  const bands = [
    { band: '~60', count_12m: 1, count_3y: 4, count: 30, last_trade_date: '2026-01-01' },
    { band: '60~85', count_12m: 9, count_3y: 20, count: 90, last_trade_date: '2026-10-01' },
    { band: '85~102', count_12m: 2, count_3y: 20, count: 300, last_trade_date: '2026-09-01' },
  ]
  it('서버 기본값이 있으면 그대로', () => expect(pickDefaultBand(bands, '85~102')).toBe('85~102'))
  it('없으면 최근 3년 최다 (같으면 앞쪽)', () => expect(pickDefaultBand(bands, null)).toBe('60~85'))
  it('서버 값이 목록에 없으면 다시 고름', () => expect(pickDefaultBand(bands, '135~')).toBe('60~85'))
  it('거래 없음', () => expect(pickDefaultBand([], null)).toBeNull())
})

describe('기본 정보 없음 문구', () => {
  it('상태별', () => {
    expect(basisMissingText('pending')).toBe(UI.apartment.basisPending)
    expect(basisMissingText('not_in_list')).toBe('공동주택 기본 정보 목록에 없음')
    expect(basisMissingText('linked')).toBeNull()
  })
})

describe('차트 스케일', () => {
  const monthly = [
    { ym: '2025-11', median_amount: 300000, count: 2 },
    { ym: '2026-02', median_amount: 320000, count: 5 },
  ]
  const points = [
    { contract_date: '2025-11-03', amount_10k_won: 290000, is_cancelled: 0 },
    { contract_date: '2026-02-20', amount_10k_won: 340000, is_cancelled: 1 },
  ]
  const opt = { width: 320, priceHeight: 140, countHeight: 60, left: 40, right: 8 }
  it('빈 달을 포함한 같은 x축', () => {
    const s = makeScales(monthly, points, opt)!
    expect(s.months).toEqual(['2025-11', '2025-12', '2026-01', '2026-02'])
    expect(monthRange('2025-12', '2026-01')).toEqual(['2025-12', '2026-01'])
    expect(s.x('2025-11')!).toBeGreaterThanOrEqual(opt.left)
    expect(s.x('2026-02')! + s.x.bandwidth()).toBeLessThanOrEqual(opt.width - opt.right)
    expect(s.xDate('2026-02-20')).toBeGreaterThan(s.x('2026-02')!)
  })
  it('가격 축은 점까지 포함, 건수 축은 0부터', () => {
    const s = makeScales(monthly, points, opt)!
    const [lo, hi] = s.yPrice.domain()
    expect(lo).toBeLessThanOrEqual(290000)
    expect(hi).toBeGreaterThanOrEqual(340000)
    expect(s.yPrice(hi)).toBeLessThan(s.yPrice(lo)) // 위가 큰 값
    expect(s.yCount.domain()[0]).toBe(0)
    expect(s.yCount.domain()[1]).toBeGreaterThanOrEqual(5)
  })
  it('자료 없음', () => expect(makeScales([], [], opt)).toBeNull())
})

describe('단지 검색', () => {
  const mk = (name: string, jibuns: string[], aliases: string[] = []): ApartmentProps => ({
    id: `apt:${name}`, kind: 'apartment', name, aliases, apt_seq: null, pnus: [], jibuns, build_year: 1979,
    last_trade_date: null, trade_count: 1, lon: 127, lat: 37.5, impact_buffer_m: null, impacts: [], basis_info: 'pending',
  })
  const fs = [mk('은마', ['대치동 316']), mk('청담자이', ['청담동 134-38']), mk('신현대9차', ['압구정동 426'], ['현대9차'])]
  it('이름·다른 이름·지번 부분 일치', () => {
    expect(searchApartments(fs, '은마').map((h) => h.props.name)).toEqual(['은마'])
    expect(searchApartments(fs, '은마아파트').map((h) => h.props.name)).toEqual(['은마'])
    expect(searchApartments(fs, '현대9').map((h) => h.props.name)).toEqual(['신현대9차'])
    expect(searchApartments(fs, '대치동 316')[0].field).toBe('jibun')
    expect(searchApartments(fs, '134-38')[0].props.name).toBe('청담자이')
    expect(searchApartments(fs, '은')).toEqual([])
  })
})

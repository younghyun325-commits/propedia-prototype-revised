/** P16 인스펙터: Stepper 렌더(지난·현재·남은), 원문 모달 키보드·포커스·확대, 효력 기간 막대, 콜아웃 배치. */
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { UI } from '../copy/ui'
import { periodBar } from '../inspector/period'
import { placeCallout, CALLOUT_GAP } from '../map/calloutPlace'
import { modalKey, nextFocusIndex } from './focusTrap'
import { MiniStepper, Stepper, stepCells } from './Stepper'
import { IDENTITY, MAX_SCALE, clampPan, panBy, pinchFactor, zoomAt } from './zoom'

const states = (html: string) => [...html.matchAll(/data-state="(\w+)"/g)].map((m) => m[1])

describe('Stepper', () => {
  const stages = Array.from({ length: 13 }, (_, i) => ({
    seq: i + 1,
    title: `단계${i + 1}`,
    status: (i + 1 < 2 ? 'done' : i + 1 === 2 ? 'current' : 'upcoming') as 'done' | 'current' | 'upcoming',
    what_happens: null,
    what_happens_note: '단계 설명 문구는 법령 대조 후 사람이 작성합니다',
    template_status: '법령 대조 전 초안',
  }))

  it('지난 1 · 현재 1 · 남은 11 칸과 아래 줄', () => {
    const html = renderToStaticMarkup(
      createElement(Stepper, { stages, currentSeq: 2, positionLabel: '재건축 13단계 중 2번째', remaining: 11, nextTitle: '정비구역 지정 고시' }),
    )
    const s = states(html)
    expect(s).toHaveLength(13)
    expect(s.filter((x) => x === 'done')).toHaveLength(1)
    expect(s.indexOf('current')).toBe(1)
    expect(s.filter((x) => x === 'upcoming')).toHaveLength(11)
    expect(html).toContain('aria-current="step"')
    expect(html).toContain('재건축 13단계 중 2번째 · 앞으로 11단계 · 다음: 정비구역 지정 고시')
  })

  it('모아타운 8단계 중 1번째: 지난 단계 없음', () => {
    const s8 = stages.slice(0, 8).map((s) => ({ ...s, status: undefined }))
    const cells = stepCells(s8, 1)
    expect(cells.map((c) => c.state)).toEqual(['current', ...Array(7).fill('upcoming')])
    expect(UI.stepper.line('모아타운 8단계 중 1번째 (관리계획 수립 중)', 7, '조합설립인가')).toBe(
      '모아타운 8단계 중 1번째 (관리계획 수립 중) · 앞으로 7단계 · 다음: 조합설립인가',
    )
    expect(UI.stepper.line('x', 0, null)).toBe('x · 앞으로 0단계')
  })

  it('API status가 있으면 그대로 쓴다 (번호로 다시 나누지 않음)', () => {
    expect(stepCells([{ seq: 1, status: 'current' }, { seq: 2, status: 'upcoming' }], 2).map((c) => c.state)).toEqual([
      'current', 'upcoming',
    ])
  })

  it('사업 목록 작은 막대', () => {
    const s = states(renderToStaticMarkup(createElement(MiniStepper, { seq: 3, total: 5 })))
    expect(s).toEqual(['done', 'done', 'current', 'upcoming', 'upcoming'])
  })
})

describe('원문 모달 키보드·포커스', () => {
  it('Tab·Shift+Tab이 처음과 끝에서 돈다 (포커스 가두기)', () => {
    expect(nextFocusIndex(0, 4, false)).toBe(1)
    expect(nextFocusIndex(3, 4, false)).toBe(0)
    expect(nextFocusIndex(0, 4, true)).toBe(3)
    expect(nextFocusIndex(-1, 4, false)).toBe(0)
    expect(nextFocusIndex(-1, 4, true)).toBe(3)
    expect(nextFocusIndex(0, 0, false)).toBe(-1)
  })
  it('키 → 할 일', () => {
    expect(modalKey('Escape', false)).toBe('close')
    expect(modalKey('ArrowLeft', false)).toBe('prev')
    expect(modalKey('ArrowRight', false)).toBe('next')
    expect(modalKey('ArrowLeft', true)).toBe('panLeft')
    expect(modalKey('ArrowUp', false)).toBeNull()
    expect(modalKey('+', false)).toBe('zoomIn')
    expect(modalKey('-', false)).toBe('zoomOut')
    expect(modalKey('0', false)).toBe('reset')
    expect(modalKey('l', false)).toBeNull()
  })
  it('확대·이동', () => {
    const v = zoomAt(IDENTITY, 2, 0, 0, 400, 300)
    expect(v.scale).toBe(2)
    expect(zoomAt(v, 100, 0, 0, 400, 300).scale).toBe(MAX_SCALE)
    expect(zoomAt(v, 0.01, 0, 0, 400, 300)).toEqual(IDENTITY)
    // 배율 2에서 이동 한도 = 상자 절반
    expect(panBy(v, 1000, -1000, 400, 300)).toEqual({ scale: 2, x: 200, y: -150 })
    expect(clampPan({ scale: 1, x: 50, y: 50 }, 400, 300)).toEqual(IDENTITY)
    // 한 점 고정 확대: 오른쪽 위 점을 기준으로 확대하면 그 점이 그대로
    const z = zoomAt(IDENTITY, 2, 100, -50, 400, 300)
    expect(z.x).toBe(-100)
    expect(z.y).toBe(50)
    expect(pinchFactor(100, 150)).toBe(1.5)
    expect(pinchFactor(0, 150)).toBe(1)
  })
})

describe('효력 기간 막대', () => {
  it('오늘이 기간 안이면 시작~끝 사이에 오늘 선', () => {
    const b = periodBar('2026-04-01', '2028-04-01', '2026-11-10')!
    expect(b.from).toBeLessThan(b.today)
    expect(b.today).toBeLessThan(b.to)
    expect(b.openEnd).toBe(false)
    expect(b.from).toBeGreaterThanOrEqual(0)
    expect(b.to).toBeLessThanOrEqual(100)
  })
  it('오늘이 기간 앞·뒤면 막대 밖, 끝 날짜가 없으면 열린 막대, 둘 다 없으면 없음', () => {
    const before = periodBar('2026-04-27', '2027-04-26', '2026-04-20')!
    expect(before.today).toBeLessThan(before.from)
    const after = periodBar('2025-10-20', '2026-12-31', '2027-01-01')!
    expect(after.today).toBeGreaterThan(after.to)
    expect(periodBar('2025-10-16', null, '2026-11-10')!.openEnd).toBe(true)
    expect(periodBar(null, null, '2026-11-10')).toBeNull()
  })
})

describe('콜아웃 배치', () => {
  const vp = { width: 1440, height: 900 }
  const insets = { top: 80, right: 424, bottom: 68, left: 344 }
  const card = { w: 220, h: 64 }
  it('기본은 오른쪽, 선은 기준점에서 카드 왼쪽 가장자리로', () => {
    const p = placeCallout({ x: 700, y: 400 }, card, vp, insets)
    expect(p.visible && p.side).toBe('right')
    if (p.visible) {
      expect(p.left).toBe(700 + CALLOUT_GAP)
      expect(p.line[0]).toEqual({ x: 700, y: 400 })
      expect(p.line[1].x).toBe(p.left)
    }
  })
  it('우측 패널과 겹치면 왼쪽', () => {
    const p = placeCallout({ x: 900, y: 400 }, card, vp, insets)
    expect(p.visible && p.side).toBe('left')
    if (p.visible) {
      expect(p.left + card.w).toBeLessThanOrEqual(900)
      expect(p.line[1].x).toBe(p.left + card.w)
    }
  })
  it('화면 밖(패널 아래 포함)이면 숨김', () => {
    expect(placeCallout({ x: 200, y: 400 }, card, vp, insets).visible).toBe(false) // 좌측 패널 밑
    expect(placeCallout({ x: 1200, y: 400 }, card, vp, insets).visible).toBe(false) // 우측 패널 밑
    expect(placeCallout({ x: 700, y: -20 }, card, vp, insets).visible).toBe(false)
    expect(placeCallout({ x: 700, y: 880 }, card, vp, insets).visible).toBe(false)
  })
  it('위쪽 가장자리 근처면 카드를 보이는 영역 안으로 내린다', () => {
    const p = placeCallout({ x: 700, y: 90 }, card, vp, insets)
    expect(p.visible && p.top).toBeGreaterThanOrEqual(insets.top)
  })
})

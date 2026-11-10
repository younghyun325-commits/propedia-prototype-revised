import { describe, expect, it } from 'vitest'
import { estimateLabelWidth, offsetFor, overlapArea, placeLabels, REGULATION_LABEL_MIN_ZOOM } from './labels'

describe('라벨 배치 (P14, 라벨 충돌)', () => {
  it('겹치지 않으면 가운데', () => {
    const r = placeLabels([{ id: 'a', x: 0, y: 0, w: 100, h: 18 }, { id: 'b', x: 0, y: 200, w: 100, h: 18 }], 12)
    expect(r.a.anchor).toBe('center')
    expect(r.b.anchor).toBe('center')
  })
  it('두 라벨이 겹치면 뒤 라벨을 다른 자리로 옮김 (variable anchor + radial offset)', () => {
    const r = placeLabels([{ id: 'a', x: 0, y: 0, w: 300, h: 18, keep: true }, { id: 'b', x: 20, y: 6, w: 300, h: 18, keep: true }], 12)
    expect(r.a.anchor).toBe('center')
    expect(r.b.anchor).not.toBe('center')
    const A = { x: 0, y: 0, w: 300, h: 18 }
    const B = { x: 20 + r.b.dx, y: 6 + r.b.dy, w: 300, h: 18 }
    expect(overlapArea(A, B)).toBe(0)
  })
  it('규제 라벨은 줌 14 미만에서 숨김', () => {
    const lab = [{ id: 'reg', x: 0, y: 0, w: 100, h: 18, minZoom: REGULATION_LABEL_MIN_ZOOM }]
    expect(placeLabels(lab, 12).reg.visible).toBe(false)
    expect(placeLabels(lab, 14).reg.visible).toBe(true)
  })
  it('자리가 없으면 keep이 아닌 라벨은 숨김, keep은 남김', () => {
    const big = { id: 'a', x: 0, y: 0, w: 2000, h: 2000, keep: true }
    expect(placeLabels([big, { id: 'b', x: 0, y: 0, w: 50, h: 18 }], 15).b.visible).toBe(false)
    expect(placeLabels([big, { id: 'c', x: 0, y: 0, w: 50, h: 18, keep: true }], 15).c.visible).toBe(true)
  })
  it('장애물(법정동 이름)을 피함', () => {
    const r = placeLabels([{ id: 'a', x: 0, y: 0, w: 120, h: 18, keep: true }], 12, [{ x: 0, y: 0, w: 60, h: 16 }])
    expect(r.a.anchor).not.toBe('center')
  })
  it('오프셋 방향과 너비 어림', () => {
    expect(offsetFor('top', 100, 18, 10)).toEqual([0, -19])
    expect(offsetFor('right', 100, 18, 10)).toEqual([60, 0])
    expect(estimateLabelWidth('가나')).toBe(39)
    expect(estimateLabelWidth('ab')).toBeLessThan(estimateLabelWidth('가나'))
  })
})

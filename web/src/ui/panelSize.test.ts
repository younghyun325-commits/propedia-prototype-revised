import { describe, expect, it } from 'vitest'
import { panelTier } from './panelLayout'
import {
  DEFAULT_WIDTHS, fitWidths, keyDelta, LEFT_RANGE, maxWidth, parseWidths, readWidths, RIGHT_RANGE, WIDTHS_KEY, writeWidths,
} from './panelSize'

const both = { left: true, right: true }

describe('패널 너비 범위 (P22-2)', () => {
  it('최소·최대로 자른다', () => {
    expect(fitWidths({ left: 100, right: 100 }, 3000, both)).toEqual({ left: LEFT_RANGE.min, right: RIGHT_RANGE.min })
    expect(fitWidths({ left: 9999, right: 9999 }, 4000, both)).toEqual({ left: LEFT_RANGE.max, right: RIGHT_RANGE.max })
  })
  it('지도 영역이 화면의 40%보다 좁아지지 않는다', () => {
    const vw = 1440
    const w = fitWidths({ left: 560, right: 720 }, vw, both)
    expect(vw - (w.left + 24) - (w.right + 24)).toBeGreaterThanOrEqual(vw * 0.4 - 1)
  })
  it('최대값은 반대쪽 너비에 따라 바뀐다', () => {
    const vw = 1440
    const a = maxWidth('left', { left: 340, right: 320 }, vw, both)
    const b = maxWidth('left', { left: 340, right: 600 }, vw, both)
    expect(a).toBeGreaterThan(b)
    expect(b).toBe(Math.max(LEFT_RANGE.min, Math.floor(vw * 0.6) - 48 - 600))
    expect(maxWidth('left', { left: 340, right: 400 }, 4000, both)).toBe(LEFT_RANGE.max)
  })
  it('창이 줄면 범위 안으로 다시 맞춘다: 왼쪽부터 줄이고, 지정한 쪽은 나중에 줄임', () => {
    const want = { left: 560, right: 720 }
    expect(fitWidths(want, 2560, both)).toEqual(want)
    const small = fitWidths(want, 1280, both)
    expect(1280 - small.left - small.right - 48).toBeGreaterThanOrEqual(1280 * 0.4 - 1)
    expect(small).toEqual({ left: LEFT_RANGE.min, right: Math.floor(1280 * 0.6) - 48 - LEFT_RANGE.min })
    const keepLeft = fitWidths(want, 1280, both, 'left')
    expect(keepLeft.right).toBe(RIGHT_RANGE.min)
    expect(keepLeft.left).toBe(Math.floor(1280 * 0.6) - 48 - RIGHT_RANGE.min)
  })
  it('숨은 패널은 예산에 넣지 않는다', () => {
    const w = fitWidths({ left: 560, right: 720 }, 1280, { left: true, right: false })
    expect(w.left).toBe(LEFT_RANGE.max)
  })
})

describe('패널 너비 저장 (P22-2)', () => {
  it('저장소가 없거나 실패하면 기본값', () => {
    expect(readWidths(null)).toEqual(DEFAULT_WIDTHS)
    const broken = { getItem: () => { throw new Error('blocked') } }
    expect(readWidths(broken)).toEqual(DEFAULT_WIDTHS)
    expect(writeWidths(DEFAULT_WIDTHS, { setItem: () => { throw new Error('quota') } })).toBe(false)
  })
  it('잘못된 값은 기본값, 범위 밖은 자름', () => {
    expect(parseWidths('not json')).toEqual(DEFAULT_WIDTHS)
    expect(parseWidths('{"left":"a","right":null}')).toEqual(DEFAULT_WIDTHS)
    expect(parseWidths('{"left":9999,"right":1}')).toEqual({ left: LEFT_RANGE.max, right: RIGHT_RANGE.min })
  })
  it('왕복', () => {
    const m = new Map<string, string>()
    const st = { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v) }
    expect(writeWidths({ left: 500.4, right: 333 }, st)).toBe(true)
    expect(m.has(WIDTHS_KEY)).toBe(true)
    expect(readWidths(st)).toEqual({ left: 500, right: 333 })
  })
})

describe('키보드 조절 (P22-2)', () => {
  it('왼쪽 손잡이는 →가 넓힘, 오른쪽 손잡이는 ←가 넓힘, Shift는 64px', () => {
    expect(keyDelta('left', 'ArrowRight', false)).toBe(16)
    expect(keyDelta('left', 'ArrowLeft', true)).toBe(-64)
    expect(keyDelta('right', 'ArrowLeft', false)).toBe(16)
    expect(keyDelta('right', 'ArrowRight', true)).toBe(-64)
    expect(keyDelta('left', 'ArrowUp', false)).toBeNull()
  })
})

describe('너비별 배치 구간 (P22-2)', () => {
  it('좁음 <380, 보통 380~520, 넓음 >520', () => {
    expect(panelTier(379)).toBe('narrow')
    expect(panelTier(380)).toBe('normal')
    expect(panelTier(519)).toBe('normal')
    expect(panelTier(560)).toBe('wide')
  })
})

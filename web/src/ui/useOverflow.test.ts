import { describe, expect, it } from 'vitest'
import { chipsThatFit, nextCompact } from './useOverflow'

describe('탭 아이콘 전환 (P22-2)', () => {
  it('넘치면 아이콘으로, 필요한 폭을 기억', () => {
    expect(nextCompact(false, 340, 300, 0)).toEqual({ compact: true, need: 340 })
    expect(nextCompact(false, 300, 300, 0)).toEqual({ compact: false, need: 0 })
  })
  it('기억한 폭 이상으로 넓어져야 글자로 돌아감', () => {
    expect(nextCompact(true, 200, 330, 340)).toEqual({ compact: true, need: 340 })
    expect(nextCompact(true, 200, 340, 340)).toEqual({ compact: false, need: 340 })
  })
})

describe('상단 칩 접기 (P22-2)', () => {
  it('모두 들어가면 더보기 없음', () => {
    expect(chipsThatFit([112, 112, 112], 400, 48, 4, 3)).toBe(3)
  })
  it('넘치면 더보기 자리를 남기고 줄임', () => {
    expect(chipsThatFit([112, 112, 112], 300, 48, 4, 3)).toBe(2)
    expect(chipsThatFit([112, 112, 112], 170, 48, 4, 3)).toBe(1)
    expect(chipsThatFit([112, 112, 112], 100, 48, 4, 3)).toBe(0)
  })
  it('최대 개수를 넘지 않음', () => {
    expect(chipsThatFit([112, 112, 112, 112], 2000, 48, 4, 3)).toBe(3)
  })
})

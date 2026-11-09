import { beforeEach, describe, expect, it } from 'vitest'
import { keyAction } from './app/keys'
import { useMapStore } from './state/useMapStore'
import { isChromium } from './ui/browser'

const UA = {
  chrome: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36',
  edge: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36 Edg/141.0',
  safari: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15',
  firefox: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0',
  iosChrome: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/141.0 Mobile/15E148 Safari/604.1',
}

describe('isChromium', () => {
  it('크롬·엣지는 참', () => {
    expect(isChromium(UA.chrome)).toBe(true)
    expect(isChromium(UA.edge)).toBe(true)
    expect(isChromium('', [{ brand: 'Chromium' }])).toBe(true)
  })
  it('Safari·Firefox·iOS 크롬은 거짓', () => {
    expect(isChromium(UA.safari)).toBe(false)
    expect(isChromium(UA.firefox)).toBe(false)
    expect(isChromium(UA.iosChrome)).toBe(false)
  })
})

describe('keyAction', () => {
  it('L·I·T·Esc', () => {
    expect(keyAction({ key: 'l' })).toBe('left')
    expect(keyAction({ key: 'I' })).toBe('right')
    expect(keyAction({ key: 't' })).toBe('timeline')
    expect(keyAction({ key: 'Escape' })).toBe('clear')
  })
  it('입력 중·수정 키는 무시', () => {
    expect(keyAction({ key: 'l', target: { tagName: 'INPUT' } })).toBeNull()
    expect(keyAction({ key: 't', ctrlKey: true })).toBeNull()
    expect(keyAction({ key: 'x' })).toBeNull()
  })
})

describe('useMapStore', () => {
  beforeEach(() => useMapStore.setState({ leftOpen: true, rightOpen: true, timelineOpen: false, selection: null }))
  it('패널 토글과 선택 해제', () => {
    const s = useMapStore.getState()
    s.toggleLeft()
    s.toggleRight()
    s.toggleTimeline()
    s.select('project:1')
    let st = useMapStore.getState()
    expect([st.leftOpen, st.rightOpen, st.timelineOpen, st.selection]).toEqual([false, false, true, 'project:1'])
    st.clearSelection()
    st = useMapStore.getState()
    expect(st.selection).toBeNull()
  })
})

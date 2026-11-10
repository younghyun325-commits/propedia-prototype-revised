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
  it('Ctrl+K·Cmd+K는 입력 중에도 검색 열기', () => {
    expect(keyAction({ key: 'k', ctrlKey: true })).toBe('palette')
    expect(keyAction({ key: 'K', metaKey: true, target: { tagName: 'INPUT' } })).toBe('palette')
    expect(keyAction({ key: 'k', ctrlKey: true, shiftKey: true })).toBeNull()
    expect(keyAction({ key: 'k' })).toBeNull()
  })
  it('입력 중·수정 키는 무시', () => {
    expect(keyAction({ key: 'l', target: { tagName: 'INPUT' } })).toBeNull()
    expect(keyAction({ key: 't', ctrlKey: true })).toBeNull()
    expect(keyAction({ key: 'x' })).toBeNull()
  })
})

describe('useMapStore', () => {
  beforeEach(() => useMapStore.setState({ leftOpen: true, rightOpen: true, timelineOpen: false, selected: null }))
  it('패널 토글과 선택 해제 (고르면 인스펙터가 열림)', () => {
    const s = useMapStore.getState()
    s.toggleLeft()
    s.toggleRight()
    s.toggleTimeline()
    let st = useMapStore.getState()
    expect([st.leftOpen, st.rightOpen, st.timelineOpen]).toEqual([false, false, true])
    s.select({ kind: 'project', id: '1' })
    st = useMapStore.getState()
    expect([st.rightOpen, st.selected]).toEqual([true, { kind: 'project', id: '1' }])
    st.clearSelection()
    st = useMapStore.getState()
    expect(st.selected).toBeNull()
  })
  it('레이어 켜기·끄기·투명도 (0~100으로 자름)', () => {
    const s = useMapStore.getState()
    s.setLayerVisible('regulations', true)
    s.setLayerOpacity('projects', 140)
    s.setLayersVisible(['impact250', 'impact500'], false)
    const st = useMapStore.getState()
    expect(st.layers.regulations.visible).toBe(true)
    expect(st.layers.projects.opacity).toBe(100)
    expect([st.layers.impact250.visible, st.layers.impact500.visible]).toEqual([false, false])
  })
})

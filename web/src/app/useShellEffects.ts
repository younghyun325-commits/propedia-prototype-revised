import { useEffect } from 'react'
import { useMapStore } from '../state/useMapStore'
import { keyAction } from './keys'

/** 키보드 단축키와 html 클래스(reduce-transparency, map-moving)를 store와 잇는다. */
export function useShellEffects(): void {
  const reduce = useMapStore((s) => s.reduceTransparency)
  const moving = useMapStore((s) => s.mapMoving)

  useEffect(() => {
    document.documentElement.classList.toggle('reduce-transparency', reduce)
  }, [reduce])

  useEffect(() => {
    document.documentElement.classList.toggle('map-moving', moving)
  }, [moving])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const action = keyAction({
        key: e.key,
        ctrlKey: e.ctrlKey,
        metaKey: e.metaKey,
        altKey: e.altKey,
        shiftKey: e.shiftKey,
        target: e.target as HTMLElement | null,
      })
      if (!action) return
      const s = useMapStore.getState()
      if (action === 'palette') {
        e.preventDefault() // 브라우저 주소창 검색 등 기본 동작을 막는다
        s.setPaletteOpen(!s.paletteOpen)
        return
      }
      if (s.paletteOpen || s.evidence) return // 팔레트·원문 모달이 열려 있으면 그쪽이 키를 처리한다
      if (action === 'left') s.toggleLeft()
      else if (action === 'right') s.toggleRight()
      else if (action === 'timeline') s.toggleTimeline()
      else {
        s.clearSelection()
        s.setSearchHit(null)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
}

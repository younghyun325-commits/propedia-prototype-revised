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
        target: e.target as HTMLElement | null,
      })
      if (!action) return
      const s = useMapStore.getState()
      if (action === 'left') s.toggleLeft()
      else if (action === 'right') s.toggleRight()
      else if (action === 'timeline') s.toggleTimeline()
      else s.clearSelection()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
}

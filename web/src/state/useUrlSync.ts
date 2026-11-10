import { useEffect } from 'react'
import { useMapStore, type MapState } from './useMapStore'
import { mergeSearch, toSearch, type UrlState } from './url'

const DEBOUNCE_MS = 300

function pick(s: MapState): UrlState {
  return { layers: s.layers, basemap: s.basemap, overlap: s.overlap, selected: s.selected, leftTab: s.leftTab, camera: s.camera }
}

/** store → URL (history.replaceState, 300ms 디바운스). 카메라는 지도가 이동을 끝냈을 때만 store에 들어온다. */
export function useUrlSync(): void {
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined
    let last = toSearch(pick(useMapStore.getState()))
    const unsub = useMapStore.subscribe((s) => {
      const next = toSearch(pick(s))
      if (next === last) return
      last = next
      clearTimeout(timer)
      timer = setTimeout(() => {
        try {
          const url = `${window.location.pathname}${mergeSearch(window.location.search, next)}${window.location.hash}`
          window.history.replaceState(window.history.state, '', url)
        } catch {
          /* 주소를 못 바꿔도 화면은 그대로 */
        }
      }, DEBOUNCE_MS)
    })
    return () => {
      clearTimeout(timer)
      unsub()
    }
  }, [])
}

import { create } from 'zustand'

export type Workspace = 'gangnam' | 'project'

export type MapState = {
  leftOpen: boolean
  rightOpen: boolean
  timelineOpen: boolean
  /** 선택한 대상 (예: 'project:1'). P16에서 지도 클릭과 연결 */
  selection: string | null
  workspace: Workspace
  /** '투명도 줄이기' — html.reduce-transparency */
  reduceTransparency: boolean
  /** 지도 이동 중 — html.map-moving (P12에서 MapLibre movestart/moveend와 연결) */
  mapMoving: boolean
  toggleLeft: () => void
  toggleRight: () => void
  toggleTimeline: () => void
  select: (id: string | null) => void
  clearSelection: () => void
  setWorkspace: (w: Workspace) => void
  toggleReduceTransparency: () => void
  setMapMoving: (v: boolean) => void
}

export const useMapStore = create<MapState>()((set) => ({
  leftOpen: true,
  rightOpen: true,
  timelineOpen: false,
  selection: null,
  workspace: 'gangnam',
  reduceTransparency: false,
  mapMoving: false,
  toggleLeft: () => set((s) => ({ leftOpen: !s.leftOpen })),
  toggleRight: () => set((s) => ({ rightOpen: !s.rightOpen })),
  toggleTimeline: () => set((s) => ({ timelineOpen: !s.timelineOpen })),
  select: (id) => set({ selection: id }),
  clearSelection: () => set({ selection: null }),
  setWorkspace: (workspace) => set({ workspace }),
  toggleReduceTransparency: () => set((s) => ({ reduceTransparency: !s.reduceTransparency })),
  setMapMoving: (mapMoving) => set({ mapMoving }),
}))
